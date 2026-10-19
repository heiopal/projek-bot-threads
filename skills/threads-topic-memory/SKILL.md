---
name: threads-topic-memory
description: Sistem pelacak topik dan memori konten yang sudah diposting ke Meta Threads untuk akun @studyp4l. Mencegah repetisi topik, mencatat histori post ke file JSON lokal, dan menjaga keberagaman pilar konten. Gunakan saat merekomendasikan topik baru atau setelah sukses posting.
metadata:
  origin: Adapted from ECC continuous-learning & topic memory
---

# Threads Topic Memory & Content History

Skill ini berfungsi sebagai sistem ingatan (memory ledger) jangka panjang untuk Hermes Agent agar akun **@studyp4l** tidak pernah mengulang topik yang sama dan mempertahankan rotasi pilar konten yang seimbang.

---

## 1. File Penyimpanan Histori

Histori konten disimpan secara lokal di:
`c:\INTERNSHIP\projek akun bot\content_history.json`

---

## 2. Cara Kerja Sebelum Brainstorming

Sebelum memberikan ide atau rekomendasi topik kepada user di Telegram:
1. Jalankan pembacaan histori postingan terakhir:
   ```bash
   python "C:\Users\Naufal\AppData\Local\hermes\skills\threads-topic-memory\scripts\memory_manager.py" --list --limit 5
   ```
2. Analisis topik apa saja yang baru dibahas dalam beberapa hari terakhir.
3. **Aturan Variasi**: Jika postingan terakhir bertema *Study & Career*, prioritaskan menyarankan pilar lain seperti *Dev Tips / Shortcut*, *Relatable Dev Bug*, atau *AI Tools Workflow*.

---

## 3. Pengecekan Topik Tertentu

Jika user mengusulkan topik spesifik (misal: *"Gua mau bahas Git branch"*), kamu bisa mengecek apakah topik tersebut sudah pernah dibahas sebelumnya:
```bash
python "C:\Users\Naufal\AppData\Local\hermes\skills\threads-topic-memory\scripts\memory_manager.py" --check "Git"
```

---

## 4. Pencatatan Setelah Berhasil Posting

Setiap kali script `post_threads.py` sukses memposting konten dan menghasilkan permalink Threads:
Eksekusi pencatatan otomatis ke memory:

```bash
python "C:\Users\Naufal\AppData\Local\hermes\skills\threads-topic-memory\scripts\memory_manager.py" --add --topic "JUDUL_TOPIK_SINGKAT" --pillar "NAMA_PILAR" --caption "TEKS_CAPTION_LENGKAP" --permalink "PERMALINK_THREADS"
```

**Pilihan Pilar Konten (@studyp4l)**:
- `Dev Tips`: Tips koding, shortcut VS Code, trik CLI/Git.
- `Relatable Dev`: Curhat error, debugging struggle, meme programmer.
- `Practical AI`: Penggunaan tools AI untuk developer.
- `Study & Career`: Tips magang, roadmap belajar, konsistensi coding.
