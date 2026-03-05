import tkinter as tk
import random
import re
import json
import yaml
import os
import datetime

# ── file paths ───────────────────────────────────────────────
QUOTES_FILE    = "log/quotes.txt"
FRAMEWORK_FILE = "framework.yml"
SCORE_FILE     = os.path.join("log", "scores.json")

DISCORD_USERS = {
    "1271500729537794229": "Niko",
    "279880443200012288":  "Seam",
    "483868190498357248":  "Deadguana",
    "490921471225626647":  "Methmer",
    "602901448778579978":  "Niko",
}

SW, SH = 480, 320

BG     = "#0a0a0f"
PANEL  = "#12121a"
BORDER = "#2a2a3a"
ACCENT = "#e2a020"   # amber/gold — easy to read on dark
CYAN   = "#E8C325"
AMBER  = "#f59e0b"
GREEN  = "#22c55e"
FG     = "#e2e8f0"
DIM    = "#4a5568"

FS  = ("Courier", 8)
FB  = ("Courier", 11, "bold")
FT  = ("Courier", 20, "bold")

# ── data loaders ─────────────────────────────────────────────
def resolve_author(raw):
    raw = raw.strip()
    raw = re.sub(r'\s+ca\..*$', '', raw).strip()
    raw = re.sub(r'\s+[🔥].*$', '', raw).strip()
    m = re.match(r'<@!?(\d+)>', raw)
    if m:
        return DISCORD_USERS.get(m.group(1), m.group(1))
    return raw.lstrip('@').strip()

def parse_quotes(filepath):
    if not os.path.exists(filepath):
        return [("no quotes file found", None)]
    with open(filepath, "r", encoding="utf-8") as f:
        raw = f.read()
    entries = raw.split("||ENTRY_SEP||")
    quotes = []
    for entry in entries:
        lines = entry.strip().splitlines()
        content_lines = []
        for line in lines:
            line = line.strip()
            if not line or re.search(r'https?://', line): continue
            if re.match(r'^\[.+\]$', line): continue
            content_lines.append(line)
        if not content_lines: continue
        full = ' '.join(content_lines)
        split = re.split(r'\\n\s*(?:—|--|\\-|~~)\s*', full, maxsplit=1)
        if len(split) == 2:
            qt = split[0].strip().strip('"').replace('\\n', ' ').strip()
            au = resolve_author(split[1])
        else:
            if full.startswith('"') and full.endswith('"'):
                qt = full.strip('"').replace('\\n', ' ').strip()
                au = None
            else:
                continue
        if qt:
            quotes.append((qt, au))
    return quotes or [("no quotes parsed", None)]

def load_framework():
    if not os.path.exists(FRAMEWORK_FILE):
        return {}, {}
    with open(FRAMEWORK_FILE, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("RESPONSES", {}), data.get("CHANCE_EVENTS", {})

def load_scores():
    if not os.path.exists(SCORE_FILE):
        return {}
    try:
        with open(SCORE_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def trunc(text, n):
    s = str(text)
    return s if len(s) <= n else s[:n-1] + "…"

def make_panel(root, x, y, w, h, title):
    outer = tk.Frame(root, bg=BORDER)
    outer.place(x=x, y=y, width=w, height=h)
    tk.Label(outer, text=title, font=("Courier", 7, "bold"),
             fg=ACCENT, bg=BORDER, anchor="w").place(x=3, y=1)
    inner = tk.Frame(outer, bg=PANEL)
    inner.place(x=1, y=13, width=w-2, height=h-14)
    return inner

# ═════════════════════════════════════════════════════════════
class Dashboard:
    def __init__(self, root, shared_state=None):
        self.root = root
        self.root.title("poopid")
        self.root.configure(bg=BG)
        self.root.attributes("-fullscreen", True)
        self.root.config(cursor="none")
        self.root.bind("<Escape>", lambda e: self.root.destroy())

        self.shared_state  = shared_state or {
            "target": "???", "prev_target": "???", "last_gen": 0,
            "last_chance": None  # {"event": str, "user": str, "chance": int}
        }
        self.quotes = parse_quotes(QUOTES_FILE)
        self.responses, self.chance_events = load_framework()

        self._build_ui()

    def _build_ui(self):
        tk.Frame(self.root, bg=ACCENT, height=2).place(x=0, y=0, width=SW)

        hdr = tk.Frame(self.root, bg=PANEL, height=22)
        hdr.place(x=0, y=2, width=SW)
        tk.Label(hdr, text="POOPID BOT", font=FB, fg=ACCENT, bg=PANEL).place(x=8, y=2)
        self.clock_lbl = tk.Label(hdr, text="", font=FS, fg=DIM, bg=PANEL)
        self.clock_lbl.place(x=SW-80, y=5)
        tk.Frame(self.root, bg=BORDER, height=1).place(x=0, y=24, width=SW)

        # LEFT  x=4   w=228   RIGHT x=236 w=240
        # y=27  total h=293
        #
        # LEFT:  quote h=140, minigame h=46, last chance h=100
        # RIGHT: lb scores h=140, lb chances h=148

        self._build_quote(4,   27,  228, 140)
        self._build_minigame(4, 171, 228, 46)
        self._build_last_chance(4, 221, 228, 94)

        self._build_leaderboard_scores(236, 27,  240, 140)
        self._build_leaderboard_chances(236, 171, 240, 144)

        self._tick()

    # ── QUOTE ────────────────────────────────────────────────
    def _build_quote(self, x, y, w, h):
        f = make_panel(self.root, x, y, w, h, "// QUOTE")
        self.q_lbl = tk.Label(f, text="", font=("Courier", 11, "italic"),
            fg=FG, bg=PANEL, wraplength=w-14, justify="left", anchor="nw")
        self.q_lbl.place(x=6, y=2, width=w-12, height=h-26)
        self.a_lbl = tk.Label(f, text="", font=FS, fg=CYAN, bg=PANEL, anchor="e")
        self.a_lbl.place(x=6, y=h-22, width=w-12)
        self._refresh_quote()

    def _refresh_quote(self):
        q, a = random.choice(self.quotes)
        self.q_lbl.config(text=f'"{trunc(q, 130)}"')
        self.a_lbl.config(text=f"— {a}" if a else "— unknown")
        self.root.after(60000, self._refresh_quote)

    # ── MINIGAME: previous target only ───────────────────────
    def _build_minigame(self, x, y, w, h):
        f = make_panel(self.root, x, y, w, h, "// LAST TARGET")
        tk.Label(f, text="was:", font=FS, fg=DIM, bg=PANEL).place(x=6, y=6)
        self.prev_tgt_lbl = tk.Label(f, text="???", font=FT, fg=DIM, bg=PANEL)
        self.prev_tgt_lbl.place(x=38, y=2)
        self._refresh_target()

    def _refresh_target(self):
        prev = self.shared_state.get("prev_target", "???")
        self.prev_tgt_lbl.config(text=prev if prev else "???")
        self.root.after(2000, self._refresh_target)

    # ── LAST CHANCE EVENT ────────────────────────────────────
    def _build_last_chance(self, x, y, w, h):
        f = make_panel(self.root, x, y, w, h, "// LAST CHANCE EVENT")
        self._lc_frame = f
        self._lc_w = w
        self._lc_h = h

        self.lc_event_lbl = tk.Label(f, text="none yet", font=("Courier", 9, "bold"),
            fg=AMBER, bg=PANEL, anchor="w")
        self.lc_event_lbl.place(x=6, y=4, width=w-12)

        self.lc_user_lbl = tk.Label(f, text="", font=FS, fg=FG, bg=PANEL, anchor="w")
        self.lc_user_lbl.place(x=6, y=22, width=w-12)

        self.lc_odds_lbl = tk.Label(f, text="", font=FS, fg=GREEN, bg=PANEL, anchor="w")
        self.lc_odds_lbl.place(x=6, y=38, width=w-12)

        self._refresh_last_chance()

    def _refresh_last_chance(self):
        lc = self.shared_state.get("last_chance")
        if lc:
            self.lc_event_lbl.config(text=trunc(lc.get("event", ""), 26))
            self.lc_user_lbl.config(text=f"hit by: {lc.get('user', '?')}")
            chance = lc.get("chance", 1000)
            self.lc_odds_lbl.config(text=f"1/{chance} odds")
        self.root.after(2000, self._refresh_last_chance)

    # ── LEADERBOARD: scores ──────────────────────────────────
    def _build_leaderboard_scores(self, x, y, w, h):
        f = make_panel(self.root, x, y, w, h, "// LEADERBOARD")
        self._lb_score_frame = f
        self._lb_score_w = w
        self._draw_scores()
        self.root.after(30000, self._refresh_scores)

    def _draw_scores(self):
        for c in self._lb_score_frame.winfo_children():
            c.destroy()
        scores = load_scores()
        if scores:
            sorted_s = sorted(scores.items(), key=lambda x: x[1]["score"], reverse=True)
            for i, (uid, d) in enumerate(sorted_s[:7], 1):
                ry = 2 + (i-1) * 18
                col = [AMBER, FG, FG] + [DIM]*10
                tk.Label(self._lb_score_frame, text=f"{i}.", font=FS,
                         fg=col[i-1], bg=PANEL, anchor="w").place(x=4, y=ry)
                tk.Label(self._lb_score_frame, text=trunc(d["name"], 13), font=FS,
                         fg=FG, bg=PANEL, anchor="w").place(x=20, y=ry)
                tk.Label(self._lb_score_frame, text=str(d["score"]), font=FS,
                         fg=GREEN, bg=PANEL, anchor="e").place(x=self._lb_score_w-18, y=ry)
        else:
            tk.Label(self._lb_score_frame, text="no scores yet", font=FS,
                     fg=DIM, bg=PANEL).place(x=6, y=6)

    def _refresh_scores(self):
        self._draw_scores()
        self.root.after(30000, self._refresh_scores)

    # ── LEADERBOARD: chance hits (clb style) ─────────────────
    def _build_leaderboard_chances(self, x, y, w, h):
        f = make_panel(self.root, x, y, w, h, "// CHANCE HITS")
        self._lb_chance_frame = f
        self._lb_chance_w = w
        self._draw_chances()
        self.root.after(30000, self._refresh_chances)

    def _draw_chances(self):
        for c in self._lb_chance_frame.winfo_children():
            c.destroy()
        scores = load_scores()

        all_chances = {}
        for uid, data in scores.items():
            name = data.get("name", uid)
            for chance_name, count in data.get("chances", {}).items():
                if chance_name not in all_chances:
                    all_chances[chance_name] = []
                all_chances[chance_name].append((name, count))

        if not all_chances:
            tk.Label(self._lb_chance_frame, text="no chance hits yet", font=FS,
                     fg=DIM, bg=PANEL).place(x=6, y=6)
            return

        ry = 2
        for event_name in sorted(all_chances.keys()):
            if ry > 130: break
            top_list = sorted(all_chances[event_name], key=lambda x: x[1], reverse=True)
            # event name row
            tk.Label(self._lb_chance_frame, text=trunc(event_name, 22),
                     font=("Courier", 7, "bold"), fg=CYAN, bg=PANEL, anchor="w").place(x=4, y=ry)
            ry += 11
            # top 2 scorers for this event
            for name, count in top_list[:2]:
                tk.Label(self._lb_chance_frame, text=f"  {trunc(name,12)} ×{count}",
                         font=FS, fg=FG, bg=PANEL, anchor="w").place(x=4, y=ry)
                ry += 11
            ry += 3  # gap between events

    def _refresh_chances(self):
        self._draw_chances()
        self.root.after(30000, self._refresh_chances)

    # ── CLOCK ────────────────────────────────────────────────
    def _tick(self):
        self.clock_lbl.config(text=datetime.datetime.now().strftime("%H:%M:%S"))
        self.root.after(1000, self._tick)


def main(shared_state=None):
    root = tk.Tk()
    app = Dashboard(root, shared_state)
    root.mainloop()

if __name__ == "__main__":
    main()