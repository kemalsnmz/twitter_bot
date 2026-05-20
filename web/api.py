"""
Web Dashboard API — FastAPI backend
Telegram botu ile paralel çalışır, aynı SQLite DB'yi paylaşır.
"""

import json
import io
import threading
from typing import Optional
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

from config import STABILITY_API_KEY, TOPICS
from db.database import (
    get_conn,
    get_pending_tweets,
    get_tweet_by_id,
    update_tweet_status,
    mark_tweet_published,
)
from agents.publisher import publish_to_twitter, generate_image

app = FastAPI(title="Twitter Bot Dashboard")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── AUTH ────────────────────────────────────────────────────────────────────

def _get_password() -> str:
    import os
    from dotenv import load_dotenv
    load_dotenv()
    return os.getenv("DASHBOARD_PASSWORD", "")


def verify_token(x_auth_token: str = Header(default="")):
    expected = _get_password()
    if expected and x_auth_token != expected:
        raise HTTPException(status_code=401, detail="Yetkisiz erişim.")


# ─── SCHEMAS ─────────────────────────────────────────────────────────────────

class EditBody(BaseModel):
    text: str


# ─── ENDPOINTS ───────────────────────────────────────────────────────────────

@app.get("/api/stats")
def get_stats(_: None = Depends(verify_token)):
    conn = get_conn()
    total_content   = conn.execute("SELECT COUNT(*) FROM content_queue").fetchone()[0]
    pending_tweets  = conn.execute("SELECT COUNT(*) FROM tweet_queue WHERE status='pending'").fetchone()[0]
    published_total = conn.execute("SELECT COUNT(*) FROM published_archive").fetchone()[0]
    last_run = conn.execute(
        "SELECT fetched_at FROM content_queue ORDER BY fetched_at DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return {
        "total_content": total_content,
        "pending_tweets": pending_tweets,
        "published_total": published_total,
        "last_run": last_run[0] if last_run else None,
    }


@app.get("/api/pending")
def get_pending(_: None = Depends(verify_token)):
    items = get_pending_tweets()
    conn = get_conn()
    result = []
    for item in items:
        content = conn.execute(
            "SELECT url, source_name, title, raw_text FROM content_queue WHERE id=?",
            (item["content_id"],)
        ).fetchone()
        alternatives = json.loads(item["alternatives"])
        result.append({
            "id": item["id"],
            "topic": item["topic"],
            "topic_label": TOPICS.get(item["topic"], {}).get("label", item["topic"]),
            "created_at": item["created_at"],
            "tweet_text": alternatives[0],
            "alternatives": alternatives,
            "content_id": item["content_id"],
            "source_url": content["url"] if content else "",
            "source_name": content["source_name"] if content else "",
            "title": content["title"] if content else "",
        })
    conn.close()
    return result


@app.post("/api/tweets/{tweet_id}/approve")
def approve_tweet(tweet_id: int, _: None = Depends(verify_token)):
    item = get_tweet_by_id(tweet_id)
    if not item:
        raise HTTPException(status_code=404, detail="Tweet bulunamadı.")

    alternatives = json.loads(item["alternatives"])
    tweet_text = alternatives[0]

    conn = get_conn()
    content = conn.execute(
        "SELECT url FROM content_queue WHERE id=?", (item["content_id"],)
    ).fetchone()
    conn.close()
    source_url = content["url"] if content else ""

    twitter_id = publish_to_twitter(tweet_text, source_url)
    if not twitter_id:
        raise HTTPException(status_code=502, detail="Twitter API hatası.")

    mark_tweet_published(
        tweet_queue_id=tweet_id,
        twitter_tweet_id=twitter_id,
        tweet_text=tweet_text,
        source_url=source_url,
        topic=item["topic"],
    )
    return {"twitter_id": twitter_id, "tweet_text": tweet_text}


@app.post("/api/tweets/{tweet_id}/reject")
def reject_tweet(tweet_id: int, _: None = Depends(verify_token)):
    item = get_tweet_by_id(tweet_id)
    if not item:
        raise HTTPException(status_code=404, detail="Tweet bulunamadı.")
    update_tweet_status(tweet_id, "rejected")
    return {"status": "rejected"}


@app.post("/api/tweets/{tweet_id}/edit")
def edit_tweet(tweet_id: int, body: EditBody, _: None = Depends(verify_token)):
    if len(body.text) > 257:
        raise HTTPException(status_code=400, detail="Metin 257 karakterden uzun.")

    item = get_tweet_by_id(tweet_id)
    if not item:
        raise HTTPException(status_code=404, detail="Tweet bulunamadı.")

    conn = get_conn()
    content = conn.execute(
        "SELECT url FROM content_queue WHERE id=?", (item["content_id"],)
    ).fetchone()
    conn.close()
    source_url = content["url"] if content else ""

    twitter_id = publish_to_twitter(body.text, source_url)
    if not twitter_id:
        raise HTTPException(status_code=502, detail="Twitter API hatası.")

    update_tweet_status(tweet_id, "edited", custom_text=body.text)
    mark_tweet_published(
        tweet_queue_id=tweet_id,
        twitter_tweet_id=twitter_id,
        tweet_text=body.text,
        source_url=source_url,
        topic=item["topic"],
    )
    return {"twitter_id": twitter_id, "tweet_text": body.text}


@app.get("/api/archive")
def get_archive(page: int = 1, _: None = Depends(verify_token)):
    page_size = 10
    offset = (page - 1) * page_size
    conn = get_conn()
    total = conn.execute("SELECT COUNT(*) FROM published_archive").fetchone()[0]
    rows = conn.execute(
        "SELECT * FROM published_archive ORDER BY published_at DESC LIMIT ? OFFSET ?",
        (page_size, offset)
    ).fetchall()
    conn.close()
    return {
        "total": total,
        "page": page,
        "pages": (total + page_size - 1) // page_size,
        "items": [dict(r) for r in rows],
    }


@app.get("/api/image/{content_id}")
def get_image(content_id: int, _: None = Depends(verify_token)):
    conn = get_conn()
    content = conn.execute(
        "SELECT title, topic FROM content_queue WHERE id=?", (content_id,)
    ).fetchone()
    conn.close()

    if not content:
        raise HTTPException(status_code=404, detail="İçerik bulunamadı.")

    image_bytes = generate_image(content["title"], content["topic"])
    if not image_bytes:
        raise HTTPException(status_code=503, detail="Görsel üretilemedi.")

    return Response(content=image_bytes, media_type="image/jpeg")


@app.post("/api/pipeline/run")
def run_pipeline(_: None = Depends(verify_token)):
    """Collector + Writer'ı arka planda tetikle."""
    def _run():
        from agents.collector import run_collector
        from agents.writer import run_writer
        collected = run_collector()
        if collected > 0:
            run_writer()

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return {"status": "started"}


@app.get("/api/recent")
def get_recent(_: None = Depends(verify_token)):
    """Son 5 yayınlanan tweet."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM published_archive ORDER BY published_at DESC LIMIT 5"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
