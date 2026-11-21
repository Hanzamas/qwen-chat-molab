# Qwen Chat di molab

Notebook [marimo](https://marimo.io) untuk chat panjang dengan Qwen3.8-27B abliterated (uncensored, FP8) di GPU gratis [molab](https://molab.marimo.io), dengan jendela chat gelap ala ChatGPT dan agent tools.

**Buka di molab:** https://molab.marimo.io/github/Hanzamas/qwen-chat-molab/blob/main/qwen_chat_molab.py

## Isi

- **vLLM 0.32.0** melayani `munekazu/Huihui-Qwen3.8-27B-abliterated-FP8` di `127.0.0.1:8000` (tidak dibuka ke luar), disetel untuk satu obrolan panjang: prefix caching, `max-num-seqs 1`, `gpu-memory-utilization 0.95`, chunk prefill 16K, konteks 1M / 512K (YaRN) atau 262K native, MTP opsional, tool calling (`qwen3_coder`)
- **Reasoning** dikunci `xhigh`, thinking tiap balasan diingat model (`preserve_thinking`)
- **Agent tools**
  - `web_search`: Google, Bing, DuckDuckGo lewat Playwright headless biasa (Chromium atau Firefox). Mesin yang memunculkan CAPTCHA dilewati, tidak diakali
  - `visit`: buka halaman (JavaScript jalan) dan ambil teksnya
  - `memory_save` / `memory_search` / `memory_forget`: memory lintas chat (SQLite FTS5)
  - `history_search` / `history_read`: cari dan baca ulang pesan asli, termasuk yang sudah diringkas
- **SQLite**: semua chat, setiap pesan (utuh, termasuk thinking dan hasil tool), ringkasan, dan memory dalam satu file
- **Auto compaction di 90% konteks**: buang thinking lama dulu, lalu ringkas giliran lama. Pesan asli tetap tersimpan dan bisa dibaca ulang lewat `history_read`
- **Lampiran** (maks 25 MB per file): gambar dan video langsung dilihat model; PDF jadi teks + gambar 12 halaman pertama; DOCX, XLSX, PPTX, ZIP, dan file teks jadi teks. Audio tidak didukung. `visit` bisa mengirim screenshot halaman
- **Jendela chat**: sidebar daftar chat, riwayat bisa di-scroll, streaming, blok thinking dan kartu tool buka-tutup, ringkasan compaction terlihat, system prompt per chat, meteran konteks, statistik token/s, indikator belum disimpan

## Cara pakai

1. Buka link molab, nyalakan GPU lewat *notebook specs*.
2. Klik **Install** (vLLM, Playwright, Chromium, Firefox), lalu **Start**, tunggu panel server `READY`.
3. Ngobrol di jendela chat.

Isi workspace molab hilang saat notebook mati. Klik **Simpan** untuk mengunduh file `.sqlite` (semua chat + memory), **Muat** untuk melanjutkan di sesi berikutnya.
Kalau notebook masih terang, ganti tema ke dark di pengaturan tampilan molab.

Belum dites di molab.
