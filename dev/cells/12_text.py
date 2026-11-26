class TXT:
    """Text utilities: search queries, counting, similarity, and the RP quality checks."""

    STOP = {
        "id": set("""yang dan di ke dari ini itu dengan untuk pada adalah dalam tidak akan juga sudah saya aku kamu dia
            mereka kami kita ada atau bisa jadi karena oleh seperti tapi tetapi lalu kemudian saat ketika masih hanya
            lebih sangat apa siapa bagaimana mengapa kenapa mana sini sana begitu begini pun lagi telah belum harus
            sebuah seorang para nya ya tak tidak bukan agar supaya setelah sebelum sambil sementara hingga sampai
            antara tentang terhadap bagi tanpa namun maka jika kalau kan dong sih deh nah oh wah mu ku""".split()),
        "de": set("""der die das den dem des ein eine einer einem einen eines und oder aber ist sind war waren bin bist
            sein hat haben hatte ich du er sie es wir ihr mich dich sich mir dir ihm ihn uns euch nicht kein keine
            auch noch schon nur so wie was wer wo wann warum mit von zu im in am an auf aus bei nach für über unter
            vor dass ob wenn als um ja nein doch mal dann denn hier da""".split()),
        "en": set("""the a an and or but is are was were be been being have has had do does did i you he she it we they
            me him her us them my your his its our their this that these those of to in on at by for with from as
            not no so if then than there here what who when where why how all any can could would should will
            just very into over under about""".split()),
    }
    ALL_STOP = set().union(*STOP.values())
    ABBREV = {"z.b.", "d.h.", "u.a.", "usw.", "bzw.", "dr.", "hr.", "fr.", "mr.", "mrs.", "st.", "dll.", "dsb.",
              "dkk.", "no.", "nr.", "vs.", "etc.", "ca.", "sog.", "prof.", "sgt.", "lt.", "kpt.", "jl."}

    @staticmethod
    def words(text):
        return re.findall(r"\w+", (text or "").lower())

    @staticmethod
    def content_words(text):
        return [w for w in TXT.words(text) if w not in TXT.ALL_STOP and len(w) > 1 and not w.isdigit()]

    @staticmethod
    def fts_query(text, limit=20):
        """FTS5 OR-query of quoted content words, so punctuation never breaks MATCH. '' when nothing is left."""
        seen, out = set(), []
        for w in TXT.content_words(text):
            if w not in seen:
                seen.add(w)
                out.append(f'"{w}"')
            if len(out) >= limit:
                break
        return " OR ".join(out)

    @staticmethod
    def overlap(text, other):
        """How many distinct content words two texts share."""
        return len(set(TXT.content_words(text)) & set(TXT.content_words(other)))

    @staticmethod
    def jaccard(a, b):
        sa, sb = set(TXT.content_words(a)), set(TXT.content_words(b))
        return len(sa & sb) / len(sa | sb) if sa and sb else 0.0

    # ---------- counting ----------

    @staticmethod
    def paragraphs(text):
        t = (text or "").strip()
        if not t:
            return []
        blocks = [b.strip() for b in re.split(r"\n\s*\n", t) if b.strip()]
        if len(blocks) == 1 and "\n" in t:
            blocks = [b.strip() for b in t.split("\n") if b.strip()]
        return blocks

    @staticmethod
    def sentences(text):
        """Split into sentences. Quotes stay with their sentence; abbreviations and decimals do not split."""
        t = re.sub(r"\s+", " ", (text or "").strip())
        if not t:
            return []
        out, start = [], 0
        # A translation in parentheses right after a quote belongs to the same sentence, so "(" never opens one.
        for m in re.finditer(r"[.!?…]+[\"'”’»)]*(?=\s+[\"'“„«]?[A-ZÄÖÜ0-9]|\s*$)", t):
            end = m.end()
            piece = t[start:end].strip()
            last = piece.split(" ")[-1].lower()
            if last in TXT.ABBREV or re.search(r"\d\.\d*$", piece):
                continue
            if piece:
                out.append(piece)
            start = end
        rest = t[start:].strip()
        if rest:
            out.append(rest)
        return out

    @staticmethod
    def shape(text):
        """(paragraph count, sentences per paragraph) of a reply."""
        paras = TXT.paragraphs(text)
        return len(paras), [len(TXT.sentences(p)) for p in paras]

    # ---------- RP checks ----------

    @staticmethod
    def repeated_phrases(text, previous, n=5, min_hits=2, top=5):
        """Word n-grams of `text` that already appeared in the previous replies (min_hits times in total)."""
        def grams(s):
            w = TXT.words(s)
            return [" ".join(w[i:i + n]) for i in range(len(w) - n + 1)]
        counts = {}
        for p in previous:
            for g in set(grams(p)):
                counts[g] = counts.get(g, 0) + 1
        hits = []
        for g in dict.fromkeys(grams(text)):
            if counts.get(g, 0) + 1 >= min_hits and len(set(g.split()) - TXT.ALL_STOP) >= 2:
                hits.append(g)
        # keep the longest distinct phrases: drop grams contained in an already kept one
        kept = []
        for g in hits:
            if not any(g in k for k in kept):
                kept.append(g)
        return kept[:top]

    @staticmethod
    def banned_hits(text, phrases):
        low = (text or "").lower()
        return [p for p in phrases if p and p.lower() in low]

    @staticmethod
    def dedupe_parens(text):
        """Drop a parenthetical that repeats the one right before it, e.g. "(Iya.) (Iya)" -> "(Iya.)"."""
        parts = re.split(r"(\([^()\n]{1,300}\))", text or "")
        out, last = [], None
        for p in parts:
            if p.startswith("(") and p.endswith(")"):
                norm = re.sub(r"[\s.!?,…]+", " ", p[1:-1]).strip().lower()
                if norm == last:
                    while out and not out[-1].strip():
                        out.pop()
                    continue
                last = norm
            elif p.strip():
                last = None
            out.append(p)
        return "".join(out)

    @staticmethod
    def narration_language(text, expected):
        """Share of stopwords per language outside quotes. Returns (dominant language, shares)."""
        outside = re.sub(r"[\"“„«][^\"”“»]*[\"”»]", " ", text or "")
        outside = re.sub(r"\([^()]*\)", " ", outside)
        w = TXT.words(outside)
        shares = {lang: sum(1 for x in w if x in stop) for lang, stop in TXT.STOP.items()}
        total = sum(shares.values()) or 1
        shares = {k: v / total for k, v in shares.items()}
        dominant = max(shares, key=shares.get) if w else expected
        return dominant, shares

    @staticmethod
    def split_dialogue(text):
        """Count quote fragments followed by a short translation: the "Das..." (Itu) "...ist..." pattern.
        A fragment has an ellipsis or at most two words; a whole short sentence does not count."""
        n = 0
        for m in re.finditer(r"[\"“„]([^\"”“]{0,40})[\"”]\s*\(([^()]{1,30})\)", text or ""):
            inner = m.group(1).strip()
            if "..." in inner or "…" in inner or len(inner.split()) <= 2:
                n += 1
        return n

    ACTS_FOR_USER = re.compile(
        r"\b(kamu|Kamu|anda|Anda)\s+(berkata|bilang|menjawab|bertanya|berteriak|berbisik|mengatakan|memutuskan|"
        r"setuju|tersenyum dan berkata)\b|\b(katamu|ucapmu|jawabmu|tanyamu|bisikmu|teriakmu)\b|"
        r"\byou (say|said|reply|replied|ask|asked|decide|decided)\b", re.I)

    @staticmethod
    def acts_for_user(text, persona_name=""):
        hits = [m.group(0) for m in TXT.ACTS_FOR_USER.finditer(text or "")]
        if persona_name:
            hits += re.findall(rf"\b{re.escape(persona_name)}\s+(?:berkata|menjawab|bertanya|says|said)\b", text or "")
        return hits

    # ---------- user input ----------

    SLASH = ("ooc", "note", "reroll", "continue", "bab", "ingat", "impersonate", "studio", "cek")

    @staticmethod
    def parse_input(text):
        """-> {"kind": "slash"|"ooc"|"text", "cmd", "arg", "text"}"""
        t = (text or "").strip()
        m = re.match(r"^/(\w+)\s*(.*)$", t, re.S)
        if m and m.group(1).lower() in TXT.SLASH:
            cmd = m.group(1).lower()
            if cmd == "ooc":
                return {"kind": "ooc", "text": m.group(2).strip()}
            return {"kind": "slash", "cmd": cmd, "arg": m.group(2).strip()}
        if t.startswith("((") and t.endswith("))"):
            return {"kind": "ooc", "text": t[2:-2].strip()}
        return {"kind": "text", "text": t}
