---
name: threads-publisher
description: Publish content directly to Meta Threads via Threads Graph API (standalone, no n8n or ngrok needed). Orchestrates brainstorming, drafting, verification, and topic logging. Use when the user asks to brainstorm, generate draft, or publish/post content to Threads.
---

# Threads Publisher & End-to-End Workflow

Skill ini mengorkestrasi seluruh proses pembuatan konten Meta Threads untuk akun **@studyp4l**, dari ideasi hingga posting langsung melalui Threads Graph API (tanpa butuh n8n atau ngrok).

---

## Alur Kerja Terintegrasi (Skills Pipeline)

1. **Memori Histori (`threads-topic-memory`)**:
   - Cek topik terakhir: `python "C:\Users\Naufal\AppData\Local\hermes\skills\threads-topic-memory\scripts\memory_manager.py" --list`
   - Pastikan topik baru tidak mengulang postingan sebelumnya.

2. **Brainstorming Sudut Pandang (`threads-brainstorming`)**:
   - Jika user meminta ide umum, ajukan 3 sudut pandang (Relatable, Pro-Tip, atau Hot Take).
   - Tunggu user memilih sudut pandang yang disukai.

3. **Penyusunan Konten & Brand Voice (`threads-content-engine`)**:
   - Terapkan hook yang kuat dan bahasa santai anak IT Indonesia.
   - Hapus kata klise AI (*"Di era digital..."*, *"Game-changer"*).
   - Maksimal 1 claim inti per post + ajakan diskusi santai.

4. **Gerbang Verifikasi (`pre-publish-verification`)**:
   - Pastikan panjang karakter **< 500 karakter**.
   - Berikan preview rapi dan minta konfirmasi eksplisit dari user (*"Gass"*, *"Publish"*, *"Oke"*).

5. **Eksekusi Publikasi (Publishing)**:
   - Jalankan script publishing via terminal:
     ```bash
     python "C:\Users\Naufal\AppData\Local\hermes\skills\threads-publisher\scripts\post_threads.py" --text "CAPTION_FINAL"
     ```
   - Jika ada link gambar:
     ```bash
     python "C:\Users\Naufal\AppData\Local\hermes\skills\threads-publisher\scripts\post_threads.py" --text "CAPTION_FINAL" --image-url "URL_GAMBAR"
     ```

6. **Pencatatan Histori (`threads-topic-memory`)**:
   - Setelah sukses dan mendapat permalink Threads:
     ```bash
     python "C:\Users\Naufal\AppData\Local\hermes\skills\threads-topic-memory\scripts\memory_manager.py" --add --topic "TOPIK" --pillar "PILAR" --caption "CAPTION" --permalink "PERMALINK"
     ```
   - Laporkan link live Threads kepada user di Telegram!
