import marimo as mo

mo.md(r"""
# Qwen Chat RP

Chat and long roleplay (up to 512K/1M tokens) on a molab GPU, with cards (character, persona, world, scenario,
style, GM), a Studio to build cards while you chat, scoped memory, a fact book, a world that keeps moving,
and compaction that does not forget details.

1. Turn on a GPU in *notebook specs*, then **Run all**.
2. Click **Install** (once per session).
3. Pick a model, click **Start**, and wait for the `READY` status.
4. Chat in the chat window at the bottom. You can also switch models from inside the chat.

All data (chats, cards, memory, facts) lives in one SQLite file. The molab workspace is wiped when the notebook
shuts down: use **Backup to Hugging Face** or the **Save** button in the chat.
""")
