import tkinter as tk
import random
import re
import json
import yaml
import os
import datetime
import threading
import tkinter.font as tkfont

from libs import calendar_sync

QUOTES_FILE    = os.path.join("log", "quotes.txt")
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
HDR_H  = 25   # header height
BODY_Y = HDR_H + 2

BG     = "#0a0a0f"
PANEL  = "#12121a"
BORDER = "#2a2a3a"
ACCENT = "#e2a020"
CYAN   = "#06b6d4"
AMBER  = "#f59e0b"
GREEN  = "#22c55e"
FG     = "#e2e8f0"
DIM    = "#E8C325"

FS  = ("Courier", 8)
FB  = ("Courier", 11, "bold")
FT  = ("Courier", 20, "bold")
FZ  = ("Courier", 14, "bold")   # zoom panel title

# ── data helpers ─────────────────────────────────────────────
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

# ── panel builder ─────────────────────────────────────────────
def bind_all_children(widget, event, callback):
    """Recursively bind event to widget and all its children."""
    widget.bind(event, lambda e: callback())
    for child in widget.winfo_children():
        bind_all_children(child, event, callback)

def make_panel(root, x, y, w, h, title, clickable=False, on_click=None):
    outer = tk.Frame(root, bg=BORDER)
    outer.place(x=x, y=y, width=w, height=h)
    title_lbl = tk.Label(outer, text=title, font=("Courier", 7, "bold"),
                          fg=ACCENT, bg=BORDER, anchor="w")
    title_lbl.place(x=3, y=1)
    inner = tk.Frame(outer, bg=PANEL)
    inner.place(x=1, y=13, width=w-2, height=h-14)
    if clickable and on_click:
        # bind now on outer/title/inner, then schedule a recursive bind
        # after children are packed so labels etc. are also covered
        for widget in (outer, title_lbl, inner):
            widget.bind("<Button-1>", lambda e: on_click())
        # store callback on inner so we can re-bind after content is added
        inner._click_cb = on_click
    return inner, outer

def rebind_panel(inner):
    """Call after adding widgets to a panel to ensure full touch coverage."""
    if hasattr(inner, '_click_cb'):
        bind_all_children(inner, "<Button-1>", inner._click_cb)

# ═════════════════════════════════════════════════════════════
class Dashboard:
    def __init__(self, root, shared_state=None):
        self.root = root
        self.root.title("poopid")
        self.root.configure(bg=BG)
        self.root.attributes("-fullscreen", True)
        self.root.config(cursor="none")
        self.root.bind("<Escape>", lambda e: self.root.destroy())

        self.shared_state = shared_state or {
            "target": "???", "prev_target": "???",
            "last_gen": 0, "last_chance": None,
        }
        self.shared_state.setdefault("scores_dirty", False)
        self.shared_state.setdefault("chances_dirty", False)

        self.quotes = parse_quotes(QUOTES_FILE)
        self._meetings = []
        self._next_meeting = None
        self._fetch_meetings()
        self.responses, self.chance_events = load_framework()
        self._last_chance_seen = None

        # overlay frame (hidden until a panel is tapped)
        self._overlay = None

        self._build_ui()

    # ── OVERLAY (fullscreen zoom) ─────────────────────────────
    def _show_overlay(self, build_fn):
        """build_fn(frame, w, h) fills the overlay frame."""
        if self._overlay:
            self._overlay.destroy()

        ow = SW
        oh = SH - BODY_Y
        self._overlay = tk.Frame(self.root, bg=PANEL, bd=0)
        self._overlay.place(x=0, y=BODY_Y, width=ow, height=oh)

        # accent top stripe
        tk.Frame(self._overlay, bg=ACCENT, height=2).place(x=0, y=0, width=ow)

        # content area
        content = tk.Frame(self._overlay, bg=PANEL)
        content.place(x=0, y=2, width=ow, height=oh-2)

        build_fn(content, ow, oh-2)

        # tap anywhere to close
        self._overlay.bind("<Button-1>", lambda e: self._close_overlay())
        content.bind("<Button-1>", lambda e: self._close_overlay())
        # also bind all child widgets after they're created
        self.root.after(50, lambda: self._bind_overlay_children(self._overlay))

    def _bind_overlay_children(self, widget):
        widget.bind("<Button-1>", lambda e: self._close_overlay())
        for child in widget.winfo_children():
            self._bind_overlay_children(child)

    def _close_overlay(self):
        if self._overlay:
            self._overlay.destroy()
            self._overlay = None

    # ── MAIN LAYOUT ──────────────────────────────────────────
    def _build_ui(self):
        tk.Frame(self.root, bg=ACCENT, height=2).place(x=0, y=0, width=SW)

        # ── header with progress bar behind text ──────────────
        hdr = tk.Frame(self.root, bg=PANEL, height=22)
        hdr.place(x=0, y=2, width=SW)

        # progress bar canvas sits behind everything in the header
        self._bar_canvas = tk.Canvas(hdr, bg=PANEL, highlightthickness=0,
                                      width=SW, height=22)
        self._bar_canvas.place(x=0, y=0)

        # meetings
        self._bar_canvas.bind("<Button-1>", lambda e: self._zoom_calendar())
        # filled progress rect (drawn first = behind)
        self._bar_fill   = self._bar_canvas.create_rectangle(0, 0, 0, 22, fill=DIM, outline="")
        # lunch block
        self._bar_lunch  = self._bar_canvas.create_rectangle(0, 0, 0, 22, fill="#FFFFFF", outline="")
        # current time cursor line
        self._bar_cursor = self._bar_canvas.create_line(0, 0, 0, 22, fill=FG, width=1)

        # text drawn on canvas — no background rectangle
        self._bar_title = self._bar_canvas.create_text(8, 11, text="POOPID BOT", font=FB, fill=ACCENT, anchor="w")
        self._bar_clock = self._bar_canvas.create_text(SW-8, 11, text="", font=FS, fill=DIM, anchor="e")

        tk.Frame(self.root, bg=BORDER, height=1).place(x=0, y=24, width=SW)
        self._update_bar()

        self._build_quote(4,   27,  228, 140)
        self._build_minigame(4, 171, 228, 46)
        self._build_last_chance(4, 221, 228, 94)
        self._build_leaderboard_scores(236, 27,  240, 140)
        self._build_leaderboard_chances(236, 171, 240, 144)

        self._tick()

    # ── QUOTE ────────────────────────────────────────────────
    def _build_quote(self, x, y, w, h):
        inner, outer = make_panel(self.root, x, y, w, h, "// QUOTE",
                                   clickable=True,
                                   on_click=self._zoom_quote)
        self.q_lbl = tk.Label(inner, text="", font=("Courier", 11, "italic"),
            fg=FG, bg=PANEL, wraplength=w-14, justify="left", anchor="nw")
        self.q_lbl.place(x=6, y=2, width=w-12, height=h-26)
        self.a_lbl = tk.Label(inner, text="", font=FS, fg=CYAN, bg=PANEL, anchor="e")
        self.a_lbl.place(x=6, y=h-22, width=w-12)
        rebind_panel(inner)
        self._refresh_quote()

    def _refresh_quote(self):
        self._cur_quote = random.choice(self.quotes)
        q, a = self._cur_quote
        self.q_lbl.config(text=f'"{trunc(q, 130)}"')
        self.a_lbl.config(text=f"— {a}" if a else "— unknown")
        # also update zoom labels if quote overlay is open
        if hasattr(self, '_zoom_q_lbl') and self._zoom_q_lbl.winfo_exists():
            self._zoom_q_lbl.config(text=f'"{q}"')
        if hasattr(self, '_zoom_a_lbl') and self._zoom_a_lbl.winfo_exists():
            self._zoom_a_lbl.config(text=f"— {a}" if a else "— unknown")
        self.root.after(60000, self._refresh_quote)

    def _zoom_quote(self):
        q, a = self._cur_quote
        def build(f, w, h):
            tk.Label(f, text="// QUOTE", font=FZ, fg=ACCENT, bg=PANEL,
                     anchor="w").place(x=12, y=10)
            self._zoom_q_lbl = tk.Label(f, text=f'"{q}"',
                     font=("Courier", 13, "italic"),
                     fg=FG, bg=PANEL, wraplength=w-24, justify="left",
                     anchor="nw")
            self._zoom_q_lbl.place(x=12, y=40, width=w-24, height=h-80)
            self._zoom_a_lbl = tk.Label(f, text=f"— {a}" if a else "— unknown",
                     font=("Courier", 10), fg=CYAN, bg=PANEL, anchor="e")
            self._zoom_a_lbl.place(x=12, y=h-36, width=w-24)
            tk.Label(f, text="tap to close", font=FS, fg=DIM, bg=PANEL,
                     anchor="center").place(x=0, y=h-18, width=w)
        self._show_overlay(build)

    # ── LAST TARGET ──────────────────────────────────────────
    def _build_minigame(self, x, y, w, h):
        inner, outer = make_panel(self.root, x, y, w, h, "// LAST TARGET",
                                   clickable=True,
                                   on_click=self._zoom_target)
        tk.Label(inner, text="was:", font=FS, fg=DIM, bg=PANEL).place(x=6, y=6)
        self.prev_tgt_lbl = tk.Label(inner, text="???", font=FT, fg=DIM, bg=PANEL)
        self.prev_tgt_lbl.place(x=38, y=2)
        rebind_panel(inner)
        self._refresh_target()

    def _refresh_target(self):
        prev = self.shared_state.get("prev_target") or "???"
        self.prev_tgt_lbl.config(text=prev)
        if self.shared_state.get("scores_dirty"):
            self.shared_state["scores_dirty"] = False
            self._draw_scores()
        self.root.after(500, self._refresh_target)

    def _zoom_target(self):
        prev = self.shared_state.get("prev_target") or "???"
        current = self.shared_state.get("target") or "???"
        def build(f, w, h):
            tk.Label(f, text="// MINIGAME", font=FZ, fg=ACCENT, bg=PANEL,
                     anchor="w").place(x=12, y=10)
            tk.Label(f, text="last target", font=("Courier", 10), fg=DIM,
                     bg=PANEL).place(x=12, y=46)
            tk.Label(f, text=prev, font=("Courier", 48, "bold"), fg=DIM,
                     bg=PANEL).place(x=12, y=64)
            tk.Label(f, text="current (secret!)", font=("Courier", 10), fg=DIM,
                     bg=PANEL).place(x=w//2+8, y=46)
            # blur current target — show as ??? since it'd be cheating
            tk.Label(f, text="???", font=("Courier", 48, "bold"), fg=BORDER,
                     bg=PANEL).place(x=w//2+8, y=64)
            tk.Label(f, text="tap to close", font=FS, fg=DIM, bg=PANEL,
                     anchor="center").place(x=0, y=h-18, width=w)
        self._show_overlay(build)

    # ── LAST CHANCE ──────────────────────────────────────────
    def _build_last_chance(self, x, y, w, h):
        inner, outer = make_panel(self.root, x, y, w, h, "// LAST CHANCE EVENT",
                                   clickable=True,
                                   on_click=self._zoom_last_chance)
        self.lc_event_lbl = tk.Label(inner, text="none yet",
            font=("Courier", 9, "bold"), fg=AMBER, bg=PANEL, anchor="w")
        self.lc_event_lbl.place(x=6, y=4, width=w-12)
        self.lc_user_lbl = tk.Label(inner, text="", font=FS, fg=FG, bg=PANEL, anchor="w")
        self.lc_user_lbl.place(x=6, y=22, width=w-12)
        self.lc_odds_lbl = tk.Label(inner, text="", font=FS, fg=GREEN, bg=PANEL, anchor="w")
        self.lc_odds_lbl.place(x=6, y=38, width=w-12)
        rebind_panel(inner)
        self._poll_last_chance()

    def _poll_last_chance(self):
        lc = self.shared_state.get("last_chance")
        if lc is not None and lc is not self._last_chance_seen:
            self._last_chance_seen = lc
            self.lc_event_lbl.config(text=trunc(lc.get("event", ""), 26))
            self.lc_user_lbl.config(text=f"hit by: {lc.get('user', '?')}")
            self.lc_odds_lbl.config(text=f"1/{lc.get('chance', 1000)} odds")
            self._draw_chances()
        self.root.after(500, self._poll_last_chance)

    def _zoom_last_chance(self):
        lc = self._last_chance_seen
        def build(f, w, h):
            tk.Label(f, text="// LAST CHANCE EVENT", font=FZ, fg=ACCENT,
                     bg=PANEL, anchor="w").place(x=12, y=10)
            if lc:
                tk.Label(f, text=lc.get("event", ""), font=("Courier", 16, "bold"),
                         fg=AMBER, bg=PANEL, wraplength=w-24,
                         justify="left").place(x=12, y=46)
                tk.Label(f, text=f"hit by  {lc.get('user','?')}",
                         font=("Courier", 12), fg=FG, bg=PANEL).place(x=12, y=110)
                tk.Label(f, text=f"odds  1/{lc.get('chance',1000)}",
                         font=("Courier", 12), fg=GREEN, bg=PANEL).place(x=12, y=134)
            else:
                tk.Label(f, text="no chance event yet", font=("Courier", 12),
                         fg=DIM, bg=PANEL).place(x=12, y=80)
            tk.Label(f, text="tap to close", font=FS, fg=DIM, bg=PANEL,
                     anchor="center").place(x=0, y=h-18, width=w)
        self._show_overlay(build)

    # ── LEADERBOARD: scores ───────────────────────────────────
    def _build_leaderboard_scores(self, x, y, w, h):
        inner, outer = make_panel(self.root, x, y, w, h, "// LEADERBOARD",
                                   clickable=True,
                                   on_click=self._zoom_scores)
        self._lb_score_frame = inner
        self._lb_score_w = w
        self._draw_scores()
        rebind_panel(inner)
        self.root.after(10000, self._tick_scores)

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
        rebind_panel(self._lb_score_frame)

    def _tick_scores(self):
        self._draw_scores()
        self.root.after(10000, self._tick_scores)

    def _zoom_scores(self):
        def build(f, w, h):
            tk.Label(f, text="// LEADERBOARD", font=FZ, fg=ACCENT,
                     bg=PANEL, anchor="w").place(x=12, y=10)
            scores = load_scores()
            if scores:
                sorted_s = sorted(scores.items(), key=lambda x: x[1]["score"], reverse=True)
                for i, (uid, d) in enumerate(sorted_s[:10], 1):
                    ry = 40 + (i-1) * 22
                    col = [AMBER, FG, FG] + [DIM]*10
                    tk.Label(f, text=f"{i}.", font=("Courier", 10),
                             fg=col[i-1], bg=PANEL, anchor="w").place(x=12, y=ry)
                    tk.Label(f, text=trunc(d["name"], 16), font=("Courier", 10),
                             fg=FG, bg=PANEL, anchor="w").place(x=36, y=ry)
                    tk.Label(f, text=str(d["score"]), font=("Courier", 10),
                             fg=GREEN, bg=PANEL, anchor="e").place(x=w-16, y=ry)
            else:
                tk.Label(f, text="no scores yet", font=("Courier", 11),
                         fg=DIM, bg=PANEL).place(x=12, y=60)
            tk.Label(f, text="tap to close", font=FS, fg=DIM, bg=PANEL,
                     anchor="center").place(x=0, y=h-18, width=w)
        self._show_overlay(build)

    # ── LEADERBOARD: chance hits ──────────────────────────────
    def _build_leaderboard_chances(self, x, y, w, h):
        inner, outer = make_panel(self.root, x, y, w, h, "// CHANCE HITS",
                                   clickable=True,
                                   on_click=self._zoom_chances)
        self._lb_chance_frame = inner
        self._lb_chance_w = w
        self._draw_chances()
        rebind_panel(inner)
        self.root.after(10000, self._tick_chances)

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
            rebind_panel(self._lb_chance_frame)
            return
        # 2-column layout: left col x=4, right col x=col_w+6
        col_w = (self._lb_chance_w - 10) // 2
        col = 0
        ry = 2
        for event_name in sorted(all_chances.keys()):
            top_list = sorted(all_chances[event_name], key=lambda x: x[1], reverse=True)
            cx = 4 if col == 0 else col_w + 6
            block_h = 11 + len(top_list) * 11  # title + one row per person
            tk.Label(self._lb_chance_frame, text=trunc(event_name, 13),
                     font=("Courier", 7, "bold"), fg=CYAN, bg=PANEL, anchor="w").place(x=cx, y=ry)
            for j, (name, count) in enumerate(top_list):
                tk.Label(self._lb_chance_frame, text=f"{trunc(name,10)} ×{count}",
                         font=FS, fg=FG, bg=PANEL, anchor="w").place(x=cx, y=ry+11+j*11)
            col += 1
            if col == 2:
                col = 0
                ry += block_h + 3
            if ry > 120:
                break
        rebind_panel(self._lb_chance_frame)

    def _tick_chances(self):
        self._draw_chances()
        self.root.after(10000, self._tick_chances)

    def _zoom_chances(self):
        def build(f, w, h):
            tk.Label(f, text="// CHANCE HITS", font=FZ, fg=ACCENT,
                     bg=PANEL, anchor="w").place(x=12, y=10)
            scores = load_scores()
            all_chances = {}
            for uid, data in scores.items():
                name = data.get("name", uid)
                for chance_name, count in data.get("chances", {}).items():
                    if chance_name not in all_chances:
                        all_chances[chance_name] = []
                    all_chances[chance_name].append((name, count))
            if not all_chances:
                tk.Label(f, text="no chance hits yet", font=("Courier", 11),
                         fg=DIM, bg=PANEL).place(x=12, y=60)
            else:
                # 2-column layout in zoom view, all scores per event
                col_w = (w - 24) // 2
                col = 0
                ry = 38
                left_block_h = 0  # track left col height to advance ry correctly
                for event_name in sorted(all_chances.keys()):
                    top_list = sorted(all_chances[event_name], key=lambda x: x[1], reverse=True)
                    block_h = 14 + len(top_list) * 13
                    cx = 12 if col == 0 else 12 + col_w + 8
                    tk.Label(f, text=trunc(event_name, 18),
                             font=("Courier", 9, "bold"), fg=CYAN, bg=PANEL,
                             anchor="w").place(x=cx, y=ry)
                    for j, (name, count) in enumerate(top_list):
                        tk.Label(f, text=f"  {trunc(name,14)} ×{count}",
                                 font=("Courier", 9), fg=FG, bg=PANEL,
                                 anchor="w").place(x=cx, y=ry + 14 + j*13)
                    if col == 0:
                        left_block_h = block_h
                        col = 1
                    else:
                        # advance by the taller of the two columns
                        ry += max(left_block_h, block_h) + 6
                        col = 0
                        left_block_h = 0
            tk.Label(f, text="tap to close", font=FS, fg=DIM, bg=PANEL,
                     anchor="center").place(x=0, y=h-18, width=w)
        self._show_overlay(build)

    # ── DAY PROGRESS BAR ─────────────────────────────────────
    def _update_bar(self):
        now   = datetime.datetime.now()
        DAY_START  = now.replace(hour=8,  minute=0,  second=0, microsecond=0)
        DAY_END    = now.replace(hour=15, minute=45, second=0, microsecond=0)
        LUNCH_START = now.replace(hour=11, minute=45, second=0, microsecond=0)
        LUNCH_END   = now.replace(hour=12, minute=30, second=0, microsecond=0)

        total_secs = (DAY_END - DAY_START).total_seconds()

        def to_x(dt):
            secs = (dt - DAY_START).total_seconds()
            return max(0, min(SW, int(SW * secs / total_secs)))

        now_x    = to_x(now)
        lunch_x1 = to_x(LUNCH_START)
        lunch_x2 = to_x(LUNCH_END)

        # fill bar (green tint up to now)
        self._bar_canvas.coords(self._bar_fill, 0, 0, now_x, 22)
        # lunch block
        self._bar_canvas.coords(self._bar_lunch, lunch_x1, 0, lunch_x2, 22)
        # cursor line
        self._bar_canvas.coords(self._bar_cursor, now_x, 0, now_x, 22)
        
        # draw meeting blocks
        for item_id in getattr(self, '_meeting_items', []):
            self._bar_canvas.delete(item_id)
        self._meeting_items = []
        for m in self._meetings:
            if m.get("date") != datetime.datetime.now().date():
                continue
            mx1 = to_x(m["start"])
            mx2 = to_x(m["end"])
            item = self._bar_canvas.create_rectangle(
                mx1, 2, mx2, 20, fill="#2563eb", outline=""
            )
            self._meeting_items.append(item)
        # keep text on top
        self._bar_canvas.tag_raise(self._bar_cursor)
        self._bar_canvas.tag_raise(self._bar_title)
        self._bar_canvas.tag_raise(self._bar_clock)

        # flip title color: black when yellow bar is behind it, accent otherwise
        # "POOPID BOT" starts at x=8, approx 9 chars * 8px per char at size 11
        title_mid = 8 + 72 // 2  # ~midpoint of title text
        title_col = "#000000" if now_x > title_mid else ACCENT
        self._bar_canvas.itemconfig(self._bar_title, fill=title_col)

        # clock sits at right edge, approx 80px wide
        clock_mid = SW - 40
        clock_col = "#000000" if now_x > clock_mid else DIM
        self._bar_canvas.itemconfig(self._bar_clock, fill=clock_col)

        self.root.after(10000, self._update_bar)  # update every 10s

    # ── CLOCK ────────────────────────────────────────────────
    def _tick(self):
        now_str = datetime.datetime.now().strftime("%H:%M:%S")
        self._bar_canvas.itemconfig(self._bar_clock, text=now_str)
        self.root.after(1000, self._tick)
    
    # ── CALENDAR SYNC ───────────────────────────────────────
    def _fetch_meetings(self):
        try:
            all_meetings = calendar_sync.get_todays_meetings()
            self._meetings = all_meetings  # full week for the bar
            now = datetime.datetime.now()
            today = now.date()
            # next meeting is only from today
            upcoming = [m for m in self._meetings
                        if m["date"] == today and m["end"] > now]
            self._next_meeting = upcoming[0] if upcoming else None
        except Exception as e:
            print(f"[Calendar] {e}")
            self._meetings = []
            self._next_meeting = None
        self.root.after(300000, self._fetch_meetings)
    
    def _zoom_calendar(self):
        m = self._next_meeting
        def build(f, w, h):
            tk.Label(f, text="// NEXT MEETING", font=FZ, fg=ACCENT,
                     bg=PANEL, anchor="w").place(x=12, y=10)
            if m:
                duration = int((m["end"] - m["start"]).total_seconds() // 60)
                tk.Label(f, text=m["title"],
                         font=("Courier", 13, "bold"), fg=FG, bg=PANEL,
                         wraplength=w-24, justify="left").place(x=12, y=42)
                tk.Label(f, text=f'{m["start"].strftime("%H:%M")} → {m["end"].strftime("%H:%M")}  ({duration} min)',
                         font=("Courier", 11), fg=CYAN, bg=PANEL).place(x=12, y=110)
                loc = m["location"] or "no location"
                tk.Label(f, text=loc, font=("Courier", 10),
                         fg=DIM, bg=PANEL, wraplength=w-24).place(x=12, y=134)
            else:
                tk.Label(f, text="no more meetings today",
                         font=("Courier", 12), fg=DIM, bg=PANEL).place(x=12, y=80)
            tk.Label(f, text="tap to close", font=FS, fg=DIM, bg=PANEL,
                     anchor="center").place(x=0, y=h-18, width=w)
        self._show_overlay(build)


def main(shared_state=None):
    root = tk.Tk()
    app = Dashboard(root, shared_state)
    root.mainloop()

if __name__ == "__main__":
    main()