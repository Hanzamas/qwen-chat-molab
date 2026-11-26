import marimo as mo

mo.md(r"""
# Qwen Chat RP

Chat dan roleplay panjang (sampai 512K/1M token) di GPU molab, dengan kartu (tokoh, persona, dunia, skenario,
gaya, GM), Studio untuk menyusun kartu sambil ngobrol, memory berlingkup, buku fakta, dunia yang tetap
berjalan, dan compaction yang tidak melupakan detail.

1. Nyalakan GPU lewat *notebook specs*, lalu **Run all**.
2. Klik **Install** (sekali per sesi).
3. Pilih model, klik **Start**, tunggu status `READY`.
4. Ngobrol di jendela chat paling bawah. Model juga bisa diganti dari dalam chat.

Semua data (chat, kartu, memory, fakta) ada di satu file SQLite. Isi workspace molab hilang saat notebook mati:
pakai **Backup ke Hugging Face** atau tombol **Simpan** di chat.
""")
