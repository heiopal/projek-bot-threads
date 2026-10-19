"""
reply_bot.py
------------
Fitur: membaca balasan (reply) yang masuk ke postingan Threads milik kita,
lalu membalasnya secara otomatis menggunakan Gemini AI.

Cara pakai:
    python reply_bot.py

Environment variables yang dibutuhkan:
    GEMINI_API_KEY
    THREADS_ACCESS_TOKEN

State (daftar reply_id yang sudah dibalas & yang ditandai spam) disimpan di
replied_state.json supaya bot tidak memproses reply yang sama dua kali setiap
kali dijalankan.

Reply yang mengandung link short-URL/WhatsApp, atau kombinasi kata kunci
promosi jasa (jasa, joki, dampingan, dll), otomatis dilewati dan dicatat
di skipped_spam_ids -- bisa kamu tinjau ulang manual lewat replied_state.json.
"""

import os
import json
import time

from threads_client import (
    get_own_profile,
    get_own_recent_posts,
    get_replies,
    create_and_publish,
    generate_with_retry,
    setup_logger,
)

log = setup_logger("reply_bot", "reply_bot.log")

STATE_FILE = "replied_state.json"
MAX_POSTS_TO_CHECK = 5      # cek reply dari 5 postingan terbaru kita
REPLY_DELAY_SECONDS = 8     # jeda antar-balasan biar tidak terkesan spam

# Filter spam sederhana berbasis kata kunci & domain.
SPAM_DOMAINS = [
    "wa.link", "wa.me", "api.whatsapp.com", "bit.ly", "linktr.ee", "s.id", "tiny.cc",
]
SPAM_KEYWORDS = [
    "jasa", "joki", "dampingan", "olah data", "sempro", "revisi skripsi",
    "chat wa", "dm ya", "open jasa", "harga mulai", "promo", "diskon",
    "titip", "cod ", "orderan",
]
SPAM_KEYWORD_THRESHOLD = 2


# ---------------------------------------------------------------------------
# Helper: state (anti proses-dobel)
# ---------------------------------------------------------------------------
def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            log.warning("State file rusak, mulai dari kosong.")
    return {"replied_ids": [], "skipped_spam_ids": []}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Filter spam
# ---------------------------------------------------------------------------
def is_spam_reply(text):
    """Heuristik sederhana: link short-URL/WhatsApp = pasti spam,
    atau kombinasi >=2 kata kunci promosi jasa."""
    if not text:
        return False
    text_lower = text.lower()

    if any(domain in text_lower for domain in SPAM_DOMAINS):
        return True

    hits = sum(1 for kw in SPAM_KEYWORDS if kw in text_lower)
    if hits >= SPAM_KEYWORD_THRESHOLD:
        return True

    return False


# ---------------------------------------------------------------------------
# Gemini: generate balasan
# ---------------------------------------------------------------------------
def generate_ai_reply(original_post_text, reply_text, reply_username):
    prompt = (
        "Kamu adalah admin akun Threads yang sedang membalas komentar dengan nada "
        "ramah, santai, dan singkat (maks 300 karakter).\n\n"
        f"Postingan asli kita:\n\"{original_post_text}\"\n\n"
        f"Komentar dari @{reply_username}:\n\"{reply_text}\"\n\n"
        "Tulis SATU balasan yang relevan dan natural untuk komentar tersebut. "
        "Jangan gunakan tanda kutip, jangan gunakan hashtag, langsung teks balasannya saja."
    )
    return generate_with_retry(prompt)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    state = load_state()
    replied_ids = set(state.get("replied_ids", []))
    skipped_spam_ids = set(state.get("skipped_spam_ids", []))

    profile = get_own_profile()
    own_username = (profile.get("username") or "").lower()
    if own_username:
        log.info(f"Login sebagai @{own_username}")

    posts = get_own_recent_posts(limit=MAX_POSTS_TO_CHECK)
    if not posts:
        log.info("Tidak ada postingan ditemukan (atau gagal mengambil data).")
        return

    total_replied = 0
    total_spam_skipped = 0
    for post in posts:
        post_id = post.get("id")
        post_text = post.get("text", "")
        replies = get_replies(post_id)

        for reply in replies:
            reply_id = reply.get("id")
            username = reply.get("username", "seseorang")
            reply_text = reply.get("text", "")

            if reply_id in replied_ids or reply_id in skipped_spam_ids:
                continue
            if own_username and username.lower() == own_username:
                # jangan membalas komentar dari akun sendiri
                replied_ids.add(reply_id)
                continue
            if is_spam_reply(reply_text):
                log.info(f"🚫 Reply dari @{username} terdeteksi spam, dilewati: {reply_text[:80]}")
                skipped_spam_ids.add(reply_id)
                state["skipped_spam_ids"] = list(skipped_spam_ids)
                save_state(state)
                total_spam_skipped += 1
                continue

            log.info(f"Reply baru dari @{username} di post {post_id}: {reply_text}")
            try:
                ai_reply = generate_ai_reply(post_text, reply_text, username)
                if not ai_reply:
                    log.error(f"❌ Gemini tidak menghasilkan balasan untuk reply {reply_id}, dilewati (akan dicoba lagi run berikutnya).")
                    continue

                log.info(f"Draft balasan: {ai_reply}")

                published_id = create_and_publish(ai_reply, reply_to_id=reply_id)
                if published_id:
                    log.info(f"✅ Berhasil membalas (ID: {published_id})")
                    replied_ids.add(reply_id)
                    state["replied_ids"] = list(replied_ids)
                    save_state(state)
                    total_replied += 1
                    time.sleep(REPLY_DELAY_SECONDS)
                else:
                    log.error(f"❌ Gagal membalas reply {reply_id}, akan dicoba lagi run berikutnya.")
            except Exception as e:
                log.error(f"❌ Error tak terduga saat memproses reply {reply_id}: {e}")
                continue

    log.info(f"Selesai. Total balasan baru terkirim: {total_replied}, total spam dilewati: {total_spam_skipped}")


if __name__ == "__main__":
    main()