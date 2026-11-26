class Files:
    """Uploaded files -> text blocks for the prompt and media the model can see."""

    MAX_BYTES = 25 * 1024 * 1024
    MAX_TEXT = 200_000
    MAX_PDF_IMAGES = 12

    @staticmethod
    def _mod(module, package):
        import importlib
        try:
            return importlib.import_module(module)
        except ImportError:
            subprocess.run([sys.executable, "-m", "pip", "install", "-q", f"{package}=={CFG.PIP_PINS.get(package, '')}"
                            if package in CFG.PIP_PINS else package], check=True, capture_output=True)
            importlib.invalidate_caches()
            return importlib.import_module(module)

    IMAGE_OK = ("image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif")

    @staticmethod
    def _text(data):
        if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
            try:
                return data.decode("utf-16")
            except UnicodeDecodeError:
                return None
        if b"\x00" in data[:4096]:
            return None
        for enc in ("utf-8-sig", "cp1252"):
            try:
                return data.decode(enc)
            except UnicodeDecodeError:
                pass
        return data.decode("latin-1")

    @classmethod
    def process(cls, files):
        texts, media, notes = [], [], []
        for f in files or []:
            name = str(f.get("name") or "file")
            mime = str(f.get("mime") or "").lower()
            ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
            try:
                data = base64.b64decode(f.get("b64") or "")
            except ValueError:
                notes.append(f"{name}: data rusak")
                continue
            if len(data) > cls.MAX_BYTES:
                notes.append(f"{name}: lebih dari 25 MB, dilewati")
                continue
            try:
                if mime.startswith("image/"):
                    if mime not in cls.IMAGE_OK:
                        # HEIC, BMP, TIFF...: convert to PNG, or the server would fail on every later turn
                        try:
                            fitz = cls._mod("fitz", "pymupdf")
                            data, mime = fitz.Pixmap(data).tobytes("png"), "image/png"
                        except Exception:
                            notes.append(f"{name}: format gambar {mime} tidak didukung (pakai PNG/JPEG/WebP)")
                            continue
                    media.append({"kind": "image", "mime": mime, "name": name, "data": data})
                elif mime.startswith("video/"):
                    media.append({"kind": "video", "mime": mime, "name": name, "data": data})
                elif mime.startswith("audio/"):
                    notes.append(f"{name}: audio tidak didukung")
                elif ext == "pdf" or mime == "application/pdf":
                    pypdf = cls._mod("pypdf", "pypdf")
                    reader = pypdf.PdfReader(io.BytesIO(data))
                    texts.append((name, "\n\n".join(f"--- halaman {i + 1} ---\n{p.extract_text() or ''}"
                                                    for i, p in enumerate(reader.pages))))
                    fitz = cls._mod("fitz", "pymupdf")
                    doc = fitz.open(stream=data, filetype="pdf")
                    for i, page in enumerate(doc):
                        if i >= cls.MAX_PDF_IMAGES:
                            notes.append(f"{name}: gambar hanya untuk {cls.MAX_PDF_IMAGES} halaman pertama")
                            break
                        media.append({"kind": "image", "mime": "image/png", "name": f"{name} hal {i + 1}",
                                      "data": page.get_pixmap(dpi=110).tobytes("png")})
                elif ext == "docx":
                    docx = cls._mod("docx", "python-docx")
                    d = docx.Document(io.BytesIO(data))
                    parts = [p.text for p in d.paragraphs]
                    for t in d.tables:
                        parts += [" | ".join(c.text for c in row.cells) for row in t.rows]
                    texts.append((name, "\n".join(parts)))
                elif ext in ("xlsx", "xlsm"):
                    openpyxl = cls._mod("openpyxl", "openpyxl")
                    wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
                    out = []
                    for ws in wb.worksheets:
                        out.append(f"--- sheet {ws.title} ---")
                        out += [",".join("" if v is None else str(v) for v in row) for row in ws.iter_rows(values_only=True)]
                    texts.append((name, "\n".join(out)))
                elif ext == "pptx":
                    pptx = cls._mod("pptx", "python-pptx")
                    prs = pptx.Presentation(io.BytesIO(data))
                    out = []
                    for i, slide in enumerate(prs.slides, 1):
                        out.append(f"--- slide {i} ---")
                        out += [sh.text_frame.text for sh in slide.shapes if sh.has_text_frame]
                    texts.append((name, "\n".join(out)))
                elif ext == "zip":
                    out = []
                    with zipfile.ZipFile(io.BytesIO(data)) as z:
                        for info in z.infolist()[:200]:
                            out.append(f"- {info.filename} ({info.file_size} byte)")
                            if not info.is_dir() and info.file_size < 200_000:
                                t = cls._text(z.read(info))
                                if t:
                                    out.append(f"```\n{t[:20000]}\n```")
                    texts.append((name, "\n".join(out)))
                else:
                    t = cls._text(data)
                    if t is None:
                        notes.append(f"{name}: file biner tidak didukung")
                    else:
                        texts.append((name, t))
            except Exception as e:
                notes.append(f"{name}: gagal dibaca ({type(e).__name__}: {str(e)[:120]})")
        blocks = [f"[Lampiran: {n}]\n```\n{t[:cls.MAX_TEXT]}\n```" + ("\n(dipotong)" if len(t) > cls.MAX_TEXT else "")
                  for n, t in texts]
        return blocks, media, notes
