import json
import os
import re
import html
from datetime import datetime, timezone, timedelta
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


JST = timezone(timedelta(hours=9))
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; JudoRSS/1.0)"
}


def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def rss_escape(text):
    return html.escape(clean(text), quote=True)


def fetch(url):
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    r.encoding = r.apparent_encoding
    return r.text


def make_item(title, link, date="", source=""):
    return {
        "title": clean(title),
        "link": link,
        "date": clean(date),
        "source": source
    }


# -------------------------
# 福岡県柔道協会
# -------------------------
def get_fukuoka():
    url = "https://fukuoka-judo.jp/"
    soup = BeautifulSoup(fetch(url), "html.parser")

    items = []
    seen = set()

    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        title = clean(a.get_text(" ", strip=True))

        if not title:
            continue

        # お知らせ詳細ページ
        if "b_id=" not in href and "detail=" not in href:
            continue

        link = urljoin(url, href)

        if link in seen:
            continue

        seen.add(link)

        parent_text = clean(a.parent.get_text(" ", strip=True))
        m = re.search(r"20\d{2}[-/.]\d{1,2}[-/.]\d{1,2}", parent_text)

        date = m.group(0).replace(".", "-").replace("/", "-") if m else ""

        items.append(
            make_item(
                title=title,
                link=link,
                date=date,
                source="福岡県柔道協会"
            )
        )

    return items


# -------------------------
# 広島県柔道連盟
# -------------------------
def get_hiroshima():
    url = "https://hiroshima-judo.com/"
    soup = BeautifulSoup(fetch(url), "html.parser")

    items = []
    seen = set()

    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        title = clean(a.get_text(" ", strip=True))

        if not title:
            continue

        if "/posts/" not in href:
            continue

        link = urljoin(url, href)

        if link in seen:
            continue

        seen.add(link)

        block = a.parent
        block_text = clean(block.get_text(" ", strip=True)) if block else title

        m = re.search(
            r"20\d{2}[-/.年]\s*\d{1,2}[-/.月]\s*\d{1,2}",
            block_text
        )

        date = ""
        if m:
            date = m.group(0)
            date = (
                date.replace("年", "-")
                .replace("月", "-")
                .replace("日", "")
                .replace(".", "-")
                .replace("/", "-")
                .replace(" ", "")
            )

        items.append(
            make_item(
                title=title,
                link=link,
                date=date,
                source="広島県柔道連盟"
            )
        )

    return items


# -------------------------
# 愛媛県柔道協会
# -------------------------
def get_ehime():
    url = "https://ehimejudo.jpn.org/"
    soup = BeautifulSoup(fetch(url), "html.parser")

    items = []
    seen = set()

    for a in soup.find_all("a", href=True):
        title = clean(a.get_text(" ", strip=True))
        href = a.get("href", "")

        if not title:
            continue

        link = urljoin(url, href)

        block = a.parent
        text = clean(block.get_text(" ", strip=True)) if block else title

        m = re.search(r"20\d{2}[./-]\d{2}[./-]\d{2}", text)

        if not m:
            continue

        date = m.group(0).replace(".", "-").replace("/", "-")

        # メニュー等を除外
        if len(title) < 4:
            continue

        key = title + link

        if key in seen:
            continue

        seen.add(key)

        items.append(
            make_item(
                title=title,
                link=link,
                date=date,
                source="愛媛県柔道協会"
            )
        )

    return items


def sort_items(items):
    def key(item):
        try:
            return datetime.strptime(item["date"], "%Y-%m-%d")
        except Exception:
            return datetime(1900, 1, 1)

    return sorted(items, key=key, reverse=True)


def build_rss(title, description, link, items):
    now = datetime.now(JST).strftime("%a, %d %b %Y %H:%M:%S %z")

    xml = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0">',
        "<channel>",
        f"<title>{rss_escape(title)}</title>",
        f"<link>{rss_escape(link)}</link>",
        f"<description>{rss_escape(description)}</description>",
        "<language>ja</language>",
        f"<lastBuildDate>{now}</lastBuildDate>",
    ]

    for item in items[:50]:
        xml.append("<item>")
        xml.append(
            f"<title>{rss_escape('【' + item['source'] + '】' + item['title'])}</title>"
        )
        xml.append(f"<link>{rss_escape(item['link'])}</link>")
        xml.append(f"<guid>{rss_escape(item['link'])}</guid>")

        if item["date"]:
            try:
                dt = datetime.strptime(item["date"], "%Y-%m-%d")
                dt = dt.replace(tzinfo=JST)
                xml.append(
                    f"<pubDate>{dt.strftime('%a, %d %b %Y %H:%M:%S %z')}</pubDate>"
                )
            except Exception:
                pass

        xml.append(
            f"<description>{rss_escape(item['source'] + ' ' + item['title'])}</description>"
        )
        xml.append("</item>")

    xml.extend(["</channel>", "</rss>"])

    return "\n".join(xml)


def save_feed(filename, title, description, link, items):
    os.makedirs("feeds", exist_ok=True)

    xml = build_rss(title, description, link, sort_items(items))

    with open(
        os.path.join("feeds", filename),
        "w",
        encoding="utf-8"
    ) as f:
        f.write(xml)


def main():
    all_items = []

    collectors = [
        (
            "fukuoka.xml",
            "福岡県柔道協会 更新情報",
            "https://fukuoka-judo.jp/",
            get_fukuoka
        ),
        (
            "hiroshima.xml",
            "広島県柔道連盟 更新情報",
            "https://hiroshima-judo.com/",
            get_hiroshima
        ),
        (
            "ehime.xml",
            "愛媛県柔道協会 更新情報",
            "https://ehimejudo.jpn.org/",
            get_ehime
        ),
    ]

    for filename, title, url, func in collectors:
        try:
            items = func()

            print(f"{title}: {len(items)}件取得")

            save_feed(
                filename,
                title,
                f"{title}を自動取得したRSSです。",
                url,
                items
            )

            all_items.extend(items)

        except Exception as e:
            print(f"{title}: 取得失敗: {e}")

    save_feed(
        "all.xml",
        "柔道関連サイト 更新情報",
        "福岡県柔道協会・広島県柔道連盟・愛媛県柔道協会の更新情報",
        "https://github.com/",
        all_items
    )

    print("RSS生成完了")


if __name__ == "__main__":
    main()
