import os
import sys
import json
import argparse
from datetime import datetime

# Import github_storage jika ada
try:
    sys.path.insert(0, r"c:\INTERNSHIP\projek akun bot")
    import github_storage
    HAS_GITHUB_STORAGE = True
except Exception:
    HAS_GITHUB_STORAGE = False

DEFAULT_HISTORY_FILE = r"c:\INTERNSHIP\projek akun bot\content_history.json"

def load_history():
    if HAS_GITHUB_STORAGE:
        history, _ = github_storage.fetch_history_from_github()
        if history:
            return history
    if not os.path.exists(DEFAULT_HISTORY_FILE):
        return []
    try:
        with open(DEFAULT_HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading history: {e}", file=sys.stderr)
        return []

def save_history(history):
    os.makedirs(os.path.dirname(DEFAULT_HISTORY_FILE), exist_ok=True)
    with open(DEFAULT_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

def list_history(limit=5):
    history = load_history()
    if not history:
        print("Belum ada histori konten yang tercatat.")
        return
    print(f"=== {len(history)} POSTINGAN TERAKHIR @studyp4l ===")
    for idx, item in enumerate(reversed(history[-limit:]), 1):
        ts = item.get("timestamp", "-")[:16].replace("T", " ")
        print(f"{idx}. [{item.get('pillar', 'Umum')}] {item.get('topic', 'Tanpa Judul')} ({ts})")
        print(f"   Caption: {item.get('caption', '')[:80]}...")
        if item.get("permalink"):
            print(f"   Link: {item.get('permalink')}")
        print()

def add_entry(topic, pillar, caption, permalink=""):
    if HAS_GITHUB_STORAGE:
        success = github_storage.add_post_to_history(topic, pillar, caption, permalink)
        if success:
            return
    history = load_history()
    new_entry = {
        "timestamp": datetime.now().isoformat(),
        "topic": topic,
        "pillar": pillar,
        "caption": caption,
        "permalink": permalink
    }
    history.append(new_entry)
    save_history(history)
    print(f"Berhasil mencatat topik: '{topic}' ke dalam content_history.json")

def check_topic(keyword):
    history = load_history()
    matches = [h for h in history if keyword.lower() in h.get("topic", "").lower() or keyword.lower() in h.get("caption", "").lower()]
    if matches:
        print(f"Ditemukan {len(matches)} postingan mirip:")
        for m in matches:
            print(f"- [{m.get('pillar')}] {m.get('topic')} ({m.get('timestamp')[:10]})")
    else:
        print(f"Topik aman! Belum pernah membahas '{keyword}' sebelumnya.")

def main():
    parser = argparse.ArgumentParser(description="Manage Threads Content Memory")
    parser.add_argument("--list", action="store_true", help="List recent content history")
    parser.add_argument("--limit", type=int, default=5, help="Number of items to list")
    parser.add_argument("--add", action="store_true", help="Add new post to history")
    parser.add_argument("--topic", type=str, default="Tech Insight", help="Topic title")
    parser.add_argument("--pillar", type=str, default="Dev Tips", help="Content pillar")
    parser.add_argument("--caption", type=str, default="", help="Caption text")
    parser.add_argument("--permalink", type=str, default="", help="Threads permalink")
    parser.add_argument("--check", type=str, help="Check if topic has been discussed before")

    args = parser.parse_args()

    if args.list:
        list_history(args.limit)
    elif args.add:
        if not args.caption:
            print("Error: --caption wajib diisi saat --add", file=sys.stderr)
            sys.exit(1)
        add_entry(args.topic, args.pillar, args.caption, args.permalink)
    elif args.check:
        check_topic(args.check)
    else:
        list_history(5)

if __name__ == "__main__":
    main()
