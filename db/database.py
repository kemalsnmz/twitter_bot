import sqlite3
import json
from datetime import datetime
from config import DB_PATH


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Tabloları oluştur (yoksa)."""
    conn = get_conn()
    c = conn.cursor()

    # Ham içerik kuyruğu — toplayıcı ajan buraya yazar
    c.execute("""
        CREATE TABLE IF NOT EXISTS content_queue (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            topic       TEXT NOT NULL,
            source_type TEXT NOT NULL,   -- 'rss' | 'twitter' | 'reddit'
            source_name TEXT,
            title       TEXT,
            url         TEXT UNIQUE,
            raw_text    TEXT,
            fetched_at  TEXT NOT NULL,
            processed   INTEGER DEFAULT 0  -- 0: bekliyor, 1: işlendi
        )
    """)

    # Tweet kuyruğu — yazar ajan buraya yazar, onay beklenir
    c.execute("""
        CREATE TABLE IF NOT EXISTS tweet_queue (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            content_id      INTEGER REFERENCES content_queue(id),
            topic           TEXT NOT NULL,
            alternatives    TEXT NOT NULL,  -- JSON listesi
            selected_index  INTEGER,        -- kullanıcının seçtiği alternatif
            custom_text     TEXT,           -- kullanıcı düzenlediyse
            status          TEXT DEFAULT 'pending',
            -- 'pending' | 'approved' | 'rejected' | 'published' | 'edited'
            telegram_msg_id INTEGER,
            created_at      TEXT NOT NULL,
            published_at    TEXT
        )
    """)

    # Arşiv — yayınlanan tweetler
    c.execute("""
        CREATE TABLE IF NOT EXISTS published_archive (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            tweet_id     TEXT,   -- Twitter'ın verdiği ID
            topic        TEXT,
            tweet_text   TEXT,
            source_url   TEXT,
            published_at TEXT
        )
    """)

    conn.commit()
    conn.close()
    print("[DB] Veritabanı hazır.")


# ─── CONTENT QUEUE ───────────────────────────────────────────────────────────

def insert_content(topic, source_type, source_name, title, url, raw_text):
    """Yeni içerik ekle. URL daha önce eklendiyse atla (UNIQUE)."""
    conn = get_conn()
    try:
        conn.execute("""
            INSERT INTO content_queue
                (topic, source_type, source_name, title, url, raw_text, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (topic, source_type, source_name, title, url, raw_text,
              datetime.utcnow().isoformat()))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False  # Zaten var
    finally:
        conn.close()


def get_unprocessed_content(topic=None, limit=10):
    conn = get_conn()
    if topic:
        rows = conn.execute(
            "SELECT * FROM content_queue WHERE processed=0 AND topic=? LIMIT ?",
            (topic, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM content_queue WHERE processed=0 LIMIT ?", (limit,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_content_processed(content_id):
    conn = get_conn()
    conn.execute("UPDATE content_queue SET processed=1 WHERE id=?", (content_id,))
    conn.commit()
    conn.close()


# ─── TWEET QUEUE ─────────────────────────────────────────────────────────────

def insert_tweet_queue(content_id, topic, alternatives: list):
    conn = get_conn()
    cursor = conn.execute("""
        INSERT INTO tweet_queue (content_id, topic, alternatives, created_at)
        VALUES (?, ?, ?, ?)
    """, (content_id, topic, json.dumps(alternatives, ensure_ascii=False),
          datetime.utcnow().isoformat()))
    tweet_queue_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return tweet_queue_id


def get_pending_tweets():
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM tweet_queue WHERE status='pending' ORDER BY created_at"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_tweet_by_id(tweet_queue_id):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM tweet_queue WHERE id=?", (tweet_queue_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def update_tweet_status(tweet_queue_id, status, selected_index=None,
                        custom_text=None, telegram_msg_id=None):
    conn = get_conn()
    conn.execute("""
        UPDATE tweet_queue
        SET status=?, selected_index=?, custom_text=?, telegram_msg_id=?
        WHERE id=?
    """, (status, selected_index, custom_text, telegram_msg_id, tweet_queue_id))
    conn.commit()
    conn.close()


def mark_tweet_published(tweet_queue_id, twitter_tweet_id, tweet_text, source_url, topic):
    conn = get_conn()
    now = datetime.utcnow().isoformat()
    conn.execute(
        "UPDATE tweet_queue SET status='published', published_at=? WHERE id=?",
        (now, tweet_queue_id)
    )
    conn.execute("""
        INSERT INTO published_archive (tweet_id, topic, tweet_text, source_url, published_at)
        VALUES (?, ?, ?, ?, ?)
    """, (twitter_tweet_id, topic, tweet_text, source_url, now))
    conn.commit()
    conn.close()
