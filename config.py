import os
from dotenv import load_dotenv

load_dotenv()

# ─── API KEYS ───────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY       = os.getenv("ANTHROPIC_API_KEY")
TWITTER_BEARER_TOKEN    = os.getenv("TWITTER_BEARER_TOKEN")
TWITTER_API_KEY         = os.getenv("TWITTER_API_KEY")
TWITTER_API_SECRET      = os.getenv("TWITTER_API_SECRET")
TWITTER_ACCESS_TOKEN    = os.getenv("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_SECRET   = os.getenv("TWITTER_ACCESS_SECRET")
TELEGRAM_BOT_TOKEN      = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID        = os.getenv("TELEGRAM_CHAT_ID")
REDDIT_CLIENT_ID        = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET    = os.getenv("REDDIT_CLIENT_SECRET")

# ─── KONULAR (NİŞLER) ────────────────────────────────────────────────────────
# Her konuya kaynaklar ve tweet tonu tanımlanır.
# İleride yeni konu eklemek için buraya bir blok eklemen yeterli.

TOPICS = {
    "ai": {
        "label": "Yapay Zeka",
        "active": True,
        "tweet_tone": (
            "Sen Türkçe yazan, yapay zeka alanında uzman bir içerik üreticisisin. "
            "Tweetlerin merak uyandırır, bilgilendirici ama sade bir dille yazılır. "
            "Teknik jargonu minimumda tut. Emoji kullanabilirsin ama abartma."
        ),
        "rss_feeds": [
            "https://techcrunch.com/category/artificial-intelligence/feed/",
            "https://www.theverge.com/ai-artificial-intelligence/rss/index.xml",
            "https://www.wired.com/feed/tag/artificial-intelligence/rss",
            "https://feeds.feedburner.com/venturebeat/SZYF",  # VentureBeat AI
        ],
        "twitter_accounts": [],  # Ucretli API gerektiriyor, devre disi
        "reddit_subs": [
            "artificial",
            "MachineLearning",
            "singularity",
        ],
        "keywords": [
            "artificial intelligence", "machine learning", "LLM", "GPT",
            "Claude", "Gemini", "neural network", "deep learning", "AI model",
            "yapay zeka", "dil modeli",
        ],
    },

    "finance": {
        "label": "Finans & Borsa",
        "active": False,   # Şimdilik kapalı, açmak için True yap
        "tweet_tone": (
            "Sen Türkçe yazan, borsa ve finans alanında uzman bir içerik üreticisisin. "
            "Tweetlerin yatırımcılara değer katar, piyasa gelişmelerini sade dille açıklar. "
            "Kesinlikle yatırım tavsiyesi verme, analiz sun."
        ),
        "rss_feeds": [
            "https://feeds.bloomberg.com/markets/news.rss",
            "https://www.investing.com/rss/news.rss",
        ],
        "twitter_accounts": [],
        "reddit_subs": ["investing", "stocks", "SecurityAnalysis"],
        "keywords": ["stock market", "inflation", "fed", "interest rate", "borsa", "hisse"],
    },
}

# ─── ZAMANLAMA ───────────────────────────────────────────────────────────────
SCRAPE_INTERVAL_MINUTES = 120   # Her kaç dakikada bir kaynaklar taransın
MAX_ITEMS_PER_RUN       = 5     # Her çalışmada işlenecek maksimum kaynak sayısı
TWEET_ALTERNATIVES      = 3     # Her içerik için kaç tweet alternatifi üretilsin

# ─── VERİTABANI ──────────────────────────────────────────────────────────────
DB_PATH = "twitter_bot.db"
