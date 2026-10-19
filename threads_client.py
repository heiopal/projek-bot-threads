"""
threads_client.py
------------------
Modul bersama: semua fungsi untuk bicara ke Threads API dan ke Gemini,
dipakai bareng oleh bot_threads.py (posting konten baru) dan reply_bot.py
(auto-reply). Tujuannya supaya logika retry, publish, dan pemanggilan AI
tidak ditulis dua kali di tempat berbeda.

Environment variables yang dibutuhkan:
    GEMINI_API_KEY
    THREADS_ACCESS_TOKEN
"""

import os
import time
import logging
import requests
from dotenv import load_dotenv
from google import genai

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
THREADS_ACCESS_TOKEN = os.getenv("THREADS_ACCESS_TOKEN")

GRAPH_BASE = "https://graph.threads.net/v1.0"

MAX_RETRIES = 3              # percobaan ulang untuk request Threads/Gemini yang gagal
CONTAINER_TIMEOUT = 30       # detik, maksimal menunggu container siap sebelum publish
CONTAINER_POLL_INTERVAL = 3  # detik, jeda antar-cek status container
THREADS_TEXT_LIMIT = 500     # batas resmi Threads untuk post/reply teks

_gemini_client = genai.Client(api_key=GEMINI_API_KEY)


def setup_logger(name, log_file):
    """Logger seragam: tulis ke console + file log masing-masing script."""
    logger = logging.getLogger(name)
    if logger.handlers:  # hindari duplikasi handler kalau dipanggil berkali-kali
        return logger
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    return logger


log = setup_logger("threads_client", "threads_client.log")


# ---------------------------------------------------------------------------
# Request wrapper dengan retry
# ---------------------------------------------------------------------------
def request_with_retry(method, url, max_retries=MAX_RETRIES, **kwargs):
    for attempt in range(1, max_retries + 1):
        try:
            res = requests.request(method, url, timeout=15, **kwargs)
            if res.status_code == 429:
                wait = 5 * attempt
                log.warning(f"Kena rate limit, tunggu {wait}s...")
                time.sleep(wait)
                continue
            return res.json()
        except requests.RequestException as e:
            log.warning(f"Request gagal (percobaan {attempt}/{max_retries}): {e}")
            time.sleep(3 * attempt)
    log.error(f"Request ke {url} gagal setelah {max_retries} percobaan.")
    return {}


# ---------------------------------------------------------------------------
# Threads API
# ---------------------------------------------------------------------------
def get_own_profile():
    url = f"{GRAPH_BASE}/me"
    params = {"fields": "id,username", "access_token": THREADS_ACCESS_TOKEN}
    return request_with_retry("GET", url, params=params)


def get_own_recent_posts(limit=5):
    url = f"{GRAPH_BASE}/me/threads"
    params = {
        "fields": "id,text,timestamp",
        "limit": limit,
        "access_token": THREADS_ACCESS_TOKEN,
    }
    data = request_with_retry("GET", url, params=params)
    return data.get("data", [])


def get_replies(media_id):
    url = f"{GRAPH_BASE}/{media_id}/replies"
    params = {
        "fields": "id,text,username,timestamp",
        "access_token": THREADS_ACCESS_TOKEN,
    }
    data = request_with_retry("GET", url, params=params)
    return data.get("data", [])


def wait_until_container_ready(container_id):
    url = f"{GRAPH_BASE}/{container_id}"
    params = {"fields": "status,error_message", "access_token": THREADS_ACCESS_TOKEN}
    waited = 0
    while waited < CONTAINER_TIMEOUT:
        data = request_with_retry("GET", url, params=params)
        status = data.get("status")
        if status == "FINISHED":
            return True
        if status == "ERROR":
            log.error(f"Container gagal diproses: {data.get('error_message')}")
            return False
        time.sleep(CONTAINER_POLL_INTERVAL)
        waited += CONTAINER_POLL_INTERVAL
    log.warning("Timeout menunggu container siap, tetap coba publish.")
    return True


def create_and_publish(text, reply_to_id=None):
    """Alur 2 langkah: buat container -> tunggu siap -> publish.
    Kalau reply_to_id diisi, hasilnya jadi balasan ke reply/post tsb.
    Teks otomatis dipotong ke 500 karakter (batas asli Threads) sebagai
    jaring pengaman kalau AI menghasilkan teks lebih panjang dari yang diminta."""
    if len(text) > THREADS_TEXT_LIMIT:
        log.warning(f"Teks melebihi {THREADS_TEXT_LIMIT} karakter, dipotong otomatis.")
        text = text[:THREADS_TEXT_LIMIT - 1].rstrip() + "…"

    create_url = f"{GRAPH_BASE}/me/threads"
    payload = {
        "media_type": "TEXT",
        "text": text,
        "access_token": THREADS_ACCESS_TOKEN,
    }
    if reply_to_id:
        payload["reply_to_id"] = reply_to_id

    res = request_with_retry("POST", create_url, data=payload)
    creation_id = res.get("id")
    if not creation_id:
        log.error(f"Gagal membuat container: {res}")
        return None

    wait_until_container_ready(creation_id)

    publish_url = f"{GRAPH_BASE}/me/threads_publish"
    pub_payload = {"creation_id": creation_id, "access_token": THREADS_ACCESS_TOKEN}
    pub_res = request_with_retry("POST", publish_url, data=pub_payload)

    if "id" in pub_res:
        return pub_res["id"]
    log.error(f"Gagal publish: {pub_res}")
    return None


# ---------------------------------------------------------------------------
# Gemini dengan retry (mengatasi error sementara seperti 503 Service Unavailable)
# ---------------------------------------------------------------------------
def generate_with_retry(prompt, model="gemini-3.6-flash", max_retries=MAX_RETRIES):
    for attempt in range(1, max_retries + 1):
        try:
            response = _gemini_client.models.generate_content(model=model, contents=prompt)
            return response.text.strip()
        except Exception as e:
            wait = 5 * attempt
            log.warning(
                f"Gemini gagal merespons (percobaan {attempt}/{max_retries}): {e}. "
                f"Tunggu {wait}s..."
            )
            time.sleep(wait)
    log.error("Gemini tetap gagal merespons setelah beberapa percobaan.")
    return None