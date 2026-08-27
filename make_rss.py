import os
import re
import html
from datetime import datetime, timezone, timedelta
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


JST = timezone(timedelta(hours=9))

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; SumoRSS/1.0)"
}


def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def esc(text):
    return html.escape(clean(text), quote=True)


def fetch(url):
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    r.encoding = r.apparent_encoding
    return r.text


def item(title, link, date="", source=""):
    return {
        "title": clean(title),
        "link": link,
        "date": clean(date),
        "source": source
    }


# -------------------------
# 日本相撲連盟
# -------------------------
def get_nihonsumo():
    url = "https://www.nihonsumo-renmei.jp/"
    soup = BeautifulSoup(fetch(url), "html.parser")

    items = []
    seen = set()

    for a in soup.find_all("a", href=True):
        title = clean(a.get_text(" ", strip=True))
        href = a.get("href", "")

        if not title:
            continue

        # News Release の記事を中心に取得
        if not (
            "NEW" in title
            or "お知らせ" in title
            or "アンチ・ドーピング" in title
            or "相撲" in title
            or "審判" in title
            or "大会" in title
        ):
            continue

        # メニューなどを除外
        if title in [
            "トップページ",
            "リンク",
            "各種申請用紙"
        ]:
            continue

        link = urljoin(url, href)

        if link in seen:
            continue

        seen.add(link)

        # タイトルやURLに日付が含まれていれば取得
        date = ""

        m = re.search(r"(20\d{2})[./_-]?(\d{2})[./_-]?(\d{2})", href)
        if m:
            date = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"

        items.append(
            item(
                title=title.replace("【NEW】", "").strip(),
                link=link,
                date=date,
                source="日本相撲連盟"
            )
        )

    return items[:30]


# -------------------------
# 日本女子相撲連盟
# -------------------------
def get_joshisumo():
    url = "https://www.joshisumo-renmei.jp/"
    soup = BeautifulSoup(fetch(url), "html.parser")

    items = []
    seen = set()

    # ページ上の「令和○年○月○日」の近くにあるリンクを取得
    text_nodes = soup.find_all(string=re.compile(r"令和\d+年"))

    for node in text_nodes:
        text = clean(str(node))

        m = re.search(
            r"令和(\d+)年\s*(\d{1,2})\s*月\s*(\d{1,2})日",
            text
        )

        if not m:
            continue

        year = 2018 + int(m.group(1))
        month = int(m.group(2))
        day = int(m.group(3))

        date = f"{year:04d}-{month:02d}-{day:02d}"

        parent = node.parent

        # 日付の直後にあるリンクを探す
        links = []

        current = parent
        count = 0

        while current is not None and count < 8:
            current = current.find_next()

            if current is None:
                break

            if current.name == "a" and current.get("href"):
                title = clean(current.get_text(" ", strip=True))

                if title:
                    links.append(current)

            # 次の日付が来たら終了
            if current.string:
                t = clean(str(current.string))
                if t != text and re.search(r"令和\d+年", t):
                    break

            count += 1

        for a in links[:3]:
            title = clean(a.get_text(" ", strip=True))
            link = urljoin(url, a.get("href", ""))

            key = date + title + link

            if key in seen:
                continue

            seen.add(key)

            items.append(
                item(
                    title=title,
                    link=link,
                    date=date,
                    source="日本女子相撲連盟"
                )
            )

    return items[:30]


# -------------------------
# 日本相撲協会
# -------------------------
def get_sumo():
    url = "https://www.sumo.or.jp/"
    soup = BeautifulSoup(fetch(url), "html.parser")

    items = []
    seen = set()

    # NEWS欄では日付がリンク直前のテキストに入る
    for a in soup.find_all("a", href=True):
        title = clean(a.get_text(" ", strip=True))

        if not title:
            continue

        parent = a.parent
        text = clean(parent.get_text(" ", strip=True)) if parent else ""

        m = re.search(r"(20\d{2})\.(\d{2})\.(\d{2})", text)

        if not m:
            continue

        date = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"

        # NEWSに関係ないリンクをなるべく除外
        if len(title) < 4:
            continue

        link = urljoin(url, a.get("href", ""))

        key = date + title + link

        if key in seen:
            continue

        seen.add(key)

        items.append(
            item(
                title=title,
                link=link,
                date=date,
                source="日本相撲協会"
            )
        )

    return items[:50]


def sort_items(items):
    def key(x):
        try:
            return datetime.strptime(x["date"], "%Y-%m-%d")
        except Exception:
            return datetime(1900, 1, 1)

    return sorted(items, key=key, reverse=True)


def build_rss(title, description, link, items):
    now = datetime.now(JST).strftime(
        "%a, %d %b %Y %H:%M:%S %z"
    )

    xml = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0">',
        "<channel>",
        f"<title>{esc(title)}</title>",
        f"<link>{esc(link)}</link>",
        f"<description>{esc(description)}</description>",
        "<language>ja</language>",
        f"<lastBuildDate>{now}</lastBuildDate>",
    ]

    for x in sort_items(items)[:50]:

        xml.append("<item>")

        xml.append(
            f"<title>{esc('【' + x['source'] + '】' + x['title'])}</title>"
        )

        xml.append(
            f"<link>{esc(x['link'])}</link>"
        )

        xml.append(
            f"<guid>{esc(x['link'])}</guid>"
        )

        if x["date"]:
            try:
                dt = datetime.strptime(
                    x["date"],
                    "%Y-%m-%d"
                ).replace(tzinfo=JST)

                xml.append(
                    f"<pubDate>{dt.strftime('%a, %d %b %Y %H:%M:%S %z')}</pubDate>"
                )

            except Exception:
                pass

        xml.append(
            f"<description>{esc(x['source'] + ' ' + x['title'])}</description>"
        )

        xml.append("</item>")

    xml.extend([
        "</channel>",
        "</rss>"
    ])

    return "\n".join(xml)


def save_feed(filename, title, description, link, items):

    os.makedirs("feeds", exist_ok=True)

    xml = build_rss(
        title,
        description,
        link,
        items
    )

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
            "nihonsumo.xml",
            "日本相撲連盟 更新情報",
            "https://www.nihonsumo-renmei.jp/",
            get_nihonsumo
        ),
        (
            "joshisumo.xml",
            "日本女子相撲連盟 更新情報",
            "https://www.joshisumo-renmei.jp/",
            get_joshisumo
        ),
        (
            "sumo.xml",
            "日本相撲協会 更新情報",
            "https://www.sumo.or.jp/",
            get_sumo
        )
    ]

    for filename, title, url, func in collectors:

        try:

            items = func()

            print(
                f"{title}: {len(items)}件取得"
            )

            save_feed(
                filename,
                title,
                f"{title}を自動取得したRSSです。",
                url,
                items
            )

            all_items.extend(items)

        except Exception as e:

            print(
                f"{title}: 取得失敗: {e}"
            )

    save_feed(
        "all.xml",
        "相撲関連サイト 更新情報",
        "日本相撲連盟・日本女子相撲連盟・日本相撲協会の更新情報",
        "https://github.com/",
        all_items
    )

    print("RSS生成完了")


if __name__ == "__main__":
    main()
