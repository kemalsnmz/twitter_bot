"""
Ajan 2 — Tweet Yazıcı
İşlenmemiş içerikleri alır, Claude API ile tweet alternatifleri üretir,
tweet_queue tablosuna yazar.
"""

import json
import anthropic

from config import (
    ANTHROPIC_API_KEY,
    TOPICS,
    MAX_ITEMS_PER_RUN,
    TWEET_ALTERNATIVES,
)
from db.database import (
    get_unprocessed_content,
    mark_content_processed,
    insert_tweet_queue,
)


client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


# ─── TWEET ÜRETME ────────────────────────────────────────────────────────────

def generate_tweets(topic_key: str, content: dict) -> list[str]:
    """
    Verilen içerik için TWEET_ALTERNATIVES kadar tweet alternatifi üret.
    Her biri 280 karakteri geçmez.
    """
    topic_cfg = TOPICS[topic_key]
    tone      = topic_cfg["tweet_tone"]
    label     = topic_cfg["label"]

    prompt = f"""
Aşağıdaki {label} haberi/içeriği için {TWEET_ALTERNATIVES} farklı tweet alternatifi yaz.

İÇERİK BAŞLIĞI: {content['title']}
KAYNAK: {content['source_name']}
İÇERİK:
{content['raw_text'][:1500]}
KAYNAK URL: {content['url']}

KURALLAR:
- Her tweet maksimum 270 karakter (URL için 10 karakter boşluk bırak)
- Türkçe yaz
- Her tweet farklı bir açıdan veya hook ile başlasın
- Biri soru formatında olsun
- Biri "X bilmek istiyorsanız:" formatında olsun
- Haber kaynaklı ama özgün, kopyala-yapıştır değil
- Emoji kullanabilirsin ama her tweette max 2-3
- Kaynak URL'yi her tweete EKLEME, zaten ayrıca eklenecek

YANIT FORMATI — sadece geçerli JSON döndür, başka hiçbir şey yazma:
{{
  "alternatives": [
    "tweet metni 1",
    "tweet metni 2",
    "tweet metni 3"
  ]
}}
"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1000,
            system=tone,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = response.content[0].text.strip()
        # JSON fence varsa temizle
        raw = raw.replace("```json", "").replace("```", "").strip()
        data = json.loads(raw)
        alternatives = data.get("alternatives", [])

        # 280 karakter sınırını kontrol et (URL için +23 karakter Twitter ekler)
        cleaned = []
        for alt in alternatives:
            if len(alt) > 257:
                alt = alt[:254] + "..."
            cleaned.append(alt)

        return cleaned

    except Exception as e:
        print(f"  [Yazıcı] Claude API hatası: {e}")
        return []


# ─── ANA FONKSİYON ───────────────────────────────────────────────────────────

def run_writer():
    """İşlenmemiş içerikleri al, tweet üret, kuyruğa ekle."""
    print(f"\n[Yazıcı Ajan] Başladı")

    items = get_unprocessed_content(limit=MAX_ITEMS_PER_RUN)

    if not items:
        print("[Yazıcı Ajan] İşlenecek içerik yok.")
        return 0

    queued = 0
    for item in items:
        topic_key = item["topic"]

        if topic_key not in TOPICS or not TOPICS[topic_key].get("active", False):
            mark_content_processed(item["id"])
            continue

        print(f"\n  → İşleniyor: {item['title'][:60]}")
        alternatives = generate_tweets(topic_key, item)

        if alternatives:
            tweet_queue_id = insert_tweet_queue(
                content_id=item["id"],
                topic=topic_key,
                alternatives=alternatives,
            )
            print(f"  ✓ {len(alternatives)} alternatif üretildi (queue_id={tweet_queue_id})")
            queued += 1
        else:
            print(f"  ✗ Tweet üretilemedi, atlanıyor.")

        mark_content_processed(item["id"])

    print(f"\n[Yazıcı Ajan] Bitti — {queued} içerik kuyruğa eklendi.")
    return queued


if __name__ == "__main__":
    from db.database import init_db
    init_db()
    run_writer()
