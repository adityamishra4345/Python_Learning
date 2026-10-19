#!/usr/bin/env python3

"""
YouTube Downloader — audio & video with playlist support
Requires: pip install yt-dlp customtkinter pillow requests
"""

import os
import sys
import threading
import subprocess
from pathlib import Path
from dataclasses import dataclass, field

try:
    import yt_dlp
except ImportError:
    sys.exit("❌  yt-dlp not found. Run: pip install yt-dlp")

try:
    import customtkinter as ctk
    HAS_GUI = True
except ImportError:
    HAS_GUI = False

# ╔══════════════════════════════════════════════════════════╗
# ║              CORE DOWNLOAD ENGINE                        ║
# ╚══════════════════════════════════════════════════════════╝

@dataclass
class DownloadConfig:
    url: str
    mode: str        # "audio" | "video"
    quality: str     # "best" | "1080" | "720" | "480" | "360" | "128k" | "320k"
    output_dir: str
    playlist: bool = True
    callbacks: dict = field(default_factory=dict)
    # callbacks keys:
    #   on_progress(d: dict)          — raw yt-dlp progress hook dict
    #   on_item_done(title: str)      — called after each item finishes
    #   on_all_done(results: list)    — called when everything is done

def _build_opts(cfg: DownloadConfig) -> dict:
    outtmpl = os.path.join(
        cfg.output_dir,
        "%(playlist_title)s" + os.sep if cfg.playlist else "",
        "%(title)s.%(ext)s",
    )
    opts = {
        "outtmpl": outtmpl,
        "noplaylist": not cfg.playlist,
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": True,
        "retries": 3,
        "fragment_retries": 3,
    }

    if cfg.mode == "audio":
        quality_map = {"best": "0", "320k": "0", "128k": "5"}
        opts["format"] = "bestaudio/best"
        opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": quality_map.get(cfg.quality, "0"),
        }]
    else:
        res = cfg.quality if cfg.quality != "best" else ""
        opts["format"] = (
            f"bestvideo[height<={res}]+bestaudio/best[height<={res}]"
            if res else "bestvideo+bestaudio/best"
        )
        opts["merge_output_format"] = "mp4"

    return opts

def fetch_info(url: str, playlist: bool = True) -> dict:
    """Fetch metadata only — no download."""
    opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": "in_playlist",
        "noplaylist": not playlist,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=False) or {}

def download(cfg: DownloadConfig) -> list[dict]:
    """Download URL (single or playlist). Returns list of result dicts."""
    os.makedirs(cfg.output_dir, exist_ok=True)
    results: list[dict] = []
    current_title: list[str] = [""]   # mutable box so hook can read it

    def progress_hook(d: dict):
        # Track current item title from filename
        if d.get("filename"):
            current_title[0] = Path(d["filename"]).stem
        if cfg.callbacks.get("on_progress"):
            cfg.callbacks["on_progress"](d)
        # When yt-dlp finishes a file (before post-processing)
        if d["status"] == "finished":
            results.append({
                "title": current_title[0],
                "status": "ok",
            })
            if cfg.callbacks.get("on_item_done"):
                cfg.callbacks["on_item_done"](current_title[0])

    opts = _build_opts(cfg)
    opts["progress_hooks"] = [progress_hook]
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([cfg.url])

    if cfg.callbacks.get("on_all_done"):
        cfg.callbacks["on_all_done"](results)
    return results

# ╔══════════════════════════════════════════════════════════╗
# ║                   CLI INTERFACE                          ║
# ╚══════════════════════════════════════════════════════════╝

def cli_main():
    import argparse
    p = argparse.ArgumentParser(description="YouTube Downloader")
    p.add_argument("url")
    p.add_argument("-m", "--mode",     choices=["audio", "video"], default="audio")
    p.add_argument("-q", "--quality",  default="best")
    p.add_argument("-o", "--output",   default=str(Path.home() / "Downloads" / "YT-Downloads"))
    p.add_argument("--no-playlist",    action="store_true")
    args = p.parse_args()

    done_count = [0]

    def on_progress(d):
        if d["status"] == "downloading":
            pct = d.get("_percent_str", "??").strip()
            spd = d.get("_speed_str",   "??").strip()
            eta = d.get("_eta_str",     "??").strip()
            print(f"\r  ⬇  {pct}  {spd}  ETA {eta}   ", end="", flush=True)

    def on_item_done(title):
        done_count[0] += 1
        print(f"\r  ✅  [{done_count[0]}] {title[:70]}{' '*10}")

    cfg = DownloadConfig(
        url=args.url, mode=args.mode, quality=args.quality,
        output_dir=args.output, playlist=not args.no_playlist,
        callbacks={"on_progress": on_progress, "on_item_done": on_item_done},
    )

    print(f"\n🎵  Mode: {cfg.mode}  |  Quality: {cfg.quality}")
    print(f"📁  Output: {cfg.output_dir}\n")
    results = download(cfg)
    print(f"\n✅  Done — {len(results)} item(s) downloaded.\n")

# ╔══════════════════════════════════════════════════════════╗
# ║                   GUI INTERFACE                          ║
# ╚══════════════════════════════════════════════════════════╝

if HAS_GUI:
    DARK    = "#0f0f13"
    PANEL   = "#18181f"
    CARD    = "#22222c"
    ACCENT  = "#7c5cfc"
    ACCENT2 = "#5cd8fa"
    TEXT    = "#e8e8f0"
    MUTED   = "#7070a0"
    SUCCESS = "#4cdb7a"
    ERROR   = "#f05a5a"

    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")

    class ProgressBar(ctk.CTkProgressBar):
        def __init__(self, master, **kw):
            super().__init__(master, height=6, corner_radius=3,
                             fg_color=CARD, progress_color=ACCENT, **kw)
            self.set(0)

    class LogBox(ctk.CTkTextbox):
        def __init__(self, master, **kw):
            super().__init__(master, fg_color=DARK, text_color=TEXT,
                             font=("Courier New", 12), corner_radius=8, **kw)
            self.configure(state="disabled")
        def append(self, text: str):
            self.configure(state="normal")
            self.insert("end", text + "\n")
            self.configure(state="disabled")
            self.see("end")

    class QueueItem(ctk.CTkFrame):
        def __init__(self, master, title: str, idx: int, **kw):
            super().__init__(master, fg_color=CARD, corner_radius=8, **kw)
            self.title_lbl = ctk.CTkLabel(
                self, text=f"  {idx}. {title[:65]}",
                text_color=TEXT, anchor="w", font=("Inter", 13))
            self.title_lbl.pack(side="left", fill="x", expand=True, padx=8, pady=8)

            self.status_lbl = ctk.CTkLabel(
                self, text="queued", text_color=MUTED, font=("Inter", 12), width=110)
            self.status_lbl.pack(side="right", padx=12)

            self.bar = ProgressBar(self, width=110)
            self.bar.pack(side="right", padx=8)

        def set_downloading(self, pct: float, speed: str = ""):
            self.bar.set(pct)
            label = f"{pct*100:.0f}%  {speed}" if speed else f"{pct*100:.0f}%"
            self.status_lbl.configure(text=label, text_color=ACCENT2)

        def set_done(self):
            self.bar.set(1.0)
            self.status_lbl.configure(text="✓  done", text_color=SUCCESS)

        def set_error(self):
            self.status_lbl.configure(text="✗  error", text_color=ERROR)

    class App(ctk.CTk):
        def __init__(self):
            super().__init__(fg_color=DARK)
            self.title("YT Downloader")
            self.geometry("880x720")
            self.minsize(760, 580)
            # State
            self._queue_items: dict[int, QueueItem] = {}   # 1-based index → widget
            self._active      = False
            self._done_count  = 0   # how many items finished so far
            self._total       = 0   # total items in queue
            self._build_ui()

        # ── UI layout ────────────────────────────────────────────────────────
        def _build_ui(self):
            # Header
            hdr = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=0, height=60)
            hdr.pack(fill="x")
            hdr.pack_propagate(False)
            ctk.CTkLabel(hdr, text="  ▶  YT Downloader",
                         font=("Inter", 20, "bold"), text_color=TEXT).pack(side="left", padx=16)
            ctk.CTkLabel(hdr, text="audio · video · playlists",
                         font=("Inter", 13), text_color=MUTED).pack(side="left", padx=4)

            body = ctk.CTkFrame(self, fg_color=DARK)
            body.pack(fill="both", expand=True, padx=20, pady=14)

            # — URL
            url_row = ctk.CTkFrame(body, fg_color=PANEL, corner_radius=10)
            url_row.pack(fill="x", pady=(0, 10))
            ctk.CTkLabel(url_row, text="URL", text_color=MUTED,
                         font=("Inter", 12)).pack(side="left", padx=(14, 6), pady=12)

            self.url_var = ctk.StringVar()
            ctk.CTkEntry(url_row, textvariable=self.url_var,
                         placeholder_text="Paste YouTube video or playlist URL…",
                         fg_color=CARD, border_color=ACCENT,
                         text_color=TEXT, font=("Inter", 13),
                         corner_radius=8, height=36).pack(
                             side="left", fill="x", expand=True, padx=8, pady=10)

            self.fetch_btn = ctk.CTkButton(
                url_row, text="Inspect", width=88, height=36,
                fg_color=CARD, hover_color=ACCENT, text_color=TEXT,
                font=("Inter", 13), corner_radius=8, command=self._inspect)
            self.fetch_btn.pack(side="right", padx=(0, 14))

            # — Options
            opts = ctk.CTkFrame(body, fg_color=PANEL, corner_radius=10)
            opts.pack(fill="x", pady=(0, 10))

            self.mode_var = ctk.StringVar(value="audio")
            ctk.CTkLabel(opts, text="Mode", text_color=MUTED,
                         font=("Inter", 12)).grid(row=0, column=0, padx=(14, 4), pady=12)
            ctk.CTkSegmentedButton(
                opts, values=["audio", "video"], variable=self.mode_var,
                fg_color=CARD, selected_color=ACCENT, selected_hover_color=ACCENT,
                font=("Inter", 13), command=self._update_quality_choices
            ).grid(row=0, column=1, padx=4)

            ctk.CTkLabel(opts, text="Quality", text_color=MUTED,
                         font=("Inter", 12)).grid(row=0, column=2, padx=(18, 4))
            self.quality_var = ctk.StringVar(value="best")
            self.quality_menu = ctk.CTkOptionMenu(
                opts, values=["best", "320k", "128k"], variable=self.quality_var,
                fg_color=CARD, button_color=ACCENT, text_color=TEXT,
                font=("Inter", 13), dropdown_fg_color=PANEL, width=110)
            self.quality_menu.grid(row=0, column=3, padx=4)

            self.playlist_var = ctk.BooleanVar(value=True)
            ctk.CTkCheckBox(
                opts, text="Download playlist", variable=self.playlist_var,
                fg_color=ACCENT, hover_color=ACCENT, text_color=TEXT,
                font=("Inter", 13)).grid(row=0, column=4, padx=18)

            ctk.CTkLabel(opts, text="Save to", text_color=MUTED,
                         font=("Inter", 12)).grid(row=0, column=5, padx=(10, 4))
            default_dir = str(Path.home() / "Downloads" / "YT-Downloads")
            self.dir_var = ctk.StringVar(value=default_dir)
            ctk.CTkEntry(opts, textvariable=self.dir_var,
                         fg_color=CARD, border_color=CARD,
                         text_color=TEXT, font=("Inter", 12),
                         width=190, height=32).grid(row=0, column=6, padx=4)

            ctk.CTkButton(opts, text="…", width=30, height=32,
                          fg_color=CARD, hover_color=ACCENT, text_color=TEXT,
                          font=("Inter", 13), command=self._pick_dir
                          ).grid(row=0, column=7, padx=(0, 14))

            opts.columnconfigure(8, weight=1)

            # — Queue header
            qhdr = ctk.CTkFrame(body, fg_color="transparent")
            qhdr.pack(fill="x", pady=(2, 4))
            ctk.CTkLabel(qhdr, text="Queue", text_color=MUTED,
                         font=("Inter", 12, "bold")).pack(side="left")
            self.count_lbl = ctk.CTkLabel(qhdr, text="", text_color=ACCENT2,
                                          font=("Inter", 12))
            self.count_lbl.pack(side="left", padx=8)

            # — Queue list
            self.queue_scroll = ctk.CTkScrollableFrame(
                body, fg_color=PANEL, corner_radius=10, height=210)
            self.queue_scroll.pack(fill="x", pady=(0, 10))

            self._empty_lbl = ctk.CTkLabel(
                self.queue_scroll,
                text="Paste a URL then click Inspect — or just hit Download directly.",
                text_color=MUTED, font=("Inter", 12))
            self._empty_lbl.pack(pady=28)

            # — Global progress bar
            gp = ctk.CTkFrame(body, fg_color="transparent")
            gp.pack(fill="x", pady=(0, 6))
            self.global_bar = ProgressBar(gp)
            self.global_bar.pack(fill="x", expand=True, side="left")
            self.global_lbl = ctk.CTkLabel(gp, text="  –",
                                           text_color=MUTED, font=("Inter", 12), width=62)
            self.global_lbl.pack(side="right")

            # — Log
            self.log = LogBox(body, height=110)
            self.log.pack(fill="x")

            # — Buttons
            btn_row = ctk.CTkFrame(body, fg_color="transparent")
            btn_row.pack(fill="x", pady=12)

            self.dl_btn = ctk.CTkButton(
                btn_row, text="⬇  Download",
                fg_color=ACCENT, hover_color="#6347e0",
                text_color="#fff", font=("Inter", 15, "bold"),
                corner_radius=10, height=44, command=self._start_download)
            self.dl_btn.pack(side="left", padx=(0, 10))

            ctk.CTkButton(btn_row, text="Clear",
                          fg_color=CARD, hover_color=ERROR,
                          text_color=TEXT, font=("Inter", 13),
                          corner_radius=10, height=44,
                          command=self._clear).pack(side="left")

            ctk.CTkButton(btn_row, text="📂  Open folder",
                          fg_color=CARD, hover_color="#2a2a3a",
                          text_color=TEXT, font=("Inter", 13),
                          corner_radius=10, height=44,
                          command=self._open_folder).pack(side="right")

        # ── Helpers ──────────────────────────────────────────────────────────
        def _update_quality_choices(self, _=None):
            mode = self.mode_var.get()
            choices = (["best", "320k", "128k"] if mode == "audio"
                       else ["best", "1080", "720", "480", "360"])
            self.quality_menu.configure(values=choices)
            self.quality_var.set(choices[0])

        def _pick_dir(self):
            from tkinter import filedialog
            d = filedialog.askdirectory(initialdir=self.dir_var.get())
            if d:
                self.dir_var.set(d)

        def _clear(self):
            if self._active:
                return
            for w in self.queue_scroll.winfo_children():
                w.destroy()
            self._queue_items.clear()
            self._empty_lbl = ctk.CTkLabel(
                self.queue_scroll,
                text="Paste a URL then click Inspect — or just hit Download directly.",
                text_color=MUTED, font=("Inter", 12))
            self._empty_lbl.pack(pady=28)
            self.count_lbl.configure(text="")
            self.global_bar.set(0)
            self.global_lbl.configure(text="  –")
            self.log.configure(state="normal")
            self.log.delete("1.0", "end")
            self.log.configure(state="disabled")

        def _open_folder(self):
            path = self.dir_var.get()
            os.makedirs(path, exist_ok=True)
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])

        def _log(self, msg: str):
            self.after(0, self.log.append, msg)

        # ── Inspect ──────────────────────────────────────────────────────────
        def _inspect(self):
            url = self.url_var.get().strip()
            if not url:
                self._log("⚠  No URL entered.")
                return
            self.fetch_btn.configure(state="disabled", text="…")
            threading.Thread(target=self._do_inspect, args=(url,), daemon=True).start()

        def _do_inspect(self, url: str):
            try:
                info = fetch_info(url, playlist=self.playlist_var.get())
                entries = info.get("entries") or [info]
                self.after(0, self._populate_queue, entries)
                self._log(f"ℹ  Found {len(entries)} item(s).")
            except Exception as ex:
                self._log(f"❌  Inspect failed: {ex}")
            finally:
                self.after(0, self.fetch_btn.configure,
                           {"state": "normal", "text": "Inspect"})

        def _populate_queue(self, entries: list):
            for w in self.queue_scroll.winfo_children():
                w.destroy()
            self._queue_items.clear()
            for i, e in enumerate(entries, 1):
                title = (e or {}).get("title", f"Item {i}")
                item = QueueItem(self.queue_scroll, title, i)
                item.pack(fill="x", pady=3, padx=4)
                self._queue_items[i] = item
            total = len(entries)
            self.count_lbl.configure(text=f"{total} items")
            self.global_bar.set(0)
            self.global_lbl.configure(text=f"  0 / {total}")
            self._total = total

        # ── Download ─────────────────────────────────────────────────────────
        def _start_download(self):
            url = self.url_var.get().strip()
            if not url:
                self._log("⚠  Paste a URL first.")
                return
            if self._active:
                self._log("⚠  Already downloading.")
                return

            self._active     = True
            self._done_count = 0
            # If queue is empty (no inspect), we don't know total yet
            if not self._queue_items:
                self._total = 0

            self.dl_btn.configure(state="disabled", text="Downloading…")
            self._log(f"⬇  Starting  [{self.mode_var.get().upper()}  {self.quality_var.get()}]…")

            cfg = DownloadConfig(
                url=url,
                mode=self.mode_var.get(),
                quality=self.quality_var.get(),
                output_dir=self.dir_var.get(),
                playlist=self.playlist_var.get(),
                callbacks={
                    "on_progress":  self._cb_progress,
                    "on_item_done": self._cb_item_done,
                    "on_all_done":  self._cb_all_done,
                },
            )
            threading.Thread(target=self._run_download, args=(cfg,), daemon=True).start()

        def _run_download(self, cfg: DownloadConfig):
            try:
                download(cfg)
            except Exception as ex:
                self._log(f"❌  Fatal error: {ex}")
                self.after(0, self._finish_ui)

        # ── Callbacks (called from download thread) ───────────────────────────
        def _cb_progress(self, d: dict):
            """Called on every yt-dlp progress tick."""
            if d["status"] != "downloading":
                return
            pct_str = d.get("_percent_str", "0%").strip().replace("%", "")
            try:
                pct = float(pct_str) / 100
            except ValueError:
                pct = 0.0
            speed = d.get("_speed_str", "").strip()

            # current item = done_count + 1
            idx = self._done_count + 1
            if idx in self._queue_items:
                self.after(0, self._queue_items[idx].set_downloading, pct, speed)

            # global bar = (done + current_pct) / total
            if self._total > 0:
                global_pct = (self._done_count + pct) / self._total
                self.after(0, self.global_bar.set, min(global_pct, 1.0))
                self.after(0, self.global_lbl.configure,
                           {"text": f"  {self._done_count} / {self._total}"})

        def _cb_item_done(self, title: str):
            """Called after each item finishes downloading (before ffmpeg post-proc)."""
            idx = self._done_count + 1
            self._done_count += 1
            if idx in self._queue_items:
                self.after(0, self._queue_items[idx].set_done)

            # Update global bar
            if self._total > 0:
                self.after(0, self.global_bar.set, self._done_count / self._total)
                self.after(0, self.global_lbl.configure,
                           {"text": f"  {self._done_count} / {self._total}"})

            self._log(f"✅  [{self._done_count}] {title[:70]}")

        def _cb_all_done(self, results: list):
            """Called after the entire batch finishes."""
            self.after(0, self._finish_ui, results)

        def _finish_ui(self, results: list = None):
            results = results or []
            # Mark any remaining items done (in case we didn't get individual signals)
            for item in self._queue_items.values():
                item.set_done()
            self.global_bar.set(1.0)
            n = len(results) or self._done_count
            self.global_lbl.configure(text=f"  {n} / {max(self._total, n)}")
            self._log(f"🎉  All done!  {n} file(s) saved → {self.dir_var.get()}")
            self._active = False
            self.dl_btn.configure(state="normal", text="⬇  Download")

    def gui_main():
        App().mainloop()

# ╔══════════════════════════════════════════════════════════╗
# ║                     ENTRY POINT                          ║
# ╚══════════════════════════════════════════════════════════╝

def main():
    if len(sys.argv) == 1 and HAS_GUI:
        gui_main()
    elif len(sys.argv) == 1:
        print("GUI libs missing — install: pip install customtkinter pillow")
        print("CLI usage: python yt_downloader.py <URL> [-m audio|video] [-q best|320k|128k|1080|720] [-o /path]")
    else:
        cli_main()

if __name__ == "__main__":
    main()