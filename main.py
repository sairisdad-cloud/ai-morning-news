import os
import datetime
import html
import requests
import feedparser

BLOGGER_CLIENT_ID = os.environ["BLOGGER_CLIENT_ID"]
BLOGGER_CLIENT_SECRET = os.environ["BLOGGER_CLIENT_SECRET"]
BLOGGER_REFRESH_TOKEN = os.environ["BLOGGER_REFRESH_TOKEN"]
BLOGGER_BLOG_ID = os.environ["BLOGGER_BLOG_ID"]

X_BEARER_TOKEN = os.environ.get("X_BEARER_TOKEN")  # まだ設定しなくてOK


def get_blogger_access_token():
    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "client_id": BLOGGER_CLIENT_ID,
        "client_secret": BLOGGER_CLIENT_SECRET,
        "refresh_token": BLOGGER_REFRESH_TOKEN,
        "grant_type": "refresh_token",
    }
    resp = requests.post(token_url, data=data)
    resp.raise_for_status()
    return resp.json()["access_token"]


# ==============================
# RSS 取得まわり
# ==============================

# 戦争・紛争（西側メディア）
WAR_FEEDS_WEST = [
    # AP
    "https://apnews.com/rss/apf-worldnews",
    # Reuters
    "https://feeds.reuters.com/reuters/worldNews",
    # BBC World
    "http://feeds.bbci.co.uk/news/world/rss.xml",
]

# 戦争・紛争（相手側・多極メディア）
WAR_FEEDS_OTHER = [
    # Al Jazeera (Middle East & world)
    "https://www.aljazeera.com/xml/rss/all.xml",
    # RT
    "https://www.rt.com/rss/news/",
    # CGTN
    "https://rss.app/feeds/0F1p4rM0Uuv8wRxR.xml",  # 非公式RSSだが例として
]

# 重大ニュース（一般）
MAJOR_FEEDS = [
    "https://feeds.reuters.com/reuters/topNews",
    "http://feeds.bbci.co.uk/news/rss.xml",
]

# AI・テックニュース
AI_FEEDS = [
    "https://techcrunch.com/tag/artificial-intelligence/feed/",
    "https://www.marktechpost.com/feed/",
]


def fetch_feed_items(feed_urls, limit_per_feed=5):
    """複数RSSから記事を集めて、シンプルなdictリストにする。"""
    items = []
    for url in feed_urls:
        try:
            parsed = feedparser.parse(url)
        except Exception:
            continue

        source_title = parsed.feed.get("title", url) if hasattr(parsed, "feed") else url
        for entry in parsed.entries[:limit_per_feed]:
            title = entry.get("title", "No title")
            link = entry.get("link", "")
            published = entry.get("published", "") or entry.get("updated", "")
            items.append(
                {
                    "source": source_title,
                    "title": title,
                    "link": link,
                    "published": published,
                }
            )
    return items


def render_items_as_list(items):
    """記事リストをHTMLの <ul> として描画。"""
    if not items:
        return "<p>該当するニュースが見つかりませんでした。</p>"

    lines = ["<ul>"]
    for item in items:
        title = html.escape(item["title"])
        source = html.escape(item["source"])
        link = html.escape(item["link"])
        pub = html.escape(item["published"]) if item["published"] else ""
        meta = f"{source}"
        if pub:
            meta += f" / {pub}"
        lines.append(
            f'<li><a href="{link}" target="_blank" rel="noopener noreferrer">{title}</a><br>'
            f'<span style="font-size: 0.85em; color: #888;">{meta}</span></li>'
        )
    lines.append("</ul>")
    return "\n".join(lines)


def generate_ai_morning_news():
    """RSSベースで『戦争・紛争＋重大ニュース＋AIニュース』の素材集を作る。"""
    today = datetime.date.today().strftime("%Y-%m-%d")
    title = f"{today} 世界情勢＆AI朝刊（過去24時間）"

    # 戦争・紛争：西側＆その他
    war_west = fetch_feed_items(WAR_FEEDS_WEST, limit_per_feed=4)
    war_other = fetch_feed_items(WAR_FEEDS_OTHER, limit_per_feed=4)

    # 重大ニュース
    major_news = fetch_feed_items(MAJOR_FEEDS, limit_per_feed=5)

    # AIニュース
    ai_news = fetch_feed_items(AI_FEEDS, limit_per_feed=5)

    # HTML 組み立て
    content_parts = []

    content_parts.append(f"<h2>{today} 世界情勢＆AI朝刊（過去24時間）</h2>")

    # 注意書き
    content_parts.append(
        """
<p><b>⚠ バイアスに関する注意：</b><br>
以下は各メディアの報道をそのまま並べた「素材集」です。同じ出来事についても、
西側メディアと相手側メディアで強調点や表現が大きく異なることがあります。
必ず両方を読み比べ、自分の頭で判断してください。</p>
"""
    )

    # 戦争・紛争
    content_parts.append("<h3>戦争・紛争（西側メディア）</h3>")
    content_parts.append(render_items_as_list(war_west))

    content_parts.append("<h3>戦争・紛争（相手側・多極メディア）</h3>")
    content_parts.append(render_items_as_list(war_other))

    # 重大ニュース
    content_parts.append("<h3>重大ニュース（世界）</h3>")
    content_parts.append(render_items_as_list(major_news))

    # AIニュース
    content_parts.append("<h3>AI・テックニュース</h3>")
    content_parts.append(render_items_as_list(ai_news))

    # 総括メモ欄（自分で書き足す前提）
    content_parts.append(
        """
<h3>全体のメモ（自分用）</h3>
<p>※ここは自分で追記する欄：</p>
<ul>
<li>気になったトピック：</li>
<li>西側と相手側で報道が食い違っている点：</li>
<li>事業・投資への影響メモ：</li>
</ul>
"""
    )

    content = "\n".join(content_parts)
    return title, content


def post_to_blogger(title, html_content, access_token):
    url = f"https://www.googleapis.com/blogger/v3/blogs/{BLOGGER_BLOG_ID}/posts/"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    body = {
        "kind": "blogger#post",
        "blog": {"id": BLOGGER_BLOG_ID},
        "title": title,
        "content": html_content,
    }
    resp = requests.post(url, headers=headers, json=body)
    resp.raise_for_status()
    return resp.json()["url"]


def post_to_x(status_text):
    if not X_BEARER_TOKEN:
        print("X_BEARER_TOKEN が設定されていないのでスキップ")
        return

    # 実際のエンドポイントは後で正式なX APIに合わせて変更
    url = "https://api.x.com/2/tweets"
    headers = {
        "Authorization": f"Bearer {X_BEARER_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {"text": status_text}
    resp = requests.post(url, headers=headers, json=payload)
    resp.raise_for_status()
    return resp.json()


def main():
    access_token = get_blogger_access_token()
    title, content = generate_ai_morning_news()
    post_url = post_to_blogger(title, content, access_token)

    tweet_text = f"AI朝刊を更新しました：{title}\n{post_url}"
    if len(tweet_text) > 260:
        tweet_text = tweet_text[:257] + "..."

    post_to_x(tweet_text)


if __name__ == "__main__":
    main()
