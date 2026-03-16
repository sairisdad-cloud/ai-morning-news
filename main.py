import os
import datetime
import html
import textwrap

import requests
import feedparser
from openai import OpenAI

BLOGGER_CLIENT_ID = os.environ["BLOGGER_CLIENT_ID"]
BLOGGER_CLIENT_SECRET = os.environ["BLOGGER_CLIENT_SECRET"]
BLOGGER_REFRESH_TOKEN = os.environ["BLOGGER_REFRESH_TOKEN"]
BLOGGER_BLOG_ID = os.environ["BLOGGER_BLOG_ID"]

X_BEARER_TOKEN = os.environ.get("X_BEARER_TOKEN")
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

client = OpenAI(api_key=OPENAI_API_KEY)


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
# RSS settings
# ==============================

WAR_FEEDS_WEST = [
    "https://apnews.com/rss/apf-worldnews",
    "https://feeds.reuters.com/reuters/worldNews",
    "http://feeds.bbci.co.uk/news/world/rss.xml",
]

WAR_FEEDS_OTHER = [
    "https://www.aljazeera.com/xml/rss/all.xml",
    "https://www.rt.com/rss/news/",
]

MAJOR_FEEDS = [
    "https://feeds.reuters.com/reuters/topNews",
    "http://feeds.bbci.co.uk/news/rss.xml",
]

AI_FEEDS = [
    "https://techcrunch.com/tag/artificial-intelligence/feed/",
    "https://www.marktechpost.com/feed/",
]


def fetch_feed_items(feed_urls, limit_total=8):
    """Fetch articles from multiple RSS feeds and return a simple list of dicts."""
    items = []
    for url in feed_urls:
        try:
            parsed = feedparser.parse(url)
        except Exception:
            continue

        source_title = parsed.feed.get("title", url) if hasattr(parsed, "feed") else url
        for entry in parsed.entries:
            title = entry.get("title", "No title")
            link = entry.get("link", "")
            summary = entry.get("summary", "") or entry.get("description", "")
            published = entry.get("published", "") or entry.get("updated", "")
            items.append(
                {
                    "source": source_title,
                    "title": title,
                    "link": link,
                    "summary": summary,
                    "published": published,
                }
            )
    return items[:limit_total]


def build_category_prompt(category_name, items, focus_note):
    """Build a prompt for one category (instructions in English, ask for Japanese output)."""
    lines = []
    lines.append(f"[Category] {category_name}")
    lines.append(f"[Focus] {focus_note}")
    lines.append("[Source articles]")

    for i, item in enumerate(items, start=1):
        title = item["title"]
        source = item["source"]
        pub = item["published"]
        summary = html.unescape(
            textwrap.shorten(
                html.unescape(item["summary"]).replace("\n", " "),
                width=500,
                placeholder="…",
            )
        )
        link = item["link"]
        lines.append(
            f"\n[{i}] Title: {title}\n"
            f"    Source: {source}\n"
            f"    Date: {pub}\n"
            f"    Summary (original language): {summary}\n"
            f"    URL: {link}"
        )

    lines.append(
        """
[Task]

You are an analyst who writes calm, neutral news briefs.

Using the articles above, write a JAPANESE summary with the following structure:

- 見出し: 1行
- 要点: 箇条書き 3〜6行
- なぜ重要か: 2〜4行
- バイアス・限界への注意: 2〜4行
- 日本や世界への影響: 2〜4行

Constraints:

- Output MUST be in Japanese.
- Use a calm, professional tone.
- Separate facts from speculation.
- Mention arguments or viewpoints from BOTH "Western" and "other" sides when relevant.
- Total length: about 600–800 Japanese characters.
"""
    )
    return "\n".join(lines)


def summarize_with_openai(system_prompt, user_prompt):
    resp = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.4,
        max_tokens=1200,
    )
    return resp.choices[0].message.content.strip()


def summary_text_to_html(text: str) -> str:
    """Convert summary text into readable HTML."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    html_lines = []
    in_list = False

    for line in lines:
        if line.startswith("- "):
            if not in_list:
                html_lines.append('<ul class="ai-brief-list">')
                in_list = True
            html_lines.append(f"<li>{html.escape(line[2:])}</li>")
        else:
            if in_list:
                html_lines.append("</ul>")
                in_list = False

            # Japanese section labels starting with e.g. "見出し", "要点" etc. will still work here
            if any(key in line for key in ["見出し", "要点", "なぜ重要か", "影響", "バイアス"]):
                html_lines.append(f'<p class="ai-brief-label">{html.escape(line)}</p>')
            else:
                html_lines.append(f'<p class="ai-brief-text">{html.escape(line)}</p>')

    if in_list:
        html_lines.append("</ul>")

    return "\n".join(html_lines)


def generate_ai_morning_news():
    """Generate the world & AI morning brief using RSS + OpenAI."""
    today = datetime.date.today().strftime("%Y-%m-%d")
    title = f"{today} 世界情勢＆AI・テック朝刊（過去24時間）"

    war_west_items = fetch_feed_items(WAR_FEEDS_WEST, limit_total=8)
    war_other_items = fetch_feed_items(WAR_FEEDS_OTHER, limit_total=8)
    major_items = fetch_feed_items(MAJOR_FEEDS, limit_total=8)
    ai_items = fetch_feed_items(AI_FEEDS, limit_total=8)

    system_prompt = (
        "You are a Japanese news analyst summarizing world conflicts, geopolitics, "
        "and AI/tech topics in clear, neutral Japanese for busy readers."
    )

    sections = []

    if war_west_items:
        prompt_west = build_category_prompt(
            "戦争・紛争（西側メディア）",
            war_west_items,
            "Focus on how Western media frames the situation, but summarize in a balanced, fact-based way.",
        )
        summary_west = summarize_with_openai(system_prompt, prompt_west)
        sections.append('<section class="ai-brief-section">')
        sections.append('<h3 class="ai-brief-heading">戦争・紛争（西側メディア）</h3>')
        sections.append(summary_text_to_html(summary_west))
        sections.append("</section>")

    if war_other_items:
        prompt_other = build_category_prompt(
            "戦争・紛争（相手側・多極メディア）",
            war_other_items,
            "Focus on how non-Western / opposing / multipolar media frames the situation, and highlight both overlaps and contradictions with Western coverage.",
        )
        summary_other = summarize_with_openai(system_prompt, prompt_other)
        sections.append('<section class="ai-brief-section">')
        sections.append('<h3 class="ai-brief-heading">戦争・紛争（相手側・多極メディア）</h3>')
        sections.append(summary_text_to_html(summary_other))
        sections.append("</section>")

    if major_items:
        prompt_major = build_category_prompt(
            "重大ニュース（世界）",
            major_items,
            "Pick global-impact topics across economy, politics, society, and technology.",
        )
        summary_major = summarize_with_openai(system_prompt, prompt_major)
        sections.append('<section class="ai-brief-section">')
        sections.append('<h3 class="ai-brief-heading">重大ニュース（世界）</h3>')
        sections.append(summary_text_to_html(summary_major))
        sections.append("</section>")

    if ai_items:
        prompt_ai = build_category_prompt(
            "AI・テックニュース",
            ai_items,
            "Focus on AI models, agents, chips, big company moves, and regulation that matter for business and development.",
        )
        summary_ai = summarize_with_openai(system_prompt, prompt_ai)
        sections.append('<section class="ai-brief-section">')
        sections.append('<h3 class="ai-brief-heading">AI・テックニュース</h3>')
        sections.append(summary_text_to_html(summary_ai))
        sections.append("</section>")

    header = f"""
<style>
.ai-brief-root {{
  max-width: 820px;
  margin: 0 auto;
  padding: 18px 14px 44px;
  font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, -system-ui, "Segoe UI", sans-serif;
  line-height: 1.9;
  color: #f5f5f7;
  background-color: #000000;
}}
.ai-brief-root h2 {{
  font-size: 1.6rem;
  font-weight: 700;
  margin: 0 0 24px;
}}
.ai-brief-heading {{
  font-size: 1.2rem;
  font-weight: 600;
  margin: 32px 0 10px;
  border-left: 3px solid #5ac8fa;
  padding-left: 10px;
}}
.ai-brief-section {{
  margin-bottom: 32px;
}}
.ai-brief-label {{
  font-weight: 600;
  margin: 16px 0 6px;
  color: #9ca3af;
}}
.ai-brief-text {{
  margin: 4px 0 14px;
}}
.ai-brief-list {{
  margin: 6px 0 18px 1.4em;
  padding-left: 0;
}}
.ai-brief-list li {{
  margin-bottom: 6px;
}}
.ai-brief-note {{
  font-size: 0.9rem;
  color: #9ca3af;
  margin-bottom: 22px;
}}
.ai-brief-links h4 {{
  margin: 30px 0 10px;
  font-size: 1rem;
}}
.ai-brief-links ul {{
  margin: 0 0 10px 1.4em;
  padding-left: 0;
}}
.ai-brief-links li {{
  margin-bottom: 4px;
  font-size: 0.9rem;
}}
</style>

<div class="ai-brief-root">
  <h2>{title}</h2>
  <p class="ai-brief-note">
    本記事は、複数の報道機関からの記事をもとにAIが要約したものです。
    情報源のバイアスやAI要約の限界により、すべてが完全に中立・正確であるとは限りません。
    必ずリンク先の一次情報や公式発表も確認し、自分の頭で判断するための「下地」として使ってください。
  </p>
"""

    def render_links_block(title_block, items):
        if not items:
            return ""
        lines = [f"<h4>{title_block}：参考リンク</h4>", "<ul>"]
        for item in items:
            t = html.escape(item["title"])
            s = html.escape(item["source"])
            l = html.escape(item["link"])
            lines.append(
                f'<li><a href="{l}" target="_blank" rel="noopener noreferrer">{t}</a> – {s}</li>'
            )
        lines.append("</ul>")
        return "\n".join(lines)

    links_block = []
    links_block.append(render_links_block("戦争・紛争（西側）", war_west_items))
    links_block.append(render_links_block("戦争・紛争（相手側・多極）", war_other_items))
    links_block.append(render_links_block("重大ニュース（世界）", major_items))
    links_block.append(render_links_block("AI・テックニュース", ai_items))

    content = (
        header
        + "\n".join(sections)
        + '<div class="ai-brief-links">'
        + "\n".join(links_block)
        + "</div></div>"
    )
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
