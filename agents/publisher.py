"""
Ajan 3 — Onay & Yayın
Telegram botu üzerinden tweet alternatiflerini sana sunar.
Onay gelince Twitter'a yayınlar.
"""

import json
import io
import httpx
import anthropic
import tweepy
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
    ConversationHandler,
)

from config import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    TWITTER_API_KEY,
    TWITTER_API_SECRET,
    TWITTER_ACCESS_TOKEN,
    TWITTER_ACCESS_SECRET,
    TOPICS,
    ANTHROPIC_API_KEY,
    STABILITY_API_KEY,
)
from db.database import (
    get_pending_tweets,
    get_tweet_by_id,
    update_tweet_status,
    mark_tweet_published,
    get_conn,
)

# ConversationHandler state
WAITING_EDIT = 1


# ─── GÖRSEL ÜRETİCİ ─────────────────────────────────────────────────────────

_TOPIC_HINTS = {
    "ai": "artificial intelligence technology, neural network, futuristic digital art, blue purple tones",
    "finance": "financial market, stock charts, business skyscrapers, professional photography",
}

def _make_image_prompt(title: str, topic: str) -> str:
    hint = _TOPIC_HINTS.get(topic, "editorial news illustration, professional")
    return f"{title[:120]}, {hint}, high quality, cinematic, no text, no watermark"


def generate_image(title: str, topic: str) -> bytes | None:
    """Stability AI ile 16:9 JPEG görsel üret. Başarılıysa bytes döndür."""
    if not STABILITY_API_KEY:
        return None
    prompt = _make_image_prompt(title, topic)
    try:
        response = httpx.post(
            "https://api.stability.ai/v2beta/stable-image/generate/core",
            headers={"authorization": f"Bearer {STABILITY_API_KEY}", "accept": "image/*"},
            data={"prompt": prompt, "output_format": "jpeg", "aspect_ratio": "16:9"},
            timeout=45,
        )
        if response.status_code == 200:
            print(f"  [Image] Gorsel uretildi ({len(response.content)//1024}KB)")
            return response.content
        print(f"  [Image] API hatasi: {response.status_code}")
        return None
    except Exception as e:
        print(f"  [Image] Hata: {e}")
        return None


# ─── TWITTER YAYINLAYICı ────────────────────────────────────────────────────

def publish_to_twitter(tweet_text: str, source_url: str) -> str | None:
    """Twitter'a tweet at. Başarılıysa tweet ID'yi döndür."""
    try:
        auth = tweepy.OAuth1UserHandler(
            TWITTER_API_KEY,
            TWITTER_API_SECRET,
            TWITTER_ACCESS_TOKEN,
            TWITTER_ACCESS_SECRET,
        )
        api = tweepy.API(auth)
        client = tweepy.Client(
            consumer_key=TWITTER_API_KEY,
            consumer_secret=TWITTER_API_SECRET,
            access_token=TWITTER_ACCESS_TOKEN,
            access_token_secret=TWITTER_ACCESS_SECRET,
        )

        # URL'yi metne ekle
        full_text = f"{tweet_text}\n\n{source_url}"
        response = client.create_tweet(text=full_text)
        tweet_id = str(response.data["id"])
        print(f"  [Twitter] Yayınlandı! ID: {tweet_id}")
        return tweet_id

    except Exception as e:
        print(f"  [Twitter] Yayın hatası: {e}")
        return None


# ─── TELEGRAM YARDIMCILAR ───────────────────────────────────────────────────

def _get_editor_comment(item: dict, content: dict) -> str:
    """Claude ile editör yorumu üret."""
    try:
        claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        response = claude.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=300,
            messages=[{
                "role": "user",
                "content": (
                    f"Asagidaki haber icin kisaca Turkce editor yorumu yaz. "
                    f"Haberin neyi ifade ettigini ve dikkat ceken noktasini 2-3 cumleyle ozet. "
                    f"Sadece yorumu yaz, baslik veya etiket koyma.\n\n"
                    f"Baslik: {content['title']}\n"
                    f"Icerik: {content['raw_text'][:800]}"
                ),
            }],
        )
        return response.content[0].text.strip()
    except Exception as e:
        return f"Yorum uretilirken hata: {e}"


def build_approval_message(item: dict) -> tuple[str, InlineKeyboardMarkup]:
    """Onay mesajı, editör yorumu ve butonlarını oluştur."""
    alternatives = json.loads(item["alternatives"])
    tweet_text   = alternatives[0]  # En iyi alternatifi kullan
    topic_label  = TOPICS.get(item["topic"], {}).get("label", item["topic"])

    conn = get_conn()
    content = conn.execute(
        "SELECT url, source_name, title, raw_text FROM content_queue WHERE id=?",
        (item["content_id"],)
    ).fetchone()
    conn.close()

    source_url  = content["url"]        if content else ""
    source_name = content["source_name"] if content else ""

    # Editör yorumu üret
    yorum = _get_editor_comment(item, dict(content)) if content else ""

    msg = f"*Tweet Generator — {topic_label}* (ID: `{item['id']}`)\n"
    msg += f"Kaynak: {source_name}\n"
    msg += f"{source_url}\n\n"
    if yorum:
        msg += f"*Editor Yorumu:*\n_{yorum}_\n\n"
    msg += "─────────────────\n"
    msg += f"{tweet_text}\n"
    msg += "─────────────────\n"

    keyboard = [
        [InlineKeyboardButton("✅ Yayinla", callback_data=f"approve_{item['id']}_0")],
        [
            InlineKeyboardButton("✏️ Duzenle", callback_data=f"edit_{item['id']}"),
            InlineKeyboardButton("❌ Reddet",  callback_data=f"reject_{item['id']}"),
        ]
    ]

    return msg, InlineKeyboardMarkup(keyboard)


# ─── TELEGRAM HANDLERS ──────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Twitter Otomasyon Botu aktif!\n\n"
        "/pending      — Bekleyen tweetleri goster\n"
        "/yorum <id>   — O haber icin editor yorumu uret\n"
        "/stats        — Istatistikler"
    )


async def cmd_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bekleyen tweetleri listele ve onay için gönder."""
    items = get_pending_tweets()

    if not items:
        await update.message.reply_text("Bekleyen tweet yok.")
        return

    await update.message.reply_text(f"{len(items)} bekleyen tweet var. Gonderiliyor...")

    for item in items[:5]:  # Flood önlemi: max 5 adet
        msg, keyboard = build_approval_message(item)

        # Kaynak başlığını al (görsel için)
        conn = get_conn()
        row = conn.execute(
            "SELECT title FROM content_queue WHERE id=?", (item["content_id"],)
        ).fetchone()
        conn.close()
        title = row["title"] if row else ""

        # Görsel üret
        image_bytes = generate_image(title, item["topic"]) if title else None

        if image_bytes:
            # Caption max 1024 karakter — kırp gerekirse
            caption = msg if len(msg) <= 1024 else msg[:1020] + "..."
            sent = await update.message.reply_photo(
                photo=io.BytesIO(image_bytes),
                caption=caption,
                parse_mode="Markdown",
                reply_markup=keyboard,
            )
        else:
            sent = await update.message.reply_text(
                msg,
                parse_mode="Markdown",
                reply_markup=keyboard,
                disable_web_page_preview=True,
            )

        update_tweet_status(item["id"], "pending", telegram_msg_id=sent.message_id)


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kısa istatistik."""
    conn = get_conn()
    total_content  = conn.execute("SELECT COUNT(*) FROM content_queue").fetchone()[0]
    total_pending  = conn.execute("SELECT COUNT(*) FROM tweet_queue WHERE status='pending'").fetchone()[0]
    total_published = conn.execute("SELECT COUNT(*) FROM published_archive").fetchone()[0]
    conn.close()

    await update.message.reply_text(
        f"📊 *İstatistikler*\n\n"
        f"📥 Toplam toplanan içerik: {total_content}\n"
        f"⏳ Onay bekleyen tweet: {total_pending}\n"
        f"🚀 Yayınlanan tweet: {total_published}",
        parse_mode="Markdown",
    )


async def cmd_yorum(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/yorum <queue_id> — O haberle ilgili editör yorumu üret."""
    if not context.args:
        await update.message.reply_text("Kullanim: /yorum <queue_id>\nOrnek: /yorum 6")
        return

    try:
        queue_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Gecersiz ID. Ornek: /yorum 6")
        return

    item = get_tweet_by_id(queue_id)
    if not item:
        await update.message.reply_text(f"ID {queue_id} bulunamadi.")
        return

    conn = get_conn()
    content = conn.execute(
        "SELECT title, raw_text, url, source_name FROM content_queue WHERE id=?",
        (item["content_id"],)
    ).fetchone()
    conn.close()

    if not content:
        await update.message.reply_text("Kaynak icerik bulunamadi.")
        return

    await update.message.reply_text("Yorum hazirlaniyor...")

    try:
        claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        response = claude.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=500,
            messages=[{
                "role": "user",
                "content": (
                    f"Asagidaki haber icin kisaca Turkce editör yorumu yaz. "
                    f"Haberin neyi ifade ettigini, sektöre etkisini ve dikkat ceken noktasini 3-4 cumleyle ozet. "
                    f"Sadece yorumu yaz, baslik koyma.\n\n"
                    f"Baslik: {content['title']}\n"
                    f"Kaynak: {content['source_name']}\n"
                    f"Icerik: {content['raw_text'][:1000]}"
                ),
            }],
        )
        yorum = response.content[0].text.strip()
        await update.message.reply_text(
            f"*Editör Yorumu — #{queue_id}*\n\n{yorum}\n\n🔗 {content['url']}",
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )
    except Exception as e:
        await update.message.reply_text(f"Yorum uretilirken hata: {e}")


async def _edit_msg(query, text: str, parse_mode=None, reply_markup=None):
    """Fotoğraf veya metin mesajını uygun metotla güncelle."""
    if query.message.photo:
        caption = text if len(text) <= 1024 else text[:1020] + "..."
        await query.edit_message_caption(caption=caption, parse_mode=parse_mode, reply_markup=reply_markup)
    else:
        await query.edit_message_text(text=text, parse_mode=parse_mode, reply_markup=reply_markup)


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Buton tıklamalarını işle."""
    query = update.callback_query
    await query.answer()

    data = query.data
    parts = data.split("_")
    action = parts[0]

    # ── ONAYLA ──────────────────────────────────────────────
    if action == "approve":
        tweet_queue_id = int(parts[1])
        alt_index      = int(parts[2])

        item = get_tweet_by_id(tweet_queue_id)
        if not item:
            await _edit_msg(query, "Tweet bulunamadi.")
            return

        alternatives = json.loads(item["alternatives"])
        tweet_text   = alternatives[alt_index]

        # Kaynak URL
        conn = get_conn()
        content = conn.execute(
            "SELECT url FROM content_queue WHERE id=?", (item["content_id"],)
        ).fetchone()
        conn.close()
        source_url = content["url"] if content else ""

        await _edit_msg(query, "Yayinlaniyor...")

        tweet_id = publish_to_twitter(tweet_text, source_url)

        if tweet_id:
            mark_tweet_published(
                tweet_queue_id=tweet_queue_id,
                twitter_tweet_id=tweet_id,
                tweet_text=tweet_text,
                source_url=source_url,
                topic=item["topic"],
            )
            await _edit_msg(
                query,
                f"*Tweet yayinlandi!*\n\n{tweet_text}\n\n"
                f"https://twitter.com/i/web/status/{tweet_id}",
                parse_mode="Markdown",
            )
        else:
            await _edit_msg(query, "Yayin basarisiz. Twitter API hatasi.")

    # ── REDDET ──────────────────────────────────────────────
    elif action == "reject":
        tweet_queue_id = int(parts[1])
        update_tweet_status(tweet_queue_id, "rejected")
        await _edit_msg(query, "Tweet reddedildi.")

    # ── DÜZENLE ─────────────────────────────────────────────
    elif action == "edit":
        tweet_queue_id = int(parts[1])
        context.user_data["editing_id"] = tweet_queue_id
        await _edit_msg(
            query,
            "Yeni tweet metnini yaz (max 257 karakter).\n"
            "URL otomatik eklenecek.\n\n/iptal ile vazgec."
        )
        return WAITING_EDIT


async def receive_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kullanıcının düzenlediği tweet metnini al ve yayınla."""
    tweet_queue_id = context.user_data.get("editing_id")
    if not tweet_queue_id:
        return ConversationHandler.END

    custom_text = update.message.text.strip()

    if len(custom_text) > 257:
        await update.message.reply_text(
            f"⚠️ Metin çok uzun ({len(custom_text)} karakter). Max 257 karakter. Tekrar yaz:"
        )
        return WAITING_EDIT

    item = get_tweet_by_id(tweet_queue_id)
    conn = get_conn()
    content = conn.execute(
        "SELECT url FROM content_queue WHERE id=?", (item["content_id"],)
    ).fetchone()
    conn.close()
    source_url = content["url"] if content else ""

    await update.message.reply_text("⏳ Yayınlanıyor...")

    tweet_id = publish_to_twitter(custom_text, source_url)

    if tweet_id:
        update_tweet_status(tweet_queue_id, "edited", custom_text=custom_text)
        mark_tweet_published(
            tweet_queue_id=tweet_queue_id,
            twitter_tweet_id=tweet_id,
            tweet_text=custom_text,
            source_url=source_url,
            topic=item["topic"],
        )
        await update.message.reply_text(
            f"🚀 *Tweet yayınlandı!*\n\n{custom_text}\n\n"
            f"🔗 https://twitter.com/i/web/status/{tweet_id}",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text("❌ Yayın başarısız. Twitter API hatası.")

    context.user_data.pop("editing_id", None)
    return ConversationHandler.END


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("editing_id", None)
    await update.message.reply_text("İptal edildi.")
    return ConversationHandler.END


# ─── BOT BAŞLATMA ───────────────────────────────────────────────────────────

def _build_app():
    """Application instance ve handler'ları oluştur."""
    edit_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(callback_handler, pattern="^edit_")],
        states={
            WAITING_EDIT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_edit)
            ]
        },
        fallbacks=[CommandHandler("iptal", cmd_cancel)],
    )
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("pending", cmd_pending))
    app.add_handler(CommandHandler("stats",   cmd_stats))
    app.add_handler(CommandHandler("yorum",   cmd_yorum))
    app.add_handler(edit_conv)
    app.add_handler(CallbackQueryHandler(callback_handler))
    return app


def _clear_telegram_session():
    """Telegram sunucusundaki eski polling oturumunu kapat."""
    import httpx, time
    try:
        with httpx.Client(timeout=10) as client:
            client.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/deleteWebhook",
                json={"drop_pending_updates": True},
            )
            client.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates",
                json={"offset": -1, "timeout": 0},
            )
        time.sleep(2)
        print("[Yayıncı Ajan] Eski oturum temizlendi.")
    except Exception as e:
        print(f"[Yayıncı Ajan] Oturum temizleme hatası: {e}")


def run_publisher():
    """Telegram botunu başlat (blocking). Conflict durumunda yeniden dener."""
    import time
    from telegram.error import Conflict

    print("[Yayıncı Ajan] Telegram botu başlatılıyor...")
    _clear_telegram_session()

    for attempt in range(1, 6):
        try:
            app = _build_app()
            print(f"[Yayıncı Ajan] Bot aktif (deneme {attempt}). /pending ile bekleyen tweetleri görüntüle.")
            app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
            break
        except Conflict:
            wait = 10 * attempt
            print(f"[Yayıncı Ajan] Conflict, {wait}s bekleniyor... ({attempt}/5)")
            _clear_telegram_session()
            time.sleep(wait)
    else:
        print("[Yayıncı Ajan] 5 denemede başlatılamadi. Botu elle yeniden calistir.")


if __name__ == "__main__":
    run_publisher()
