import os
import sys
import json
import base64
import urllib.request
import urllib.error
from datetime import datetime

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO = os.getenv("GITHUB_REPO", "heiopal/projek-bot-threads")
FILE_PATH = "content_history.json"
LOCAL_FALLBACK_FILE = os.path.join(os.path.dirname(__file__), "content_history.json")

def get_headers():
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "User-Agent": "ThreadsBot-Cloud",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json"
    }

def fetch_history_from_github():
    """Mengambil history dari GitHub repo, jika gagal fallback ke file lokal."""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{FILE_PATH}"
    req = urllib.request.Request(url, headers=get_headers())
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content_b64 = data.get("content", "")
            sha = data.get("sha", "")
            raw_json = base64.b64decode(content_b64).decode("utf-8")
            history = json.loads(raw_json)
            # Sync ke lokal jika ada
            try:
                with open(LOCAL_FALLBACK_FILE, "w", encoding="utf-8") as f:
                    f.write(raw_json)
            except Exception:
                pass
            return history, sha
    except urllib.error.HTTPError as e:
        if e.code == 404:
            # File belum ada di GitHub, baca lokal jika ada
            if os.path.exists(LOCAL_FALLBACK_FILE):
                try:
                    with open(LOCAL_FALLBACK_FILE, "r", encoding="utf-8") as f:
                        return json.load(f), None
                except Exception:
                    pass
            return [], None
        print(f"[Warning] Gagal mengambil history dari GitHub (HTTP {e.code}), fallback lokal", file=sys.stderr)
    except Exception as e:
        print(f"[Warning] Error koneksi GitHub: {e}, fallback lokal", file=sys.stderr)

    # Fallback lokal
    if os.path.exists(LOCAL_FALLBACK_FILE):
        try:
            with open(LOCAL_FALLBACK_FILE, "r", encoding="utf-8") as f:
                return json.load(f), None
        except Exception:
            pass
    return [], None

def push_history_to_github(history, sha=None):
    """Menyimpan list history baru ke GitHub repo via GitHub REST API."""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{FILE_PATH}"
    content_str = json.dumps(history, indent=2, ensure_ascii=False)
    content_b64 = base64.b64encode(content_str.encode("utf-8")).decode("utf-8")

    payload = {
        "message": f"chore: update content_history.json [skip ci] ({datetime.now().strftime('%Y-%m-%d %H:%M')})",
        "content": content_b64
    }
    if sha:
        payload["sha"] = sha

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=get_headers(), method="PUT")

    try:
        with urllib.request.urlopen(req) as resp:
            res_data = json.loads(resp.read().decode("utf-8"))
            new_sha = res_data.get("content", {}).get("sha", "")
            # Update lokal
            try:
                with open(LOCAL_FALLBACK_FILE, "w", encoding="utf-8") as f:
                    f.write(content_str)
            except Exception:
                pass
            return True, new_sha
    except Exception as e:
        print(f"[Error] Gagal push history ke GitHub: {e}", file=sys.stderr)
        return False, None

def add_post_to_history(topic, pillar, caption, permalink=""):
    """Menambahkan entry baru ke history dan menyimpannya secara permanen ke GitHub."""
    history, sha = fetch_history_from_github()
    new_entry = {
        "timestamp": datetime.now().isoformat(),
        "topic": topic,
        "pillar": pillar,
        "caption": caption,
        "permalink": permalink
    }
    history.append(new_entry)
    success, new_sha = push_history_to_github(history, sha)
    if success:
        print(f"✅ Sukses menyimpan histori ke GitHub ({GITHUB_REPO})!")
    else:
        print("⚠️ Gagal push ke GitHub, data disimpan di file lokal sementara.")
    return success

def list_recent_posts(limit=5):
    """Menampilkan postingan terakhir dari GitHub."""
    history, _ = fetch_history_from_github()
    if not history:
        print("Belum ada histori konten yang tercatat di GitHub.")
        return []
    print(f"=== {len(history)} POSTINGAN TERAKHIR DARI GITHUB ({GITHUB_REPO}) ===")
    for idx, item in enumerate(reversed(history[-limit:]), 1):
        ts = item.get("timestamp", "-")[:16].replace("T", " ")
        print(f"{idx}. [{item.get('pillar', 'Umum')}] {item.get('topic', 'Tanpa Judul')} ({ts})")
        print(f"   Caption: {item.get('caption', '')[:80]}...")
        if item.get("permalink"):
            print(f"   Link: {item.get('permalink')}")
        print()
    return history[-limit:]

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="GitHub Persistent Storage for Threads Bot")
    parser.add_argument("--list", action="store_true", help="List recent history from GitHub")
    parser.add_argument("--limit", type=int, default=5, help="Limit list count")
    parser.add_argument("--sync-initial", action="store_true", help="Sync existing local history to GitHub")
    args = parser.parse_args()

    if args.sync_initial:
        history, sha = fetch_history_from_github()
        if not history and os.path.exists(LOCAL_FALLBACK_FILE):
            with open(LOCAL_FALLBACK_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
        success, _ = push_history_to_github(history, sha)
        if success:
            print(f"Initial sync berhasil ke https://github.com/{GITHUB_REPO}/blob/main/{FILE_PATH}")
    elif args.list:
        list_recent_posts(args.limit)
    else:
        list_recent_posts(5)
