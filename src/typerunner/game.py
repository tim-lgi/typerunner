#!/usr/bin/env python3
"""
HURDLE RUSH  -  terminal typing race game
Run it with:  typerunner

Races are stored per player in ~/.hurdle_rush.db

Copyright (C) 2026 Timothy Teetzel
Licensed under the GNU General Public License v3.0 or later. See LICENSE.
"""

import curses, os, random, sqlite3, sys, time, webbrowser
from datetime import datetime
from importlib import resources

# ══ Words ═════════════════════════════════════════════════════════════════════
# ~9,300 English words in descending order of how often they occur in real
# writing, so a word's index IS its difficulty: rarer words sit deeper and run
# longer. Levels draw from a rank window that starts deeper and reaches further
# as you climb. Sampling is without replacement, so no word repeats in a race.
WORDS_PATH = os.path.expanduser("~/.hurdle_rush_words.txt")

FALLBACK = ("the and for that this with you not are from your all have new more "
            "when can has who been would there their said each which will about "
            "other than then them these some time very into just first over").split()

# Put a payment link here to offer it on the player screen. Left empty the key
# and its prompt stay hidden, so an unconfigured build never shows a dead link.
COFFEE_URL = ""

# Once you have raced a level at least once, PACE is pinned to YOUR average wpm
# for that level, minus this much — so it is a target you can just about catch,
# and it closes up as the levels climb.
PACE_HANDICAP = {1: 0.100, 2: 0.075, 3: 0.050, 4: 0.025, 5: 0.0, 6: 0.0}

LEVEL_RANGE = {          # (first rank, last rank) the level draws from
    1: (0,    1000),
    2: (0,    2000),
    3: (150,  3500),
    4: (400,  5500),
    5: (900,  7500),
    6: (1800, 9999),
}

def load_words():
    """A copy in the home directory wins, so the list can be swapped without
    reinstalling; otherwise the one shipped inside the package is used."""
    try:
        with open(WORDS_PATH) as f:
            got = [w for w in (ln.strip() for ln in f) if w]
        if len(got) >= 200:
            return got
    except OSError:
        pass
    try:
        text = resources.files(__package__).joinpath("words.txt").read_text()
        got  = [w for w in (ln.strip() for ln in text.splitlines()) if w]
        if len(got) >= 200:
            return got
    except (OSError, ModuleNotFoundError, AttributeError, TypeError):
        pass
    return FALLBACK

WORDS = load_words()

def make_words(level, n=40):
    lo, hi = LEVEL_RANGE[max(1, min(level, 6))]
    band = WORDS[lo:hi] or WORDS
    return random.sample(band, min(n, len(band)))

# ══ Sprites  (every row exactly 8 chars) ══════════════════════════════════════
SRUN_W, SRUN_H = 8, 5

RUN1 = ["  .@@.  ", " =@@@@= ", "  =@@=  ", "  @  /% ", " @%     "]
RUN2 = ["  .@@.  ", " =@@@@= ", "  =@@=  ", " \\  @   ", "    %@  "]
JUMP = ["  .@@.  ", " =@@@@= ", "  =@@=  ", " =@  @= ", "        "]
STRCH= ["  .@@.  ", " =@@@@= ", "  =@@=  ", "  |  |  ", " =|  |= "]
# Stumble: a full wipeout — body flat on the deck, limbs spread
STUM = ["        ", "        ", "   .@.  ", "=@@@@@@=", "=@%@=@%="]
# Victory: arms up / arms out, driven by the bounce cycle
VICT1= ["\\ .@@. /", " =@@@@= ", "  =@@=  ", "  |  |  ", " =|  |= "]
VICT2= ["  .@@.  ", "=@@@@@@=", "  =@@=  ", "  =  =  ", "        "]

JUMP_ARC    = [0, 1, 2, 3, 3, 2, 1, 0]
VICT_BOUNCE = [0, 1, 2, 3, 3, 2, 1, 0, 0, 0]
MAX_LIFT    = 3

FRAMES = {
    'run':     (RUN1, RUN2),
    'jump':    (JUMP,),
    'stretch': (STRCH,),
    'stumble': (STUM,),
    'victory': (VICT1, VICT2),
}

HRD_ROW, HRD_W, HRD_H = "||", 2, 2
SPARK = "▁▂▃▄▅▆▇█"

# ══ Colours ═══════════════════════════════════════════════════════════════════
# Body text, frames and the cursor use -1, the terminal's own foreground, so the
# game stays readable on a light theme and a dark one alike. Naming a literal
# colour here (white) makes it vanish on whichever background matches it.
(CP_NORM, CP_GREEN, CP_RED, CP_YELLOW, CP_CYAN,
 CP_MAGEN, CP_TRACK, CP_GOLD, CP_FG) = range(1, 10)

CP_LEVEL = {lv: 9 + lv for lv in range(1, 7)}      # pairs 10..15, one per level

# A light-to-dark green ramp from the xterm 256 cube, so a chart mixing levels
# reads at a glance: the higher the level, the deeper the green. Falls back to
# one flat green where the terminal has only the 8 base colours.
LEVEL_RAMP = (46, 40, 34, 28, 22, 23)

def init_colors():
    curses.start_color()
    curses.use_default_colors()
    for pair, col in ((CP_NORM,   -1),
                      (CP_GREEN,  curses.COLOR_GREEN),
                      (CP_RED,    curses.COLOR_RED),
                      (CP_YELLOW, curses.COLOR_YELLOW),
                      (CP_CYAN,   curses.COLOR_CYAN),
                      (CP_MAGEN,  curses.COLOR_MAGENTA),
                      (CP_TRACK,  curses.COLOR_BLUE),
                      (CP_GOLD,   curses.COLOR_YELLOW),
                      (CP_FG,     -1)):
        curses.init_pair(pair, col, -1)
    rich = curses.COLORS >= 256
    for lv, pair in CP_LEVEL.items():
        curses.init_pair(pair,
                         LEVEL_RAMP[lv - 1] if rich else curses.COLOR_GREEN, -1)

# ══ Database ══════════════════════════════════════════════════════════════════
DB_PATH = os.path.expanduser("~/.hurdle_rush.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS players (
    id          INTEGER PRIMARY KEY,
    name        TEXT UNIQUE NOT NULL,
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS races (
    id          INTEGER PRIMARY KEY,
    player_id   INTEGER NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    played_at   TEXT    NOT NULL,
    level       INTEGER NOT NULL,
    wpm         INTEGER NOT NULL,
    accuracy    INTEGER NOT NULL,
    score       INTEGER NOT NULL,
    seconds     REAL    NOT NULL,
    words       INTEGER NOT NULL,
    chars_ok    INTEGER NOT NULL,
    chars_tried INTEGER NOT NULL,
    place       INTEGER NOT NULL,
    won         INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_races_player ON races(player_id, id);
"""

def db_run(sql, args=(), fetch=None):
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        cur = conn.execute(sql, args)
        if fetch == 'one':
            return cur.fetchone()
        if fetch == 'all':
            return cur.fetchall()
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()

def db_init():
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()

def players_all():
    return db_run("""
        SELECT p.id, p.name,
               COUNT(r.id)              AS races,
               COALESCE(MAX(r.wpm), 0)  AS best_wpm,
               MAX(r.id)                AS last_race
        FROM players p
        LEFT JOIN races r ON r.player_id = p.id
        GROUP BY p.id, p.name
        ORDER BY (last_race IS NULL), last_race DESC, p.name
    """, fetch='all')

def player_create(name):
    return db_run("INSERT INTO players (name, created_at) VALUES (?, ?)",
                  (name, datetime.now().isoformat(timespec='seconds')))

def player_delete(pid):
    db_run("DELETE FROM races WHERE player_id = ?", (pid,))
    db_run("DELETE FROM players WHERE id = ?", (pid,))

def player_best(pid, level=None):
    """Best result as (wpm, accuracy), for one level or across all of them.

    Accuracy breaks a tie on wpm, so matching your record at a cleaner accuracy
    counts as beating it. Levels use rarer and longer words, so a record is only
    meaningful against the same level — callers comparing a race pass its level.
    """
    sql  = "SELECT wpm, accuracy FROM races WHERE player_id = ?"
    args = [pid]
    if level is not None:
        sql += " AND level = ?"
        args.append(level)
    row = db_run(sql + " ORDER BY wpm DESC, accuracy DESC LIMIT 1",
                 tuple(args), fetch='one')
    return (row['wpm'], row['accuracy']) if row else (0, 0)

def player_level_rows(pid):
    """Per-level summary, so overall figures are never mistaken for level ones."""
    return db_run("""SELECT level,
                            COUNT(*)                     AS races,
                            COALESCE(MAX(wpm), 0)        AS best_wpm,
                            COALESCE(ROUND(AVG(wpm)), 0) AS avg_wpm,
                            COALESCE(MAX(accuracy), 0)   AS best_acc,
                            COALESCE(SUM(won), 0)        AS wins
                     FROM races WHERE player_id = ?
                     GROUP BY level ORDER BY level""", (pid,), fetch='all')

def player_avg_wpm(pid, level):
    """(races_at_this_level, mean wpm) — drives the PACE runner's handicap."""
    row = db_run("""SELECT COUNT(*) AS n, COALESCE(AVG(wpm), 0) AS avg_wpm
                    FROM races WHERE player_id = ? AND level = ?""",
                 (pid, level), fetch='one')
    return (row['n'], row['avg_wpm']) if row else (0, 0.0)

def player_stats(pid):
    return db_run("""
        SELECT COUNT(*)                        AS races,
               COALESCE(MAX(wpm), 0)           AS best_wpm,
               COALESCE(ROUND(AVG(wpm)), 0)    AS avg_wpm,
               COALESCE(MAX(accuracy), 0)      AS best_acc,
               COALESCE(SUM(won), 0)           AS wins
        FROM races WHERE player_id = ?
    """, (pid,), fetch='one')

def races_recent(pid, limit=20, level=None):
    sql  = "SELECT wpm, accuracy, seconds, played_at, level, place FROM races WHERE player_id = ?"
    args = [pid]
    if level is not None:
        sql += " AND level = ?"
        args.append(level)
    args.append(limit)
    return list(reversed(db_run(sql + " ORDER BY id DESC LIMIT ?",
                                tuple(args), fetch='all')))

def race_save(pid, g, place, seconds):
    return db_run("""
        INSERT INTO races (player_id, played_at, level, wpm, accuracy, score,
                           seconds, words, chars_ok, chars_tried, place, won)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    """, (pid, datetime.now().isoformat(timespec='seconds'), g.level, g.wpm,
          g.accuracy, g.score, round(seconds, 2), g.total, g.chars_ok,
          g.chars_tried, place, 1 if place == 1 else 0))

DASH = ('▁', '─', '▔')     # low / middle / high within a row

def chart_block(wpms, accs=None, levels=None, rows=5, bar_w=2):
    """Bars are wpm; the overlaid dash line is accuracy, on ONE shared scale.

    The scale always reaches at least 100 so an accuracy percentage lands at
    its own height — 97% sits where 97 wpm would — which puts the accuracy
    line above the bars in a good race and lets it cut through them in a
    sloppy one. The floor sits just under the slowest race so the bars do not
    bottom out as solid blocks.

    Each row holds 8 sub-steps for the bars and 3 for the dash, so heights
    stay distinct instead of collapsing. Returns rows of [(text, kind)]
    segments, top row first, where kind is 'bar' or 'acc'.
    """
    if not wpms:
        return [], 0, 0
    best, worst = max(wpms), min(wpms)
    spread = max(best - worst, 1)
    hi = max(100.0, best * 1.08)                    # always room above 100
    lo = max(0.0, worst - max(spread * 0.15, 2))
    span = max(hi - lo, 1e-9)
    units = rows * 8

    cells = [[(' ' * bar_w, 'bar') for _ in wpms] for _ in range(rows)]
    for ci, v in enumerate(wpms):
        total = int(round((v - lo) / span * units))
        kind  = f"lv{levels[ci]}" if levels else 'bar'
        for r in range(rows):
            e = max(0, min(8, total - (rows - 1 - r) * 8))
            if e:
                cells[r][ci] = (SPARK[e - 1] * bar_w, kind)
    for ci, a in enumerate(accs or ()):
        pos = min(max((a - lo) / span * units, 0.0), units - 0.001)
        r = rows - 1 - int(pos // 8)
        if 0 <= r < rows:
            cells[r][ci] = (DASH[min(2, int(pos % 8) // 3)] * bar_w, 'acc')

    out = []
    for row_cells in cells:                          # merge same-kind runs
        segs, buf, kind = [], "", row_cells[0][1]
        for text, k in row_cells:
            if k != kind:
                segs.append((buf, kind)); buf, kind = text, k
            else:
                buf += text
        segs.append((buf, kind))
        out.append(segs)
    return out, lo, hi

# ══ Word layout ═══════════════════════════════════════════════════════════════
class WordLayout:
    def __init__(self, words, width):
        self.words, self.lines, self._wl = words, [], {}
        cur, cw = [], 0
        for i, w in enumerate(words):
            need = len(w) + (1 if cur else 0)
            if cur and cw + need > width:
                self.lines.append(cur); cur, cw = [i], len(w)
            else:
                cur.append(i); cw += need
        if cur:
            self.lines.append(cur)
        for li, line in enumerate(self.lines):
            for wi in line:
                self._wl[wi] = li

    def line_of(self, wi):
        return self._wl.get(wi, len(self.lines) - 1)

# ══ Runner ════════════════════════════════════════════════════════════════════
class Runner:
    __slots__ = ('lane','is_player','ai_wpm','cp','pct','frame','ftick','state',
                 'jump_idx','stum_tick','finished','finish_t','melt','bounce_i',
                 'next_hurdle','name')

    def __init__(self, lane, is_player, name, ai_wpm=0, cp=CP_CYAN):
        self.lane, self.is_player, self.name = lane, is_player, name
        self.ai_wpm, self.cp = ai_wpm, cp
        self.pct = self.ftick = self.stum_tick = self.melt = 0.0
        self.frame = self.jump_idx = self.bounce_i = self.next_hurdle = 0
        self.state = 'run'
        self.finished = False
        self.finish_t = None

    def screen_x(self, tx, tw):
        return tx + int(self.pct * 0.01 * max(0, tw - SRUN_W))

    def lift(self):
        if self.state == 'jump':
            return JUMP_ARC[min(self.jump_idx, len(JUMP_ARC) - 1)]
        if self.state == 'victory':
            return VICT_BOUNCE[self.bounce_i % len(VICT_BOUNCE)]
        return 0

    def ai_step(self, dt, total_chars, hurdle_pcts, elapsed):
        if self.finished:
            return
        self.pct = min(100.0, self.pct + (self.ai_wpm * 5 / 60 / total_chars) * dt * 100)
        if self.pct >= 100.0:
            self.finished = True
            self.finish_t = elapsed
            # over the line: bounce at the finish while the race runs on
            self.state, self.bounce_i, self.ftick, self.frame = 'victory', 0, 0.0, 0
            return
        # hurdle_pcts is sorted and pct only rises: walk a pointer, never rescan
        while (self.next_hurdle < len(hurdle_pcts)
               and hurdle_pcts[self.next_hurdle] <= self.pct):
            self.next_hurdle += 1
            if self.state == 'run':
                self.state, self.jump_idx, self.ftick = 'jump', 0, 0.0

    def animate(self, dt):
        self.ftick += dt
        if self.state == 'jump':
            if self.ftick > 0.07:
                self.ftick = 0.0
                self.jump_idx += 1
                if self.jump_idx >= len(JUMP_ARC):
                    self.state, self.frame, self.jump_idx = 'run', 0, 0
        elif self.state == 'stumble':
            self.stum_tick += dt
            if self.stum_tick > 1.6:
                self.state, self.frame, self.ftick = 'stretch', 0, 0.0
        elif self.state == 'victory':
            if self.ftick > 0.06:
                self.ftick = 0.0
                self.bounce_i += 1
                self.frame = 1 if self.lift() else 0
        elif self.ftick > 0.14:
            self.ftick = 0.0
            self.frame ^= 1

# ══ Game ══════════════════════════════════════════════════════════════════════
class Game:
    def __init__(self, level, player_name, pace_wpm=None):
        self.level       = level
        self.score       = 0
        self.words       = make_words(level)
        self.total       = len(self.words)
        self.total_chars = sum(map(len, self.words))
        self.wi = self.ci = 0
        self.chars_before = 0          # running total: avoids an O(n) sum per key
        self.error_at    = -1
        self.typed       = []
        self.wpm = self.chars_ok = self.chars_tried = 0
        self.accuracy    = 100
        self.elapsed     = 0.0
        self.t_start     = None
        self.t_last      = time.time()
        self.over_t      = None
        self.game_over   = False
        self.won         = False
        self.saved       = False
        self.place       = 1
        self.hurdle_set  = set(range(2, self.total, 3))
        self.layout      = None
        self.layout_w    = -1

        cc = 0
        self.hurdle_pcts = []
        for i, w in enumerate(self.words):
            cc += len(w)
            if i in self.hurdle_set:
                self.hurdle_pcts.append(cc / self.total_chars * 100)

        base = 20 + level * 7
        self.pace_wpm = pace_wpm if pace_wpm else base
        self.runners = [
            Runner(0, True,  player_name[:4].upper() or "YOU",  cp=CP_CYAN),
            Runner(1, False, "PACE", ai_wpm=self.pace_wpm, cp=CP_MAGEN),
            Runner(2, False, "RIVL", ai_wpm=base + 9,      cp=CP_YELLOW),
        ]
        self.player = self.runners[0]

    def word(self):
        return self.words[self.wi] if self.wi < self.total else ""

    # ── input ────────────────────────────────────────────────────────────────
    def handle_key(self, ch):
        if self.game_over:
            return
        w = self.word()
        if not w:
            return
        p = self.player

        if ch in (curses.KEY_BACKSPACE, 127, 8):
            if self.ci > 0:
                self.ci -= 1
                if self.typed:
                    self.typed.pop()
                if self.error_at >= self.ci:
                    self.error_at = -1
                    if p.state == 'stumble':
                        p.state, p.frame, p.ftick = 'stretch', 0, 0.0

        elif ch == ord(' '):
            # the word must be complete AND clean — no skipping past mistakes
            if self.ci == len(w) and self.error_at == -1 and self.wi < self.total - 1:
                self._complete_word()

        elif 33 <= ch <= 126:
            if self.ci >= len(w):
                return
            self.chars_tried += 1
            if self.error_at != -1:
                self.typed.append(chr(ch))
                self.ci += 1
            elif chr(ch) == w[self.ci]:
                self.typed.append(chr(ch))
                self.ci += 1
                self.chars_ok += 1
                if p.state in ('run', 'stretch'):
                    p.state, p.frame = 'run', p.frame ^ 1
                p.pct = min(99.9, (self.chars_before + self.ci) / self.total_chars * 100)
                if self.ci == len(w) and self.wi == self.total - 1:
                    self._complete_word()          # last letter ends the race
            else:
                self.error_at = self.ci
                self.typed.append(chr(ch))
                self.ci += 1
                p.state, p.stum_tick, p.frame = 'stumble', 0.0, 0
            self.accuracy = int(self.chars_ok / self.chars_tried * 100)

    def _complete_word(self):
        w = self.word()
        p = self.player
        pts = len(w) * 10
        if self.wi in self.hurdle_set:
            pts *= 3
            p.state, p.jump_idx, p.ftick = 'jump', 0, 0.0
        elif p.state != 'jump':
            p.state = 'run'
        self.score += pts
        self.chars_before += len(w)
        self.wi += 1
        self.ci = 0
        self.error_at = -1
        self.typed = []
        if self.wi >= self.total:
            p.pct, p.finished, p.finish_t = 100.0, True, self.elapsed
            self._finish()

    # ── race end ─────────────────────────────────────────────────────────────
    def _finish(self):
        if self.game_over:
            return
        self.game_over = True
        self.over_t    = time.time()
        order = sorted(self.runners,
                       key=lambda r: (0, r.finish_t) if r.finish_t is not None
                                     else (1, -r.pct))
        for i, r in enumerate(order):
            if i == 0:
                r.state, r.bounce_i, r.ftick, r.frame = 'victory', 0, 0.0, 0
            elif r.state == 'victory':
                r.state = 'run'        # placed but did not win: stop celebrating, melt
        self.place = order.index(self.player) + 1
        self.won   = self.place == 1

    # ── per-frame update ─────────────────────────────────────────────────────
    def tick(self):
        now = time.time()
        dt, self.t_last = now - self.t_last, now

        if not self.game_over:
            if self.t_start is None:
                return                 # nobody moves until the first keystroke
            self.elapsed = now - self.t_start
            if self.chars_ok:
                self.wpm = int((self.chars_ok / 5) / max(self.elapsed / 60, 1e-6))
            for r in self.runners:
                if not r.is_player:
                    r.ai_step(dt, self.total_chars, self.hurdle_pcts, self.elapsed)
                r.animate(dt)
            # the race runs until YOU cross the line; a CPU finishing first just
            # leaves it bouncing at the finish, it does not end your race
        else:
            for r in self.runners:
                if r.state == 'victory':
                    r.animate(dt)
                else:
                    r.melt = min(1.0, r.melt + dt / 2.0)

# ══ Draw helpers ══════════════════════════════════════════════════════════════
_H = _W = 0

def safe_add(scr, row, col, text, attr=0):
    if row < 0 or row >= _H:
        return
    if col < 0:
        text, col = text[-col:], 0
    if col >= _W or not text:
        return
    text = text[:_W - col]
    if not text:
        return
    try:
        scr.addstr(row, col, text, attr)
    except curses.error:
        pass

def draw_sprite(scr, row, col, art, cp, sink=0, floor=None, dim=False):
    attr = curses.color_pair(cp) | (curses.A_DIM if dim else curses.A_BOLD)
    for i, line in enumerate(art):
        y = row + i + sink
        if floor is not None and y >= floor:
            break
        safe_add(scr, y, col, line, attr)

def draw_frame(scr, row, col, width, height, attr):
    inner = width - 2
    safe_add(scr, row, col, '╔' + '═' * inner + '╗', attr)
    for i in range(1, height - 1):
        safe_add(scr, row + i, col, '║', attr)
        safe_add(scr, row + i, col + width - 1, '║', attr)
    safe_add(scr, row + height - 1, col, '╚' + '═' * inner + '╝', attr)

def draw_panel(scr, row, col, width, lines, attr):
    """Framed, opaque panel.

    A line is a plain string, a (text, attr) pair, or a LIST of (text, attr)
    segments laid left to right — which lets one row carry two colours, as the
    progress chart does for its bars and its accuracy line.
    """
    height = len(lines) + 2
    blank  = ' ' * (width - 2)
    for i in range(1, height - 1):
        safe_add(scr, row + i, col + 1, blank)
    draw_frame(scr, row, col, width, height, attr)
    for i, ln in enumerate(lines):
        y, limit = row + 1 + i, width - 4
        if isinstance(ln, list):
            x = 0
            for text, a in ln:
                if x >= limit:
                    break
                safe_add(scr, y, col + 2 + x, text[:limit - x], a)
                x += len(text)
        else:
            text, a = ln if isinstance(ln, tuple) else (
                ln, curses.color_pair(CP_NORM) | curses.A_BOLD)
            safe_add(scr, y, col + 2, text[:limit], a)
    return height

def centre(text, width):
    return text.center(width)

# ══ Layout constants ══════════════════════════════════════════════════════════
# 0 stats · 1 blank · 2-6 word frame · 7-9 jump clearance · 10+ lanes
# A lane is SRUN_H runner rows + 1 track row + headroom for the jump arc.
# Headroom shrinks on a short terminal, and lift is clamped to match, so a
# jumping runner can never climb into the lane above.
WORD_ROW  = 2
BODY_Y    = 10
LANE_MIN  = SRUN_H + 1
LANE_MAX  = SRUN_H + 1 + MAX_LIFT
TX        = 1
MIN_H     = BODY_Y + 3 * LANE_MIN
MIN_W     = 64

def lane_metrics(h):
    lane_h = max(LANE_MIN, min(LANE_MAX, (h - BODY_Y) // 3))
    return lane_h, lane_h - LANE_MIN

def draw_word_line(scr, row, col, avail, layout, li, cur_wi, typed, error_at, hurdle_set):
    if li < 0 or li >= len(layout.lines):
        return
    x, limit = col, col + avail
    ntyped = len(typed)
    for j, wi in enumerate(layout.lines[li]):
        word = layout.words[wi]
        if x >= limit:
            return
        if wi < cur_wi:
            safe_add(scr, row, x, word[:limit - x], curses.color_pair(CP_GREEN))
            x += len(word)
        elif wi == cur_wi:
            for i, chx in enumerate(word):
                if x >= limit:
                    return
                if i < ntyped:
                    a = (curses.color_pair(CP_RED) if error_at != -1 and i >= error_at
                         else curses.color_pair(CP_GREEN)) | curses.A_BOLD
                elif i == ntyped:
                    a = curses.color_pair(CP_FG) | curses.A_REVERSE | curses.A_BOLD
                else:
                    a = curses.color_pair(CP_NORM) | curses.A_BOLD
                safe_add(scr, row, x, chx, a)
                x += 1
        else:
            a = (curses.color_pair(CP_GOLD) | curses.A_BOLD if wi in hurdle_set
                 else curses.color_pair(CP_NORM) | curses.A_BOLD)
            safe_add(scr, row, x, word[:limit - x], a)
            x += len(word)
        x += 1          # the space between words

# ══ Race screen ═══════════════════════════════════════════════════════════════
def draw_race(scr, app, g):
    w = _W
    track_w = w - TX - 1
    inner_w = w - 4

    if g.layout_w != inner_w:
        g.layout, g.layout_w = WordLayout(g.words, inner_w), inner_w
        app.track_line = '=' * max(0, track_w - 5)
        app.hurdle_xs  = [TX + 5 + int(p * 0.01 * max(0, track_w - 5 - HRD_W))
                          for p in g.hurdle_pcts]

    over    = g.game_over
    elapsed = (time.time() - g.over_t) if over else 0.0

    # word frame — slides up and off once the race ends.
    # Drawn before the stats bar so it never paints over row 0 on its way out.
    off = int(min(1.0, elapsed / 0.35) * (WORD_ROW + 6)) if over else 0
    if off < WORD_ROW + 6:
        draw_frame(scr, WORD_ROW - off, 0, w, 5,
                   curses.color_pair(CP_FG) | curses.A_BOLD)
        cur_line = g.layout.line_of(g.wi)
        for slot in range(3):
            draw_word_line(scr, WORD_ROW + 1 + slot - off, 2, inner_w,
                           g.layout, cur_line + slot, g.wi, g.typed,
                           g.error_at, g.hurdle_set)

    # stats bar
    mins, secs = divmod(g.elapsed, 60)
    tstr = f"{int(mins)}:{secs:04.1f}" if mins else f"{secs:.1f}s"
    safe_add(scr, 0, 0, ' ' * w)
    safe_add(scr, 0, 1,
             f"{app.player['name'][:12]:<12} WPM {g.wpm:3d}   Acc {g.accuracy:3d}%   "
             f"Time {tstr:>7}   Lv {g.level}   Score {g.score:5d}   "
             f"Word {g.wi}/{g.total}",
             curses.color_pair(CP_YELLOW))
    title = " HURDLE RUSH "
    safe_add(scr, 0, w - len(title) - 1, title,
             curses.color_pair(CP_CYAN) | curses.A_BOLD | curses.A_REVERSE)

    # lanes
    hattr = curses.color_pair(CP_GOLD) | curses.A_BOLD
    tattr = curses.color_pair(CP_TRACK) | curses.A_BOLD
    fattr = curses.color_pair(CP_FG) | curses.A_BOLD
    finish_x = TX + track_w - 1
    lane_h, max_lift = lane_metrics(_H)
    for r in g.runners:
        track_row = BODY_Y + r.lane * lane_h + SRUN_H
        safe_add(scr, track_row, TX, f"{r.name:<4}",
                 curses.color_pair(r.cp) | curses.A_BOLD)
        safe_add(scr, track_row, TX + 5, app.track_line, tattr)

        for hx in app.hurdle_xs:
            for dy in range(1, HRD_H + 1):
                safe_add(scr, track_row - dy, hx, HRD_ROW, hattr)
        if not r.finished:          # posts would clutter the finish celebration
            for dy in (1, 2, 3):
                safe_add(scr, track_row - dy, finish_x, '┋', fattr)

        art  = FRAMES[r.state][r.frame % len(FRAMES[r.state])]
        base = track_row - SRUN_H
        if over and r.state != 'victory':
            draw_sprite(scr, base, r.screen_x(TX, track_w), art, r.cp,
                        sink=int(r.melt * (SRUN_H + 1)), floor=track_row,
                        dim=r.melt > 0.45)
        else:
            draw_sprite(scr, base - min(r.lift(), max_lift),
                        r.screen_x(TX, track_w), art, r.cp)

    if over and app.result:
        draw_result_box(scr, app, g, elapsed)

# ══ Result box ════════════════════════════════════════════════════════════════
ORDINAL = {1: "1st", 2: "2nd", 3: "3rd"}

def result_lines(app, g, width):
    inner = width - 4
    gold  = curses.color_pair(CP_GOLD)  | curses.A_BOLD
    cyan  = curses.color_pair(CP_CYAN)  | curses.A_BOLD
    norm  = curses.color_pair(CP_NORM) | curses.A_BOLD
    soft   = curses.color_pair(CP_CYAN)
    green = curses.color_pair(CP_GREEN) | curses.A_BOLD
    red   = curses.color_pair(CP_RED)   | curses.A_BOLD

    res = app.result
    mins, secs = divmod(res['seconds'], 60)
    tstr = f"{int(mins)}m {secs:05.2f}s" if mins else f"{secs:.2f}s"
    bw, ba = res['prev_best']
    if res['prior_n']:
        cmp_ = f"   (lv {g.level} avg {int(round(res['prior_avg']))}, best {bw})"
    else:
        cmp_ = f"   (first race at level {g.level})"

    def row(label, value, a=norm):
        return (f"{label:<11}{value}", a)

    lines = [
        (centre("RACE COMPLETE" if g.won else "RACE OVER", inner),
         gold if g.won else red),
        "",
        row("Player",   app.player['name'], cyan),
        row("Finish",   f"{ORDINAL.get(g.place, g.place)} of {len(g.runners)}",
            gold if g.won else norm),
        row("Time",     tstr),
        row("WPM",      f"{g.wpm}{cmp_}", green if res['is_best'] else norm),
        row("Accuracy", f"{g.accuracy}%"),
        row("Score",    f"{g.score}"),
        row("Level",    f"{g.level}"),
    ]
    if res['is_best']:
        lines.append((centre(f"NEW BEST AT LEVEL {g.level}", inner), green))
    recent = res['recent']
    if len(recent) > 1:
        rows_ = chart_block([r[0] for r in recent], [r[1] for r in recent],
                            rows=5, bar_w=2)
        rows_, lo, hi = rows_[0], rows_[1], rows_[2]
        attr_of = {'bar': green, 'acc': gold}
        last = len(rows_) - 1
        lines += ["", (f"Progress   last {len(recent)} races at level {g.level}", cyan),
                  [("bars wpm", green), ("    ", soft),
                   ("dashes accuracy", gold)]]
        for i, segs in enumerate(rows_):
            tag = (f"{int(hi):>5} ┤" if i == 0 else
                   f"{int(lo):>5} ┤" if i == last else "      ┤")
            lines.append([(tag, soft)] + [(t, attr_of[k]) for t, k in segs])
        lines.append((f"      └{'─' * sum(len(t) for t, _ in rows_[0])}", soft))
    lines += ["", (centre("R retry   N next   H history   P player   Q quit",
                          inner), soft)]
    return lines

def draw_result_box(scr, app, g, elapsed):
    width  = min(58, _W - 4)
    lines  = result_lines(app, g, width)
    height = len(lines) + 2
    # sit below the word frame, but ride up if a short terminal would clip it
    target = max(1, min(BODY_Y - 3, _H - height - 1))
    t      = max(0.0, min(1.0, (elapsed - 0.25) / 0.6))
    ease   = 1 - (1 - t) ** 3
    row    = int(-height + (target + height) * ease)
    draw_panel(scr, row, (_W - width) // 2, width, lines,
               curses.color_pair(CP_GOLD if g.won else CP_FG) | curses.A_BOLD)

# ══ Player select ═════════════════════════════════════════════════════════════
def draw_players(scr, app):
    width = min(54, _W - 4)
    inner = width - 4
    cyan  = curses.color_pair(CP_CYAN) | curses.A_BOLD
    soft   = curses.color_pair(CP_CYAN)
    gold  = curses.color_pair(CP_GOLD) | curses.A_BOLD
    norm  = curses.color_pair(CP_NORM) | curses.A_BOLD

    lines = [(centre("HURDLE RUSH", inner), gold), ""]
    if not app.players:
        lines += [("No players yet — press N to create one.", norm), ""]
    else:
        lines += [("Who is racing?", norm), ""]
        for i, p in enumerate(app.players):
            sel  = i == app.sel
            mark = '>' if sel else ' '
            if sel and app.confirm_delete:
                text = f"{mark} {p['name'][:16]:<16}  delete? press D again"
            else:
                text = (f"{mark} {p['name'][:16]:<16}"
                        f"{p['best_wpm']:>5} wpm{p['races']:>5} races")
            lines.append((text, cyan if sel else norm))
        lines.append("")

    if app.msg:
        lines.append((app.msg, curses.color_pair(CP_RED) | curses.A_BOLD))
    lines += [(centre("up/down select    ENTER race    S player stats", inner), soft),
              (centre("N new player    D delete    Q quit", inner), soft)]
    if COFFEE_URL:
        lines += ["", (centre("C   buy Tim a coffee", inner), gold)]
    draw_panel(scr, max(1, (_H - len(lines) - 2) // 3),
               (_W - width) // 2, width, lines, cyan)

def draw_newname(scr, app):
    width = min(48, _W - 4)
    inner = width - 4
    cyan  = curses.color_pair(CP_CYAN) | curses.A_BOLD
    soft   = curses.color_pair(CP_CYAN)
    lines = [(centre("NEW PLAYER", inner), cyan), "",
             ("Name:", curses.color_pair(CP_NORM) | curses.A_BOLD),
             (f"  {app.newname}_", curses.color_pair(CP_FG) | curses.A_BOLD), ""]
    if app.msg:
        lines.append((app.msg, curses.color_pair(CP_RED) | curses.A_BOLD))
    lines.append((centre("ENTER create    ESC cancel", inner), soft))
    draw_panel(scr, max(1, (_H - len(lines) - 2) // 3),
               (_W - width) // 2, width, lines, cyan)

# ══ History / progress graph ══════════════════════════════════════════════════
def draw_history(scr, app):
    rows  = app.history
    st    = app.stats
    width = min(76, _W - 4)
    inner = width - 4
    cyan  = curses.color_pair(CP_CYAN) | curses.A_BOLD
    soft   = curses.color_pair(CP_CYAN)
    gold  = curses.color_pair(CP_GOLD) | curses.A_BOLD
    norm  = curses.color_pair(CP_NORM) | curses.A_BOLD

    lines = [(centre(f"PROGRESS  —  {app.player['name']}", inner), gold), ""]

    if not rows:
        lines += [(centre("No races recorded yet.", inner), norm), ""]
    else:
        green   = curses.color_pair(CP_GREEN) | curses.A_BOLD
        chart_h = max(4, min(8, _H - 16))
        # Bars start wide and narrow as races pile up, so the whole history
        # keeps fitting. Only once even single-column bars overflow does the
        # oldest get dropped.
        space   = max(1, inner - 8)
        bar_w   = 3 if len(rows) * 3 <= space else (
                  2 if len(rows) * 2 <= space else 1)
        avail   = max(1, space // bar_w)
        vis     = rows[-avail:]
        bars, lo, hi = chart_block([r['wpm'] for r in vis],
                                   [r['accuracy'] for r in vis],
                                   levels=[r['level'] for r in vis],
                                   rows=chart_h, bar_w=bar_w)
        lv_attr = {lv: curses.color_pair(p) | curses.A_BOLD
                   for lv, p in CP_LEVEL.items()}
        attr_of = {'bar': green, 'acc': gold}
        attr_of.update({f"lv{lv}": a for lv, a in lv_attr.items()})
        last_i  = len(bars) - 1

        legend = [("bars wpm", norm), ("   ", soft), ("dashes accuracy", gold),
                  ("   levels", norm)]
        for lv in sorted({r['level'] for r in vis}):
            legend += [(f" {lv}", norm), ("██", lv_attr[lv])]
        lines.append(legend)
        for i, segs in enumerate(bars):
            tag = (f"{int(hi):>4} ┤" if i == 0 else
                   f"{int(lo):>4} ┤" if i == last_i else "     ┤")
            lines.append([(tag, soft)] + [(t, attr_of[k]) for t, k in segs])
        lines.append(("     └" + "─" * sum(len(t) for t, _ in bars[0]), soft))
        lines += ["",
                  (f"  {'':<12}{'races':>6}{'wins':>6}{'best':>6}"
                   f"{'avg':>6}{'acc':>7}", soft),
                  (f"  {'all levels':<12}{st['races']:>6}{st['wins']:>6}"
                   f"{st['best_wpm']:>6}{int(st['avg_wpm']):>6}"
                   f"{st['best_acc']:>6}%", norm)]
        for lr in player_level_rows(app.player['id']):
            lines.append((f"  {'level ' + str(lr['level']):<12}{lr['races']:>6}"
                          f"{lr['wins']:>6}{lr['best_wpm']:>6}"
                          f"{int(lr['avg_wpm']):>6}{lr['best_acc']:>6}%", soft))
        last = rows[-1]
        lines += ["", (f"  latest  {last['wpm']} wpm   {last['accuracy']}%   "
                       f"{last['seconds']:.2f}s   level {last['level']}   "
                       f"{ORDINAL.get(last['place'], last['place'])}", soft)]

    lines += ["", (centre("ESC back    Q quit", inner), soft)]
    draw_panel(scr, max(1, (_H - len(lines) - 2) // 4),
               (_W - width) // 2, width, lines, cyan)

# ══ Welcome sequence ══════════════════════════════════════════════════════════
HERO_ART = """
                                                .=*#*=.
                                               =@@@@@@@#
                                              .#@@@@@@@%=
                                       .--:.. .#@@@@@@@%:
                               .-*%@@@@@@@@@@@@@@@@@@@@%-                =@@*.
                       .:+%@@@@@@@@@@@@@@@@@@@@@@@@@@@@%*+==+#%@%#######@@%#=.
                    :+%@@@@@@###%%%%@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@%#*+=-:.
           .-----+#@@@@#*+=:.      +@@@@@@@@@@@@@@%+--=++=-::---:.
          =*%@@@@@#=:.            -@@@@@@@@@@@@@@+.
           -#=#@=                :%@@@@@@@@@@@@#:
                                .#@@@@@@@@@@%-
                                +@@@@@@@@@@=
                               :#@@@@@@@@@%#%%@@%%##**#*=.
                               +@@@@@@@@@@@@@@@@@@@@@@@@@#:
                              :#@@@@@@@@@@@@@@@@@@@@@@@@@@@+.
                              .*@@@@@@@@@@@@@@@@@%#=-:%@@@@@@=
                               .+%@@@@@@@@%%#*+-.     .*@@@@@@%:
                                 +@@@@@@@=              :*@@@@@@*.        -+-
                  =%%*.          +@@@@@@@=                 .-%@@@%*:  .-#%@%=
               .*@@@@@%#**+--=*+-:%@@@@@@=                     +@@@@@@@@@@%-
             -%@@@@@@@@@@@@@@@@@@@@@@@@@#:                       -%@@@@@#:
            =@%*=::-.   .:=*#@@@@@@@@@@@+                         .*@@@=
            ::                .:=*%@@@@+.                           .-.
                                    ...
                                          -##*=:.
                                          =%@@@@@@@@@@%#*-
                                           .%@%***#%%@@@@+
                                            #@%:    :@@%-.
                                            #@%:    :@@%:
                                            #@%:    :@@%:
                                            #@%:    :@@%:
                                            #@%:    :@@%:
                                            #@%:    :@@%:
                                            #@%:    :@@%:
                                            #@%:    :@@%:
                                            #@%:    :@@%:
                                            #@%:    :@@%:
                                            #@%:    :@@%:
                                            #@%:    :@@%:
                              :::::::::::::-%@%-    :@@%:
                             -%@@@@@@@@@@@@@@@@@%*-.:@@%:
                                              -*%@@@#@@%:
                                 :*#############%@@@@@@%:
                               .+####################*.
"""

WELCOME_ART = r"""
          ___       __   __         ___    ___  __     ___      __   ___  __                  ___  __  
    |  | |__  |    /  ` /  \  |\/| |__      |  /  \     |  \ / |__) |__  |__) |  | |\ | |\ | |__  |__) 
    |/\| |___ |___ \__, \__/  |  | |___     |  \__/     |   |  |    |___ |  \ \__/ | \| | \| |___ |  \ 
"""

CREDIT_ART = """
┬             ┌─┬─┐            ┬  ┬             ┌─┬─┐          ┬          ┐
│               │   o          │  │               │            │          │
├─┐ ┬ ┬         │   ┬ ┌┬┐ ┌─┐ ─┼─ ├─┐ ┬ ┬         │   ┌─┐ ┌─┐ ─┼─ ┌─┐ ┌─┐ │
│ │ │ │         │   │ │││ │ │  │  │ │ │ │         │   ├─┘ ├─┘  │  ┌─┘ ├─┘ │
└─┘ └─┤         ┴   ┴ ┴ ┴ └─┘  └┘ ┴ ┴ └─┤         ┴   └─┘ └─┘  └┘ └─┘ └─┘ ┴
      │                                 │
    └─┘                               └─┘
"""

def _art(s):
    return s.strip("\n").split("\n")

HERO, WELCOME, CREDIT = _art(HERO_ART), _art(WELCOME_ART), _art(CREDIT_ART)

TEXT_IN, TEXT_HOLD = 1.4, 3.0          # title eases in, then holds to be read
HERO_AT  = TEXT_IN + TEXT_HOLD         # the runner then comes down for it
TEXT_OUT = 1.1                         # title drops away, gathering speed
HERO_IN  = 2.0

class Rain:
    """Falling rain where every drop is a real word from the game's vocabulary.

    A column holds one word written down the screen, first letter highest, so
    it reads top to bottom as it descends; the leading letter is the bright
    head. Each column falls at its own speed and takes a new word when it
    clears the bottom.
    """
    __slots__ = ('w', 'h', 'head', 'speed', 'word')

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.head  = [random.uniform(-h, 0.0) for _ in range(w)]
        self.speed = [random.uniform(3.5, 11)  for _ in range(w)]
        self.word  = [random.choice(WORDS)    for _ in range(w)]

    def step(self, dt):
        for i in range(self.w):
            self.head[i] += self.speed[i] * dt
            if self.head[i] - len(self.word[i]) > self.h:
                self.head[i]  = random.uniform(-14, -1)
                self.speed[i] = random.uniform(3.5, 11)
                self.word[i]  = random.choice(WORDS)

    def draw(self, scr, mask):
        # compose whole rows, then one addstr per row: a couple of hundred
        # per-cell writes a frame collapse into a few dozen
        grid, heads = [[' '] * self.w for _ in range(self.h)], []
        for i in range(self.w):
            hd, wd = int(self.head[i]), self.word[i]
            top = hd - len(wd) + 1
            for j, ch in enumerate(wd):
                y = top + j
                if 0 <= y < self.h and not mask[y][i]:
                    grid[y][i] = ch
            if 0 <= hd < self.h and not mask[hd][i]:
                heads.append((hd, i, wd[-1]))
        trail = curses.color_pair(CP_GREEN)
        for y in range(self.h):
            line = "".join(grid[y]).rstrip()
            if line:
                safe_add(scr, y, 0, line, trail)
        bright = curses.color_pair(CP_GREEN) | curses.A_BOLD | curses.A_REVERSE
        for y, x, ch in heads:
            safe_add(scr, y, x, ch, bright)

_RUNS = {}

def runs_of(art):
    """(line index, start, end) for every horizontal run of ink. Cached: art is
    fixed, so this is computed once however long the intro plays."""
    key = id(art)
    if key not in _RUNS:
        out = []
        for i, line in enumerate(art):
            start = None
            for j, ch in enumerate(line):
                if ch == ' ':
                    if start is not None:
                        out.append((i, start, j))
                        start = None
                elif start is None:
                    start = j
            if start is not None:
                out.append((i, start, len(line)))
        _RUNS[key] = out
    return _RUNS[key]

def art_x0(art):
    """Left edge of the centred block; art wider than the screen clips right."""
    return max(0, (_W - max(len(l) for l in art)) // 2)

def draw_art(scr, art, row, attr):
    x0 = art_x0(art)
    for i, a, b in runs_of(art):
        y = row + i
        if 0 <= y < _H:
            safe_add(scr, y, x0 + a, art[i][a:b], attr)

def mask_art(mask, art, row):
    """Keep the rain one clear cell away from any ink, so the lettering reads.

    Marks each run of ink plus a one-cell margin on every side; working by run
    rather than by cell keeps this to a few hundred slice writes a frame.
    """
    x0 = art_x0(art)
    for i, a, b in runs_of(art):
        lo, hi = max(0, x0 + a - 1), min(_W, x0 + b + 1)
        if hi <= lo:
            continue
        fill = b"\x01" * (hi - lo)
        for y in range(row + i - 1, row + i + 2):
            if 0 <= y < _H:
                mask[y][lo:hi] = fill

def mask_span(mask, row, col, length):
    lo, hi = max(0, col - 1), min(_W, col + length + 1)
    if hi <= lo:
        return
    fill = b"\x01" * (hi - lo)
    for y in range(row - 1, row + 2):
        if 0 <= y < _H:
            mask[y][lo:hi] = fill

def draw_welcome(scr, app):
    now = time.time()
    if app.rain is None or app.rain.w != _W or app.rain.h != _H:
        app.rain, app.t_rain = Rain(_W, _H), now
    app.rain.step(min(0.06, now - app.t_rain))
    app.t_rain = now

    t    = now - app.t_welcome
    gold = curses.color_pair(CP_GOLD) | curses.A_BOLD
    cyan = curses.color_pair(CP_CYAN) | curses.A_BOLD

    # settle what is on screen and where BEFORE the rain goes down, so the rain
    # can be held clear of it rather than painted over
    block = len(WELCOME) + 1 + len(CREDIT)
    # title sits a little below centre, clamped so it still fits a short screen
    t_row = max(0, min(_H - block - 2, (_H - block - 2) // 2 + 5))
    # The ease-out has a long tail: its last row costs about a fifth of a
    # second, so the title appears to settle and then tick down once more.
    # Capping one row short drops that final step; the glide into it is
    # untouched, the motion simply ends where it had already come to rest.
    t_rest = max(0, t_row - 1)
    # runner's resting row — never row 0, so a clear row sits above his head
    h_row = max(1, (_H - len(HERO) - 2) // 2)
    shown = []

    # round, never truncate: an eased arrival spends its last stretch at x.9,
    # and truncating holds that a row short before snapping over at the end,
    # which reads as a flicker after the motion has already settled
    if t < HERO_AT:
        # WELCOME TO TYPERUNNER / by ... eases in and then sits still to be read
        p   = min(1.0, t / TEXT_IN)
        row = min(t_rest,
                  round(-block + (t_row + block) * (1 - (1 - p) ** 3)))
    else:
        # the runner shoulders it aside: the title drops away under gravity,
        # q squared so it starts slow and accelerates out of frame
        q   = (t - HERO_AT) / TEXT_OUT
        row = round(t_rest + (_H + block - t_rest) * q * q) if q < 1.0 else None
    if row is not None:
        shown += [(WELCOME, row, gold), (CREDIT, row + len(WELCOME) + 1, cyan)]

    if t >= HERO_AT:                     # drawn last, so it rides over the title
        p = min(1.0, (t - HERO_AT) / HERO_IN)
        shown.append((HERO,
                      round(-len(HERO) + (h_row + len(HERO)) * (1 - (1 - p) ** 3)),
                      cyan))

    msg      = " press any key to start "
    msg_col  = max(0, (_W - len(msg)) // 2)
    show_msg = t > 0.7

    mask = [bytearray(_W) for _ in range(_H)]
    for art, row, _ in shown:
        mask_art(mask, art, row)
    if show_msg:
        mask_span(mask, _H - 2, msg_col, len(msg))

    app.rain.draw(scr, mask)
    for art, row, attr in shown:
        draw_art(scr, art, row, attr)
    if show_msg:
        safe_add(scr, _H - 2, msg_col, msg,
                 curses.color_pair(CP_FG) | curses.A_BOLD | curses.A_REVERSE)

# ══ App ═══════════════════════════════════════════════════════════════════════
S_WELCOME, S_PLAYER, S_NEWNAME, S_RACE, S_HISTORY = (
    'welcome', 'player', 'newname', 'race', 'history')

class App:
    def __init__(self):
        self.screen  = S_WELCOME
        self.rain       = None
        self.t_welcome  = time.time()
        self.t_rain     = time.time()
        self.players = players_all()
        self.sel     = 0
        self.player  = None
        self.level   = 1
        self.game    = None
        self.newname = ""
        self.msg     = ""
        self.confirm_delete = False
        self.result  = None
        self.history = []
        self.stats   = None
        self.history_back = S_PLAYER
        self.track_line = ""
        self.hurdle_xs  = []

    def reload_players(self):
        self.players = players_all()
        self.sel = max(0, min(self.sel, len(self.players) - 1))

    def start_race(self, level=None):
        self.level  = level or self.level
        n, avg = player_avg_wpm(self.player['id'], self.level)
        pace = avg * (1 - PACE_HANDICAP[self.level]) if n and avg else None
        self.game   = Game(self.level, self.player['name'], pace_wpm=pace)
        self.result = None
        self.screen = S_RACE

    def finish_race(self):
        g = self.game
        g.saved = True
        # everything here is scoped to the level just raced — a level 3 run is
        # not comparable with a level 1 one, the words are rarer and longer
        pid, lvl = self.player['id'], g.level
        prev        = player_best(pid, lvl)             # (wpm, accuracy)
        prior_n, prior_avg = player_avg_wpm(pid, lvl)   # what PACE was set from
        race_save(pid, g, g.place, g.elapsed)
        recent = races_recent(pid, 14, level=lvl)
        self.result = {
            'seconds':   g.elapsed,
            'prev_best': prev,
            'prior_n':   prior_n,
            'prior_avg': prior_avg,
            'is_best':   (g.wpm, g.accuracy) > prev,
            'recent':    [(r['wpm'], r['accuracy']) for r in recent],
        }

    def open_history(self, back=S_PLAYER):
        self.history      = races_recent(self.player['id'], 500)
        self.stats        = player_stats(self.player['id'])
        self.history_back = back
        self.screen       = S_HISTORY

# ══ Key handling  (return False to quit) ══════════════════════════════════════
def keys_players(app, ch):
    n = len(app.players)
    if ch in (curses.KEY_UP, ord('k')) and n:
        app.sel, app.confirm_delete = (app.sel - 1) % n, False
    elif ch in (curses.KEY_DOWN, ord('j')) and n:
        app.sel, app.confirm_delete = (app.sel + 1) % n, False
    elif ch in (ord('n'), ord('N')):
        app.screen, app.newname, app.msg = S_NEWNAME, "", ""
    elif ch in (ord('d'), ord('D')) and n:
        if app.confirm_delete:
            player_delete(app.players[app.sel]['id'])
            app.confirm_delete = False
            app.reload_players()
        else:
            app.confirm_delete = True
    elif ch in (ord('s'), ord('S')) and n:
        p = app.players[app.sel]
        app.player = {'id': p['id'], 'name': p['name']}
        app.open_history(back=S_PLAYER)
    elif ch in (ord('c'), ord('C')) and COFFEE_URL:
        try:
            webbrowser.open(COFFEE_URL)
            app.msg = "opened in your browser - thank you"
        except Exception:
            app.msg = COFFEE_URL
    elif ch in (ord('q'), ord('Q')):
        return False
    elif ch in (curses.KEY_ENTER, 10, 13) and n:
        p = app.players[app.sel]
        app.player = {'id': p['id'], 'name': p['name']}
        app.start_race(1)
    return True

def keys_newname(app, ch):
    if ch == 27:
        app.screen, app.msg = S_PLAYER, ""
    elif ch in (curses.KEY_ENTER, 10, 13):
        name = app.newname.strip()
        if not name:
            app.msg = "Name cannot be empty."
        elif any(p['name'].lower() == name.lower() for p in app.players):
            app.msg = "That name is taken."
        else:
            pid = player_create(name)
            app.reload_players()
            app.sel = next((i for i, p in enumerate(app.players)
                            if p['id'] == pid), 0)
            app.screen, app.msg = S_PLAYER, ""
    elif ch in (curses.KEY_BACKSPACE, 127, 8):
        app.newname = app.newname[:-1]
    elif 32 <= ch <= 126 and len(app.newname) < 16:
        app.newname += chr(ch)
    return True

def keys_race(app, ch):
    g = app.game
    if not g.game_over:
        if ch == 27:
            app.screen = S_PLAYER
            app.reload_players()
        else:
            if g.t_start is None:
                g.t_start = g.t_last = time.time()
            g.handle_key(ch)
        return True
    # swallow in-flight keystrokes for a beat, so the letters still being typed
    # as the race ends cannot fire retry/next/quit
    if time.time() - g.over_t < 0.8:
        return True
    if ch in (ord('q'), ord('Q'), 27):
        return False
    if ch in (ord('r'), ord('R')):
        app.start_race()
    elif ch in (ord('n'), ord('N')) and g.won:
        app.start_race(min(app.level + 1, 6))
    elif ch in (ord('h'), ord('H')):
        app.open_history(back=S_RACE)
    elif ch in (ord('p'), ord('P')):
        app.screen = S_PLAYER
        app.reload_players()
    return True

def keys_history(app, ch):
    if ch in (27, ord('h'), ord('H'), ord('s'), ord('S'),
              curses.KEY_ENTER, 10, 13):
        back = app.history_back
        app.screen = back if back != S_RACE or app.game else S_PLAYER
    elif ch in (ord('q'), ord('Q')):
        return False
    return True

def keys_welcome(app, ch):
    app.screen = S_PLAYER          # any key skips the intro
    return True

HANDLERS = {S_WELCOME: keys_welcome, S_PLAYER: keys_players, S_NEWNAME: keys_newname,
            S_RACE: keys_race, S_HISTORY: keys_history}

DRAWERS = {S_WELCOME: draw_welcome, S_PLAYER: draw_players, S_NEWNAME: draw_newname,
           S_HISTORY: draw_history}

# ══ Main loop ═════════════════════════════════════════════════════════════════
def run(stdscr):
    global _H, _W
    curses.cbreak(); curses.noecho()
    stdscr.keypad(True); stdscr.nodelay(True)
    curses.curs_set(0)
    init_colors()
    db_init()
    app = App()

    while True:
        # drain the whole queue so fast typing never drops a keystroke
        for _ in range(24):
            ch = stdscr.getch()
            if ch == -1:
                break
            if not HANDLERS[app.screen](app, ch):
                return

        if app.game and app.screen in (S_RACE, S_HISTORY):
            app.game.tick()
            if app.game.game_over and not app.game.saved:
                app.finish_race()

        _H, _W = stdscr.getmaxyx()
        stdscr.erase()
        if _H < MIN_H or _W < MIN_W:
            safe_add(stdscr, _H // 2, 2,
                     f"Terminal too small — need {MIN_W}x{MIN_H}, have {_W}x{_H}",
                     curses.color_pair(CP_RED) | curses.A_BOLD)
        else:
            drawer = DRAWERS.get(app.screen)
            if drawer:
                drawer(stdscr, app)
            else:
                draw_race(stdscr, app, app.game)
        stdscr.refresh()
        time.sleep(0.025)

USAGE = """typerunner - a terminal typing race game

usage: typerunner [-h] [-V]

  -h, --help     show this message and exit
  -V, --version  show the version and exit

Needs a terminal of at least 64x28. Players and race history are kept in
~/.hurdle_rush.db
"""

def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    if arg in ("-V", "--version"):
        from . import __version__
        print(f"typerunner {__version__}")
        return 0
    if arg in ("-h", "--help"):
        print(USAGE, end="")
        return 0
    if arg:
        print(f"typerunner: unknown option {arg!r}\n", file=sys.stderr)
        print(USAGE, end="", file=sys.stderr)
        return 2
    try:
        curses.wrapper(run)
    except KeyboardInterrupt:
        pass
    return 0

if __name__ == "__main__":
    sys.exit(main())
