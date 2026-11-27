def _f(key, label, section, type_="text", core=True, visibility="model", **extra):
    return {"key": key, "label": label, "section": section, "type": type_, "core": core, "visibility": visibility, **extra}


# How well known a character is in the story's surroundings (a campus, a village). The top two are common knowledge.
FAME_LEVELS = ["bintang", "terkenal", "dikenal di lingkungannya", "biasa"]
TOP_FAME = ("bintang", "terkenal")

# Default schemas. They are data: stored in card_schemas, editable in the schema editor, exported with cards.
# Nothing here is tied to a genre; examples in `help` are only hints.
DEFAULT_SCHEMAS = {
    "character": {"type": "character", "label": "Character", "version": 4, "fields": [
        _f("name", "Name", "Identity"),
        _f("aliases", "Other names / nicknames", "Identity", "tags"),
        _f("age", "Age", "Identity"),
        _f("role", "Role in the story", "Identity"),
        _f("fame", "Fame", "Identity", "select", core=False, options=FAME_LEVELS,
           help="How well known the character is around the story (a campus, for example). bintang (star) and terkenal "
                "(famous): known to everyone, more active in the world, and their card is always in the prompt when there "
                "are more than 12 characters"),
        _f("fame_for", "Known for", "Identity", core=False),
        _f("appearance", "Appearance", "Identity", "longtext"),
        _f("description", "General description", "Identity", "longtext"),
        _f("traits", "Traits", "Personality", "table", columns=["trait", "strength 1-5"]),
        _f("personality", "Personality", "Personality", "longtext"),
        _f("speech_style", "Speech style", "Speech", "longtext",
           help="Speech habits, what they call you, mixing of languages"),
        _f("speech_samples", "Signature lines", "Speech", "list", max_items=5,
           help="3-5 lines exactly as this character speaks"),
        _f("example_dialogue", "Example dialogue", "Speech", "longtext", core=False),
        _f("languages", "Languages spoken", "Speech"),
        _f("goals", "Goals", "Agenda", "list"),
        _f("plan", "Current plan (at the start)", "Agenda", "longtext", core=False),
        _f("routine", "Routine", "Agenda", "longtext", core=False),
        _f("schedule", "Schedule (location by world time)", "Agenda", "table", core=False, columns=["jam", "lokasi", "kegiatan"],
           help="Hour 0-23 or a range such as 08-12. Used to know where the character is when not on screen"),
        _f("skill_levels", "Skill levels", "Skills", "table", core=False, columns=["skill", "level 0-100"],
           help="Used by the system to work out dice odds"),
        _f("fears", "Fears", "Agenda", "list", core=False),
        _f("secrets", "Secrets", "Agenda", "list", visibility="secret"),
        _f("backstory", "Backstory", "History", "longtext", core=False),
        _f("relations", "Relationships", "History", "table", core=False, columns=["name", "relationship", "notes"]),
        _f("limits", "Things this character will never do", "Limits", "longtext"),
        _f("knowledge", "What the character knows", "Limits", "list", core=False),
        _f("greetings", "Opening messages", "Opening", "list", visibility="ui"),
        _f("default_scenario", "Default scenario", "Opening", "longtext", core=False),
        _f("tags", "Tags", "Other", "tags", visibility="ui"),
        _f("notes", "Notes for you", "Other", "longtext", visibility="ui"),
    ]},
    "persona": {"type": "persona", "label": "Persona", "version": 4, "fields": [
        _f("name", "Name", "Identity"),
        _f("age", "Age", "Identity"),
        _f("role", "Role", "Identity"),
        _f("fame", "Fame", "Identity", "select", core=False, options=FAME_LEVELS,
           help="bintang (star) or terkenal (famous): other people know who your character is even before you meet"),
        _f("fame_for", "Known for", "Identity", core=False),
        _f("appearance", "Appearance", "Identity", "longtext"),
        _f("background", "Background", "Identity", "longtext"),
        _f("personality", "Personality", "Identity", "longtext"),
        _f("skills", "Skills", "Skills", "list"),
        _f("skill_levels", "Skill levels", "Skills", "table", core=False, columns=["skill", "level 0-100"],
           help="Used by the system to work out dice odds, for example: German, 55"),
        _f("model_may_decide", "What the narrator may decide for the player character", "Rules", "longtext",
           help="For example: small movements and reflexes are fine; speech and decisions are not"),
        _f("limits", "Limits", "Rules", "longtext"),
        _f("notes", "Notes for you", "Other", "longtext", visibility="ui"),
    ]},
    "world": {"type": "world", "label": "World", "version": 3, "fields": [
        _f("name", "World name", "Core"),
        _f("era", "Era", "Core"),
        _f("setting", "Place and setting", "Core", "longtext"),
        _f("realworld", "Based on the real world", "Core", "select", options=["ya", "tidak"],
           help="ya (yes) = real-world facts must be accurate and are checked; tidak (no) = checked against the lore"),
        _f("technology", "Technology", "Core", "longtext"),
        _f("society", "Politics, factions, society", "Core", "longtext"),
        _f("rules", "World rules", "Core", "longtext", help="Laws of nature, magic, limits of technology"),
        _f("languages", "Languages", "Core", "longtext"),
        _f("daily_life", "Daily life", "Details", "longtext", core=False),
        _f("terms", "Terms", "Details", "table", core=False, columns=["istilah", "arti"]),
        _f("climate", "Climate (for the weather)", "Details", "table", core=False, visibility="ui",
           columns=["bulan", "suhu min", "suhu max", "cuaca"],
           help="Month 1-12 or a season name; weather kinds separated by commas, for example: clear, cloudy, rain"),
        _f("stats", "Player stats", "Mechanics", "table", core=False, visibility="ui",
           columns=["key", "label", "min", "max", "awal", "laju per jam"],
           help="Example: hunger, Hunger, 0, 100, 20, 4 (rises 4 per hour). An empty rate means it does not change on its own"),
        _f("locations", "Travel time between places", "Mechanics", "table", core=False, columns=["dari", "ke", "menit"],
           help="The world clock moves on by the travel time when your character goes somewhere else"),
        _f("wiki_lang", "Wikipedia language for research", "Mechanics", visibility="ui", help="For example: de,en"),
        _f("notes", "Notes for you", "Other", "longtext", visibility="ui"),
    ]},
    "scenario": {"type": "scenario", "label": "Scenario", "version": 2, "fields": [
        _f("title", "Title", "Core"),
        _f("premise", "Premise", "Core", "longtext"),
        _f("situation", "Starting situation", "Core", "longtext"),
        _f("conflict", "Conflict", "Core", "longtext"),
        _f("stakes", "Stakes", "Core", "longtext"),
        _f("plan", "Planned plot", "Plot", "list", core=False),
        _f("start_time", "Starting world date and time", "Start", "datetime", help="Format 1916-07-01 06:30"),
        _f("start_location", "Starting location", "Start"),
        _f("start_stats", "Starting stats (override the world's starting values)", "Start", "table", core=False, visibility="ui",
           columns=["key", "nilai"]),
        _f("opening", "Opening scene", "Start", "longtext", visibility="ui"),
    ]},
    "style": {"type": "style", "label": "Style", "version": 2, "fields": [
        _f("pov", "Point of view", "Narration", "select",
           options=["orang kedua (kamu)", "orang pertama (aku)", "orang ketiga"]),
        _f("narration_lang", "Narration language", "Narration"),
        _f("dialogue_rule", "Dialogue and translation rule", "Narration", "longtext"),
        _f("target_lang", "Target language (learning mode)", "Narration", visibility="ui", help="Language code, for example de"),
        _f("paragraphs", "Number of paragraphs", "Length", visibility="ui", help="A range, for example 5-10"),
        _f("sentences", "Sentences per paragraph", "Length", visibility="ui", help="A range, for example 5-10"),
        _f("sentence_style", "Sentence style", "Length", "longtext"),
        _f("dialogue_ratio", "Share of dialogue", "Length"),
        _f("violence", "Detail of violence", "Content", "select", options=["tersirat", "sedang", "grafis"]),
        _f("tone", "Tone", "Content", "longtext"),
        _f("pacing", "Pacing", "Content"),
        _f("banned", "Banned phrases", "Restrictions", "list"),
        _f("rules", "Extra rules", "Restrictions", "list"),
    ]},
    "gm": {"type": "gm", "label": "GM", "version": 4, "fields": [
        _f("format", "Format", "Format", "select", options=["prosa", "game"], visibility="ui"),
        _f("realism", "Realism", "World", "select", options=["santai", "membumi", "keras"]),
        _f("lethality", "Lethality", "World", "select", options=["rendah", "sedang", "tinggi"]),
        _f("consequences", "Consequence rules", "World", "longtext"),
        _f("npc_behavior", "NPC behavior", "World", "longtext"),
        _f("random_events", "Random events", "World", "select", options=["jarang", "kadang", "sering"]),
        _f("dice", "When to roll dice", "Mechanics", "select", options=["saat ragu", "sering", "jarang"]),
        _f("fact_policy", "Fact rules", "Mechanics", "longtext"),
        _f("checklist", "Checklist before answering", "Mechanics", "list"),
        _f("rules", "Extra rules", "Mechanics", "list"),
        _f("choices", "Choices", "Choices", "select", options=["selalu", "kadang", "tidak"], visibility="ui"),
        _f("choice_problems", "Number of problems", "Choices", visibility="ui", help="A range, for example 1-3"),
        _f("choice_options", "Options per problem", "Choices", visibility="ui", help="A range, for example 3-5"),
        _f("choice_sentences", "Sentences per question/option", "Choices", visibility="ui", help="A range, for example 1-2"),
        _f("time_skips", "Time skip buttons", "Time", "list", visibility="ui"),
        _f("afk_scale", "Time scale while AFK", "Time", visibility="ui",
           help="Story hours per real hour. 0 = the world stops, 1 = same as real time"),
        _f("tick_minutes", "World tick every (idle minutes)", "Time", visibility="ui"),
        _f("offscreen_hours", "Off-screen world moves every (world hours)", "Time", visibility="ui",
           help="Characters who are not in the scene carry out their agenda in the background every so many world hours. "
                "0 = off"),
        _f("state_check", "State check after each turn", "Continuity", "select", options=["ya", "tidak"],
           visibility="ui", help="Fills in the time, status and character memories the model forgot to record"),
        _f("continuity_check", "Continuity check", "Continuity", "select", options=["latar", "ketat", "mati"], visibility="ui",
           help="Flags characters who know things outside their memory, are in the wrong place, are dead, or ignore the "
                "dice. latar (background): flags only; ketat (strict): the reply is rewritten; mati: off"),
    ]},
    "status": {"type": "status", "label": "Character status", "version": 3, "fields": [
        _f("location", "Location", "Status"),
        _f("keadaan", "Condition", "Status", "select", options=["hidup", "terluka parah", "pingsan", "ditahan", "pergi", "mati"]),
        _f("outfit", "Outfit", "Status"),
        _f("mood", "Mood", "Status"),
        _f("injuries", "Injuries", "Status", "list"),
        _f("inventory", "Inventory", "Status", "list"),
        _f("attitude", "Attitude toward other characters", "Status", "table", columns=["character", "attitude"]),
        _f("plan_now", "Current plan", "Status", "longtext"),
        _f("knows", "Newly learned", "Status", "list"),
    ]},
}

DIALOGUE_RULE_ID = ("Dialog ditulis dalam bahasa tokohnya. Kalau bukan bahasa Indonesia, tulis kalimatnya UTUH dalam satu "
                    "tanda kutip, lalu terjemahannya SATU kali dalam kurung tepat setelahnya.")
DIALOGUE_RULE_EN = ("Dialogue is written in each character's own language. When it is not English, write the whole sentence "
                    "inside one pair of quotes, then its English translation ONCE in parentheses right after it. Every such "
                    "sentence is translated.")

# Default values that changed: a default card still holding the old value moves to the new one, once per database
# (one flag per change set).
DEFAULTS_CHANGED = {
    "defaults_v2": [("style", "Gaya RP default", "paragraphs", "5-10", "4-7"),
                    ("style", "Gaya RP default", "sentences", "5-10", "4-7"),
                    ("gm", "GM membumi", "afk_scale", "1", "0")],
    "defaults_v3": [("style", "Gaya RP default", "narration_lang", "Indonesia", "English"),
                    ("style", "Gaya RP default", "dialogue_rule", DIALOGUE_RULE_ID, DIALOGUE_RULE_EN)],
}

DEFAULT_CARDS = [
    ("style", "Gaya RP default", {
        "pov": "orang kedua (kamu)", "narration_lang": "English", "dialogue_rule": DIALOGUE_RULE_EN,
        "paragraphs": "4-7", "sentences": "4-7",
        "sentence_style": "Kalimat panjang yang merangkai deskripsi, gerak, dan ucapan tokoh. Detail konkret dan indrawi.",
        "dialogue_ratio": "30-50%", "violence": "sedang", "tone": "Membumi dan wajar, tanpa superlatif.",
        "pacing": "Sedang; tiap paragraf memajukan sesuatu.",
        "banned": ["jantungku berdegup kencang", "waktu seolah berhenti", "tanpa disadari", "sebuah senyuman tipis",
                   "seolah-olah dunia", "tidak bisa dipercaya"],
        "rules": ["Jangan menceramahi atau menambahkan peringatan moral.",
                  "Jangan mengulang isi giliran sebelumnya."],
    }),
    ("gm", "GM membumi", {
        "format": "prosa", "realism": "membumi", "lethality": "sedang",
        "consequences": "Tidak ada plot armor untuk pemain maupun NPC. Aksi bisa gagal. Luka dan tindakan punya akibat "
                        "yang wajar dan berlanjut. Setiap aksi makan waktu.",
        "npc_behavior": "NPC punya tujuan dan rencana sendiri, bertindak tanpa disuruh, bisa menolak, berbohong, dan salah "
                        "paham, dan hanya bertindak berdasarkan apa yang mereka tahu. NPC tidak memuja pemain.",
        "random_events": "kadang", "dice": "saat ragu",
        "fact_policy": "Fakta dunia nyata yang spesifik dan tidak pasti wajib dicari dulu (fact_lookup, lalu wiki_search "
                       "atau web_search). Jangan mengarang angka, nama, atau tanggal nyata. Kalau tidak ketemu, tulis umum "
                       "tanpa angka atau nama yang tidak pasti.",
        "checklist": ["Masuk akal secara fisik?", "Apa akibatnya?", "Tokoh ini sebenarnya tahu apa?",
                      "Berapa waktu yang lewat?", "Ada yang lebay?", "Ada fakta nyata yang belum pasti?"],
        "rules": [], "choices": "kadang", "choice_problems": "1-3", "choice_options": "3-5", "choice_sentences": "1-2",
        "time_skips": ["2 jam", "3 jam", "1 hari", "1 minggu", "1 bulan"], "afk_scale": "0", "tick_minutes": "20", "offscreen_hours": "4",
    }),
]
