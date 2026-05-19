# Twitter Otomasyon Botu

## Proje Yapısı

```
twitter_bot/
├── config.py              # Tüm ayarlar (API key'ler, kaynaklar, konular)
├── main.py                # Ana orkestratör - sistemi başlatır
├── agents/
│   ├── collector.py       # Ajan 1: Kaynak tarayıcı (RSS, Twitter, Reddit)
│   ├── writer.py          # Ajan 2: Tweet yazıcı (Claude API)
│   └── publisher.py       # Ajan 3: Onay & yayın (Telegram + Twitter)
├── db/
│   └── database.py        # SQLite - kuyruk ve arşiv
├── utils/
│   └── logger.py          # Loglama
└── requirements.txt
```

## Kurulum

```bash
pip install -r requirements.txt
```

## Çalıştırma

```bash
python main.py
```

## Ortam Değişkenleri (.env)

```
ANTHROPIC_API_KEY=...
TWITTER_BEARER_TOKEN=...
TWITTER_API_KEY=...
TWITTER_API_SECRET=...
TWITTER_ACCESS_TOKEN=...
TWITTER_ACCESS_SECRET=...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
REDDIT_CLIENT_ID=...
REDDIT_CLIENT_SECRET=...
```
