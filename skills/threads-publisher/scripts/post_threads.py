import argparse
import json
import os
import sys
import time
from pathlib import Path
import requests
from dotenv import load_dotenv

# Ensure UTF-8 output on Windows
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Candidate locations for .env
CANDIDATE_PATHS = [
    Path("C:/INTERNSHIP/projek akun bot/.env"),
    Path("C:/Users/Naufal/AppData/Local/hermes/.env"),
    Path.home() / ".hermes" / ".env",
    Path(".env"),
]

for p in CANDIDATE_PATHS:
    if p.exists():
        load_dotenv(p, override=False)

ACCESS_TOKEN = os.getenv("THREADS_ACCESS_TOKEN")
GRAPH_BASE = "https://graph.threads.net/v1.0"
THREADS_TEXT_LIMIT = 500


def publish_to_threads(text: str, image_url: str = None) -> dict:
    if not ACCESS_TOKEN:
        return {
            "success": False,
            "error": "THREADS_ACCESS_TOKEN tidak ditemukan di environment atau file .env",
        }

    clean_text = text.strip()
    if len(clean_text) > THREADS_TEXT_LIMIT:
        clean_text = clean_text[: THREADS_TEXT_LIMIT - 1].rstrip() + "…"

    # 1. Create media container
    create_url = f"{GRAPH_BASE}/me/threads"
    payload = {
        "text": clean_text,
        "access_token": ACCESS_TOKEN,
    }
    if image_url:
        payload["media_type"] = "IMAGE"
        payload["image_url"] = image_url
    else:
        payload["media_type"] = "TEXT"

    try:
        res = requests.post(create_url, data=payload, timeout=20)
        res_data = res.json()
    except Exception as e:
        return {"success": False, "error": f"Gagal menghubungi Threads API: {e}"}

    creation_id = res_data.get("id")
    if not creation_id:
        error_msg = res_data.get("error", {}).get("message", str(res_data))
        return {"success": False, "error": f"Gagal membuat container Threads: {error_msg}"}

    # 2. Wait until container is ready
    status_url = f"{GRAPH_BASE}/{creation_id}"
    params = {"fields": "status,error_message", "access_token": ACCESS_TOKEN}
    for _ in range(12):
        time.sleep(2)
        try:
            st = requests.get(status_url, params=params, timeout=10).json()
            status = st.get("status")
            if status == "FINISHED":
                break
            if status == "ERROR":
                err = st.get("error_message", "Unknown container error")
                return {"success": False, "error": f"Container error: {err}"}
        except Exception:
            pass

    # 3. Publish container
    publish_url = f"{GRAPH_BASE}/me/threads_publish"
    pub_payload = {"creation_id": creation_id, "access_token": ACCESS_TOKEN}
    try:
        pub_res = requests.post(publish_url, data=pub_payload, timeout=20).json()
    except Exception as e:
        return {"success": False, "error": f"Gagal publish ke Threads: {e}"}

    post_id = pub_res.get("id")
    if not post_id:
        error_msg = pub_res.get("error", {}).get("message", str(pub_res))
        return {"success": False, "error": f"Gagal menerbitkan postingan: {error_msg}"}

    # 4. Fetch permalink
    permalink = None
    try:
        detail = requests.get(
            f"{GRAPH_BASE}/{post_id}",
            params={"fields": "permalink", "access_token": ACCESS_TOKEN},
            timeout=10,
        ).json()
        permalink = detail.get("permalink")
    except Exception:
        pass

    return {
        "success": True,
        "post_id": post_id,
        "permalink": permalink,
        "text": clean_text,
    }


def main():
    parser = argparse.ArgumentParser(description="Publish content directly to Meta Threads")
    parser.add_argument("--text", required=True, help="Caption text for Threads post")
    parser.add_argument("--image-url", help="Optional public image URL")
    args = parser.parse_args()

    result = publish_to_threads(args.text, args.image_url)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["success"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
