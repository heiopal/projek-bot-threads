---
name: pre-publish-verification
description: Gerbang verifikasi wajib dan quality check sebelum mempublikasikan konten ke Meta Threads via post_threads.py. Memastikan panjang karakter <500, format rapi, tidak ada placeholder atau typo, dan meminta konfirmasi eksplisit dari user. Gunakan sebelum setiap eksekusi posting ke Threads.
metadata:
  origin: Adapted from obra/superpowers verification-before-completion
---

# Pre-Publish Verification Skill (Quality Gate)

Skill ini berfungsi sebagai gerbang verifikasi (safety gate) wajib sebelum Hermes Agent mengeksekusi postingan ke akun Meta Threads **@studyp4l**.

---

## 1. Aturan Emas (Golden Rule)

> **JANGAN PERNAH mengeksekusi script `post_threads.py` secara otomatis sebelum melewati checklist verifikasi ini DAN mendapatkan konfirmasi eksplisit dari user!**

---

## 2. Checklist Verifikasi (Pre-Flight Checks)

Sebelum meminta konfirmasi posting, lakukan verifikasi mandiri berikut:

### [ ] 1. Cek Limit Karakter Meta Threads
- Meta Threads memiliki batas maksimal **500 karakter**.
- Hitung total panjang string (termasuk huruf, spasi, emoji, dan hashtag).
- **Rekomendasi aman**: 200 - 450 karakter.
- Jika karakter > 480: Ringkas dan pangkas kata-kata berlebih sebelum ditampilkan ke user.

### [ ] 2. Cek Format Teks
- **Hapus tag Markdown yang tidak didukung**: Threads tidak merender `**teks tebal**` atau `*miring*`. Ubah menjadi huruf kapital untuk penekanan atau gunakan emoji.
- **Line Breaks**: Pastikan ada jarak antar paragraf (double newline) agar nyaman dibaca di layar HP.
- **Placeholder Check**: Pastikan tidak ada teks sisa seperti `[NAMA]`, `[LINK]`, atau `<link>` yang tertinggal.

### [ ] 3. Cek Filter Anti-Klise AI
- Pastikan tidak ada frasa kaku AI (*"Di era digital..."*, *"Mari kita bahas..."*, *"Game-changer"*).

---

## 3. Protokol Konfirmasi Publikasi

Setelah lolos verifikasi, sajikan review rapi kepada user di Telegram:

```text
📋 Preview Postingan Threads (@studyp4l):
──────────────────────────────
[Teks caption lengkap yang sudah diverifikasi]
──────────────────────────────
📊 Panjang: [X] / 500 karakter (Aman ✅)
🎯 Target: Meta Threads (@studyp4l)

Ketik "Gass posting", "Publish", atau "Oke" jika kamu sudah setuju untuk langsung diposting ke Threads!
```

---

## 4. Eksekusi Setelah Konfirmasi

Hanya ketika user memberikan konfirmasi kata sepakat (e.g. *"Gass"*, *"Publish"*, *"Oke posting"*):

Jalankan perintah eksekusi via tool terminal:
```bash
python "C:\Users\Naufal\AppData\Local\hermes\skills\threads-publisher\scripts\post_threads.py" --text "CAPTION_FINAL"
```

Setelah script mengembalikan hasil JSON dengan status `success: true`:
1. Berikan ucapan selamat dan link permalink Threads live (`https://www.threads.net/@studyp4l/post/...`).
2. Jalankan skill `threads-topic-memory` untuk mencatat postingan ini ke log histori.
