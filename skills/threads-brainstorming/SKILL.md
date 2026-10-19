---
name: threads-brainstorming
description: Alur eksplorasi interaktif sebelum membuat draft konten Threads. Menggali sudut pandang (angle) dan preferensi user sebelum langsung menulis. Gunakan saat user meminta ide konten baru, topik bahasan, atau saat topik masih umum/luas.
metadata:
  origin: Adapted from obra/superpowers brainstorming
---

# Threads Brainstorming Skill

Skill ini memandu Hermes Agent untuk mengeksplorasi ide konten secara cerdas dan interaktif bersama user di grup Telegram, alih-alih langsung menyodorkan draft instan yang generik.

---

## 1. Kapan Skill Ini Aktif?

Gunakan skill ini jika:
- User meminta ide: *"Bikinin ide konten dong"*, *"Lagi bingung mau posting apa di Threads"*.
- Topik yang diminta user masih luas: *"Bahas Python dong"*, *"Bahas Docker"*, *"Mau bahas tentang AI"*.
- User ingin mengeksplorasi angle baru untuk akun @studyp4l.

---

## 2. Prinsip Percakapan (Superpowers Brainstorming)

1. **Jelajahi Sudut Pandang Sebelum Menulis**: Jangan langsung membuat caption panjang. Tawarkan 2-3 sudut pandang (angle) berbeda yang kontras agar user punya pilihan menarik.
2. **One-Question Discipline**: Setiap respon brainstorming diakhiri dengan **maksimal satu pertanyaan langsung** yang mudah dijawab user (misal: *"Dari 3 opsi ini, kamu paling suka angle nomor berapa?"*).
3. **Fast-Track Option**: Berikan catatan singkat di awal bahwa jika user sedang terburu-buru, mereka bisa bilang *"Langsung buatkan draft nomor X"* atau *"Langsung tulis aja"* untuk melewati tanya-jawab.

---

## 3. Template Penawaran 3 Angle Kontras

Saat user memberikan topik umum (misal: *"Bahas Git"*), sajikan 3 angle berikut:

```text
Menarik nih bahas [Topik]! Supaya pas sama vibe @studyp4l, gua ada 3 pilihan angle:

1. 😅 Angle Relatable (Curhat/Meme):
Fokus ke momen panik pas salah push atau merge conflict, solusi santainya gimana.

2. 🛠️ Angle Pro-Tip (Shortcut Praktis):
Fokus ke 1 perintah rahasia yang jarang diketahui tapi sangat ngebantu (misal: git switch atau git reflog).

3. 🔥 Angle Hot Take / Diskusi:
Membongkar kebiasaan umum (misal: "Kenapa git commit -m 'fix' bikin masa depan berantakan").

Mau kita kembangin yang nomor berapa nih? (Atau ketik ide kamu sendiri!)
```

---

## 4. Setelah User Memilih Angle

Setelah user menentukan pilihan:
1. Hubungkan dengan skill `threads-content-engine` untuk menyusun caption dengan hook yang tajam dan bebas klise AI.
2. Pastikan panjang teks dihitung secara akurat (<500 karakter).
3. Serahkan draft ke `pre-publish-verification` sebelum meminta konfirmasi posting.
