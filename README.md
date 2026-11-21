# Qwen Chat di molab

Notebook [marimo](https://marimo.io) untuk chat panjang dengan Qwen3.8-27B abliterated (uncensored, FP8) di GPU gratis [molab](https://molab.marimo.io), dengan jendela chat gelap ala ChatGPT.

**Buka di molab:** https://molab.marimo.io/github/Hanzamas/qwen-chat-molab/blob/main/qwen_chat_molab.py

## Isi

- vLLM 0.32.0 melayani `munekazu/Huihui-Qwen3.8-27B-abliterated-FP8` di `127.0.0.1:8000` (tidak dibuka ke luar)
- Disetel untuk satu obrolan panjang: prefix caching, `max-num-seqs 1`, `gpu-memory-utilization 0.95`, chunk prefill 16K, konteks 1M / 512K (YaRN) atau 262K native, MTP opsional
- Reasoning dikunci `xhigh`, thinking tiap balasan diingat model (`preserve_thinking`)
- Jendela chat anywidget: riwayat bisa di-scroll, streaming, blok thinking buka-tutup, system prompt, meteran konteks, statistik token/s, simpan/muat obrolan sebagai file JSON
- Tanpa tool (tidak ada web search atau eksekusi kode)

## Cara pakai

1. Buka link molab, nyalakan GPU lewat *notebook specs*.
2. Klik **Install**, lalu **Start**, tunggu panel server `READY`.
3. Ngobrol di jendela chat.

Kalau notebook masih terang, ganti tema ke dark di pengaturan tampilan molab.
Isi workspace molab hilang saat notebook mati: klik **Simpan** di chat untuk mengunduh obrolan, **Muat** untuk melanjutkan.

Belum dites di molab.
