import os
import sys
import time
import json
import base64
import logging
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime
from flask import Flask, request, jsonify

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("VercelThreadsBot")

app = Flask(__name__)

# =============================================================================
# ENVIRONMENT & CONFIGURATION
# =============================================================================
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", os.getenv("GOOGLE_API_KEY", ""))
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
THREADS_ACCESS_TOKEN = os.getenv("THREADS_ACCESS_TOKEN", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO = os.getenv("GITHUB_REPO", "heiopal/projek-bot-threads")
GEMINI_MODEL = "gemini-3.6-flash"
DEEPSEEK_MODEL = "deepseek-chat"

START_TIME = datetime.now()

# In-memory session cache (warm instances)
MEMORY_SESSIONS = {}

# =============================================================================
# GITHUB STORAGE CLIENT
# =============================================================================
GITHUB_FILE_PATH = "content_history.json"
GITHUB_SESSION_PATH = "active_session.json"

def get_github_headers():
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "User-Agent": "ThreadsBot-Vercel",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json"
    }

def fetch_history():
    if not GITHUB_TOKEN or not GITHUB_REPO:
        return [], None
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
    if not GITHUB_TOKEN or not GITHUB_REPO:
        log.warning("No GitHub token or repo set, skipping history save.")
        return False
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

def get_session(chat_id):
    chat_key = str(chat_id)
    if chat_key in MEMORY_SESSIONS:
        return MEMORY_SESSIONS[chat_key]
    # Check GitHub fallback
    if GITHUB_TOKEN and GITHUB_REPO:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_SESSION_PATH}"
        req = urllib.request.Request(url, headers=get_github_headers())
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                raw = base64.b64decode(data.get("content", "")).decode("utf-8")
                sessions = json.loads(raw)
                return sessions.get(chat_key, {"state": "IDLE"})
        except Exception:
            pass
    return {"state": "IDLE"}

def set_session(chat_id, session_data):
    chat_key = str(chat_id)
    MEMORY_SESSIONS[chat_key] = session_data
    # Optionally save to GitHub in background / quick sync
    if GITHUB_TOKEN and GITHUB_REPO:
        try:
            url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_SESSION_PATH}"
            req = urllib.request.Request(url, headers=get_github_headers())
            sha = None
            sessions = {}
            try:
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    sha = data.get("sha")
                    sessions = json.loads(base64.b64decode(data.get("content", "")).decode("utf-8"))
            except Exception:
                sessions = {}
            sessions[chat_key] = session_data
            content_str = json.dumps(sessions, ensure_ascii=False)
            content_b64 = base64.b64encode(content_str.encode("utf-8")).decode("utf-8")
            payload = {
                "message": f"chore: update active session for {chat_key} [skip ci]",
                "content": content_b64
            }
            if sha:
                payload["sha"] = sha
            put_req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=get_github_headers(), method="PUT")
            urllib.request.urlopen(put_req, timeout=5)
        except Exception as e:
            log.warning(f"Session sync to GitHub: {e}")

# =============================================================================
# AI GENERATION (DEEPSEEK PRIMARY, GEMINI FALLBACK)
# =============================================================================
def call_deepseek(system_instruction, user_prompt):
    if not DEEPSEEK_API_KEY:
        return None
    url = "https://api.deepseek.com/chat/completions"
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 1000
    }
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            res_json = json.loads(resp.read().decode("utf-8"))
            choices = res_json.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "").strip()
    except Exception as e:
        log.error(f"DeepSeek call error: {e}")
    return None

def call_gemini(system_instruction, user_prompt):
    if not GEMINI_API_KEY:
        return None
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
        with urllib.request.urlopen(req, timeout=25) as resp:
            res_json = json.loads(resp.read().decode("utf-8"))
            candidates = res_json.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text", "").strip()
    except Exception as e:
        log.error(f"Gemini call error: {e}")
    return None

def is_deepseek_peak_hour():
    """
    Check if current UTC time falls into DeepSeek's Peak Hours (Mon-Fri):
    - Sesi 1: 01:00 - 04:00 UTC (08:00 - 11:00 WIB)
    - Sesi 2: 06:00 - 10:00 UTC (13:00 - 17:00 WIB)
    Returns: (is_peak: bool, status_desc: str)
    """
    now_utc = datetime.utcnow()
    # 5 = Saturday, 6 = Sunday (Weekend full off-peak)
    if now_utc.weekday() >= 5:
        return False, "Weekend (Off-Peak Diskon 50% • DeepSeek Prioritas)"
    
    hour = now_utc.hour + now_utc.minute / 60.0
    # Sesi 1: 01:00 - 04:00 UTC
    if 1.0 <= hour < 4.0:
        return True, "Peak Hour Pagi (08:00-11:00 WIB • Proteksi Kuota via Gemini Free)"
    # Sesi 2: 06:00 - 10:00 UTC
    if 6.0 <= hour < 10.0:
        return True, "Peak Hour Sore (13:00-17:00 WIB • Proteksi Kuota via Gemini Free)"
    return False, "Off-Peak (Diskon 50% • DeepSeek Prioritas)"

def call_ai(system_instruction, user_prompt):
    """
    Smart Cost-Aware Model Routing:
    - Peak Hour (Mon-Fri 08:00-11:00 & 13:00-17:00 WIB):
      Routes to FREE Gemini 3.6 Flash (protects DeepSeek balance from 2x rate).
      Fallback: DeepSeek-V3 if Gemini fails.
    - Off-Peak (Malam, Pagi hari, Istirahat Siang, Weekend):
      Routes to DeepSeek-V3 (50% cheaper token rate).
      Fallback: Gemini 3.6 Flash if DeepSeek fails.
    """
    is_peak, peak_status = is_deepseek_peak_hour()

    if is_peak:
        log.info(f"⏰ Peak Hour ({peak_status}): Prioritizing FREE Gemini 3.6 Flash...")
        res = call_gemini(system_instruction, user_prompt)
        if res:
            return res
        log.warning("Gemini failed during peak, falling back to DeepSeek...")
        return call_deepseek(system_instruction, user_prompt)
    else:
        log.info(f"🌙 Off-Peak Hour ({peak_status}): Prioritizing DeepSeek-V3 (50% cheaper)...")
        if DEEPSEEK_API_KEY:
            res = call_deepseek(system_instruction, user_prompt)
            if res:
                return res
            log.warning("DeepSeek failed during off-peak, falling back to Gemini Flash...")
        return call_gemini(system_instruction, user_prompt)

# =============================================================================
# THREADS API CLIENT
# =============================================================================
def publish_to_threads(text):
    """Publish text directly to Meta Threads Graph API."""
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

    time.sleep(3)

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
# TELEGRAM API CLIENT & HELPERS
# =============================================================================
def send_telegram_message(chat_id, text, reply_to_id=None, reply_markup=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text
    }
    if reply_to_id:
        payload["reply_to_message_id"] = reply_to_id
    if reply_markup:
        payload["reply_markup"] = reply_markup
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15):
            pass
    except Exception as e:
        log.error(f"Error sending telegram message: {e}")

def answer_callback_query(callback_query_id, text=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery"
    payload = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10):
            pass
    except Exception as e:
        log.error(f"Error answering callback query: {e}")

def edit_telegram_message(chat_id, message_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/editMessageText"
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15):
            pass
    except Exception as e:
        log.error(f"Error editing telegram message: {e}")

# =============================================================================
# BOT BUSINESS LOGIC
# =============================================================================
def generate_draft(chat_id, topic, chosen_angle, message_id=None):
    send_telegram_message(chat_id, "⏳ Sedang meracik draft konten dengan gaya @studyp4l...", message_id)

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

    draft = call_ai(system_prompt, user_prompt)
    if not draft:
        send_telegram_message(chat_id, "Maaf ada kendala saat menyusun draft, coba ulangi ya.", message_id)
        return

    char_count = len(draft)
    session_data = {
        "state": "AWAITING_CONFIRMATION",
        "topic": topic,
        "pillar": "Dev Tips",
        "draft": draft
    }
    set_session(chat_id, session_data)

    preview_text = (
        f"📋 Preview Draft Postingan Threads (@studyp4l):\n"
        f"──────────────────────────────\n"
        f"{draft}\n"
        f"──────────────────────────────\n"
        f"📊 Karakter: {char_count} / 500 (Aman ✅)\n"
        f"🎯 Target: Meta Threads (@studyp4l)\n\n"
        f"Pilih tindakan di bawah atau ketik \"Gass\" untuk langsung menerbitkan:"
    )

    markup = {
        "inline_keyboard": [
            [
                {"text": "🚀 Gass Publish ke Threads", "callback_data": "action:publish"},
                {"text": "❌ Batal", "callback_data": "action:cancel"}
            ]
        ]
    }
    send_telegram_message(chat_id, preview_text, message_id, reply_markup=markup)

def execute_publish(chat_id, draft_text, topic, message_id=None):
    send_telegram_message(chat_id, "🚀 Siap, sedang mempublikasikan draft ke Threads @studyp4l...", message_id)
    success, permalink = publish_to_threads(draft_text)
    if success:
        save_history(topic or "Tech Insight", "Dev Tips", draft_text, permalink)
        set_session(chat_id, {"state": "IDLE"})
        success_msg = (
            f"🎉 BERHASIL DIPOSTING KE THREADS!\n\n"
            f"📌 Live Post:\n{permalink}\n\n"
            f"✅ Histori telah dicatat secara permanen ke GitHub repository ({GITHUB_REPO})."
        )
        send_telegram_message(chat_id, success_msg, message_id)
    else:
        send_telegram_message(chat_id, "❌ Maaf, gagal mempublikasikan ke Threads. Silakan coba lagi atau ketik 'batal'.", message_id)

def handle_user_message(chat_id, user_text, message_id, user_name, reply_to_text=None):
    clean_text = user_text.strip()
    session = get_session(chat_id)

    # Cancel / Reset command
    if clean_text.lower() in ["/batal", "batal", "reset", "/start"]:
        set_session(chat_id, {"state": "IDLE"})
        send_telegram_message(chat_id, "Siap! Sesi di-reset. Mau bahas topik apa nih untuk Threads @studyp4l?", message_id)
        return

    # Check if user is replying to a draft preview or confirming publication
    if session.get("state") == "AWAITING_CONFIRMATION" or any(w in clean_text.lower() for w in ["gass", "publish", "posting", "oke", "lanjut"]):
        draft = session.get("draft")
        topic = session.get("topic", "Tech Insight")
        # Self-contained extraction from reply_to_text if available
        if reply_to_text and "──────────────────────────────" in reply_to_text:
            parts = reply_to_text.split("──────────────────────────────")
            if len(parts) >= 3:
                draft = parts[1].strip()

        if draft:
            execute_publish(chat_id, draft, topic, message_id)
            return

    # Check if user is selecting an angle (1, 2, 3 or angle description)
    if session.get("state") == "AWAITING_ANGLE" or (reply_to_text and "3 Pilihan Sudut Pandang" in reply_to_text):
        topic = session.get("topic", "")
        if not topic and reply_to_text and 'untuk: "' in reply_to_text:
            try:
                topic = reply_to_text.split('untuk: "')[1].split('"')[0]
            except Exception:
                topic = "Tech Topic"
        generate_draft(chat_id, topic, clean_text, message_id)
        return

    # Default: IDLE -> Brainstorming New Topic
    # Clean topic trigger from prefix like 'hermes,' or 'bot,'
    topic_query = clean_text
    lower_t = clean_text.lower()
    for prefix in ["hermes,", "hermes", "bot,", "bot", "/topik", "ide:"]:
        if lower_t.startswith(prefix):
            topic_query = clean_text[len(prefix):].strip(" :,-")
            break

    if not topic_query:
        topic_query = clean_text

    send_telegram_message(chat_id, f"🔍 Memeriksa histori GitHub & merancang 3 sudut pandang untuk: \"{topic_query}\"...", message_id)

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
        "- Bahasa santai anak tech Indonesia, padat, dan menarik."
    )
    user_prompt = f"{recent_summary}User ingin membahas: {topic_query}\n\nBerikan 3 pilihan angle brainstorming!"

    angles_response = call_ai(system_prompt, user_prompt)
    if not angles_response:
        send_telegram_message(chat_id, "Gagal merancang ide, coba topik lain ya.", message_id)
        return

    session_data = {
        "state": "AWAITING_ANGLE",
        "topic": topic_query,
        "angles_text": angles_response
    }
    set_session(chat_id, session_data)

    markup = {
        "inline_keyboard": [
            [
                {"text": "😅 1. Relatable", "callback_data": "angle:1"},
                {"text": "🛠️ 2. Pro-Tip", "callback_data": "angle:2"},
                {"text": "🔥 3. Hot Take", "callback_data": "angle:3"}
            ]
        ]
    }
    msg_text = (
        f"💡 3 Pilihan Sudut Pandang (Angles) untuk: \"{topic_query}\"\n\n"
        f"{angles_response}\n\n"
        f"👇 Klik tombol pilihanmu di bawah atau balas chat dengan nomor (1 / 2 / 3):"
    )
    send_telegram_message(chat_id, msg_text, message_id, reply_markup=markup)

def handle_callback_query(cq):
    cq_id = cq.get("id")
    data = cq.get("data", "")
    message = cq.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    msg_id = message.get("message_id")
    msg_text = message.get("text", "")

    answer_callback_query(cq_id)

    if data.startswith("angle:"):
        choice = data.split(":")[1]
        session = get_session(chat_id)
        topic = session.get("topic", "")
        if not topic and 'untuk: "' in msg_text:
            try:
                topic = msg_text.split('untuk: "')[1].split('"')[0]
            except Exception:
                topic = "Tech Topic"

        angle_map = {
            "1": "Angle 1 (Relatable / Curhat koding)",
            "2": "Angle 2 (Pro-Tip / Shortcut praktis)",
            "3": "Angle 3 (Hot Take / Opini kritis diskusi)"
        }
        chosen_angle = angle_map.get(choice, f"Angle {choice}")
        generate_draft(chat_id, topic, chosen_angle, msg_id)

    elif data == "action:publish":
        # Extract draft from preview text
        draft = ""
        if "──────────────────────────────" in msg_text:
            parts = msg_text.split("──────────────────────────────")
            if len(parts) >= 3:
                draft = parts[1].strip()

        session = get_session(chat_id)
        if not draft:
            draft = session.get("draft", "")
        topic = session.get("topic", "Tech Insight")

        if draft:
            edit_telegram_message(chat_id, msg_id, f"🚀 Sedang mempublikasikan ke Threads @studyp4l...\n\n{draft}")
            execute_publish(chat_id, draft, topic, msg_id)
        else:
            send_telegram_message(chat_id, "Draft tidak ditemukan, silakan ketik topik baru.", msg_id)

    elif data == "action:cancel":
        set_session(chat_id, {"state": "IDLE"})
        edit_telegram_message(chat_id, msg_id, "❌ Pembuatan konten dibatalkan. Ketik topik baru kapan saja!")

# =============================================================================
# FLASK WEBHOOK ROUTES & HEALTH DASHBOARD
# =============================================================================
def render_dashboard():
    uptime = str(datetime.now() - START_TIME).split(".")[0]
    history, _ = fetch_history()
    history_items_html = ""
    for h in reversed(history[-5:]):
        ts = h.get("timestamp", "-")[:16].replace("T", " ")
        history_items_html += f"<li><strong>[{h.get('pillar')}]</strong> {h.get('topic')} <small>({ts})</small><br><em>{h.get('caption')[:120]}...</em></li>"

    host_url = request.host_url.rstrip("/")
    webhook_url = f"{host_url}/api/webhook"

    is_peak, peak_desc = is_deepseek_peak_hour()
    active_engine = "Gemini 3.6 Flash (Peak Protection)" if is_peak else "DeepSeek-V3 (Off-Peak 50% Diskon)"

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>StudyP4L Threads Bot - Vercel Serverless</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #090d16; color: #f8fafc; padding: 2rem; margin: 0; }}
            .card {{ max-width: 650px; margin: 0 auto; background: #131b2e; border-radius: 14px; padding: 2rem; border: 1px solid #1e293b; box-shadow: 0 15px 35px rgba(0,0,0,0.6); }}
            .badge {{ display: inline-block; padding: 0.35rem 0.75rem; border-radius: 9999px; background: #10b981; color: #022c22; font-weight: bold; font-size: 0.85rem; }}
            h1 {{ font-size: 1.5rem; margin-top: 0.75rem; }}
            ul {{ padding-left: 1.2rem; }}
            li {{ margin-bottom: 1rem; color: #cbd5e1; }}
            .meta {{ color: #94a3b8; font-size: 0.9rem; }}
            hr {{ border: 0; border-top: 1px solid #1e293b; margin: 1.5rem 0; }}
            .btn {{ display: inline-block; padding: 0.6rem 1.2rem; background: #3b82f6; color: #fff; text-decoration: none; border-radius: 8px; font-weight: bold; font-size: 0.9rem; transition: background 0.2s; }}
            .btn:hover {{ background: #2563eb; }}
            code {{ background: #0b1120; padding: 0.2rem 0.5rem; border-radius: 4px; font-family: monospace; font-size: 0.85rem; color: #38bdf8; }}
        </style>
    </head>
    <body>
        <div class="card">
            <span class="badge">● VERCEL SERVERLESS ONLINE</span>
            <h1>StudyP4L Meta Threads Bot</h1>
            <p class="meta">Engine Aktif: <strong>{active_engine}</strong><br><small style="color:#94a3b8;">Jadwal: {peak_desc}</small></p>
            <hr>
            <p><strong>Target Akun:</strong> <a style="color: #38bdf8;" href="https://www.threads.net/@studyp4l" target="_blank">@studyp4l</a></p>
            <p><strong>Penyimpanan Histori:</strong> <a style="color: #38bdf8;" href="https://github.com/{GITHUB_REPO}" target="_blank">GitHub ({GITHUB_REPO})</a></p>
            <p><strong>Webhook Endpoint:</strong> <code>{webhook_url}</code></p>
            <p style="margin-top: 1rem;">
                <a class="btn" href="/set-webhook" target="_blank">⚡ Aktifkan / Sync Telegram Webhook</a>
            </p>
            <hr>
            <h3>📜 5 Postingan Terakhir:</h3>
            <ul>{history_items_html if history_items_html else "<li>Belum ada histori tercatat</li>"}</ul>
            <hr>
            <p class="meta" style="text-align: center;">Murni Serverless • Bebas Kartu Kredit • Tanpa Pinger</p>
        </div>
    </body>
    </html>
    """
    return html

def execute_set_webhook():
    host_url = request.host_url.rstrip("/")
    webhook_url = f"{host_url}/api/webhook"
    tg_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook?url={webhook_url}"
    try:
        with urllib.request.urlopen(tg_url, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return jsonify({
                "status": "success",
                "registered_webhook": webhook_url,
                "telegram_response": data
            })
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e),
            "target_webhook": webhook_url
        }), 500

def process_webhook():
    try:
        update = request.get_json(force=True, silent=True) or {}
        log.info(f"Incoming Telegram Webhook Update: {list(update.keys())}")

        if "callback_query" in update:
            handle_callback_query(update["callback_query"])
            return jsonify({"ok": True}), 200

        if "message" in update or "channel_post" in update:
            msg = update.get("message") or update.get("channel_post")
            # Ignore messages sent by bots
            if msg.get("from", {}).get("is_bot", False):
                return jsonify({"ok": True}), 200

            text = msg.get("text", "")
            if not text:
                return jsonify({"ok": True}), 200

            chat_id = msg.get("chat", {}).get("id")
            msg_id = msg.get("message_id")
            user_name = msg.get("from", {}).get("username", "user")
            reply_to_text = msg.get("reply_to_message", {}).get("text")

            handle_user_message(chat_id, text, msg_id, user_name, reply_to_text)
            return jsonify({"ok": True}), 200

        return jsonify({"ok": True}), 200
    except Exception as e:
        log.error(f"Error handling webhook update: {e}", exc_info=True)
        return jsonify({"ok": False, "error": str(e)}), 200

# Universal handler for all paths and HTTP methods
@app.route("/", defaults={"path": ""}, methods=["GET", "POST", "HEAD", "OPTIONS"])
@app.route("/<path:path>", methods=["GET", "POST", "HEAD", "OPTIONS"])
def master_router(path=""):
    # If POST -> Process Telegram update
    if request.method == "POST":
        return process_webhook()

    # If GET with 'set-webhook'
    req_path = request.path.lower()
    if "set-webhook" in req_path or "set-webhook" in path.lower():
        return execute_set_webhook()

    # Default GET -> Render dashboard
    return render_dashboard()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
