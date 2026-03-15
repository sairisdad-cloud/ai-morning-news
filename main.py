import os
import datetime
import requests

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

def generate_ai_morning_news():
    today = datetime.date.today().strftime("%Y-%m-%d")
    title = f"{today} AI朝刊（過去24時間）"

    content = f"""
<h2>{today} AI朝刊（過去24時間）</h2>

<ul>
<li><b>見出し</b><br>
  <b>要点：</b> ...<br>
  <b>なぜ重要か：</b> ...<br>
  <b>日本への影響：</b> ...
</li>
</ul>

<h3>Today's Top 3</h3>
<ol>
<li>...</li>
<li>...</li>
<li>...</li>
</ol>
"""
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

    url = "https://api.x.com/2/tweets"  # 後で正式エンドポイントに差し替え
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
