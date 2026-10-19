"""
bot_threads.py
--------------
Generate konten dengan Gemini AI lalu posting sebagai Threads baru.

Cara pakai:
    python bot_threads.py

Environment variables yang dibutuhkan:
    GEMINI_API_KEY
    THREADS_ACCESS_TOKEN
"""

from threads_client import generate_with_retry, create_and_publish, setup_logger

log = setup_logger("bot_threads", "bot_threads.log")


def generate_content_with_gemini():
    """Meminta Gemini AI membuat postingan menarik untuk Threads."""
    prompt = (
        "Buatkan 1 postingan menarik dan santai untuk Threads tentang tips produktivitas "
        "atau teknologi/pemrograman untuk mahasiswa. "
        "Ketentuan:\n"
        "- Maksimal 250 karakter.\n"
        "- Gunakan nada bicara yang ramah, santai, dan tidak kaku.\n"
        "- Jangan gunakan hashtag berlebihan.\n"
        "- Berikan LANGSUNG teks postingannya tanpa tanda kutip atau penjelasan tambahan."
    )

    log.info("🤖 Gemini sedang membuat konten...")
    text_result = generate_with_retry(prompt)

    if not text_result:
        log.error("❌ Gemini gagal menghasilkan konten setelah beberapa percobaan.")
        return None

    log.info(f"📝 Hasil Konten AI:\n---\n{text_result}\n---")
    return text_result


def main():
    konten_ai = generate_content_with_gemini()
    if not konten_ai:
        return

    published_id = create_and_publish(konten_ai)
    if published_id:
        log.info(f"🎉 Postingan AI berhasil terbit di Threads! (ID: {published_id})")
    else:
        log.error("❌ Gagal menerbitkan ke Threads.")


if __name__ == "__main__":
    main()