"""AI Context Meter - always-on-top Windows widget showing context-window fill %.

Sources:
  * Claude Code (CLI): read from local transcripts in ~/.claude/projects/**/*.jsonl
  * Desktop apps (Claude, ChatGPT, ...): estimated from the text visible in the
    app window via Windows UI Automation (needs: pip install pywinauto)

Run:  pythonw meter.py     (no console)   or   python meter.py
Only the standard library is used (tkinter ships with Python on Windows).
"""
import json
import threading
import time
import tkinter as tk
from pathlib import Path

CONFIG_PATH = Path.home() / ".ai_context_meter.json"
DEFAULTS = {
    "refresh_ms": 3000,
    "stale_seconds": 90,          # hide app rows with no update for this long
    "scan_seconds": 10,           # how often to scan desktop app windows
    "chars_per_token": 3.5,       # rough estimate
    # name shown, exe name (lowercase), context window in tokens
    "apps": [
        {"name": "Claude", "exe": "claude.exe", "window": 200000},
        {"name": "ChatGPT", "exe": "chatgpt.exe", "window": 128000},
    ],
    "claude_code_window": 200000, # set 1000000 if you use the 1M-context model
    "x": 40,
    "y": 40,
}


def load_config():
    cfg = dict(DEFAULTS)
    try:
        cfg.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass
    return cfg


def save_config(cfg):
    try:
        CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    except OSError:
        pass


# ---------- Claude Code source ----------
def read_claude_code(window):
    root = Path.home() / ".claude" / "projects"
    try:
        files = list(root.glob("*/*.jsonl"))
        if not files:
            return None
        newest = max(files, key=lambda p: p.stat().st_mtime)
        with newest.open("rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 400_000))
            lines = f.read().decode("utf-8", "ignore").splitlines()
    except OSError:
        return None
    for line in reversed(lines):
        try:
            msg = json.loads(line).get("message") or {}
        except ValueError:
            continue
        usage = msg.get("usage")
        if msg.get("role") == "assistant" and usage:
            used = (usage.get("input_tokens", 0)
                    + usage.get("cache_creation_input_tokens", 0)
                    + usage.get("cache_read_input_tokens", 0))
            win = 1_000_000 if "[1m]" in str(msg.get("model", "")) else window
            return {"used": used, "window": win,
                    "age": time.time() - newest.stat().st_mtime}
    return None


# ---------- desktop apps (Windows UI Automation) ----------
web_state = {}   # name -> {"used", "window", "ts"}
web_lock = threading.Lock()


def scan_apps(cfg):
    """Background loop: estimate tokens from text visible in each app's windows."""
    try:
        from pywinauto import Desktop
        from pywinauto.application import process_get_path
    except ImportError:
        return
    while True:
        try:
            wins = Desktop(backend="uia").windows()
            for app in cfg["apps"]:
                chars = 0
                for w in wins:
                    try:
                        exe = Path(process_get_path(w.process_id())).name.lower()
                        if exe != app["exe"].lower():
                            continue
                        for e in w.descendants():
                            chars += len(e.window_text() or "")
                    except Exception:
                        continue
                if chars:
                    used = int(chars / cfg["chars_per_token"])
                    with web_lock:
                        web_state[app["name"]] = {"used": used,
                                                  "window": app["window"],
                                                  "ts": time.time()}
        except Exception:
            pass
        time.sleep(cfg["scan_seconds"])


# ---------- UI ----------
def color_for(pct):
    return "#4caf50" if pct < 60 else "#ffb300" if pct < 85 else "#e53935"


class Widget:
    W, BAR_W = 250, 120

    def __init__(self, cfg):
        self.cfg = cfg
        self.root = tk.Tk()
        r = self.root
        r.overrideredirect(True)
        r.attributes("-topmost", True)
        r.attributes("-alpha", 0.92)
        r.configure(bg="#1e1e1e")
        r.geometry(f"+{cfg['x']}+{cfg['y']}")
        self.frame = tk.Frame(r, bg="#1e1e1e", padx=8, pady=6)
        self.frame.pack()
        self.rows = {}
        r.bind("<ButtonPress-1>", self._start_drag)
        r.bind("<B1-Motion>", self._drag)
        r.bind("<ButtonRelease-1>", self._save_pos)
        menu = tk.Menu(r, tearoff=0)
        menu.add_command(label="Exit", command=r.destroy)
        r.bind("<Button-3>", lambda e: menu.tk_popup(e.x_root, e.y_root))
        self.tick()

    def _start_drag(self, e):
        self._dx, self._dy = e.x, e.y

    def _drag(self, e):
        self.root.geometry(f"+{self.root.winfo_x() + e.x - self._dx}"
                           f"+{self.root.winfo_y() + e.y - self._dy}")

    def _save_pos(self, _):
        self.cfg["x"], self.cfg["y"] = self.root.winfo_x(), self.root.winfo_y()
        save_config(self.cfg)

    def _row(self, name):
        if name not in self.rows:
            f = tk.Frame(self.frame, bg="#1e1e1e")
            f.pack(fill="x", pady=1)
            lbl = tk.Label(f, text=name, width=12, anchor="w", fg="#ddd",
                           bg="#1e1e1e", font=("Segoe UI", 9))
            lbl.pack(side="left")
            cv = tk.Canvas(f, width=self.BAR_W, height=10, bg="#3a3a3a",
                           highlightthickness=0)
            cv.pack(side="left", padx=4)
            bar = cv.create_rectangle(0, 0, 0, 10, width=0)
            pct = tk.Label(f, width=5, anchor="e", fg="#ddd", bg="#1e1e1e",
                           font=("Segoe UI", 9, "bold"))
            pct.pack(side="left")
            self.rows[name] = (f, cv, bar, pct)
        return self.rows[name]

    def _set(self, name, used, window):
        f, cv, bar, pct = self._row(name)
        p = min(100.0, used * 100.0 / window)
        cv.coords(bar, 0, 0, self.BAR_W * p / 100, 10)
        cv.itemconfig(bar, fill=color_for(p))
        pct.config(text=f"{p:.0f}%")
        if not f.winfo_ismapped():
            f.pack(fill="x", pady=1)

    def tick(self):
        seen = set()
        cc = read_claude_code(self.cfg["claude_code_window"])
        if cc:
            self._set("Claude Code", cc["used"], cc["window"])
            seen.add("Claude Code")
        now = time.time()
        with web_lock:
            items = list(web_state.items())
        for name, e in items:
            if now - e["ts"] <= self.cfg["stale_seconds"]:
                self._set(name, e["used"], e["window"])
                seen.add(name)
        for name, (f, *_rest) in self.rows.items():
            if name not in seen:
                f.pack_forget()
        self.root.after(self.cfg["refresh_ms"], self.tick)


def main():
    cfg = load_config()
    threading.Thread(target=scan_apps, args=(cfg,), daemon=True).start()
    Widget(cfg).root.mainloop()


if __name__ == "__main__":
    main()
