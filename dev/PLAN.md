# Rencana Qwen Chat untuk RP

Status: rencana, belum ada kode. Repo target: `Hanzamas/qwen-chat-molab`.

Tujuan: chat RP panjang (sampai 512K/1M token) yang konsisten, membumi, tidak melupakan detail,
reproducible, dengan UI bersih gaya ChatGPT. Semua fitur yang dibahas masuk.

---

## 0. Prinsip yang mengikat semua tahap

1. **Generik, bukan khusus satu cerita.** Tidak ada genre, zaman, bahasa, atau aturan cerita yang ditanam di
   kode. WW1, dialog Jerman, gore, dan sejenisnya hanya isi kartu. Fantasi, sci-fi, modern, atau sejarah
   lain cukup memakai kartu yang berbeda.
2. **Disiplin cache prompt.** Bagian atas prompt hanya berubah saat compaction atau saat kamu menekan
   "terapkan sekarang". Semua yang berubah tiap giliran ditempel sementara di pesan user terakhir dan
   tidak disimpan ke riwayat. Ada tes otomatis yang memastikan awal prompt identik antar giliran.
3. **Tugas sampingan memakai awal prompt yang sama.** Impersonate, analisis bahasa, update status, world
   tick, pemeriksa fakta, dan simpan memory sebelum compaction dikirim sebagai prompt chat ditambah satu
   pesan instruksi di akhir. Hasilnya tidak masuk riwayat. Dengan begitu cache tidak tergusur, termasuk di
   llama.cpp yang hanya punya satu slot (`-np 1`).
4. **Tidak ada yang hardcoded untuk kartu.** Semua jenis kartu didefinisikan oleh skema JSON yang disimpan
   sebagai data. Form UI, prompt, importer, dan exporter dibangkitkan dari skema.
5. **Yang bisa dihitung, dihitung kode.** Waktu dunia, dadu, statistik yang berubah per jam, dan peristiwa
   bertanggal dihitung kode, bukan diputuskan model. Ini melawan kecenderungan model berpihak ke pemain.
6. **Fakta nyata tidak boleh dikarang.** Fakta dunia nyata yang tidak pasti dicari dulu, disimpan di buku
   fakta dengan sumber, dan diperiksa setelah jawaban.
7. **Database selalu bisa dimuat.** Migrasi berurutan dengan `PRAGMA user_version`, jadi backup lama
   tetap bisa dibuka oleh versi baru.
8. **Reproducible.** Semua versi dikunci dan setiap jawaban mencatat setelan yang menghasilkannya.
9. **Gagal dengan jelas.** Tidak ada error yang diam: compaction kosong, server mati, search gagal,
   semuanya tampil di UI.

---

## 1. Arsitektur

**Satu notebook mandiri.** Semua kode ada di sel-sel `qwen_chat_molab.py`. Tidak ada lagi unduhan
`qwen_chat_app.py` saat jalan dan tidak ada patch teks. Yang diunduh hanya binary llama.cpp, vLLM, dan bobot
model. Cara pakai: **Run all → Install (sekali per sesi) → pilih model → Start → ngobrol.**

Sel dikelompokkan per bagian (kode tetap terpisah rapi walau satu file):

| kelompok sel | isi |
|---|---|
| Setelan | path, port, preset model (sampler, konteks, YaRN, MTP), versi yang dikunci |
| Kontrol | tombol Install, pilih model, Start/Stop, status server, monitor GPU |
| Backup | field token HF, repo private, Backup sekarang / Pulihkan terbaru |
| Store | skema SQLite + migrasi |
| Server | start/stop vLLM, llama.cpp, embedder (dipakai sel Kontrol dan widget) |
| Prompt | perakit prompt otomatis dari kartu + aturan cache |
| Compaction | simpan memory dulu, ringkasan per potongan, kronik bertingkat |
| Memory | memory berlingkup, buku fakta, recall, embedding hybrid |
| Kartu | skema semua jenis kartu (JSON sebagai data), render, impor/ekspor, versi |
| Studio | menyusun kartu sambil ngobrol dengan model |
| Dunia | jam dunia, dadu, statistik, garis waktu, agenda NPC, batas pengetahuan, world tick |
| RP | OOC, slash command, deteksi pengulangan, frasa terlarang, penjaga format, panjang balasan |
| Fakta | `wiki_search` / `wiki_read`, web search Camoufox, buku fakta, pemeriksa fakta |
| Tools | definisi + eksekusi semua tool model |
| Belajar | mode belajar bahasa, kosakata, flashcard |
| UI | ESM + CSS widget, ikon Lucide (SVG inline), marked + DOMPurify (disimpan di sel) |
| Widget | glue anywidget, chat ditampilkan |

Tes tetap di luar notebook (repo `tests/`): notebook diimpor lewat `app.run()` seperti tes benchmark, lalu
diuji dengan server OpenAI palsu. UI dites lewat `tests/ui/harness.html` dengan model palsu.

---

## 2. Model data (ringkas)

Semua tersimpan di satu file SQLite, ikut Simpan/Muat dan backup HF.

| tabel | isi |
|---|---|
| `chats` | judul, `story_id`, `kind` (rp / studio / group), setelan per chat (sampler, thinking, panjang, author's note, mode pemeriksa fakta), `head_id` |
| `messages` | pohon: `parent_id`, `role`, `content`, `reasoning`, `ooc`, `pinned`, `status` (final / partial), `meta` (model, quant, sampler, seed, ctx, YaRN, durasi, token, pilihan yang ditawarkan, target panjang dan hasil hitungannya) |
| `stories` | cerita lintas chat: kartu yang dipakai (dunia, skenario, gaya, GM, persona, tokoh), buku cerita (canon), "jangan pernah lupa", **jam dunia** |
| `chapters` | penanda bab: `chat_id`, `message_id`, judul |
| `summaries` | ringkasan per potongan: rentang pesan, `level` (potongan / era), node pohon tempat ringkasan berlaku |
| `canon_snapshot` | prompt beku per epoch chat |
| `card_schemas` | skema per jenis kartu (JSON), versi |
| `cards` / `card_versions` | kartu: `type` (character / persona / world / scenario / style / gm), data JSON, avatar, riwayat versi |
| `lore_entries` | lore milik kartu Dunia: jenis (tempat / faksi / benda / peristiwa / istilah / dll., dari skema), judul, kata kunci, isi, `core` |
| `facts` | **buku fakta**: `world_card_id`, klaim, URL + judul sumber, tanggal dicek, keyakinan, status (terverifikasi / diperdebatkan / belum terverifikasi), tag |
| `timeline` | peristiwa bertanggal milik kartu Dunia (nyata atau fiksi), dipicu jam dunia |
| `chat_cards` | tautan chat ↔ kartu: peran (utama / samping / persona), versi yang dipakai |
| `char_status` | status dinamis per tokoh per cerita: field dari skema (lokasi, pakaian, mood, luka, hubungan, rencana saat ini, statistik angka + laju per jam) |
| `status_events` | perubahan status per pesan: field, delta/nilai, alasan; status sekarang = putar ulang di jalur aktif |
| `world_events` | kejadian di luar layar: waktu dunia, isi, `known_to`, sudah diketahui/ditampilkan atau belum |
| `dice_log` | setiap lemparan: kejadian, peluang, hasil RNG, pesan terkait |
| `memories` | `scope` (user / card / story / chat), `card_id`, `story_id`, `chat_id`, `kind` (fakta / inti ringkasan), `updated` |
| `memory_log` | catatan setiap save/update/forget oleh model, untuk tombol undo |
| `vectors` | embedding float16 per (jenis, id), untuk pencarian hybrid |
| `vocab` | kosakata bahasa target + jadwal flashcard |
| `attachments` | gambar, video, file (sudah ada) |

Semua tabel teks yang perlu dicari punya indeks FTS5.

Pohon pesan menjadi dasar untuk reroll/geser versi, edit, dan cabang. Nomor `#` di tool riwayat adalah
posisi pada jalur aktif. Ringkasan hanya dipakai kalau node tempatnya masih ada di jalur aktif, jadi
mengedit pesan lama otomatis membatalkan ringkasan yang sudah basi.

---

## 3. Susunan prompt (dirakit otomatis)

Kamu tidak menulis system prompt sendiri. Kolom system prompt manual tetap ada di pengaturan lanjutan.

```
[system: beku per epoch]
  aturan dasar app
  kartu Gaya (prosa, sudut pandang, bahasa, panjang, frasa terlarang)
  kartu GM (realisme, kekejaman, dadu, aturan konsekuensi, checklist thinking, aturan fakta)
  kartu Persona
  kartu Dunia (field inti + lore core=true)
  kartu Skenario
  kartu inti tokoh di cerita ini (field core=true)
  memory lingkup user + kartu (dipendekkan)
  buku cerita (snapshot) + "jangan pernah lupa"
  momen tersemat (pesan yang di-pin dan sudah masuk wilayah ringkasan, disalin persis)
  kronik: ringkasan era (lama) + ringkasan potongan (baru)
[riwayat: pesan setelah titik ringkasan, jalur aktif saja]
[pesan user terakhir + blok sementara, tidak disimpan]
  jam dunia sekarang + peristiwa garis waktu yang jatuh tempo
  kejadian di luar layar yang kini bisa diketahui pemain
  perubahan kartu / buku cerita sejak snapshot
  status tokoh yang muncul di adegan (termasuk statistik yang sudah dihitung kode)
  detail kartu tokoh yang muncul (field core=false yang relevan)
  lore yang terpicu kata kunci + fakta relevan dari buku fakta + 10 memory teratas (hybrid)
  author's note, target panjang giliran ini (paragraf × kalimat), "hindari frasa X",
  giliran bicara (group chat)
```

Epoch baru dimulai saat compaction atau "terapkan sekarang". Hanya di titik itu cache dibangun ulang.

---

## 4. Kartu berbasis skema

### Enam jenis kartu

| kartu | isi | dipakai ulang |
|---|---|---|
| **Tokoh** | identitas, penampilan, sifat (skala), tujuan/ketakutan/rahasia, gaya bicara + 3-5 contoh kalimat, riwayat, relasi, batasan, **agenda: tujuan, rencana, rutinitas**, pesan pembuka alternatif | di banyak cerita |
| **Persona** | siapa "aku": nama, peran, penampilan, latar, apa yang boleh dan tidak boleh diputuskan model untukmu | ya |
| **Dunia** | zaman/tempat, teknologi, politik/faksi, kehidupan sehari-hari, bahasa, istilah, **apakah berbasis dunia nyata** (untuk aturan fakta), **lore** (`lore_entries`), **garis waktu** (`timeline`), **definisi statistik** (mis. lapar/lelah/moral, atau mana/stamina untuk fantasi) | di banyak cerita |
| **Skenario** | premis, situasi awal, konflik dan taruhan, alur yang direncanakan, adegan pembuka, tanggal/jam dunia awal, kartu yang dipakai | per cerita |
| **Gaya** | sudut pandang, bahasa narasi, aturan dialog/terjemahan (mis. dialog Jerman + terjemahan Indonesia), panjang balasan, tingkat detail kekerasan, tempo, **frasa terlarang**, "jangan bicara atas nama aku", "jangan menceramahi" | sebagai preset |
| **GM (narator)** | tingkat realisme dan kekejaman, aturan konsekuensi, kapan memakai dadu, perilaku NPC, kejadian acak, skala waktu saat AFK, frekuensi world tick, aturan fakta, checklist thinking | sebagai preset, bisa dicampur dengan Gaya mana pun |

### Skema sebagai data
Setiap field adalah satu entri di skema jenis kartunya:

```json
{"key": "speech_samples", "label": "Contoh kalimat khas", "section": "Gaya bicara",
 "type": "list", "core": true, "visibility": "model", "max_items": 5,
 "help": "3-5 kalimat persis seperti tokoh ini bicara"}
```

- `type`: `text`, `longtext`, `list`, `scale` (1-5 dengan label), `tags`, `select`, `table`
  (misalnya relasi: nama / hubungan / catatan), `number` (+ `rate_per_hour` untuk statistik), `datetime`, `image`.
- `core`: `true` masuk prompt beku; `false` jadi detail yang ditempel saat relevan atau dibaca model lewat
  `card_read`.
- `visibility`: `model` (masuk prompt), `secret` (masuk prompt, disembunyikan di UI saat RP),
  `ui` (catatan untukmu, tidak pernah masuk prompt).
- Menambah field = mengedit skema di editor skema UI atau mengimpor file skema. Tidak ada perubahan kode.
- Kartu menyimpan data sebagai JSON bebas per `key`. Field yang tidak dikenal skema tetap disimpan.
- Skema bawaan: `character.v1`, `persona.v1`, `world.v1`, `scenario.v1`, `style.v1`, `gm.v1`, ditambah skema
  `status.v1` untuk status dinamis tokoh. Isinya netral, tidak terikat genre.

### Kartu dipisah dari status cerita
Kartu berisi hal yang tetap. Yang berubah selama main disimpan di status cerita dan tidak pernah mengubah
kartu: jam dunia, lokasi, luka, perlengkapan, statistik, hubungan antar tokoh, rencana NPC saat ini, rahasia
yang sudah terungkap, status alur, kejadian di luar layar, kronik.

### Format file
`{"format": "qcard", "version": 1, "type": "...", "schema": {...}, "data": {...}, "lore": [...],
"timeline": [...], "facts": [...], "memories": [...], "avatar": "<b64>"}`.
Kartu Dunia ikut membawa lore, garis waktu, dan buku faktanya. Importer satu arah menerima JSON/PNG
SillyTavern V2/V3 lewat tabel mapping (juga data). Ekspor V2 opsional.

### Memory per kartu
| lingkup | contoh | dipakai di |
|---|---|---|
| `user` | preferensi RP-mu | semua chat |
| `card` | perkembangan identitas tokoh yang berlaku di semua cerita | semua chat yang memakai kartu itu |
| `story` | kejadian, janji, rahasia yang terungkap | chat dalam cerita yang sama |
| `chat` | detail sementara | chat itu saja |

- Model memilih lingkup saat menyimpan; default `story`.
- Recall hanya mengambil `user` + kartu yang ada di chat + cerita aktif + chat aktif, jadi kejadian satu
  cerita tidak bocor ke cerita lain.
- "Jadikan bagian karakter": fakta `story` bisa dipromosikan ke `card`, menghasilkan versi kartu baru.

### Versi
Setiap simpan membuat versi. Chat memakai versi saat dimulai. Kartu yang diedit ditawarkan ke chat lama
saat compaction berikutnya.

### Studio (menggantikan workshop kartu)
Chat jenis `studio`: kiri obrolan, kanan tab per kartu yang dibangkitkan dari skema.
1. Kamu membuka dengan bebas (premis, genre, siapa kamu, tokoh yang kamu mau).
2. Model bertanya per putaran (dunia → persona → tokoh → skenario → gaya → GM), mengusulkan isi, dan mengisi
   kartu lewat `card_draft_update(jenis, key, isi)`. Kamu setuju, minta ganti, atau edit langsung di form.
3. Alat bantu:
   - **Lengkapi yang kosong.**
   - **Cek konsistensi antar kartu**; untuk dunia berbasis dunia nyata juga **cek anakronisme**.
   - **Riset**: model memakai `wiki_search` / `wiki_read` / `web_search` / `visit`, hasilnya masuk buku
     fakta dan lore dengan sumber.
   - **Uji adegan**: satu paragraf pembuka dengan Gaya + GM yang dipilih.
   - **Uji suara tokoh** (3 situasi) dan **wawancara tokoh**.
   - **Variasi per field** (geser), **isi penampilan dari gambar** (mmproj), **rapikan dari teks bebas**.
4. **Mulai RP**: cerita + chat baru dibuat, dengan pilihan pesan pembuka.
- Di tengah RP: `/studio` atau `((ubah: ...))` → model memperbarui kartu atau status cerita lewat tool.
  Berlaku di epoch berikutnya, atau langsung lewat "terapkan sekarang".
- Thinking tinggi di Studio; chat RP memakai level per chat.

---

## 5. Realisme dan dunia yang hidup

Model cenderung berpihak ke pemain, mengejar drama, dan membiarkan dunia diam saat kamu diam. Penanganannya
dua lapis: aturan tertulis di kartu, dan mekanisme di kode. Semuanya generik dan diatur lewat kartu GM.

### Aturan tertulis
- **Gaya:** detail konkret dan indrawi, reaksi proporsional, tanpa superlatif, cara bicara sesuai latar,
  daftar frasa terlarang.
- **GM:** tanpa plot armor untuk pemain maupun NPC, aksi bisa gagal, luka dan tindakan punya akibat, setiap
  aksi makan waktu, NPC tidak memuja pemain, NPC bisa menolak, berbohong, salah paham, dan bertindak sendiri.
- **Checklist di thinking** sebelum menjawab: masuk akal? akibatnya? NPC ini tahu apa? waktu yang lewat?
  ada yang lebay? ada fakta nyata yang belum pasti?

### Mekanisme di kode
1. **Jam dunia.** Status cerita menyimpan tanggal dan jam dunia. Model melaporkan waktu yang lewat lewat
   `world_advance(menit, ringkasan)`.
2. **Dadu nyata.** `roll(kejadian, peluang)`: peluang ditetapkan model, hasil dari RNG kode. **Hasil
   ditampilkan di chat** sebagai catatan kecil dan dicatat di `dice_log`.
3. **Agenda NPC.** Tujuan, rencana, dan rutinitas di kartu tokoh; rencana yang sedang dijalankan di status
   cerita, diperbarui model lewat tool.
4. **Batas pengetahuan.** Setiap kejadian dicatat dengan `known_to`. NPC hanya bertindak berdasarkan yang
   mereka tahu.
5. **Statistik berjalan sendiri.** Field `number` dengan `rate_per_hour` dihitung kode setiap jam dunia maju.
6. **Garis waktu.** Peristiwa bertanggal di kartu Dunia (nyata atau fiksi) terjadi saat jam dunia sampai,
   siap atau tidak siap pemainnya.

### Dunia tetap jalan saat kamu AFK
- **World tick**: tugas sampingan "waktu maju X; apa yang dilakukan tokoh lain di luar layar; apa yang
  terjadi di dunia?" Hasilnya masuk `world_events` dengan waktu dan `known_to`, tidak ke system prompt.
- Kejadian ditempel sementara saat relevan atau saat pemain bisa mengetahuinya (kabar, surat, kembali ke lokasi).
- Saat GPU diam, tick jalan otomatis (misalnya tiap 15-30 menit, diatur di kartu GM). Begitu kamu mengetik,
  tick dibatalkan. Saat kembali, muncul ringkasan "Selama kamu pergi: …".
- **Skala waktu default: 1 jam nyata = 1 jam cerita.** Bisa diganti di kartu GM (berhenti, atau skala lain).
- Biaya: GPU terpakai per tick (sekitar 1-2K token output). Konteks tidak membengkak karena kejadian disimpan
  di database dan ikut diringkas saat compaction.

---

## 6. Format RP terstruktur dan panjang balasan

Format dipilih di kartu GM: **prosa** (narasi saja) atau **game** (narasi + panel + pilihan). Prinsipnya:
**model hanya menulis narasi; status, dunia, dan pilihan dikerjakan kode atau tugas sampingan dan tidak
masuk riwayat.** Dengan begitu model tidak bisa menyalin blok lama, dan konteks tidak habis untuk blok yang
diulang tiap giliran.

### Panel status (dihitung kode)
- Field dari skema status + definisi statistik kartu Dunia (contoh WG: energi, lapar, hidrasi, mandi, wangi,
  saku, level bahasa, reputasi per kelompok, umur, tinggi; cerita lain bisa HP, mana, peluru, dll.).
- Model melaporkan perubahan lewat `status_update({field: delta atau nilai, "alasan": "..."})`; statistik
  dengan `rate_per_hour` turun/naik otomatis saat jam dunia maju.
- Setiap perubahan disimpan sebagai event yang menempel ke pesan (`status_events`). Status sekarang = putar
  ulang event di jalur aktif, jadi reroll, edit, dan cabang otomatis mengembalikan status.
- Tampil sebagai panel tetap di atas chat (atau sidebar kanan): tanggal, jam, lokasi, nomor giliran, bar
  statistik, perubahan ditandai +/− dengan alasan saat disorot. Ke model hanya dikirim status ringkas di blok
  sementara.

### Panel Dunia (dirakit kode)
- Tanggal/jam dari jam dunia; cuaca dari tabel iklim kartu Dunia + RNG yang di-seed dengan cerita + tanggal
  (hasilnya sama kalau diulang); berita dan gosip dari `world_events`. Yang baru ditandai, yang sudah
  ditampilkan tidak diulang. Panel bisa dilipat.
- **Tombol lompat waktu** (daftar durasi dari kartu GM, contoh 2 jam / 3 jam / 1 hari / 1 minggu / 1 bulan):
  kode memajukan jam, menghitung statistik, menjalankan world tick untuk periode itu, lalu model menulis
  narasi transisi singkat (apa yang kamu lakukan, apa yang terjadi).

### Pilihan (tugas sampingan)
- Dibuat setelah narasi selesai, dengan awal prompt yang sama (cache aman); disimpan di `meta` pesan, tidak
  masuk riwayat.
- Aturan dari kartu GM (default): 1-3 masalah per giliran, 3-5 pilihan per masalah; pertanyaan 1-2 kalimat
  panjang yang menjelaskan situasi dan ketegangannya dengan detail konkret; pilihan 1-2 kalimat panjang berisi
  tindakan dan niat/caranya, tanpa membocorkan hasil.
- Variasi: kode mengirim pilihan 3-5 giliran terakhir sebagai daftar "jangan ulangi"; pilihan yang terlalu
  mirip dibuang (cek kemiripan); tiap set wajib berisi kategori berbeda (sosial, fisik/aksi, berisiko, memakai
  barang/skill, memajukan agenda NPC); pilihan harus spesifik ke situasi; temperature tugas ini sedikit lebih
  tinggi dari narasi.
- Kode mengecek jumlah kalimat; yang tidak sesuai dibuat ulang.
- "Bebas" tidak jadi pilihan karena kolom ketik selalu ada. Frekuensi pilihan diatur di kartu GM (selalu /
  kadang-kadang / tidak pernah).
- UI: kartu selebar kolom; klik = kirim, ikon pensil = masukkan ke kolom ketik untuk diedit dulu.

### Panjang narasi
- Field kartu Gaya (generik): paragraf `[5, 10]`, kalimat per paragraf `[5, 10]`, gaya kalimat "panjang,
  deskripsi dan dialog tokoh dirangkai dalam satu kalimat", porsi dialog (misalnya 30-50%).
- **Variasi oleh kode:** tiap giliran kode mengacak target di dalam rentang dan menempelkannya ke blok
  sementara ("Giliran ini: 7 paragraf, 6-9 kalimat per paragraf").
- Checklist thinking: susun kerangka per paragraf dulu (aksi, dialog, reaksi NPC, detail dunia), baru tulis.
- **Dicek setelah selesai:** kode menghitung paragraf dan kalimat (dengan pengecualian kutipan dan singkatan).
  Kurang → otomatis "lanjutkan" dengan instruksi menambah paragraf. Lebih → dibiarkan, dicatat.
- Anti bertele-tele: tiap paragraf wajib memajukan sesuatu, tidak mengulang isi giliran sebelumnya; detektor
  pengulangan dan frasa terlarang tetap jalan.
- **Jangan bertindak untukmu:** narasi berhenti di titik kamu harus merespons dan tidak melanjutkan aksimu
  melebihi yang kamu tulis (aturan kartu GM + pemeriksa di penjaga format).
- Preset panjang pendek / sedang / panjang = preset rentang ini; "panjang" = 5-10 × 5-10.
- Biaya: ~1.000-4.000 token per balasan, `max_tokens` minimal ~6K + jatah thinking, ~30-100 detik per balasan
  di 40 tok/s (lebih cepat dengan MTP), 512K penuh setelah ~120-150 giliran.

---

## 7. Fakta dan anti-halusinasi

Berlaku untuk dunia yang ditandai berbasis dunia nyata. Untuk dunia fiksi, pemeriksaan yang sama dipakai untuk
konsistensi terhadap lore dan buku cerita.

1. **Fakta nyata vs fiksi.** Nama NPC karangan dan kejadian kecil boleh dikarang. Fakta dunia nyata yang
   spesifik (tanggal, satuan, senjata, pangkat, geografi, seragam, prosedur, harga) wajib akurat. Kalau tidak
   pasti: cari dulu. Jangan pernah mengarang angka, nama, atau tanggal nyata. Kalau tidak ketemu: narasi dibuat
   umum + catatan OOC kecil "belum terverifikasi".
2. **Checklist thinking** memuat pertanyaan "ada fakta nyata yang belum pasti?" Qwen3.8 dan Gemma 4 bisa
   memanggil tool di tengah thinking.
3. **Buku fakta di SQLite** (`facts`, FTS + vektor): klaim, sumber, tanggal dicek, keyakinan, status. Model
   memakai `fact_lookup` dulu sebelum search, dan `fact_save` setelah menemukan sesuatu. Fakta milik kartu
   Dunia, jadi dipakai ulang di semua cerita dengan dunia yang sama, ikut ekspor kartu Dunia dan ikut backup.
4. **Riset di Studio**: topik inti dunia diriset di awal, jadi saat RP jarang perlu search di tengah adegan.
5. **Pemeriksa fakta otomatis**: setelah jawaban, tugas sampingan memilah klaim "fakta nyata" vs "fiksi", lalu
   klaim yang tidak ada di buku fakta atau lore dicek. Mode per chat:
   - mati;
   - **latar belakang (default)**: jawaban tampil dulu, kalau salah muncul ⚠ + koreksi + sumber;
   - ketat: jawaban baru tampil setelah dicek (tambah ~10-60 detik).
6. **Sumber lebih andal**: `wiki_search` / `wiki_read` lewat API Wikipedia (bahasa dipilih otomatis atau dari
   kartu Dunia), tanpa key dan tanpa CAPTCHA. Web search Camoufox tetap ada; browsernya dibiarkan menyala di
   antara pencarian supaya cepat.
7. **Sumber ditampilkan** di panel catatan / OOC, tidak di dalam narasi. Chat biasa (bukan RP) tetap
   mencantumkan URL di jawaban.

Batasan: lapisan ini menekan halusinasi fakta nyata dengan kuat, tapi tidak menjamin 100%.

---

## 8. Tahap kerja

Setiap tahap selesai dengan tes lokal lulus, commit, dan push. Tes GPU di Molab dilakukan olehmu di
akhir tiap tahap (saya tidak bisa mengakses sandbox).

### Tahap 0 — Fondasi
- [x] Semua kode masuk ke sel notebook (lihat bagian 1); unduhan `qwen_chat_app.py` dan semua patch teks dihapus.
- [x] Semua patch lama dibawa ke kode, tidak ada yang hilang: Camoufox + browser stealth, selector Google
      yang diperbaiki, DuckDuckGo dibuang, sampler per model, kwargs Gemma + Qwen (`enable_thinking`,
      `reasoning_effort`, `preserve_thinking`), tombol Compact manual, `dedupe_parens`, aturan bahasa
      (dipindah jadi isi kartu Gaya default), lampiran (gambar, video, PDF, docx, xlsx, pptx, zip).
- [x] Preset model di sel Setelan: Dark-Gemistry Q8/Q6, Qwen3.8 27B heretic-ara Q8, 40B Build2, Huihui 27B
      (vLLM). Default 512K, temperature 1.0, thinking xhigh, MTP untuk Qwen, YaRN sampai 1M untuk Qwen,
      YaRN 512K eksperimental + peringatan untuk Gemma, KV fp8 saat YaRN di vLLM.
- [x] Dark-Gemistry 31B di vLLM 0.32.0 (`Gemma4ForConditionalGeneration` didukung) — kode siap, belum diuji di GPU:
      - Dua pilihan bobot: `hoborific/Gemma-4-Dark-Gemistry-31B-W8A16-FP8` (~33GB, quant komunitas) atau BF16
        asli `Nimbz/Gemma-4-Dark-Gemistry-31B` + `--quantization fp8` (unduh ~65GB).
      - `--tool-call-parser gemma4 --reasoning-parser gemma4`, kwargs `enable_thinking`, sampler card
        Dark-Gemistry (temp 1.0, top_k 0, top_p 0.95, min_p 0.05), maks 262K tanpa YaRN, KV fp8, prefix caching.
      - lm_head StyleTune ikut termuat (`tie_word_embeddings: false`, `lm_head.weight` di index). Dicek saat
        tes: bandingkan gaya jawaban dengan versi GGUF untuk prompt dan seed yang sama.
      - **MTP nyala** pakai drafter resmi `google/gemma-4-31B-it-assistant` (0.47B, BF16, tidak di-gate):
        `--speculative-config '{"model": "google/gemma-4-31B-it-assistant", "num_speculative_tokens": N}'`.
        Drafter dilatih untuk Gemma 4 31B asli, jadi percepatannya di Dark-Gemistry bisa lebih kecil; hasil
        jawaban tidak berubah. N dipilih dari tingkat penerimaan di metrik vLLM.
      - Belum terbukti: memori KV Gemma 4 di 262K pada vLLM.
- [x] (belum diuji di GPU) MTP Gemma di llama.cpp: preset Dark-Gemistry GGUF memakai GGUF drafter assistant (`--spec-type draft-mtp`
      + file drafter). Flag persisnya dicek di versi llama.cpp yang dikunci.
- [x] Cegah konteks meluap: perkirakan token pesan baru (karakter/3 + 1500 per gambar) sebelum melewati
      pengukuran token.
- [x] Kunci versi: llama.cpp per tag rilis, model HF per revisi commit, dependency Python.
- [x] Migrasi `user_version`; impor database lama (skema sekarang) ke skema baru.
- [x] Server OpenAI palsu + tes dasar (stream, tool call, tokenize).
- [x] **Bug:** `max_context()` dibaca ulang setiap Start / setiap giliran.
- [x] Header menampilkan model yang sedang jalan; pesan error tidak lagi menyebut "vLLM" untuk llama.cpp.
- [x] Hasil tool lama dipangkas dari prompt (aslinya tetap di database).
- [x] Metadata per pesan (model, quant, sampler, seed, ctx, YaRN).
- [x] Lihat prompt: prompt persis + jumlah token per bagian.
- [x] Pulih dari crash: jawaban parsial disimpan berkala (`status=partial`) dan bisa dilanjutkan.
- [x] Antrian pesan saat model masih menjawab.
- [x] `wiki_search` / `wiki_read` (API Wikipedia); browser Camoufox dibiarkan menyala di antara pencarian.
- [x] Sel backup: field token HF (tersembunyi, hanya di memori kernel; kalau kosong pakai env `HF_TOKEN`),
      repo private, jeda, "Backup sekarang", "Pulihkan terbaru"; hanya jalan kalau ada perubahan; snapshot
      via SQLite backup API; simpan N terakhir. Token tidak pernah ditulis ke database, disk, atau backup.

### Tahap 1 — UI baru + RP dasar
- [x] UI gaya ChatGPT: sidebar (cari, cerita → chat, status backup, Simpan/Muat), bar atas (model + quant +
      konteks, level thinking, indikator konteks, jam dunia, ikon Compact / Studio / Pengaturan), laci
      pengaturan dengan tab Chat | Cerita | Memory | Sampler | Backup.
- [x] Pesan: bubble kanan untukmu, jawaban model selebar kolom; tombol saat kursor di atas: salin, edit,
      jawab ulang, lanjutkan, hapus, ‹ 1/3 ›; tool tampil sebagai chip; titik compaction jadi garis pemisah
      yang bisa diklik.
- [x] Kolom ketik bentuk pil: lampiran, chip author's note, tombol kirim/stop bundar.
- [x] Responsif di layar sempit (sidebar jadi laci).
- [x] Ikon Lucide inline, renderer markdown sendiri + DOMPurify 3.2.4 disimpan di sel (bukan marked: span dialog dan avatar pembicara bergantung pada renderer sendiri), tema ikut dark/light marimo.
- [x] Tipografi RP: 16px, jarak baris 1.7, maks ~72 karakter; terjemahan dalam kurung setelah dialog bahasa
      target ditampilkan redup dan miring (aturannya dari kartu Gaya).
- [x] **Scroll:** berhenti menempel saat kamu menggulung ke atas (wheel/sentuh/keyboard), menempel lagi
      hanya di dasar atau lewat tombol; gulungan buatan widget tidak dihitung; `overscroll-behavior: contain`.
- [x] **Thinking:** kotak hanya mengikuti teks baru selama kamu belum menggulung di dalamnya; tombol
      "ikuti" dan "tampilkan penuh"; tidak lagi menutup otomatis (pengaturan: terbuka / tertutup /
      tertutup setelah selesai); durasi + token; thinking lama tetap bisa dibaca dan dicari walau sudah
      dibuang dari prompt.
- [x] Render bertahap: pesan ditambahkan, bukan digambar ulang; 150 pesan terakhir + "muat sebelumnya".
- [x] Pohon pesan: reroll + geser versi, edit, lanjutkan, hapus, cabang dari sini + pohon cabang.
- [x] Ganti nama chat.
- [x] Per chat: slider sampler (default dari card model, tombol reset, seed, max_tokens), author's note, panjang
      balasan, level thinking (dikunci saat chat dibuat).
- [x] OOC `((...))` / `/ooc`: dipisah dari cerita, tidak masuk ringkasan, tidak dibalas sebagai tokoh.
- [x] Slash command: `/ooc`, `/note`, `/reroll`, `/continue`, `/bab`, `/ingat <kata>`, `/impersonate`, `/studio`.
- [x] Penanda bab + daftar isi.
- [x] Pin pesan.
- [x] Cari di semua chat dari UI, loncat ke pesan.
- [x] Komponen UI format game: panel status tetap (bar statistik, +/− dengan alasan), panel Dunia yang bisa
      dilipat, kartu pilihan selebar kolom (klik kirim / pensil edit), tombol lompat waktu.

### Tahap 2 — Kartu dan Studio
- [x] Enam jenis kartu + skema status, semua sebagai data; editor skema; form yang dibangkitkan dari skema.
- [x] Perpustakaan kartu per jenis, avatar, versi.
- [x] Kartu Dunia dengan lore (`lore_entries`), garis waktu (`timeline`), definisi statistik, tanda berbasis
      dunia nyata.
- [x] Perakit prompt otomatis dari kartu (bagian 3); kolom system prompt manual pindah ke pengaturan lanjutan.
- [x] Tautan cerita/chat ↔ kartu; kartu inti beku, detail ditempel saat tokoh muncul; `card_read`.
- [x] Impor/ekspor `qcard` (kartu Dunia membawa lore, garis waktu, buku fakta); importer SillyTavern V2/V3
      (JSON + PNG) via mapping.
- [x] Studio (semua fitur di bagian 4), termasuk riset ke buku fakta dan cek anakronisme.
- [x] `/studio` dan `((ubah: ...))` di tengah RP, berlaku di epoch berikutnya atau lewat "terapkan sekarang".
- [x] Pilih pesan pembuka saat chat baru dibuat.
- [x] Lore terpicu kata kunci dari 2 pesan terakhir.

### Tahap 3 — Memory, buku fakta, compaction
- [x] Buku cerita (canon) per cerita + snapshot beku + perubahan sementara. Batas ukuran supaya prompt tetap
      ramping: profil user + memory lingkup user ~2K token, buku cerita ~12K token, kartu inti ~1-1.5K per tokoh.
- [x] Compaction tahap 1 yang sudah ada tetap dipakai: di 90% konteks, thinking dan lampiran giliran lama
      dibuang dulu; kalau sudah di bawah 60%, berhenti tanpa meringkas. 3 giliran user terakhir selalu utuh.
- [x] Status tokoh (skema `status.v1`), diperbarui model lewat tool, ditempel sementara.
- [x] Daftar "jangan pernah lupa".
- [x] Memory berlingkup (user / card / story / chat), `memory_update`, dedup yang mengembalikan kandidat,
      catatan memory + undo.
- [x] Buku fakta: tabel `facts` + FTS, `fact_lookup`, `fact_save`, fakta relevan ditempel sementara.
- [x] 10 memory teratas sementara (FTS dulu; hybrid di tahap 7): stopword ID/DE/EN, minimal 2 kata cocok,
      maksimal 500 karakter per memory, lewati yang sudah ada di snapshot, entri ringkasan tidak ikut.
- [x] Compaction: simpan memory dulu → ringkasan per potongan ~100K token (bab jadi batas potongan) →
      cek nama yang hilang → kronik bertingkat.
      - Budget per potongan `min(32768, ctx/16)`: 512K dan 1M → 32K, 262K → 16K. `max_tokens` = budget +
        jatah thinking, karena thinking tetap nyala supaya kwargs sama.
      - Kronik maksimal ~25% konteks (512K → ~128K). Kalau lewat, potongan paling lama dipadatkan jadi era.
      - Request ringkasan memakai `tools` + kwargs yang sama dan `tool_choice: "none"`.
      - Ringkasan kosong = error yang tampil.
- [x] Format ringkasan: dibuka `## Inti` (maksimal ~200 kata), lalu tujuan dan preferensi, tokoh dan status,
      kronologi per rentang `#` (dengan jam dunia), fakta/angka/nama, kutipan penting (dialog disalin persis),
      urusan belum selesai. Hanya bagian Inti yang masuk memory; ringkasan lengkap tetap di `summaries`.
- [x] Pesan yang di-pin disalin persis ke "momen tersemat" saat masuk wilayah ringkasan.
- [x] Lanjutkan di chat baru (cerita yang sama, kronik + 2-3 giliran terakhir).
- [x] Baca lintas chat: `history_read(chat_id, ...)`, `summary_read(chat_id)`.
- [x] Hapus chat membersihkan memory lingkup chat, snapshot, dan salinan ringkasan.

### Tahap 4 — Realisme dan dunia yang hidup
- [x] Skema `gm.v1` dan `style.v1` lengkap dengan aturan realisme, frasa terlarang, dan checklist thinking.
- [x] Jam dunia + `world_advance`.
- [x] Dadu: `roll(kejadian, peluang)`, RNG kode, hasil tampil di chat, `dice_log`.
- [x] Agenda NPC (tujuan, rencana, rutinitas) + update rencana lewat tool.
- [x] Batas pengetahuan: `known_to` di kejadian dan rahasia; hanya yang diketahui tokoh yang ditempel untuknya.
- [x] Statistik `number` + `rate_per_hour` dihitung kode setiap jam dunia maju.
- [x] Garis waktu dipicu jam dunia.
- [x] World tick saat GPU diam + batal saat kamu mengetik + ringkasan "Selama kamu pergi"; skala default
      1 jam nyata = 1 jam cerita, diatur di kartu GM.
- [x] Format RP terstruktur (bagian 6), pilihan format prosa / game di kartu GM:
      - panel status dihitung kode + `status_update` + `status_events` yang mengikuti pohon pesan;
      - panel Dunia: jam, cuaca dari tabel iklim + RNG ber-seed, berita/gosip dari `world_events`;
      - lompat waktu: jam maju → statistik → world tick → narasi transisi;
      - pilihan sebagai tugas sampingan: jumlah masalah/pilihan, 1-2 kalimat panjang, daftar "jangan ulangi",
        cek kemiripan, kategori wajib, cek jumlah kalimat, frekuensi dari kartu GM.

### Tahap 5 — Kualitas, fakta, bahasa
- [x] Deteksi pengulangan (n-gram di beberapa balasan terakhir) → author's note sementara "hindari frasa X".
- [x] Deteksi frasa terlarang dari kartu Gaya.
- [x] Panjang narasi: target acak dalam rentang kartu Gaya tiap giliran, hitung paragraf + kalimat setelah
      selesai, kurang → lanjutkan otomatis; preset pendek / sedang / panjang (panjang = 5-10 × 5-10); `max_tokens`
      default mengikuti preset (panjang ≥ ~6K + jatah thinking).
- [x] Pemeriksa "jangan bertindak untukmu": tandai narasi yang melanjutkan aksi atau ucapan pemain melebihi
      yang ditulis, tawarkan reroll.
- [x] Penjaga format: narasi pindah bahasa, terjemahan dobel, dialog bahasa target terpecah → perbaiki
      otomatis (yang aman) atau tawarkan reroll.
- [x] Pemeriksa fakta otomatis dengan mode mati / latar belakang (default) / ketat; ⚠ + koreksi + sumber.
- [x] Mode belajar bahasa (bahasa target dari kartu Gaya): terjemahan tersembunyi sampai disorot, klik
      kalimat untuk tata bahasa + kosakata (tugas sampingan dengan awal prompt yang sama), daftar kosakata,
      flashcard dengan jadwal ulang.

### Tahap 6 — Ganti model, group chat, ekspor
- [x] Ganti model dari widget: daftar preset, Start/Stop, status READY, reset konteks + sampler. Peringatan:
      ganti model berarti seluruh konteks diproses ulang (bisa beberapa menit di 400K token).
- [x] Group chat: banyak kartu tokoh.
      - **Default: mode narator GM.** Satu balasan bisa berisi beberapa tokoh; model (sebagai GM) memutuskan
        siapa yang bereaksi berdasarkan agenda, posisi, dan batas pengetahuan tiap tokoh. Satu kali generate
        per giliran, cache tetap aman.
      - Paksa pembicara: klik avatar atau tulis `@nama`, berlaku untuk giliran itu saja.
      - Mode opsional "satu tokoh per balasan": model memilih pembicara berikutnya, tiap tokoh generate sendiri
        (lebih lambat karena beberapa kali generate per giliran).
      - Avatar dan nama tokoh ditampilkan per bagian balasan.
- [x] Ekspor cerita ke Markdown / HTML / EPUB tanpa OOC dan thinking, dengan bab.

### Tahap 7 — Embedding dan uji ingatan
- [x] Embedder **Qwen3-Embedding-0.6B** (keputusan; 4B tetap bisa dipilih di Setelan) lewat `llama-server --embedding --pooling last` di port +3.
      Binary llama.cpp dipasang otomatis juga di mode vLLM; `--gpu-memory-utilization` vLLM turun dari 0.94 ke
      0.92 saat embedder aktif; query memakai awalan instruksi sesuai card Qwen3-Embedding.
- [x] Vektor float16 di tabel SQLite, pencarian numpy, gabung dengan BM25 lewat RRF (k=60); fallback FTS.
- [x] Yang di-embed: memory, buku cerita, lore, buku fakta, kartu, ringkasan, kejadian dunia, potongan pesan
      (~400 token, overlap 80). Embed ulang otomatis setelah Muat.
- [x] Tombol uji ingatan: pertanyaan otomatis tentang detail awal cerita, dinilai terhadap arsip mentah.
- [x] Compaction otomatis saat diam, mulai di 75% (giliran chat sendiri memadatkan di 90%), dengan progres token
      dan batal bersih saat kamu mengirim pesan.

### Tahap 8 — Kontinuitas tokoh dan cerita
Celah yang ditemukan setelah v2 jalan, diurutkan dari dampak terbesar. "Dicek di kode" = sudah dipastikan
dengan membaca kodenya.

**Cabang dan chat**
- [x] Memory dan buku cerita ikut cabang (dicek di kode). Tabel `memories` tidak menyimpan `message_id`, dan
      `canon_set` juga tidak; status dan kejadian dunia sudah ikut cabang. Setelah reroll, swipe, atau edit, fakta
      dari cabang yang dibuang masih terbaca. Perbaikan: simpan posisi cabang di setiap memory dan perubahan buku
      cerita, saring menurut jalur aktif seperti kejadian dunia.
- [x] Dua chat dari cerita yang sama tidak saling mencemari. Buku cerita dan memory `story` disimpan per cerita;
      dua jalan alternatif di dua chat membaca fakta satu sama lain.

**Ingatan per tokoh**
- [x] Buku cerita tetap satu: kebenaran objektif cerita, hanya narator yang tahu semuanya.
- [x] Setiap tokoh punya ingatan sendiri, termasuk tokohmu. Isinya apa yang ia tahu atau yakini. Tiap catatan:
      - jenis: fakta, rahasia, pendapat, perasaan ke seseorang, janji, salah paham;
      - sumber: lihat sendiri, diberi tahu oleh siapa, gosip;
      - benar/keliru dibanding buku cerita (tokoh bisa percaya hal yang salah, dibohongi, gosip melenceng);
      - jam dunia dan posisi di cabang;
      - bobot penting.
- [x] Cara pengetahuan masuk:
      - menyaksikan: kejadian di adegan otomatis masuk ke ingatan semua tokoh yang hadir (sekarang model harus
        ingat menulis `known_to` sendiri);
      - diberi tahu: model mencatat "A memberi tahu B soal X", termasuk kalau isinya bohong;
      - gosip: saat dunia berjalan, kabar menyebar antar NPC di tempat yang sama dan `known_to` ikut bertambah;
      - compaction: saat bagian lama diringkas, siapa-tahu-apa ikut diambil (sekarang ringkasan hanya sudut
        pandang narator).
- [x] Kehadiran tokoh ditentukan dari lokasi yang sama di status (dicek di kode). Sekarang `present_characters`
      hanya memasukkan tokoh pertama plus tokoh yang namanya disebut di pesanmu atau balasan terakhir; NPC yang
      hadir tapi tidak disebut kehilangan status dan pengetahuannya di giliran itu.
- [x] Tiap giliran, tokoh yang hadir mendapat ingatan yang paling relevan (kemiripan isi + bobot penting), bukan
      5 kejadian terakhir (dicek di kode). Narator diberi aturan: tokoh hanya bertindak berdasarkan isi kepalanya.
- [x] Pengetahuan tokohmu dicatat terpisah dari pengetahuanmu sebagai pemain, supaya tokohmu tidak "tahu"
      rahasia yang tidak pernah ia pelajari di cerita.
- [x] Memory tidak bocor ke NPC: memory punya pemilik dan daftar siapa yang tahu.
- [x] Lore rahasia punya daftar siapa yang tahu, supaya tidak terbaca semua NPC begitu kata kuncinya muncul.
- [x] Memory `card` (ikut ke semua cerita) tetap ada, hanya untuk hal yang benar lintas cerita.
- [x] UI: di kartu tokoh, dalam cerita, tab Ingatan untuk melihat, mengedit, dan menghapus, dengan sumber dan
      tanda "keliru".
- [x] Usulan perubahan kartu: setiap epoch atau compaction, model mengusulkan perubahan kartu (hubungan yang
      berubah, sifat yang bergeser); kamu yang menyetujui.

**Keadaan dunia dan tokoh**
- [x] Pemeriksa keadaan setelah tiap giliran, di latar seperti cek fakta (dicek di kode: waktu hanya maju kalau
      model memanggil `world_advance`, status hanya berubah kalau model memanggil `status_update`). Ia membaca
      narasi lalu mengisi yang terlupa: waktu berlalu, makan, luka, barang berpindah tangan; ditambah perkiraan
      waktu minimum per giliran dari panjang adegan.
- [x] Waktu berlaku juga untuk NPC: luka sembuh setelah sekian jam, mood mereda, jadwal rutin tokoh menentukan di
      mana ia berada menurut jam dunia. Sekarang laju per jam hanya untuk statistik pemain.
- [x] Keadaan tokoh yang eksplisit: hidup, mati, pergi, ditahan.
- [x] Daftar lokasi dengan waktu tempuh di kartu Dunia; jam dunia maju sesuai perjalanan.
- [x] Riwayat hubungan antar tokoh: skor plus alasan setiap perubahan, ditampilkan di panel. Sekarang sikap cuma
      teks bebas.
- [x] Bobot penting untuk memory, supaya di cerita 1 juta token detail remeh tidak menyingkirkan fakta penting
      saat pemanggilan 10 teratas.

**Cek kontinuitas**
- [x] Tugas sampingan seperti cek fakta, dengan mode ketat yang menulis ulang balasan. Menangkap:
      - NPC yang tahu hal yang tidak ada di ingatannya / `known_to`-nya;
      - tokoh yang muncul padahal sedang di lokasi lain;
      - tokoh yang sudah mati tapi bicara;
      - narasi yang tidak mengikuti hasil dadu.
- [x] Pengecekan suara NPC di latar: gaya bicara dibandingkan dengan contoh ucapan di kartunya; ditandai kalau
      melenceng.

**Panel dan dadu**
- [x] Panel "Tokoh lain" hanya menampilkan yang bisa diamati tokohmu (lokasi, raut wajah) (dicek di kode: sekarang
      menampilkan semua status NPC termasuk rencana, sikap, dan apa yang mereka tahu). Tampilan lengkap di balik
      tombol mode GM.
- [x] Dadu berbasis skill (dicek di kode: peluang sekarang ditentukan model sendiri). Kartu persona dan tokoh diberi
      skill dan atribut; peluang dihitung kode dari skill, tingkat kesulitan, dan pengubah seperti luka atau lelah.

**Benang cerita**
- [x] Daftar benang cerita di buku cerita: janji, misteri, petunjuk, utang, dendam. Tiap benang punya status
      terbuka/selesai dan tenggat di jam dunia; GM diingatkan kalau ada benang yang lama atau jatuh tempo. Sekarang
      "Alur yang direncanakan" di skenario cuma teks.
- [x] Janji temu ("ketemu jam 7 di Odeonsplatz") dicatat sebagai benang bertenggat; saat dunia berjalan, akibatnya
      ikut terjadi (NPC menunggu, kesal, pergi).

**Selesai (Tahap 8.1-8.8).** Catatan pelaksanaan: ingatan per tokoh disimpan di tabel `knowledge` (bukan memory dengan daftar pemilik) dan tabnya ada di Cerita, bukan di kartu; pengecekan suara NPC jadi bagian cek kontinuitas; luka sembuh dan suasana hati mereda lewat world tick, bukan timer pasti.

**Urutan kerja:** cabang untuk memory/buku cerita → ingatan per tokoh + kehadiran dari lokasi → pemeriksa keadaan
→ panel → cek kontinuitas → benang cerita → dadu berbasis skill → sisanya.

### Review kedua — perbaikan celah (selesai, belum dites di GPU)

Lima pemeriksa (data, engine, konkurensi, UI, kualitas RP). Yang berupa bug diperbaiki; yang berupa fitur baru
dicatat di bawah sebagai usulan.

- [x] Data: id pesan/chat tidak pernah dipakai ulang; hapus pesan/chat ikut membersihkan pengetahuan tokoh, benang,
      hubungan, perubahan buku cerita, memory, dan vektornya; "lanjut di chat baru" menyalin keadaan sehingga tidak
      bergantung pada chat lama; catatan "menunggu epoch" dan lupa/ubah memory mengikuti cabang; edit manual di UI
      berlaku untuk seluruh chat (tidak hilang saat reroll); Lanjutkan pada balasan lama ikut membawa efek gilirannya.
- [x] Engine: pesan OOC tidak lagi diperlakukan sebagai giliran cerita; group satu-tokoh memberi instruksi pembicara
      di setiap putaran, 1-3 paragraf, dan pemeriksaan per bagian tokoh; tulis ulang mode ketat berhenti setelah
      menulis ulang dan memakai hasil dadu yang sama; satu penerjemah nama untuk semua tool ("Lotte", "pemain", nama
      persona); lokasi awal skenario masuk ke status; benang yang sama tidak dibuka dua kali; kehadiran menurut tempat
      (bukan potongan kata); tugas sampingan memakai setelan thinking yang sama dengan chat (prefix sama, cache kena);
      compaction menyisakan ±25% konteks sebagai giliran utuh dan epoch baru tetap dibuat kalau gagal di tengah.
- [x] Konkurensi: loop diam tidak bisa kehilangan sinyal batal atau berjalan saat Load; hapus chat menunggu tugas
      latar; compaction diam tanpa kemajuan menunggu 10 menit; waktu AFK tidak dimajukan dua kali.
- [x] UI: perintah tidak hilang saat kernel sibuk (nomor urut + ack); dialog berisi tautan tidak bisa menyuntik
      atribut; pilihan embedder menampilkan yang berjalan dan minta konfirmasi sebelum ganti; tab Cerita ikut cabang
      aktif; teks yang sedang diketik tidak tertimpa; avatar per kartu; tombol Mode GM selalu ada; daftar bab urut.
- [x] Kualitas RP: aturan yang bertentangan dirapikan (Persona boleh mengizinkan, tokoh tahu isi kartunya sendiri,
      penanda rahasia, cara roll); target panjang kalah dari titik berhenti; pilihan ditulis sebagai "Aku …" dan hanya
      di balasan terakhir; frasa berulang dihindari bergulir (kecuali contoh ucapan kartu); Studio melihat semua field.

**Fitur dari usulan review kedua (selesai, belum dites di GPU):**
- [x] Cek pembuka berulang: lima kata pertama balasan dibandingkan dengan empat giliran sebelumnya (tiga kata awal
      sama, tiga kata isi sama, dua kata awal sama dengan dua giliran terakhir, atau kata pertama sama dengan empat
      giliran terakhir). Balasannya diberi tanda, dan tiga giliran berikutnya diminta memulai dengan cara lain.
- [x] Aturan Gaya tambahan tidak ditulis ke kartu: form Gaya punya tombol "Tambah saran aturan" yang memasukkan
      empat saran ke kolom Aturan tambahan; kamu ubah atau hapus dulu, lalu Simpan sendiri.
- [x] Default panjang 4-7 × 4-7 kalimat dan AFK mati (skala 0). Kartu "Gaya RP default" dan "GM membumi" yang masih
      memakai nilai lama ikut pindah sekali (versi lama tetap bisa dipulihkan); nilai yang sudah kamu ubah tidak disentuh.
- [x] Thinking live tertutup di chat cerita; sekali kamu buka, balasan berikutnya ikut terbuka. Beberapa panggilan
      tool dalam satu balasan dilipat jadi satu baris ("3 alat …").
- [x] Hapus ingatan tokoh hanya berlaku di cabang aktif (sejak pesan pemain terakhir, jadi reroll balasan tidak
      memunculkannya lagi) dan bisa dipulihkan dari daftar "Dilupakan di cabang ini". Laci menyimpan teks yang sedang
      diketik saat digambar ulang; selama kursor di kolom, gambar ulang menunggu sampai fokus pindah.

### Review ketiga — RP yang buyar dan tidak natural (selesai, belum dites di GPU)

- [x] Catatan sistem tiap giliran jadi latar, bukan daftar: baris pembuka "acuan konsistensi, bukan daftar yang harus
      disebut"; benang cerita hanya yang mendesak atau terkait adegan (+jumlah sisanya); perasaan tanpa angka, alasan
      hanya kalau baru; detail kartu penuh saat tokoh masuk adegan, selama ia tetap di adegan hanya ketakutan, relasi,
      dan pengetahuannya. Catatan ditaruh di awal pesan, tulisan pemain paling akhir ([Pesan pemain]).
- [x] Status basi: mood dan rencana yang dicatat lama (2 dan 6 jam waktu dunia) diberi umur "bisa sudah berubah";
      pemeriksa keadaan memperbarui mood/rencana yang berubah atau mereda.
- [x] Panjang: target berupa jumlah kalimat total; ucapan tokoh boleh jadi paragraf pendek; instruksi kerangka per
      paragraf dibuang. Tambal paragraf hanya untuk balasan di bawah separuh target dan tidak berakhir dengan pertanyaan
      atau ucapan tokoh (titik serah).
- [x] Dunia di luar layar bergerak di latar setiap 4 jam waktu dunia (GM: "Dunia di luar layar bergerak tiap", 0 = mati);
      tokoh di adegan pemain tidak diubah; pesan baru menghentikannya dan ia diulang nanti. Lompat waktu dan AFK
      menghitung rentang yang sama, jadi tidak dobel.
- [x] Kejadian dunia dan garis waktu baru dianggap diketahui pemain kalau balasan menyebutnya (atau setelah 3 kali
      ditawarkan); sebelumnya langsung hilang walau tidak diceritakan.
- [x] Narator fokus bercerita: kalau pemeriksa keadaan aktif, prompt epoch baru menyerahkan pengetahuan tokoh,
      hubungan, dan benang cerita ke pemeriksa. Chat lama ikut setelah epoch berikutnya (compaction/Terapkan sekarang).
- [x] Cache: pemeriksa keadaan, world tick, dan flush compaction mengirim daftar tool lengkap chat (yang boleh dipakai
      dibatasi di sisi engine), jadi prefix prompt sama dengan giliran dan riwayat tidak diproses ulang.

### Pamor dan momen kenalan (selesai, belum dites di GPU)

- [x] Field Pamor (bintang / terkenal / dikenal di lingkungannya / biasa) dan "Dikenal karena" di kartu Tokoh dan Persona.
- [x] Pemeran besar (lebih dari 12 tokoh): hanya bintang dan terkenal yang kartu intinya di system prompt; sisanya satu
      baris di "Tokoh lain", dan kartu intinya ikut catatan sistem saat tokoh itu muncul atau disebut.
- [x] "Dikenal umum": nama, peran, dan reputasi tokoh bintang/terkenal (dan tokoh pemain kalau ia terkenal) diketahui
      semua orang walau belum kenalan; detail pribadi dan rahasia tidak.
- [x] Momen kenalan: tokoh di adegan yang belum punya ingatan "kenalan" atau ingatan yang menyebut nama pemain diberi
      tanda "belum tercatat kenal" (tidak tahu nama pemain kecuali diperkenalkan; kartu/cerita yang menyatakan sudah
      kenal tetap berlaku). Pemeriksa keadaan mencatat pertemuan pertama (kind "kenalan": tahu nama atau belum, kesan
      pertama, cara bertemu) dan relasi awal. Per chat dan per cabang.
- [x] Usulkan pamor: model membaca kartu tokoh cerita per 10 kartu dan mengusulkan pamor + "dikenal karena"; tabel bisa
      diubah lalu Simpan semua (versi kartu baru, bisa dipulihkan). Batas saran bintang 5, terkenal 10 (ditandai kalau lewat).
- [x] Tab Cerita: "Top tokoh (pamor)" dan "Atur semua". World tick mendahulukan agenda tokoh paling dikenal dan
      menjadikan mereka bahan gosip.

---

## 9. Tes

- Tes unit dengan server OpenAI palsu: stream, tool call, crash di tengah jawaban, antrian.
- **Tes stabilitas prefix:** awal prompt identik antar giliran dalam satu epoch, termasuk setelah tugas
  sampingan (world tick, pemeriksa fakta, impersonate).
- Tes compaction: potongan, budget, ringkasan kosong, pin, bab, cek nama.
- Tes migrasi: database dari versi sekarang dimuat dan dipakai.
- Tes kartu: skema → form → prompt untuk keenam jenis, field tidak dikenal tetap ada, impor V2/V3, ekspor
  kartu Dunia membawa lore/garis waktu/fakta.
- Tes dunia: jam maju → statistik dihitung, garis waktu terpicu, `known_to` dihormati, dadu memakai RNG.
- Tes fakta: `fact_lookup` sebelum search, `fact_save` setelah search, mode pemeriksa fakta.
- Tes format game: status diputar ulang dengan benar setelah reroll / edit / cabang; lompat waktu menghitung
  statistik dan memicu world tick; cuaca sama untuk cerita + tanggal yang sama; pilihan yang mirip dibuang;
  penghitung paragraf/kalimat (termasuk kutipan dan singkatan); narasi kurang panjang memicu lanjutkan.
- Tes riwayat: blok status, dunia, dan pilihan tidak pernah masuk riwayat prompt.
- Tes generik: cerita contoh non-WW1 (misalnya fantasi) jalan tanpa perubahan kode.
- UI: `tests/ui/harness.html` dengan model palsu, screenshot desktop + mobile di browser bawaan.
- Smoke test GPU di Molab tiap akhir tahap (olehmu), dengan daftar langkah yang saya siapkan.

---

## 10. Risiko

| risiko | penanganan |
|---|---|
| Ringkasan per potongan lambat (32K × 4 potongan: ~25-55 menit di 512K) | compaction saat diam, progress di UI, bisa dibatalkan |
| Ganti model / edit pesan lama / "terapkan sekarang" membuat konteks diproses ulang | peringatan di UI sebelum aksi |
| Balasan panjang (5-10 × 5-10) makan waktu dan konteks: ~30-100 detik, 512K penuh setelah ~120-150 giliran | MTP, compaction saat diam, panel/pilihan tidak masuk riwayat |
| Balasan panjang cenderung bertele-tele atau bertindak untuk pemain | aturan kartu GM, detektor pengulangan/frasa, pemeriksa "jangan bertindak untukmu" |
| World tick, pilihan, dan pemeriksa fakta memakai GPU | hanya saat diam / latar belakang, dibatalkan saat kamu mengetik |
| Search kena CAPTCHA | Wikipedia API dulu, Camoufox sebagai cadangan, buku fakta sebagai cache |
| VRAM tidak cukup untuk LLM + embedder | vLLM turun ke 0.92 saat embedder aktif; embedder 0.6B hanya ~1GB |
| Template chat model berbeda (Gemma vs Qwen) membaca kwargs berbeda | kwargs per preset, dites lewat "Lihat prompt" |
| Skala pekerjaan besar | tahap kecil, masing-masing bisa dipakai sendiri |

---

## 11. Di luar rencana ini

- Memasukkan 40B Build2 ke notebook benchmark (`rp_ab_test_molab.py`, repo melebsdbs) dengan thinking nyala.
- Preset gembrain-31b-heretic: diusulkan, belum diminta.
- Varian Dark-Gemistry (@base / @vendor / @vendor-prompt) melawan Qwen abliterated di benchmark: diusulkan, belum diminta.
- Suara untuk dialog (TTS): diusulkan, tidak ikut kamu pilih.
- Membuat gambar: dibuang atas permintaanmu.

## 12. Keputusan

- Group chat: default mode narator GM (model memilih siapa yang bereaksi), bisa dipaksa lewat avatar / `@nama`.
- Embedder: Qwen3-Embedding-0.6B.
- Tidak ada keputusan yang masih terbuka.

### Compaction, bahasa Inggris, dan level bahasa target (selesai, belum dites di GPU)

- [x] Compaction memakai ukuran prompt giliran berikutnya yang sebenarnya (total server ikut menghitung thinking yang
      dibuang prompt berikutnya). Jalan di 80%, atau lebih awal kalau prompt + ruang jawaban (thinking + teks) lewat
      95% konteks. Chat grup cukup menyisakan 1 pesan pemain utuh. Kalau tidak bisa jalan, ada pemberitahuan alasannya.
- [x] Narasi bahasa Inggris dipaksa: bahasa narasi disebut tiap giliran; balasan yang jelas berbahasa lain ditulis ulang
      sekali. Ringkasan, catatan pemeriksa, dan kejadian dunia ikut bahasa narasi. Kartu Gaya default pindah ke English
      dengan terjemahan bahasa Inggris (sekali, hanya kalau nilainya masih default lama).
- [x] Level bahasa target tokoh pemain: baris skill di Persona (misalnya "Bahasa Jerman, 55") + poin dari bermain
      (+1 menulis bahasa itu, +2/+0,5 roll berhasil/gagal, +3 per minggu waktu dunia). Level A1-C1 menentukan panjang dan
      kerumitan ucapan tokoh lain; SEMUA kalimat selalu diterjemahkan. Ucapan terlalu pendek atau tanpa terjemahan
      ditandai dan 3 giliran berikutnya diingatkan. Dadu memakai level yang sudah naik; naik level diumumkan.
- [x] "Lihat arti" dalam bahasa Inggris.
- [x] Tampilan aplikasi dalam bahasa Inggris: tombol, tab, form kartu (label skema), toast, status, pemberitahuan, kontrol
      notebook. Nilai data tetap (fakta, bintang, "2 jam", dll.) dan ditampilkan dengan label Inggris. Perintah /chapter,
      /remember, /check ditambahkan di samping /bab, /ingat, /cek. Instruksi ke model tetap bahasa Indonesia.
