# Qwen Chat RP di molab

Notebook [marimo](https://marimo.io) untuk chat dan roleplay panjang (sampai 512K/1M token) di GPU
[molab](https://molab.marimo.io): kartu (tokoh, persona, dunia, skenario, gaya, GM), Studio untuk menyusun kartu
sambil ngobrol, memory berlingkup, buku fakta, dunia yang tetap berjalan, dan compaction yang tidak melupakan detail.

**Buka di molab:** https://molab.marimo.io/github/Hanzamas/qwen-chat-molab/blob/main/qwen_chat_molab.py

## Cara pakai

1. Nyalakan GPU lewat *notebook specs*, lalu **Run all**.
2. Klik **Install** (sekali per sesi: vLLM, llama.cpp, Camoufox, Playwright).
3. Pilih model dan konteks, klik **Start**, tunggu status `READY`.
4. Ngobrol di jendela chat paling bawah. Model juga bisa diganti dari dalam chat (laci → Model).

Isi workspace molab hilang saat notebook mati. Isi token di sel **Backup ke Hugging Face** (repo dataset private,
backup otomatis tiap beberapa menit kalau ada perubahan), atau pakai tombol **Simpan / Muat** di chat.

## Model

| preset | backend | konteks | catatan |
|---|---|---|---|
| Huihui Qwen3.8 27B abliterated FP8 | vLLM | 262K native, YaRN sampai 1M | MTP |
| Dark-Gemistry 31B FP8 (W8A16) | vLLM | 262K | MTP dengan drafter `google/gemma-4-31B-it-assistant` |
| Dark-Gemistry 31B BF16 → FP8 saat dimuat | vLLM | 262K | idem, unduh ~65 GB |
| Dark-Gemistry 31B HB16-Q8_0 / Q6_K | llama.cpp | 262K, 512K eksperimental | drafter GGUF, mmproj Gemma 4 |
| Qwen3.8 27B heretic-ara Q8_0 | llama.cpp | YaRN sampai 1M | MTP |
| Qwen3.8 40B Heretic Build2 i1-Q6_K | llama.cpp | YaRN sampai 1M | MTP, hanya mode thinking |

Semua bobot dikunci ke revisi commit Hugging Face, llama.cpp ke tag rilis, paket Python ke versi tertentu.
Kalau MTP/drafter membuat server gagal start, server otomatis dijalankan ulang tanpa MTP.

## Fitur

- **Kartu berbasis skema**: enam jenis kartu + status; field didefinisikan skema JSON yang bisa diedit di UI, tanpa
  ubah kode. Impor/ekspor `qcard`, impor SillyTavern V2/V3 (JSON/PNG). Versi per kartu, lore dan garis waktu di kartu Dunia.
- **Studio**: model menyusun kartu bersama kamu (lengkapi, cek konsistensi dan anakronisme, riset, uji adegan, uji suara,
  wawancara), lalu **Mulai RP**.
- **Prompt dirakit otomatis** dan dibekukan per epoch (cache awet); semua yang berubah tiap giliran ditempel sementara di
  pesan terakhir.
- **Dunia yang hidup**: jam dunia, dadu (RNG kode, hasil tampil di chat), statistik yang berubah per jam, garis waktu,
  agenda NPC, batas pengetahuan, world tick saat diam/AFK (default 1 jam nyata = 1 jam cerita).
- **Format game** (opsional per kartu GM): panel status dan panel Dunia dihitung kode, pilihan sebagai kartu yang bisa
  diklik, tombol lompat waktu. Panjang narasi diacak dalam rentang kartu Gaya dan dicek setelah selesai.
- **Memory**: lingkup user / kartu / cerita / chat, `memory_update`, catatan + undo, 10 memory relevan per giliran,
  pencarian hybrid BM25 + embedding (Qwen3-Embedding-0.6B).
- **Buku fakta + anti-halusinasi**: `fact_lookup`, `wiki_search`/`wiki_read` (Wikipedia API), web search Camoufox,
  pemeriksa fakta (mati / latar belakang / ketat).
- **Compaction**: buang thinking/lampiran lama dulu, lalu simpan memory, ringkasan per potongan ~100K token
  (sampai 32K token per potongan), cek nama yang hilang, kronik bertingkat. Pesan asli tetap bisa dibaca ulang.
- **Pohon pesan**: jawab ulang + geser versi, edit, lanjutkan, hapus, cabang, pin, bab, pencarian di semua chat,
  lanjut di chat baru, ekspor MD/HTML/EPUB, group chat (narator GM atau satu tokoh per balasan).
- **Mode belajar bahasa**: terjemahan disembunyikan, klik dialog untuk penjelasan, kosakata + flashcard.
- **UI**: gaya ChatGPT, tema ikut marimo, scroll yang tidak menarik balik saat kamu membaca ke atas, thinking yang bisa
  digulung dan dibuka penuh, responsif di layar sempit.

## Pengembangan

Kode notebook dibangun dari sel-sel di `dev/cells/` (satu file = satu sel):

```
python dev/build.py          # tulis ulang qwen_chat_molab.py
python -m pytest tests       # tes dengan server OpenAI palsu (tanpa GPU)
```

Rencana lengkap ada di `dev/PLAN.md`.

## Belum dites di GPU

Semua tes jalan dengan server palsu. Uji pertama di molab:

1. Run all → Install → pilih **Huihui Qwen3.8 27B abliterated FP8 · vLLM**, konteks 512K → Start → kirim satu pesan.
2. Laci → Model: ganti ke **Dark-Gemistry 31B FP8 (W8A16) · vLLM** → cek apakah MTP tetap nyala (status server) dan
   gaya bahasanya sama dengan versi GGUF.
3. Ganti ke **Dark-Gemistry 31B HB16-Q8_0 · llama.cpp** → cek log: apakah drafter assistant diterima `--spec-type draft-mtp`.
4. Studio → susun satu cerita kecil → Mulai RP dengan kartu GM format game → kirim beberapa giliran.
5. Compact manual di chat yang sudah panjang → cek ringkasan dan "Lihat prompt".
