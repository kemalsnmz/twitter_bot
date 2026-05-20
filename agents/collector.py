"""
Ajan 1 — Kaynak Toplayıcı
RSS feed'leri, Twitter hesaplarını ve Reddit'i tarar.
Yeni içerikleri content_queue tablosuna yazar.
"""

import feedparser
import praw
import tweepy
import asyncio
import re
from datetime import datetime, timezone

from config import (
    TOPICS,
    TWITTER_BEARER_TOKEN,
    TWITTER_USERNAME,
    TWITTER_EMAIL,
    TWITTER_PASSWORD,
    REDDIT_CLIENT_ID,
    REDDIT_CLIENT_SECRET,
    MAX_ITEMS_PER_RUN,
)
from db.database import insert_content


# ─── YARDIMCI ────────────────────────────────────────────────────────────────

def clean_html(text: str) -> str:
    """HTML etiketlerini temizle."""
    return re.sub(r"<[^>]+>", "", text or "").strip()


def is_relevant(text: str, keywords: list) -> bool:
    """İçerik anahtar kelimelere uyuyor mu?"""
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in keywords)


# ─── RSS ─────────────────────────────────────────────────────────────────────

def collect_rss(topic_key: str, topic_cfg: dict) -> int:
    """RSS feed'lerinden yeni içerik topla. Kaç yeni içerik eklendi döndürür."""
    added = 0
    keywords = topic_cfg["keywords"]

    for feed_url in topic_cfg["rss_feeds"]:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:10]:  # her feed'den max 10 giriş
                title   = entry.get("title", "")
                url     = entry.get("link", "")
                summary = clean_html(entry.get("summary", entry.get("description", "")))
                raw     = f"{title}\n\n{summary}"

                if not url:
                    continue
                if not is_relevant(raw, keywords):
                    continue

                ok = insert_content(
                    topic=topic_key,
                    source_type="rss",
                    source_name=feed.feed.get("title", feed_url),
                    title=title,
                    url=url,
                    raw_text=raw[:2000],
                )
                if ok:
                    added += 1
                    print(f"  [RSS] Eklendi: {title[:60]}")

        except Exception as e:
            print(f"  [RSS] Hata ({feed_url}): {e}")

    return added


# ─── TWITTER / X ─────────────────────────────────────────────────────────────

def collect_twitter(topic_key: str, topic_cfg: dict) -> int:
    """Belirlenen hesapların son tweetlerini topla."""
    if not TWITTER_BEARER_TOKEN:
        print("  [Twitter] Bearer token eksik, atlanıyor.")
        return 0

    added = 0
    keywords = topic_cfg["keywords"]

    try:
        client = tweepy.Client(bearer_token=TWITTER_BEARER_TOKEN)

        for username in topic_cfg["twitter_accounts"]:
            try:
                user = client.get_user(username=username)
                if not user.data:
                    continue

                tweets = client.get_users_tweets(
                    id=user.data.id,
                    max_results=10,
                    tweet_fields=["text", "created_at"],
                    exclude=["retweets", "replies"],
                )

                if not tweets.data:
                    continue

                for tweet in tweets.data:
                    url = f"https://twitter.com/{username}/status/{tweet.id}"
                    raw = tweet.text

                    if not is_relevant(raw, keywords):
                        continue

                    ok = insert_content(
                        topic=topic_key,
                        source_type="twitter",
                        source_name=f"@{username}",
                        title=raw[:100],
                        url=url,
                        raw_text=raw,
                    )
                    if ok:
                        added += 1
                        print(f"  [Twitter] Eklendi: @{username} — {raw[:50]}")

            except Exception as e:
                print(f"  [Twitter] Hata (@{username}): {e}")

    except Exception as e:
        print(f"  [Twitter] Bağlantı hatası: {e}")

    return added


# ─── REDDIT ──────────────────────────────────────────────────────────────────

def collect_reddit(topic_key: str, topic_cfg: dict) -> int:
    """Reddit subreddit'lerinden hot/new gönderileri topla."""
    if not REDDIT_CLIENT_ID or not REDDIT_CLIENT_SECRET:
        print("  [Reddit] Credentials eksik, atlanıyor.")
        return 0

    added = 0
    keywords = topic_cfg["keywords"]

    try:
        reddit = praw.Reddit(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            user_agent="TwitterBot/1.0 (by u/kemal)",
        )

        for sub_name in topic_cfg["reddit_subs"]:
            try:
                subreddit = reddit.subreddit(sub_name)
                for post in subreddit.hot(limit=15):
                    if post.is_self and not post.selftext:
                        continue

                    title   = post.title
                    raw     = f"{title}\n\n{post.selftext[:500]}"
                    url     = f"https://reddit.com{post.permalink}"

                    if not is_relevant(raw, keywords):
                        continue

                    ok = insert_content(
                        topic=topic_key,
                        source_type="reddit",
                        source_name=f"r/{sub_name}",
                        title=title,
                        url=url,
                        raw_text=raw[:2000],
                    )
                    if ok:
                        added += 1
                        print(f"  [Reddit] Eklendi: {title[:60]}")

            except Exception as e:
                print(f"  [Reddit] Hata (r/{sub_name}): {e}")

    except Exception as e:
        print(f"  [Reddit] Bağlantı hatası: {e}")

    return added


# ─── TWİKİT (API KEY GEREKMEDEN TWITTER) ─────────────────────────────────────

COOKIES_FILE = "twikit_cookies.json"

async def _get_twikit_client():
    """Twikit client'ı başlat, cookie varsa kullan, yoksa login yap."""
    from twikit import Client
    import os

    client = Client("en-US")
    if os.path.exists(COOKIES_FILE):
        client.load_cookies(COOKIES_FILE)
    else:
        if not TWITTER_USERNAME or not TWITTER_PASSWORD:
            return None
        await client.login(
            auth_info_1=TWITTER_USERNAME,
            auth_info_2=TWITTER_EMAIL or TWITTER_USERNAME,
            password=TWITTER_PASSWORD,
        )
        client.save_cookies(COOKIES_FILE)
    return client


async def _collect_twikit_accounts(topic_key: str, topic_cfg: dict) -> int:
    """Belirtilen Twitter hesaplarının son tweetlerini twikit ile topla."""
    accounts = topic_cfg.get("twitter_accounts", [])
    if not accounts:
        return 0

    keywords = topic_cfg["keywords"]
    added = 0

    try:
        client = await _get_twikit_client()
        if not client:
            print("  [twikit] Hesap bilgileri eksik, atlanıyor.")
            return 0

        for username in accounts:
            try:
                user = await client.get_user_by_screen_name(username)
                tweets = await user.get_tweets("Tweets", count=10)
                for tweet in tweets:
                    raw = tweet.full_text or tweet.text or ""
                    if not is_relevant(raw, keywords):
                        continue
                    url = f"https://twitter.com/{username}/status/{tweet.id}"
                    ok = insert_content(
                        topic=topic_key,
                        source_type="twitter",
                        source_name=f"@{username}",
                        title=raw[:100],
                        url=url,
                        raw_text=raw,
                    )
                    if ok:
                        added += 1
                        print(f"  [twikit] Eklendi: @{username} — {raw[:50]}")
            except Exception as e:
                print(f"  [twikit] Hata (@{username}): {e}")
    except Exception as e:
        print(f"  [twikit] Bağlantı hatası: {e}")

    return added


async def _collect_twikit_search(topic_key: str, topic_cfg: dict) -> int:
    """Anahtar kelimelerle Twitter'da arama yap."""
    keywords = topic_cfg.get("search_queries", topic_cfg["keywords"][:3])
    added = 0

    try:
        client = await _get_twikit_client()
        if not client:
            return 0

        for query in keywords[:3]:  # Max 3 sorgu
            try:
                results = await client.search_tweet(query, product="Latest", count=10)
                for tweet in results:
                    raw = tweet.full_text or tweet.text or ""
                    if len(raw) < 50:  # Çok kısa tweetleri atla
                        continue
                    username = tweet.user.screen_name
                    url = f"https://twitter.com/{username}/status/{tweet.id}"
                    ok = insert_content(
                        topic=topic_key,
                        source_type="twitter_search",
                        source_name=f"Twitter/{query[:30]}",
                        title=raw[:100],
                        url=url,
                        raw_text=raw,
                    )
                    if ok:
                        added += 1
                        print(f"  [twikit] Arama '{query[:20]}': {raw[:50]}")
            except Exception as e:
                print(f"  [twikit] Arama hatası ('{query}'): {e}")
    except Exception as e:
        print(f"  [twikit] Arama bağlantı hatası: {e}")

    return added


def collect_twikit(topic_key: str, topic_cfg: dict) -> int:
    """twikit koleksiyonunu senkron olarak çalıştır."""
    if not TWITTER_USERNAME or not TWITTER_PASSWORD:
        return 0
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        accounts = loop.run_until_complete(_collect_twikit_accounts(topic_key, topic_cfg))
        search   = loop.run_until_complete(_collect_twikit_search(topic_key, topic_cfg))
        loop.close()
        return accounts + search
    except Exception as e:
        print(f"  [twikit] Genel hata: {e}")
        return 0


# ─── ANA FONKSİYON ───────────────────────────────────────────────────────────

def run_collector():
    """Tüm aktif konular için kaynak taraması yap."""
    total = 0
    print(f"\n{'='*50}")
    print(f"[Toplayıcı Ajan] Başladı — {datetime.now().strftime('%H:%M:%S')}")

    for topic_key, topic_cfg in TOPICS.items():
        if not topic_cfg.get("active", False):
            continue

        print(f"\n→ Konu: {topic_cfg['label']}")
        total += collect_rss(topic_key, topic_cfg)
        total += collect_twitter(topic_key, topic_cfg)
        total += collect_reddit(topic_key, topic_cfg)
        total += collect_twikit(topic_key, topic_cfg)

    print(f"\n[Toplayıcı Ajan] Bitti — Toplam {total} yeni içerik eklendi.")
    return total


if __name__ == "__main__":
    from db.database import init_db
    init_db()
    run_collector()
