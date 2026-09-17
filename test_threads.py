import os
import requests
from dotenv import load_dotenv

# 1. Muat variabel dari file .env
load_dotenv()

# 2. Ambil Access Token dari file .env
ACCESS_TOKEN = os.getenv("THREADS_ACCESS_TOKEN")

def post_to_threads(text_content):
    # Tahap 1: Buat Container Postingan
    create_url = "https://graph.threads.net/v1.0/me/threads"
    payload = {
        "media_type": "TEXT",
        "text": text_content,
        "access_token": ACCESS_TOKEN
    }
    
    response = requests.post(create_url, data=payload)
    res_data = response.json()
    
    if "id" not in res_data:
        print("❌ Gagal membuat container:", res_data)
        return

    creation_id = res_data["id"]
    print(f"✅ Container berhasil dibuat (ID: {creation_id})")

    # Tahap 2: Menerbitkan Postingan
    publish_url = "https://graph.threads.net/v1.0/me/threads_publish"
    pub_payload = {
        "creation_id": creation_id,
        "access_token": ACCESS_TOKEN
    }
    
    pub_response = requests.post(publish_url, data=pub_payload)
    pub_data = pub_response.json()

    if "id" in pub_data:
        print(f"🎉 Postingan berhasil terbit! Post ID: {pub_data['id']}")
    else:
        print("❌ Gagal menerbitkan postingan:", pub_data)

if __name__ == "__main__":
    pesan_tes = "Halo Threads! Ini postingan uji coba otomatis via Python script 🚀"
    post_to_threads(pesan_tes)