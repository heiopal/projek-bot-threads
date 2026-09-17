import os

import requests
from google import genai

# 1. Kredensial API
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
THREADS_ACCESS_TOKEN = os.environ["THREADS_ACCESS_TOKEN"]

# 2. Inisialisasi Client Gemini
client = genai.Client(api_key=GEMINI_API_KEY)

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
    
    print("Gemini sedang membuat konten...")
    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt
    )
    
    text_result = response.text.strip()
    print(f"📝 Hasil Konten AI:\n---\n{text_result}\n---")
    return text_result

def post_to_threads(text_content):
    """Mengirimkan teks konten ke Threads API."""
    # Tahap A: Buat Container
    create_url = "https://graph.threads.net/v1.0/me/threads"
    payload = {
        "media_type": "TEXT",
        "text": text_content,
        "access_token": THREADS_ACCESS_TOKEN
    }
    
    res = requests.post(create_url, data=payload).json()
    if "id" not in res:
        print("❌ Gagal membuat container Threads:", res)
        return

    creation_id = res["id"]

    # Tahap B: Publish
    publish_url = "https://graph.threads.net/v1.0/me/threads_publish"
    pub_payload = {
        "creation_id": creation_id,
        "access_token": THREADS_ACCESS_TOKEN
    }
    
    pub_res = requests.post(publish_url, data=pub_payload).json()
    if "id" in pub_res:
        print(f"🎉 Postingan AI berhasil terbit di Threads! (ID: {pub_res['id']})")
    else:
        print("❌ Gagal menerbitkan ke Threads:", pub_res)

if __name__ == "__main__":
    # 1. Generate konten otomatis dari Gemini
    konten_ai = generate_content_with_gemini()
    
    # 2. Kirim postingan ke Threads
    if konten_ai:
        post_to_threads(konten_ai)