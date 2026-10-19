import os
import sys
import time
import json
import base64
import logging
import threading
import urllib.request
import urllib.error
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("CloudThreadsBot")

# =============================================================================
# ENVIRONMENT & CONFIGURATION
# =============================================================================
# Load local .env if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", os.getenv("GOOGLE_API_KEY", ""))
THREADS_ACCESS_TOKEN = os.getenv("THREADS_ACCESS_TOKEN", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO = os.getenv("GITHUB_REPO", "heiopal/projek-bot-threads")
GEMINI_MODEL = "gemini-3.6-flash"
PORT = int(os.getenv("PORT", 7860))

START_TIME = datetime.now()

# In-memory session state per chat
# chat_id -> {"state": "IDLE"|"AWAITING_ANGLE"|"AWAITING_CONFIRM", "topic": "", "angles": {}, "draft": ""}
SESSIONS = {}

# =============================================================================
# GITHUB STORAGE CLIENT
# =============================================================================
GITHUB_FILE_PATH = "content_history.json"

def get_github_headers():
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "User-Agent": "ThreadsBot-Cloud",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json"
    }

def fetch_history():
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE_PATH}"
    req = urllib.request.Request(url, headers=get_github_headers())
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content_b64 = data.get("content", "")
            sha = data.get("sha", "")
            raw = base64.b64decode(content_b64).decode("utf-8")
            return json.loads(raw), sha
    except Exception as e:
        log.warning(f"Fetch GitHub history fallback: {e}")
        return [], None

def save_history(topic, pillar, caption, permalink=""):
    history, sha = fetch_history()
    new_entry = {
        "timestamp": datetime.now().isoformat(),
        "topic": topic,
        "pillar": pillar,
        "caption": caption,
        "permalink": permalink
    }
    history.append(new_entry)
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE_PATH}"
    content_str = json.dumps(history, indent=2, ensure_ascii=False)
    content_b64 = base64.b64encode(content_str.encode("utf-8")).decode("utf-8")

    payload = {
        "message": f"chore: add post '{topic[:30]}' to content_history.json [skip ci]",
        "content": content_b64
    }
    if sha:
        payload["sha"] = sha

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=get_github_headers(), method="PUT")
    try:
        with urllib.request.urlopen(req, timeout=15):
            log.info(f"Successfully recorded post to GitHub ({GITHUB_REPO})")
            return True
    except Exception as e:
        log.error(f"Failed to push post to GitHub: {e}")
        return False

# =============================================================================
# GEMINI AI GENERATION
# =============================================================================
def call_gemini(system_instruction, user_prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "system_instruction": {
            "parts": [{"text": system_instruction}]
        },
        "contents": [
            {"parts": [{"text": user_prompt}]}
        ],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 800
        }
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            res_json = json.loads(resp.read().decode("utf-8"))
            candidates = res_json.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text", "").strip()
    except Exception as e:
        log.error(f"Gemini call error: {e}")
    return None

# =============================================================================
# THREADS API CLIENT
# =============================================================================
def publish_to_threads(text):
    """Publish text directly to Meta Threads Graph API."""
    # Step 1: Create container
    url = "https://graph.threads.net/v1.0/me/threads"
    params = {
        "media_type": "TEXT",
        "text": text,
        "access_token": THREADS_ACCESS_TOKEN
    }
    data = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            creation_id = res.get("id")
    except Exception as e:
        log.error(f"Threads container creation failed: {e}")
        return False, None

    if not creation_id:
        return False, None

    # Step 2: Wait for container to be ready
    time.sleep(3)

    # Step 3: Publish container
    pub_url = "https://graph.threads.net/v1.0/me/threads_publish"
    pub_params = {
        "creation_id": creation_id,
        "access_token": THREADS_ACCESS_TOKEN
    }
    pub_data = urllib.parse.urlencode(pub_params).encode("utf-8")
    pub_req = urllib.request.Request(pub_url, data=pub_data, method="POST")
    try:
        with urllib.request.urlopen(pub_req, timeout=20) as resp:
            pub_res = json.loads(resp.read().decode("utf-8"))
            post_id = pub_res.get("id")
            permalink = f"https://www.threads.net/@studyp4l/post/{post_id}" if post_id else "https://www.threads.net/@studyp4l"
            return True, permalink
    except Exception as e:
        log.error(f"Threads publish failed: {e}")
        return False, None

# =============================================================================
# TELEGRAM BOT CLIENT
# =============================================================================
def send_telegram_message(chat_id, text, reply_to_id=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text
    }
    if reply_to_id:
        payload["reply_to_message_id"] = reply_to_id
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15):
            pass
    except Exception as e:
        log.error(f"Error sending telegram message: {e}")

def handle_user_message(chat_id, user_text, message_id, user_name):
    clean_text = user_text.strip()
    session = SESSIONS.get(chat_id, {"state": "IDLE"})

    # Check for cancel or reset
    if clean_text.lower() in ["/batal", "batal", "reset", "/start"]:
        SESSIONS[chat_id] = {"state": "IDLE"}
        send_telegram_message(chat_id, "Siap! Sesi di-reset. Mau bahas topik apa nih untuk Threads @studyp4l?", message_id)
        return

    # STATE 1: AWAITING_CONFIRMATION (User wants to publish)
    if session.get("state") == "AWAITING_CONFIRMATION":
        if any(w in clean_text.lower() for w in ["gass", "publish", "posting", "oke", "ya", "kirim", "lanjut"]):
            send_telegram_message(chat_id, "🚀 Siap, sedang mempublikasikan draft ke Threads @studyp4l...", message_id)
            draft = session.get("draft", "")
            topic = session.get("topic", "Tech Insight")
            pillar = session.get("pillar", "Dev Tips")

            success, permalink = publish_to_threads(draft)
            if success:
                # Sync ke GitHub
                save_history(topic, pillar, draft, permalink)
                msg = (
                    f"🎉 BERHASIL DIPOSTING KE THREADS!\n\n"
                    f"📌 Live Post:\n{permalink}\n\n"
                    f"✅ Histori telah dicatat secara permanen ke GitHub repository ({GITHUB_REPO})."
                )
                send_telegram_message(chat_id, msg, message_id)
                SESSIONS[chat_id] = {"state": "IDLE"}
            else:
                send_telegram_message(chat_id, "❌ Maaf, gagal mempublikasikan ke Threads. Silakan coba lagi atau ketik 'batal'.", message_id)
            return
        elif any(w in clean_text.lower() for w in ["revisi", "ubah", "ganti", "kurang"]):
            # User wants to change
            session["state"] = "IDLE"
            send_telegram_message(chat_id, "Oke, bagian mana yang mau direvisi atau mau ganti topik?", message_id)
            return

    # STATE 2: AWAITING_ANGLE (User chose an angle from brainstorming)
    if session.get("state") == "AWAITING_ANGLE":
        chosen_angle = clean_text
        topic = session.get("topic", "")

        # Generate Draft with Content Engine & Brand Voice
        system_prompt = (
            "Kamu adalah content creator profesional untuk akun Threads @studyp4l (audiens: mahasiswa IT, junior developer, programmer muda Indonesia).\n"
            "Terapkan aturan ketat:\n"
            "1. Tone: Santai, cerdas, relatable, gaya anak IT Indonesia ('gua/lu', 'kodingan', 'error', 'deploy').\n"
            "2. FILTER ANTI-KLISE AI: DILARANG KERAS menggunakan frasa: 'Di era digital yang serba cepat', 'Game-changer', 'Revolusioner', 'Mari kita telaah', 'Secara keseluruhan'.\n"
            "3. LIMIT: Maksimal 450 karakter (harus di bawah 500).\n"
            "4. Format Plain Text (Threads tidak support bold markdown).\n"
            "5. Struktur: Hook kuat + 1 insight konkret + ajakan diskusi santai di akhir.\n"
            "Berikan teks caption-nya saja secara langsung."
        )
        user_prompt = f"Topik bahasan: {topic}\nPilihan sudut pandang / angle yang diminta: {chosen_angle}\n\nBuatkan 1 draft caption Threads terbaik!"

        send_telegram_message(chat_id, "⏳ Sedang meracik draft konten dengan gaya @studyp4l...", message_id)
        draft = call_gemini(system_prompt, user_prompt)

        if not draft:
            send_telegram_message(chat_id, "Maaf ada kendala saat menyusun draft, coba ulangi ya.", message_id)
            return

        # Verification checks
        char_count = len(draft)
        session["draft"] = draft
        session["state"] = "AWAITING_CONFIRMATION"
        session["pillar"] = "Dev Tips"
        SESSIONS[chat_id] = session

        reply = (
            f"📋 Preview Draft Postingan Threads (@studyp4l):\n"
            f"──────────────────────────────\n"
            f"{draft}\n"
            f"──────────────────────────────\n"
            f"📊 Karakter: {char_count} / 500 (Aman ✅)\n"
            f"🎯 Target: Meta Threads (@studyp4l)\n\n"
            f"Ketik \"Gass posting\", \"Publish\", atau \"Oke\" jika setuju untuk langsung diterbitkan!"
        )
        send_telegram_message(chat_id, reply, message_id)
        return

    # STATE 3: IDLE -> Brainstorming New Topic
    # Fetch recent history from GitHub
    recent_history, _ = fetch_history()
    recent_summary = ""
    if recent_history:
        recent_topics = [f"- {h.get('topic')}" for h in recent_history[-3:]]
        recent_summary = "Topik yang baru saja dibahas sebelumnya (HINDARI topik ini):\n" + "\n".join(recent_topics) + "\n\n"

    system_prompt = (
        "Kamu adalah content strategist untuk akun Meta Threads @studyp4l.\n"
        "Gunakan metodologi Brainstorming Superpowers:\n"
        "- Tawarkan 3 sudut pandang (angles) berbeda yang kontras untuk topik yang diminta:\n"
        "  1. 😅 Angle Relatable (Curhat/Meme struggle koding)\n"
        "  2. 🛠️ Angle Pro-Tip (Shortcut/Trik praktis 1 menit)\n"
        "  3. 🔥 Angle Hot Take / Diskusi (Opini kritis yang memantik obrolan)\n"
        "- Akhiri dengan SATU pertanyaan langsung: meminta user memilih nomor angle yang disukai.\n"
        "- Bahasa santai anak tech Indonesia, padat, dan menarik."
    )
    user_prompt = f"{recent_summary}User ingin membahas: {clean_text}\n\nBerikan 3 pilihan angle brainstorming!"

    send_telegram_message(chat_id, "🔍 Memeriksa histori GitHub & merancang 3 sudut pandang...", message_id)
    angles_response = call_gemini(system_prompt, user_prompt)

    if not angles_response:
        send_telegram_message(chat_id, "Gagal merancang ide, coba topik lain ya.", message_id)
        return

    session["state"] = "AWAITING_ANGLE"
    session["topic"] = clean_text
    SESSIONS[chat_id] = session

    send_telegram_message(chat_id, angles_response, message_id)

# =============================================================================
# TELEGRAM POLLING WORKER
# =============================================================================
def telegram_worker():
    log.info("Telegram background polling worker started.")
    offset = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates?offset={offset}&timeout=25"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                for update in data.get("result", []):
                    offset = update.get("update_id", 0) + 1
                    msg = update.get("message") or update.get("channel_post")
                    if not msg:
                        continue
                    text = msg.get("text", "")
                    if not text:
                        continue
                    chat_id = msg.get("chat", {}).get("id")
                    msg_id = msg.get("message_id")
                    user_name = msg.get("from", {}).get("username", "user")

                    # Abaikan pesan dari bot sendiri
                    if msg.get("from", {}).get("is_bot", False):
                        continue

                    log.info(f"Received Telegram msg from {user_name} ({chat_id}): '{text[:50]}'")
                    handle_user_message(chat_id, text, msg_id, user_name)
        except Exception as e:
            log.warning(f"Telegram polling retry: {e}")
            time.sleep(3)

# =============================================================================
# HTTP HEALTH & STATUS SERVER (FOR HUGGING FACE & PINGER)
# =============================================================================
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        uptime = str(datetime.now() - START_TIME).split(".")[0]
        history, _ = fetch_history()
        history_items_html = ""
        for h in reversed(history[-5:]):
            ts = h.get("timestamp", "-")[:16].replace("T", " ")
            history_items_html += f"<li><strong>[{h.get('pillar')}]</strong> {h.get('topic')} <small>({ts})</small><br><em>{h.get('caption')[:120]}...</em></li>"

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>StudyP4L Threads Bot - Online</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #f8fafc; padding: 2rem; }}
                .card {{ max-width: 650px; margin: 0 auto; background: #1e293b; border-radius: 12px; padding: 2rem; border: 1px solid #334155; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }}
                .badge {{ display: inline-block; padding: 0.35rem 0.75rem; border-radius: 9999px; background: #10b981; color: #022c22; font-weight: bold; font-size: 0.85rem; }}
                h1 {{ font-size: 1.5rem; margin-top: 0.5rem; }}
                ul {{ padding-left: 1.2rem; }}
                li {{ margin-bottom: 1rem; color: #cbd5e1; }}
                .meta {{ color: #94a3b8; font-size: 0.9rem; }}
                hr {{ border: 0; border-top: 1px solid #334155; margin: 1.5rem 0; }}
            </style>
        </head>
        <body>
            <div class="card">
                <span class="badge">● ONLINE 24/7</span>
                <h1>StudyP4L Meta Threads Bot</h1>
                <p class="meta">Uptime: <strong>{uptime}</strong> | Model: <strong>{GEMINI_MODEL}</strong></p>
                <hr>
                <p><strong>Target Akun:</strong> <a style="color: #38bdf8;" href="https://www.threads.net/@studyp4l" target="_blank">@studyp4l</a></p>
                <p><strong>Penyimpanan Histori:</strong> <a style="color: #38bdf8;" href="https://github.com/{GITHUB_REPO}" target="_blank">GitHub ({GITHUB_REPO})</a></p>
                <hr>
                <h3>📜 5 Postingan Terakhir:</h3>
                <ul>{history_items_html if history_items_html else "<li>Belum ada histori tercatat</li>"}</ul>
                <hr>
                <p class="meta" style="text-align: center;">Keep-Alive Endpoint Ready for UptimeRobot / Cron-Job</p>
            </div>
        </body>
        </html>
        """
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def log_message(self, format, *args):
        # Mute normal HTTP access logs to keep terminal clean
        return

def run_web_server():
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    log.info(f"Health & Status Web Server running on port {PORT}")
    server.serve_forever()

# =============================================================================
# MAIN ENTRYPOINT
# =============================================================================
if __name__ == "__main__":
    log.info("Starting StudyP4L Cloud Bot...")
    # 1. Start Telegram Polling in Background Thread
    tg_thread = threading.Thread(target=telegram_worker, daemon=True)
    tg_thread.start()

    # 2. Start Web Server in Main Thread
    run_web_server()
