"""
Ana Orkestratör
Toplayıcı ve Yazıcı ajanları zamanlı çalıştırır.
Telegram botunu ayrı thread'de başlatır.
"""

import time
import threading
import schedule
from datetime import datetime

from db.database import init_db
from agents.collector import run_collector
from agents.writer import run_writer
from agents.publisher import run_publisher
from config import SCRAPE_INTERVAL_MINUTES


# ─── PIPELINE ────────────────────────────────────────────────────────────────

def run_pipeline():
    """Toplayıcı → Yazıcı pipeline'ını çalıştır."""
    print(f"\n{'='*60}")
    print(f"[Orkestratör] Pipeline başladı — {datetime.now().strftime('%d.%m.%Y %H:%M')}")

    try:
        new_content = run_collector()
        if new_content > 0:
            run_writer()
        else:
            print("[Orkestratör] Yeni içerik yok, Yazıcı atlandı.")
    except Exception as e:
        print(f"[Orkestratör] HATA: {e}")

    print(f"[Orkestratör] Pipeline tamamlandı.")
    print(f"Onay icin Telegram'dan /pending komutunu kullan.\n")


# ─── ZAMANLAYICI ─────────────────────────────────────────────────────────────

def start_scheduler():
    """Arka planda zamanlı çalışır."""
    schedule.every(SCRAPE_INTERVAL_MINUTES).minutes.do(run_pipeline)
    print(f"[Zamanlayıcı] Her {SCRAPE_INTERVAL_MINUTES} dakikada bir çalışacak.")

    while True:
        schedule.run_pending()
        time.sleep(30)


# ─── MAIN ────────────────────────────────────────────────────────────────────

def main():
    print("Twitter Otomasyon Sistemi Baslatiliyor...")
    print("=" * 60)

    # 1. Veritabanını hazırla
    init_db()

    # 2. İlk çalışmayı hemen yap
    run_pipeline()

    # 3. Zamanlayıcıyı arka thread'de başlat
    scheduler_thread = threading.Thread(target=start_scheduler, daemon=True)
    scheduler_thread.start()

    # 4. Telegram botunu ana thread'de başlat (blocking)
    run_publisher()


if __name__ == "__main__":
    main()
