_work = Path(os.environ.get("QCHAT_WORK", "/tmp/qwen-chat"))
_work.mkdir(parents=True, exist_ok=True)
_key_file = _work / "api_key"
if not _key_file.exists():
    _key_file.write_text(secrets.token_hex(16))

# Everything that pins a version lives here, so a run can be reproduced exactly.
CFG = SimpleNamespace(
    WORK=_work,
    DB_PATH=_work / "qwen_chat.sqlite",
    PORT=int(os.environ.get("QCHAT_PORT", "8000")),  # what the chat talks to (vLLM, or the llama.cpp proxy)
    LLAMA_PORT=int(os.environ.get("QCHAT_PORT", "8000")) + 2,
    EMBED_PORT=int(os.environ.get("QCHAT_PORT", "8000")) + 3,
    API_KEY=os.environ.get("QWEN_CHAT_API_KEY", _key_file.read_text().strip()),
    SERVED_NAME="qwen-chat",
    # QCHAT_BASE_URL points the chat at another OpenAI-compatible server (tests use a fake one).
    BASE_URL=os.environ.get("QCHAT_BASE_URL", ""),
    VENV=Path.home() / "vllm-env",
    VLLM_VERSION="0.32.0",
    LLAMA_DIR=Path.home() / "llama.cpp",
    LLAMA_TAG="b12757",
    LLAMA_ASSETS={
        "llama-b12757-bin-ubuntu-cuda-13.5-x64.tar.gz":
            "15f610dc4e643a725972db99ca2283f2fe7e126d41c9be259247b155c80895cc",
        "cudart-llama-b12757-bin-ubuntu-cuda-13.5-x64.tar.gz":
            "94c0023cd24eeebe806f62fb401a6586c31496f4bb2acc8e283275ec7d64e48f",
    },
    MODEL_DIR=Path.home() / "models",
    PIP_PINS={
        "camoufox[geoip]": "0.5.9",
        "huggingface_hub[hf_xet]": "2.4.0",
        "pypdf": "7.1.1",
        "pymupdf": "2.2",
        "python-docx": "1.2.0",
        "openpyxl": "3.1.5",
        "python-pptx": "1.0.2",
    },
    USER_AGENT="qwen-chat-molab/2.0 (marimo notebook)",
)
CFG.VLLM_BIN = CFG.VENV / "bin" / "vllm"
CFG.VLLM_OK = CFG.VENV / f".install-ok-{CFG.VLLM_VERSION}"
CFG.LOG_DIR = CFG.WORK / "logs"
CFG.LOG_DIR.mkdir(exist_ok=True)

_QWEN_SAMPLING = {"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.0,
                  "presence_penalty": 0.0, "frequency_penalty": 0.0, "repetition_penalty": 1.0}
# Dark-Gemistry card (Nimbz): temp 0.75-1.0, top_k 0, top_p 0.95, min_p 0.05, no repetition penalty or DRY,
# because they fight the StyleTune "voice" in its lm_head.
_DG_SAMPLING = {"temperature": 1.0, "top_p": 0.95, "top_k": 0, "min_p": 0.05,
                "presence_penalty": 0.0, "frequency_penalty": 0.0, "repetition_penalty": 1.0}
# DavidAU 40B Build2 card: temp 1.0 (0.6-0.7 for tools), top_k 64, top_p 0.95, min_p 0.05, rep pen 1.0.
_B2_SAMPLING = {"temperature": 1.0, "top_p": 0.95, "top_k": 64, "min_p": 0.05,
                "presence_penalty": 0.0, "frequency_penalty": 0.0, "repetition_penalty": 1.0}

_G4_MMPROJ = ("ggml-org/gemma-4-31B-it-GGUF", "mmproj-gemma-4-31B-it-BF16.gguf",
              "f39d380138390ea246513ff0f087352f3cfc3a1b")
_G4_DRAFT_GGUF = ("AtomicChat/gemma-4-31B-it-assistant-GGUF", "gemma-4-31B-it-assistant.Q8_0.gguf",
                  "53431ae9339f81e3aca3933ee874fcd4e625e6bb")
_G4_DRAFT_HF = ("google/gemma-4-31B-it-assistant", "627c5ec1458b9086b841a91e0512fd31fd2fbbf1")
_DG_GGUF = ("ReadyArt/Nimbz_Gemma-4-Dark-Gemistry-31B-GGUF", "c65c964373f131c2f91c424b8d321b7455ca37df")

# family decides the chat template switches: "qwen" reads reasoning_effort, "gemma" reads enable_thinking.
# mtp: "heads" = MTP layers inside the GGUF/checkpoint, "draft" = separate drafter, None = off.
# max_ctx = native context; yarn_max = limit with YaRN; yarn_exp = YaRN without an official recipe.
PRESETS = {
    "Huihui Qwen3.8 27B abliterated FP8 · vLLM": dict(
        backend="vllm", family="qwen", repo="munekazu/Huihui-Qwen3.8-27B-abliterated-FP8",
        revision="badcb1961b646b3bdf1fc9ebdd9727826a55a48f", size_gb=31, mtp="heads",
        max_ctx=262144, yarn_max=1000000, yarn_exp=False, reasoning_parser="qwen3", tool_parser="qwen3_coder",
        sampling=_QWEN_SAMPLING, thinking=("off", "low", "medium", "high", "xhigh"), vision=True),
    "Dark-Gemistry 31B FP8 (W8A16) · vLLM": dict(
        backend="vllm", family="gemma", repo="hoborific/Gemma-4-Dark-Gemistry-31B-W8A16-FP8",
        revision="6fe96dfdda65559562944624cd954ba21caaef3f", size_gb=33, mtp="draft", draft_hf=_G4_DRAFT_HF,
        # vLLM 0.32.0 picks the Humming kernel first for FP8 W8A16; its JIT compile (NVRTC, humming-kernels 0.1.17)
        # fails on molab. Marlin ships prebuilt in the vLLM wheel.
        vllm_args=["--kernel-config", json.dumps({"linear_backend_per_quant": {"w8a16_fp8": "marlin"}})],
        max_ctx=262144, yarn_max=262144, yarn_exp=False, reasoning_parser="gemma4", tool_parser="gemma4",
        sampling=_DG_SAMPLING, thinking=("off", "on"), vision=True, kv_dtype="fp8"),
    "Dark-Gemistry 31B BF16 → FP8 saat dimuat · vLLM": dict(
        backend="vllm", family="gemma", repo="Nimbz/Gemma-4-Dark-Gemistry-31B",
        revision="69b04897274140722e326f29c9f31ecbaca637ac", size_gb=65, quantization="fp8", mtp="draft",
        draft_hf=_G4_DRAFT_HF, max_ctx=262144, yarn_max=262144, yarn_exp=False, reasoning_parser="gemma4",
        tool_parser="gemma4", sampling=_DG_SAMPLING, thinking=("off", "on"), vision=True, kv_dtype="fp8"),
    "Dark-Gemistry 31B HB16-Q8_0 · llama.cpp": dict(
        backend="llama", family="gemma", repo=_DG_GGUF[0], revision=_DG_GGUF[1],
        file="Gemma-4-Dark-Gemistry-31B-HB16-Q8_0.gguf", size_gb=36.8, mmproj=_G4_MMPROJ, mtp="draft",
        draft_gguf=_G4_DRAFT_GGUF, max_ctx=262144, yarn_max=524288, yarn_exp=True,
        sampling=_DG_SAMPLING, thinking=("off", "on"), vision=True),
    "Dark-Gemistry 31B HB16-Q6_K · llama.cpp": dict(
        backend="llama", family="gemma", repo=_DG_GGUF[0], revision=_DG_GGUF[1],
        file="Gemma-4-Dark-Gemistry-31B-HB16-Q6_K.gguf", size_gb=29.7, mmproj=_G4_MMPROJ, mtp="draft",
        draft_gguf=_G4_DRAFT_GGUF, max_ctx=262144, yarn_max=524288, yarn_exp=True,
        sampling=_DG_SAMPLING, thinking=("off", "on"), vision=True),
    "Qwen3.8 27B heretic-ara Q8_0 · llama.cpp": dict(
        backend="llama", family="qwen", repo="mradermacher/Qwen3.8-27B-heretic-ara-GGUF",
        revision="f69c978f262c983cb312395d18bbce340260e89f", file="Qwen3.8-27B-heretic-ara.Q8_0.gguf",
        size_gb=29.0,
        mmproj=("mradermacher/Qwen3.8-27B-heretic-ara-GGUF", "Qwen3.8-27B-heretic-ara.mmproj-Q8_0.gguf",
                "f69c978f262c983cb312395d18bbce340260e89f"),
        mtp="heads", max_ctx=262144, yarn_max=1000000, yarn_exp=False, sampling=_QWEN_SAMPLING,
        thinking=("off", "low", "medium", "high", "xhigh"), vision=True),
    "Qwen3.8 40B Heretic Build2 i1-Q6_K · llama.cpp": dict(
        backend="llama", family="qwen", repo="mradermacher/Qwen3.8-40B-Ultimate-Heretic-Uncensored-Build2-i1-GGUF",
        revision="590ad69bc75a01d2b909f13c6454edd7d328ea57",
        file="Qwen3.8-40B-Ultimate-Heretic-Uncensored-Build2.i1-Q6_K.gguf", size_gb=32.4,
        mmproj=("mradermacher/Qwen3.8-40B-Ultimate-Heretic-Uncensored-Build2-GGUF",
                "Qwen3.8-40B-Ultimate-Heretic-Uncensored-Build2.mmproj-Q8_0.gguf",
                "98c92f851d9aef9a9516ce84d841a79c60f56db9"),
        # Build2 only works with thinking on (DavidAU card), so "off" is not offered.
        mtp="heads", max_ctx=262144, yarn_max=1000000, yarn_exp=False, sampling=_B2_SAMPLING,
        thinking=("low", "medium", "high", "xhigh"), vision=True),
}

EMBEDDER = dict(repo="Qwen/Qwen3-Embedding-0.6B-GGUF", revision="370f27d7550e0def9b39c1f16d3fbaa13aa67728",
                file="Qwen3-Embedding-0.6B-Q8_0.gguf", dim=1024,
                query_prefix="Instruct: Given a roleplay or chat query, retrieve relevant memories, lore and facts\nQuery: ")

CTX_CHOICES = {"128K": 131072, "262K (native)": 262144, "512K (YaRN)": 524288, "1M (YaRN, Qwen)": 1000000}


def thinking_kwargs(preset, level):
    """chat_template_kwargs for a thinking level. Unknown keys are ignored by the other family's template."""
    levels = preset["thinking"]
    if level not in levels:
        # off stays off where possible; a named level becomes "on" for on/off models, "high" for Qwen levels
        if level == "off":
            level = "off" if "off" in levels else levels[0]
        elif "on" in levels:
            level = "on"
        else:
            level = "high" if "high" in levels else next((x for x in reversed(levels) if x != "off"), levels[-1])
    if preset["family"] == "gemma":
        return {"enable_thinking": level != "off", "preserve_thinking": True}
    if level == "off":
        return {"enable_thinking": False, "preserve_thinking": True}
    return {"enable_thinking": True, "reasoning_effort": level, "preserve_thinking": True}
