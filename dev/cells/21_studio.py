STUDIO_SYSTEM = """Kamu desainer cerita dan karakter di Studio. Tugasmu menyusun kartu bersama pengguna lewat obrolan:
Dunia (dengan lore, garis waktu, statistik), Persona (pengguna sendiri), Tokoh, Skenario, Gaya, dan GM.

Cara kerja:
- Bertanya per putaran, sedikit demi sedikit: dunia, lalu persona, tokoh, skenario, gaya, GM. Usulkan isi yang konkret dan
  menarik (termasuk kontradiksi pada tokoh), lalu isi kartu dengan card_draft_update. Jangan menunggu semuanya lengkap.
- Kartu yang sedang disusun dan isinya ada di "Catatan sistem" pada pesan terakhir pengguna.
- Field kartu mengikuti skemanya. Untuk field list kirim array, untuk table kirim array of array sesuai kolom.
- Lore, garis waktu, dan fakta: lore_add, timeline_add, fact_save. Kalau dunia berbasis dunia nyata, riset dulu dengan
  wiki_search/wiki_read/web_search dan cek anakronisme (benda, istilah, pangkat, teknologi yang belum ada di zamannya).
- Pengguna bisa meminta: lengkapi yang kosong, cek konsistensi antar kartu, uji adegan (satu paragraf pembuka dengan Gaya+GM),
  uji suara tokoh (balas 3 situasi: santai, marah, sedih), wawancara tokoh (jawab sebagai tokoh), variasi (3 alternatif untuk
  satu field), rapikan teks bebas ke format kartu, atau isi penampilan dari gambar yang dilampirkan.
- Contoh kalimat khas tokoh (speech_samples) sangat penting supaya suaranya tidak melenceng. Isi 3-5.
- Jangan pernah menulis cerita panjang di Studio kecuali diminta uji adegan."""


def STUDIO_EPHEMERAL(c):
    """Current drafts of this studio session, shown on every turn (they change, so they cannot be frozen)."""
    drafts = (c["settings"].get("studio") or {}).get("drafts") or {}
    lines = []
    for type_, ids in drafts.items():
        for cid in (ids if isinstance(ids, list) else [ids]):
            card = CARDS.get(cid)
            if not card:
                continue
            sch = CARDS.schema(card["type"])
            filled = {k for k, v in card["data"].items() if v not in (None, "", [], {})}
            empty = [f["key"] for f in sch["fields"] if f["key"] not in filled]
            lines.append(f"[kartu #{cid}, jenis {type_}]\n{CARDS.render(card, mode='all', limit=4000)}\n"
                         f"Field kosong: {', '.join(empty) or '-'}")
            if card["type"] == "world":
                lore = CARDS.lore(cid)
                if lore:
                    lines.append("Lore: " + "; ".join(e["title"] for e in lore[:40]))
                tl = CARDS.timeline(cid)
                if tl:
                    lines.append("Garis waktu: " + "; ".join(f"{e['at']} {e['title']}" for e in tl[:40]))
    schemas = {t: [f"{f['key']} ({f['type']}{', kolom ' + '/'.join(f['columns']) if f.get('columns') else ''})"
                   for f in CARDS.schema(t)["fields"]] for t in Cards.TYPE_ORDER}
    lines.append("Field per jenis kartu:\n" + "\n".join(f"- {t}: {', '.join(fs)}" for t, fs in schemas.items()))
    head = "Kartu di Studio ini:" if drafts else "Kartu di Studio ini: belum ada, buat dengan card_draft_update."
    return head + "\n\n" + "\n\n".join(lines)
