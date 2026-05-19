"""
Ajan 3 — Onay & Yayın
Telegram botu üzerinden tweet alternatiflerini sana sunar.
Onay gelince Twitter'a yayınlar.
"""

import json
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

def build_approval_message(item: dict) -> tuple[str, InlineKeyboardMarkup]:
    """Onay mesajı ve butonlarını oluştur."""
    alternatives = json.loads(item["alternatives"])
    topic_label  = TOPICS.get(item["topic"], {}).get("label", item["topic"])

    # Kaynak URL'yi content_queue'dan al
    conn = get_conn()
    content = conn.execute(
        "SELECT url, source_name FROM content_queue WHERE id=?",
        (item["content_id"],)
    ).fetchone()
    conn.close()

    source_url  = content["url"]  if content else ""
    source_name = content["source_name"] if content else ""

    msg = f"🤖 *Yeni Tweet — {topic_label}*\n"
    msg += f"📰 Kaynak: {source_name}\n"
    msg += f"🔗 {source_url}\n\n"
    msg += "─────────────────\n"

    for i, alt in enumerate(alternatives, 1):
        msg += f"\n*{i}.* {alt}\n"

    msg += "\n─────────────────\n"
    msg += "Hangisini yayınlayalım?"

    # Butonlar: her alternatif + düzenle + reddet
    buttons = []
    for i in range(len(alternatives)):
        buttons.append(
            InlineKeyboardButton(
                f"✅ {i+1}. Tweet",
                callback_data=f"approve_{item['id']}_{i}"
            )
        )

    keyboard = [
        buttons,
        [
            InlineKeyboardButton("✏️ Düzenle", callback_data=f"edit_{item['id']}"),
            InlineKeyboardButton("❌ Reddet",  callback_data=f"reject_{item['id']}"),
        ]
    ]

    return msg, InlineKeyboardMarkup(keyboard)


# ─── TELEGRAM HANDLERS ──────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Twitter Otomasyon Botu aktif!\n\n"
        "/pending — Bekleyen tweetleri göster\n"
        "/stats   — İstatistikler"
    )


async def cmd_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bekleyen tweetleri listele ve onay için gönder."""
    items = get_pending_tweets()

    if not items:
        await update.message.reply_text("✅ Bekleyen tweet yok.")
        return

    await update.message.reply_text(f"📋 {len(items)} bekleyen tweet var. Gönderiliyor...")

    for item in items[:5]:  # Flood önlemi: max 5 adet
        msg, keyboard = build_approval_message(item)
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
            await query.edit_message_text("❌ Tweet bulunamadı.")
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

        await query.edit_message_text(f"⏳ Yayınlanıyor...")

        tweet_id = publish_to_twitter(tweet_text, source_url)

        if tweet_id:
            mark_tweet_published(
                tweet_queue_id=tweet_queue_id,
                twitter_tweet_id=tweet_id,
                tweet_text=tweet_text,
                source_url=source_url,
                topic=item["topic"],
            )
            await query.edit_message_text(
                f"🚀 *Tweet yayınlandı!*\n\n{tweet_text}\n\n"
                f"🔗 https://twitter.com/i/web/status/{tweet_id}",
                parse_mode="Markdown",
            )
        else:
            await query.edit_message_text("❌ Yayın başarısız. Twitter API hatası.")

    # ── REDDET ──────────────────────────────────────────────
    elif action == "reject":
        tweet_queue_id = int(parts[1])
        update_tweet_status(tweet_queue_id, "rejected")
        await query.edit_message_text("❌ Tweet reddedildi.")

    # ── DÜZENLE ─────────────────────────────────────────────
    elif action == "edit":
        tweet_queue_id = int(parts[1])
        context.user_data["editing_id"] = tweet_queue_id
        await query.edit_message_text(
            "✏️ Yeni tweet metnini yaz (max 257 karakter).\n"
            "URL otomatik eklenecek.\n\n/iptal ile vazgeç."
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

def run_publisher():
    """Telegram botunu başlat (blocking)."""
    import asyncio
    import httpx

    print("[Yayıncı Ajan] Telegram botu başlatılıyor...")

    # Telegram'daki eski polling oturumunu kapat
    try:
        with httpx.Client() as client:
            client.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/deleteWebhook",
                json={"drop_pending_updates": True},
                timeout=10,
            )
            # offset=-1 ile mevcut getUpdates oturumunu kapat
            client.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates",
                json={"offset": -1, "timeout": 0},
                timeout=10,
            )
        print("[Yayıncı Ajan] Eski oturum temizlendi.")
    except Exception as e:
        print(f"[Yayıncı Ajan] Oturum temizleme hatası (devam ediliyor): {e}")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Düzenleme konuşması
    edit_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(callback_handler, pattern="^edit_")],
        states={
            WAITING_EDIT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_edit)
            ]
        },
        fallbacks=[CommandHandler("iptal", cmd_cancel)],
    )

    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("pending", cmd_pending))
    app.add_handler(CommandHandler("stats",   cmd_stats))
    app.add_handler(edit_conv)
    app.add_handler(CallbackQueryHandler(callback_handler))

    print("[Yayıncı Ajan] Bot aktif. /pending ile bekleyen tweetleri görüntüle.")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    run_publisher()
