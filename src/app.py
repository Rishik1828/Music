"""
app.py
------
Emotion-Based Music Player — Redesigned UI

Flow:
  1. Home screen (centered window, fullscreen)  →  Click START
  2. Webcam snapshot screen                     →  Single photo taken, emotion detected
  3. Language + Era selection screen            →  User picks preferences
  4. Songs display screen                       →  Beautiful scrollable song cards

Run:
    python src/app.py
"""

import sys
import threading
import time
import collections
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import tkinter as tk
from tkinter import ttk, messagebox
import cv2
import numpy as np
from PIL import Image, ImageTk

from detect       import EmotionDetector
from music_engine import MusicEngine

# ── Theme ──────────────────────────────────────────────────────────────────────
BG_DARK    = "#0a0a14"
BG_CARD    = "#141428"
BG_CARD2   = "#1c1c38"
ACCENT     = "#7f5af0"
ACCENT2    = "#2cb67d"
ACCENT3    = "#ff6b6b"
ACCENT4    = "#ffd93d"
TEXT_MAIN  = "#fffffe"
TEXT_SUB   = "#94a1b2"
BTN_START  = "#7f5af0"
BTN_STOP   = "#e53170"

FONT_GIANT = ("Segoe UI", 36, "bold")
FONT_HEAD  = ("Segoe UI", 22, "bold")
FONT_TITLE = ("Segoe UI", 16, "bold")
FONT_BODY  = ("Segoe UI", 13)
FONT_SMALL = ("Segoe UI", 10)
FONT_SONG  = ("Segoe UI", 14, "bold")
FONT_ARTIST= ("Segoe UI", 11)

EMOTION_EMOJI = {
    "happy":    "😊",
    "sad":      "😢",
    "angry":    "😠",
    "surprise": "😲",
    "fear":     "😨",
    "disgust":  "🤢",
    "neutral":  "😐",
}

EMOTION_COLOR = {
    "happy":    "#ffd93d",
    "sad":      "#4fc3f7",
    "angry":    "#ff6b6b",
    "surprise": "#ce93d8",
    "fear":     "#80cbc4",
    "disgust":  "#a5d6a7",
    "neutral":  "#94a1b2",
}


class EmotionMusicApp:
    def __init__(self, root: tk.Tk):
        self.root   = root
        self.engine = MusicEngine()

        self._detected_emotion = None
        self._selected_lang    = tk.StringVar(value="Telugu")
        self._selected_era     = tk.StringVar(value="new")
        self._selected_genre   = tk.StringVar(value="Any")

        # DPI
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

        self.root.title("🎵 Emotion Music Player")
        self.root.configure(bg=BG_DARK)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Center window at a nice size first
        self._set_window_centered(900, 620)

        self._show_home()

    # ── Window helpers ─────────────────────────────────────────────────────────
    def _set_window_centered(self, w, h):
        self.root.resizable(True, True)
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x  = (sw - w) // 2
        y  = (sh - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _go_fullscreen(self):
        """Expand to fullscreen / maximized."""
        self.root.state("zoomed")   # maximized on Windows

    def _clear(self):
        for w in self.root.winfo_children():
            w.destroy()

    # ──────────────────────────────────────────────────────────────────────────
    # SCREEN 1 — HOME
    # ──────────────────────────────────────────────────────────────────────────
    def _show_home(self):
        self._clear()
        self.root.configure(bg=BG_DARK)

        # Gradient-like top banner
        top = tk.Frame(self.root, bg="#12082b", height=6)
        top.pack(fill="x")

        main = tk.Frame(self.root, bg=BG_DARK)
        main.pack(expand=True, fill="both")

        # ── Logo / Title ──────────────────────────────────────────────────────
        tk.Label(
            main,
            text="🎵",
            font=("Segoe UI Emoji", 60),
            bg=BG_DARK,
            fg=ACCENT,
        ).pack(pady=(60, 10))

        tk.Label(
            main,
            text="Emotion Music Player",
            font=FONT_GIANT,
            bg=BG_DARK,
            fg=TEXT_MAIN,
        ).pack()

        tk.Label(
            main,
            text="Your face. Your mood. Your music.",
            font=("Segoe UI", 15, "italic"),
            bg=BG_DARK,
            fg=TEXT_SUB,
        ).pack(pady=(8, 50))

        # ── Features row ──────────────────────────────────────────────────────
        feat_row = tk.Frame(main, bg=BG_DARK)
        feat_row.pack(pady=(0, 50))

        features = [
            ("📸", "Snap your face"),
            ("🧠", "AI detects mood"),
            ("🎶", "Music matches you"),
        ]
        for icon, text in features:
            col = tk.Frame(feat_row, bg=BG_CARD, padx=24, pady=18)
            col.pack(side="left", padx=16)
            tk.Label(col, text=icon, font=("Segoe UI Emoji", 26),
                     bg=BG_CARD, fg=TEXT_MAIN).pack()
            tk.Label(col, text=text, font=FONT_SMALL,
                     bg=BG_CARD, fg=TEXT_SUB).pack(pady=(6, 0))

        # ── START button ──────────────────────────────────────────────────────
        start_btn = tk.Button(
            main,
            text="▶   START",
            font=("Segoe UI", 16, "bold"),
            bg=ACCENT,
            fg=TEXT_MAIN,
            activebackground="#6b46d6",
            activeforeground=TEXT_MAIN,
            relief="flat",
            padx=48,
            pady=16,
            cursor="hand2",
            bd=0,
            command=self._on_start_clicked,
        )
        start_btn.pack()
        self._add_hover(start_btn, ACCENT, "#6b46d6")

        # Footer
        tk.Label(
            main,
            text="Fully offline  •  Powered by custom CNN",
            font=FONT_SMALL,
            bg=BG_DARK,
            fg=TEXT_SUB,
        ).pack(side="bottom", pady=20)

    def _on_start_clicked(self):
        self._go_fullscreen()
        self.root.after(200, self._show_capture)

    # ──────────────────────────────────────────────────────────────────────────
    # SCREEN 2 — WEBCAM SNAPSHOT
    # ──────────────────────────────────────────────────────────────────────────
    def _show_capture(self):
        self._clear()
        self.root.configure(bg=BG_DARK)

        outer = tk.Frame(self.root, bg=BG_DARK)
        outer.pack(expand=True, fill="both")

        # Header
        hdr = tk.Frame(outer, bg=BG_DARK)
        hdr.pack(pady=(40, 20))
        tk.Label(hdr, text="📸  Let's capture your emotion",
                 font=FONT_HEAD, bg=BG_DARK, fg=TEXT_MAIN).pack()
        tk.Label(hdr, text="Position your face in the frame and click  'Take Snapshot'",
                 font=FONT_BODY, bg=BG_DARK, fg=TEXT_SUB).pack(pady=(8, 0))

        # Camera preview
        self._cam_label = tk.Label(outer, bg="#000010",
                                   relief="flat", bd=0)
        self._cam_label.pack(pady=10)

        # Status
        self._cap_status = tk.StringVar(value="● Camera initializing…")
        tk.Label(outer, textvariable=self._cap_status,
                 font=FONT_BODY, bg=BG_DARK, fg=ACCENT2).pack(pady=(6, 14))

        # Buttons row
        btn_row = tk.Frame(outer, bg=BG_DARK)
        btn_row.pack()

        self._snap_btn = tk.Button(
            btn_row,
            text="📸  Take Snapshot",
            font=("Segoe UI", 14, "bold"),
            bg=ACCENT,
            fg=TEXT_MAIN,
            activebackground="#6b46d6",
            activeforeground=TEXT_MAIN,
            relief="flat",
            padx=32,
            pady=12,
            cursor="hand2",
            bd=0,
            state="disabled",
            command=self._take_snapshot,
        )
        self._snap_btn.pack(side="left", padx=12)

        tk.Button(
            btn_row,
            text="← Back",
            font=FONT_BODY,
            bg=BG_CARD2,
            fg=TEXT_SUB,
            activebackground=BG_CARD,
            activeforeground=TEXT_MAIN,
            relief="flat",
            padx=20,
            pady=12,
            cursor="hand2",
            bd=0,
            command=self._back_to_home,
        ).pack(side="left", padx=12)

        # Start webcam feed
        self._cap_running = True
        self._cap         = None
        self._latest_frame = None
        threading.Thread(target=self._webcam_feed, daemon=True).start()

    def _webcam_feed(self):
        """Background thread: read frames and push to label (preview only)."""
        self._cap = cv2.VideoCapture(0)
        if not self._cap.isOpened():
            self.root.after(0, lambda: self._cap_status.set("❌ Cannot open camera"))
            return

        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.root.after(0, lambda: (
            self._cap_status.set("● Camera ready — click Snapshot when ready"),
            self._snap_btn.config(state="normal"),
        ))

        while self._cap_running:
            ret, frame = self._cap.read()
            if not ret:
                time.sleep(0.05)
                continue

            self._latest_frame = frame.copy()

            # Draw guide oval
            display = frame.copy()
            h, w = display.shape[:2]
            cx, cy = w // 2, h // 2
            cv2.ellipse(display, (cx, cy), (120, 150), 0, 0, 360, (127, 90, 240), 2)
            cv2.putText(display, "Position face here", (cx - 90, cy + 170),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (127, 90, 240), 1)

            # Convert to PhotoImage
            rgb   = cv2.cvtColor(display, cv2.COLOR_BGR2RGB)
            img   = Image.fromarray(rgb)
            photo = ImageTk.PhotoImage(img)

            try:
                self._cam_label.config(image=photo)
                self._cam_label.image = photo
            except Exception:
                break

            time.sleep(0.033)  # ~30 fps

        if self._cap and self._cap.isOpened():
            self._cap.release()

    def _take_snapshot(self):
        """Freeze feed, detect emotion from the latest frame."""
        if self._latest_frame is None:
            messagebox.showwarning("Camera", "No frame captured yet. Try again.")
            return

        self._cap_running = False  # stop live feed
        self._snap_btn.config(state="disabled")
        self._cap_status.set("🔍 Analyzing emotion…")
        self.root.update_idletasks()

        frame = self._latest_frame.copy()

        # Run emotion detection in background
        threading.Thread(
            target=self._detect_from_frame,
            args=(frame,),
            daemon=True,
        ).start()

    def _detect_from_frame(self, frame):
        """Detect emotion from a single frame (runs in background thread)."""
        try:
            # Create a temp detector just to run inference
            detector = EmotionDetector(show_window=False)
            detector._load_model()
            detector._init_face_detector()

            faces = detector.detect_faces(frame)
            emotion = "neutral"

            if faces:
                x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
                fh, fw = frame.shape[:2]
                face_crop = frame[y:min(y+h, fh), x:min(x+w, fw)]
                if face_crop.size > 0:
                    label, conf = detector._infer_emotion(face_crop)
                    emotion = label
                    print(f"[App] Detected emotion: {emotion} ({conf*100:.1f}%)")

            self._detected_emotion = emotion

            # Show snapshot with overlay on UI
            rgb   = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img   = Image.fromarray(rgb)
            photo = ImageTk.PhotoImage(img)

            self.root.after(0, lambda: self._on_emotion_detected(photo))

        except Exception as e:
            print(f"[App] Detection error: {e}")
            self._detected_emotion = "neutral"
            self.root.after(0, lambda: self._show_preference(None))

    def _on_emotion_detected(self, photo):
        """Show detected emotion and proceed."""
        # Show result briefly then go to preference screen
        self._cam_label.config(image=photo)
        self._cam_label.image = photo

        emoji  = EMOTION_EMOJI.get(self._detected_emotion, "🎵")
        color  = EMOTION_COLOR.get(self._detected_emotion, ACCENT2)
        self._cap_status.set(f"{emoji}  Detected:  {self._detected_emotion.upper()}")

        # After 1.5 s, go to preference screen
        self.root.after(1500, lambda: self._show_preference(photo))

    def _back_to_home(self):
        self._cap_running = False
        self.root.after(200, self._show_home)

    # ──────────────────────────────────────────────────────────────────────────
    # SCREEN 3 — LANGUAGE, ERA & GENRE SELECTION
    # ──────────────────────────────────────────────────────────────────────────
    def _show_preference(self, snap_photo):
        self._clear()
        self.root.configure(bg=BG_DARK)

        # Scrollable outer
        canvas_outer = tk.Canvas(self.root, bg=BG_DARK, highlightthickness=0)
        vsb = ttk.Scrollbar(self.root, orient="vertical", command=canvas_outer.yview)
        canvas_outer.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas_outer.pack(fill="both", expand=True)
        canvas_outer.bind("<MouseWheel>", lambda e: canvas_outer.yview_scroll(
            int(-1*(e.delta/120)), "units"))

        outer = tk.Frame(canvas_outer, bg=BG_DARK)
        win   = canvas_outer.create_window((0, 0), window=outer, anchor="nw")
        canvas_outer.bind("<Configure>", lambda e: canvas_outer.itemconfig(win, width=e.width))
        outer.bind("<Configure>", lambda e: canvas_outer.configure(
            scrollregion=canvas_outer.bbox("all")))

        emotion = self._detected_emotion or "neutral"
        emoji   = EMOTION_EMOJI.get(emotion, "🎵")
        color   = EMOTION_COLOR.get(emotion, ACCENT2)

        # ── Emotion Badge ─────────────────────────────────────────────────────
        badge_outer = tk.Frame(outer, bg=BG_DARK)
        badge_outer.pack(pady=(40, 24), padx=60, fill="x")

        badge_frame = tk.Frame(badge_outer, bg=BG_CARD, padx=0, pady=0)
        badge_frame.pack(fill="x")

        # Colored top bar
        tk.Frame(badge_frame, bg=color, height=5).pack(fill="x")

        inner_badge = tk.Frame(badge_frame, bg=BG_CARD, padx=30, pady=22)
        inner_badge.pack(fill="x")

        tk.Label(inner_badge, text=emoji,
                 font=("Segoe UI Emoji", 44), bg=BG_CARD,
                 fg=color).pack(side="left", padx=(0, 20))
        txt_col = tk.Frame(inner_badge, bg=BG_CARD)
        txt_col.pack(side="left", anchor="w")
        tk.Label(txt_col, text=f"Feeling  {emotion.upper()}",
                 font=("Segoe UI", 20, "bold"), bg=BG_CARD, fg=color).pack(anchor="w")
        tk.Label(txt_col, text="Now customize your music experience below",
                 font=FONT_BODY, bg=BG_CARD, fg=TEXT_SUB).pack(anchor="w", pady=(4, 0))

        # ── Section builder helper ────────────────────────────────────────────
        def section(title_text, subtitle_text):
            sec = tk.Frame(outer, bg=BG_DARK)
            sec.pack(fill="x", padx=60, pady=(0, 28))
            hdr = tk.Frame(sec, bg=BG_DARK)
            hdr.pack(fill="x", pady=(0, 12))
            tk.Label(hdr, text=title_text, font=FONT_TITLE,
                     bg=BG_DARK, fg=TEXT_MAIN).pack(side="left")
            tk.Label(hdr, text=f"  —  {subtitle_text}", font=FONT_SMALL,
                     bg=BG_DARK, fg=TEXT_SUB).pack(side="left", pady=(4, 0))
            pills = tk.Frame(sec, bg=BG_DARK)
            pills.pack(fill="x")
            return pills

        def make_pills(parent, options, var, accent_col=ACCENT):
            """Create a row of pill-toggle buttons bound to a StringVar."""
            btns = {}

            def select(val):
                var.set(val)
                for v, b in btns.items():
                    if v == val:
                        b.config(bg=accent_col, fg=TEXT_MAIN,
                                 relief="flat", bd=0)
                    else:
                        b.config(bg=BG_CARD2, fg=TEXT_SUB,
                                 relief="flat", bd=0)

            for label, val in options:
                b = tk.Button(
                    parent,
                    text=label,
                    font=("Segoe UI", 11, "bold"),
                    bg=BG_CARD2,
                    fg=TEXT_SUB,
                    activebackground=accent_col,
                    activeforeground=TEXT_MAIN,
                    relief="flat",
                    bd=0,
                    padx=22,
                    pady=10,
                    cursor="hand2",
                    command=lambda v=val: select(v),
                )
                b.pack(side="left", padx=6, pady=4)
                btns[val] = b

            # Set initial highlight
            select(var.get())
            return btns

        # ── Language pills ────────────────────────────────────────────────────
        lang_pills = section("🌐  Language", "Pick your preferred language")
        langs = [
            ("🇮🇳 Telugu",  "Telugu"),
            ("🎵 Hindi",    "Hindi"),
            ("🌍 English",  "English"),
            ("🎶 Tamil",    "Tamil"),
            ("🎸 Kannada",  "Kannada"),
            ("🎺 Malayalam","Malayalam"),
        ]
        make_pills(lang_pills, langs, self._selected_lang, ACCENT)

        # ── Era pills ─────────────────────────────────────────────────────────
        era_pills = section("🕰️  Era", "Choose the music era")
        eras = [
            ("🎙️ Classic  (pre-1990)", "classic"),
            ("📼 Retro  (1990–2005)",  "old"),
            ("🔥 Modern  (2005+)",     "new"),
        ]
        make_pills(era_pills, eras, self._selected_era, "#e07b54")

        # ── Genre pills ───────────────────────────────────────────────────────
        genre_pills = section("🎸  Genre", "Filter by music genre")
        genres = [
            ("🎵 Any",        "Any"),
            ("🎤 Pop",         "Pop"),
            ("🥁 Folk",        "Folk"),
            ("🎻 Classical",   "Classical"),
            ("🎸 Rock",        "Rock"),
            ("💿 R&B",         "RnB"),
            ("🎷 Jazz",        "Jazz"),
            ("💃 Dance",       "Dance"),
            ("🕉️ Devotional", "Devotional"),
        ]
        make_pills(genre_pills, genres, self._selected_genre, ACCENT2)

        # ── Find Songs button ─────────────────────────────────────────────────
        btn_row = tk.Frame(outer, bg=BG_DARK)
        btn_row.pack(pady=(10, 20), padx=60, anchor="w")

        find_btn = tk.Button(
            btn_row,
            text="🎶   Find Songs for my mood",
            font=("Segoe UI", 15, "bold"),
            bg=ACCENT2,
            fg="#0a1a12",
            activebackground="#24a36a",
            activeforeground="#0a1a12",
            relief="flat",
            padx=48,
            pady=14,
            cursor="hand2",
            bd=0,
            command=self._on_find_songs,
        )
        find_btn.pack(side="left", padx=(0, 16))
        self._add_hover(find_btn, ACCENT2, "#24a36a")

        tk.Button(
            btn_row,
            text="← Retake Photo",
            font=FONT_BODY,
            bg=BG_CARD2,
            fg=TEXT_SUB,
            activebackground=BG_CARD,
            activeforeground=TEXT_MAIN,
            relief="flat",
            padx=20,
            pady=14,
            cursor="hand2",
            bd=0,
            command=self._show_capture,
        ).pack(side="left")

        # bottom padding
        tk.Frame(outer, bg=BG_DARK, height=40).pack()

    def _on_find_songs(self):
        lang  = self._selected_lang.get()
        era   = self._selected_era.get()
        genre = self._selected_genre.get()
        # Map era values: classic → old (DB might not have 'classic')
        db_era = "old" if era == "classic" else era
        self.engine.set_preferences(language=lang, era=db_era)
        self._show_songs()

    # ──────────────────────────────────────────────────────────────────────────
    # SCREEN 4 — SONGS DISPLAY
    # ──────────────────────────────────────────────────────────────────────────
    def _show_songs(self):
        self._clear()
        self.root.configure(bg=BG_DARK)

        emotion   = self._detected_emotion or "neutral"
        emoji     = EMOTION_EMOJI.get(emotion, "🎵")
        color     = EMOTION_COLOR.get(emotion, ACCENT2)
        lang      = self._selected_lang.get()
        era_label = {"classic": "Classic", "old": "Retro", "new": "Modern"}.get(
            self._selected_era.get(), "Modern"
        )

        # ── Top header bar ────────────────────────────────────────────────────
        header = tk.Frame(self.root, bg=BG_CARD, pady=18)
        header.pack(fill="x")

        left_hdr = tk.Frame(header, bg=BG_CARD)
        left_hdr.pack(side="left", padx=30)

        tk.Label(left_hdr, text=f"{emoji}  Songs for your mood",
                 font=FONT_HEAD, bg=BG_CARD, fg=TEXT_MAIN).pack(anchor="w")
        tk.Label(left_hdr,
                 text=f"Emotion: {emotion.upper()}  •  {lang}  •  {era_label}",
                 font=FONT_BODY, bg=BG_CARD, fg=color).pack(anchor="w", pady=(4, 0))

        right_hdr = tk.Frame(header, bg=BG_CARD)
        right_hdr.pack(side="right", padx=30)

        tk.Button(
            right_hdr,
            text="← New Scan",
            font=FONT_BODY,
            bg=ACCENT,
            fg=TEXT_MAIN,
            activebackground="#6b46d6",
            activeforeground=TEXT_MAIN,
            relief="flat",
            padx=18,
            pady=8,
            cursor="hand2",
            bd=0,
            command=self._show_capture,
        ).pack()

        # ── Now playing strip ─────────────────────────────────────────────────
        self._now_playing_var = tk.StringVar(value="Click a song to play  ♪")
        self._is_paused = False
        
        np_bar = tk.Frame(self.root, bg="#0e0e22", pady=12)
        np_bar.pack(fill="x")
        
        tk.Label(np_bar, textvariable=self._now_playing_var,
                 font=("Segoe UI", 12, "italic"), bg="#0e0e22",
                 fg=ACCENT4).pack(side="left", padx=30, anchor="w")
                 
        # Playback Control Buttons
        controls_frame = tk.Frame(np_bar, bg="#0e0e22")
        controls_frame.pack(side="right", padx=30)
        
        # Pause / Resume Button
        self._pause_btn = tk.Button(
            controls_frame,
            text="⏸  Pause",
            font=("Segoe UI", 10, "bold"),
            bg=BG_CARD2,
            fg=TEXT_MAIN,
            activebackground=ACCENT,
            activeforeground=TEXT_MAIN,
            relief="flat",
            padx=16,
            pady=6,
            cursor="hand2",
            bd=0,
            command=self._toggle_pause,
        )
        self._pause_btn.pack(side="left", padx=6)
        self._add_hover(self._pause_btn, BG_CARD2, ACCENT)
        
        # Stop Button
        self._stop_btn = tk.Button(
            controls_frame,
            text="⏹  Stop",
            font=("Segoe UI", 10, "bold"),
            bg=BG_CARD2,
            fg=TEXT_MAIN,
            activebackground=BTN_STOP,
            activeforeground=TEXT_MAIN,
            relief="flat",
            padx=16,
            pady=6,
            cursor="hand2",
            bd=0,
            command=self._stop_song,
        )
        self._stop_btn.pack(side="left", padx=6)
        self._add_hover(self._stop_btn, BG_CARD2, BTN_STOP)

        # ── Scrollable song grid ──────────────────────────────────────────────
        container = tk.Frame(self.root, bg=BG_DARK)
        container.pack(expand=True, fill="both", padx=0, pady=0)

        canvas = tk.Canvas(container, bg=BG_DARK, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        songs_frame = tk.Frame(canvas, bg=BG_DARK)
        window_id   = canvas.create_window((0, 0), window=songs_frame, anchor="nw")

        def _on_resize(event):
            canvas.itemconfig(window_id, width=event.width)
        canvas.bind("<Configure>", _on_resize)

        def _on_frame_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
        songs_frame.bind("<Configure>", _on_frame_configure)

        # Mousewheel
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # ── Fetch songs ───────────────────────────────────────────────────────
        songs = self._fetch_songs(emotion)
        self._current_playing_frame = None

        if not songs:
            tk.Label(
                songs_frame,
                text=f"😕  No songs found for your mood.\nTry changing language or era.",
                font=FONT_HEAD,
                bg=BG_DARK,
                fg=TEXT_SUB,
                justify="center",
            ).pack(expand=True, pady=80)
        else:
            # Grid: 3 columns
            cols  = 3
            for idx, song in enumerate(songs):
                row = idx // cols
                col = idx % cols
                self._make_song_card(songs_frame, song, row, col, color)

        # Status bar at bottom
        status_bar = tk.Frame(self.root, bg="#08080f", pady=8)
        status_bar.pack(fill="x", side="bottom")
        tk.Label(
            status_bar,
            text=f"Found {len(songs)} songs  •  Fully offline  •  Emotion: {emotion.upper()}",
            font=FONT_SMALL,
            bg="#08080f",
            fg=TEXT_SUB,
        ).pack(padx=20, anchor="w")

    def _fetch_songs(self, emotion: str, limit: int = 30) -> list:
        """Fetch multiple songs from the database for the given emotion."""
        import sqlite3
        from pathlib import Path

        db_path = Path(__file__).resolve().parent.parent / "data" / "songs.db"
        lang    = self._selected_lang.get()
        era     = "old" if self._selected_era.get() == "classic" else self._selected_era.get()

        # Map disgust → neutral
        if emotion == "disgust":
            emotion = "neutral"

        songs = []
        try:
            with sqlite3.connect(str(db_path)) as conn:
                conn.row_factory = sqlite3.Row

                # 1. Exact match
                rows = conn.execute("""
                    SELECT song_id, title, artist, language, era, emotion_tag, mood, file_path
                    FROM songs
                    WHERE emotion_tag = ? AND language = ? AND era = ? AND file_path != ''
                    ORDER BY RANDOM() LIMIT ?
                """, (emotion, lang, era, limit)).fetchall()
                songs = [dict(r) for r in rows]

                # 2. Relax era
                if len(songs) < 6:
                    rows2 = conn.execute("""
                        SELECT song_id, title, artist, language, era, emotion_tag, mood, file_path
                        FROM songs
                        WHERE emotion_tag = ? AND language = ? AND file_path != ''
                        ORDER BY RANDOM() LIMIT ?
                    """, (emotion, lang, limit)).fetchall()
                    seen = {s["song_id"] for s in songs}
                    for r in rows2:
                        d = dict(r)
                        if d["song_id"] not in seen:
                            songs.append(d)
                            seen.add(d["song_id"])

                # 3. Relax all filters
                if len(songs) < 6:
                    rows3 = conn.execute("""
                        SELECT song_id, title, artist, language, era, emotion_tag, mood, file_path
                        FROM songs
                        WHERE emotion_tag = ? AND file_path != ''
                        ORDER BY RANDOM() LIMIT ?
                    """, (emotion,), ).fetchall()
                    seen = {s["song_id"] for s in songs}
                    for r in rows3:
                        d = dict(r)
                        if d["song_id"] not in seen:
                            songs.append(d)
                            seen.add(d["song_id"])

        except Exception as e:
            print(f"[App] DB error: {e}")

        print(f"\n[App Debug] _fetch_songs for emotion='{emotion}', lang='{lang}', era='{era}' returned {len(songs)} songs:")
        for s in songs:
            print(f"  - '{s['title']}' by '{s['artist']}' | file_path='{s['file_path']}'")
        print()

        return songs[:limit]

    def _make_song_card(self, parent, song: dict, row: int, col: int, accent_color: str):
        """Create a premium song card widget."""
        title   = song.get("title",  "Unknown Title")
        artist  = song.get("artist", "Unknown Artist")
        lang    = song.get("language", "")
        era     = song.get("era", "")
        emotion = song.get("emotion_tag", "")
        mood    = song.get("mood", "")
        e_emoji = EMOTION_EMOJI.get(emotion, "🎵")

        card = tk.Frame(
            parent,
            bg=BG_CARD2,
            padx=20,
            pady=20,
            relief="flat",
            bd=0,
            cursor="hand2",
        )
        card.grid(row=row, column=col, padx=16, pady=14, sticky="nsew")
        parent.columnconfigure(col, weight=1)

        # Accent bar on top
        accent_bar = tk.Frame(card, bg=accent_color, height=4)
        accent_bar.pack(fill="x", pady=(0, 12))

        # Emoji / icon
        tk.Label(card, text=e_emoji,
                 font=("Segoe UI Emoji", 28), bg=BG_CARD2).pack(anchor="w")

        # Title
        tk.Label(
            card,
            text=title,
            font=FONT_SONG,
            bg=BG_CARD2,
            fg=TEXT_MAIN,
            wraplength=220,
            justify="left",
        ).pack(anchor="w", pady=(4, 2))

        # Artist
        tk.Label(
            card,
            text=f"🎤  {artist}",
            font=FONT_ARTIST,
            bg=BG_CARD2,
            fg=TEXT_SUB,
        ).pack(anchor="w")

        # Tags row
        tags_frame = tk.Frame(card, bg=BG_CARD2)
        tags_frame.pack(anchor="w", pady=(10, 4))

        for tag_text, tag_color in [(lang, "#4a3580"), (era, "#1a4a3a"), (mood, "#d85a38")]:
            if tag_text:
                tk.Label(
                    tags_frame,
                    text=f" {tag_text} ",
                    font=("Segoe UI", 9, "bold"),
                    bg=tag_color,
                    fg=TEXT_MAIN,
                    padx=6,
                    pady=2,
                ).pack(side="left", padx=(0, 6))

        # Play button
        play_btn = tk.Button(
            card,
            text="▶  Play",
            font=("Segoe UI", 10, "bold"),
            bg=ACCENT,
            fg=TEXT_MAIN,
            activebackground="#6b46d6",
            activeforeground=TEXT_MAIN,
            relief="flat",
            padx=14,
            pady=6,
            cursor="hand2",
            bd=0,
            command=lambda s=song, c=card: self._play_song(s, c),
        )
        play_btn.pack(anchor="w", pady=(10, 0))

        # Hover effects on card
        for widget in [card, accent_bar]:
            widget.bind("<Enter>", lambda e, c=card: c.config(bg="#242450"))
            widget.bind("<Leave>", lambda e, c=card: c.config(bg=BG_CARD2))

    def _play_song(self, song: dict, card: tk.Frame):
        """Play a song and update now-playing strip."""
        title  = song.get("title",  "Unknown")
        artist = song.get("artist", "Unknown")

        # Reset previously highlighted card
        if self._current_playing_frame and self._current_playing_frame.winfo_exists():
            self._current_playing_frame.config(bg=BG_CARD2)

        card.config(bg="#1a1a50")
        self._current_playing_frame = card

        self._now_playing_var.set(f"♪  Now Playing:  {title}  —  {artist}")

        # Reset pause state
        self._is_paused = False
        if hasattr(self, "_pause_btn") and self._pause_btn.winfo_exists():
            self._pause_btn.config(text="⏸  Pause", bg=BG_CARD2)

        # Play in background
        threading.Thread(
            target=lambda: self.engine.play_song(song),
            daemon=True,
        ).start()

    def _toggle_pause(self):
        """Toggle between pause and resume states."""
        current = self.engine.get_current_song()
        if not current:
            return

        title = current.get("title", "Unknown")
        artist = current.get("artist", "Unknown")

        if self._is_paused:
            self.engine.resume()
            self._is_paused = False
            self._pause_btn.config(text="⏸  Pause", bg=BG_CARD2)
            self._now_playing_var.set(f"♪  Now Playing:  {title}  —  {artist}")
        else:
            self.engine.pause()
            self._is_paused = True
            self._pause_btn.config(text="▶  Resume", bg=ACCENT)
            self._now_playing_var.set(f"⏸  Paused:  {title}  —  {artist}")

    def _stop_song(self):
        """Stop the currently playing song."""
        self.engine.stop()
        self._is_paused = False
        if hasattr(self, "_pause_btn") and self._pause_btn.winfo_exists():
            self._pause_btn.config(text="⏸  Pause", bg=BG_CARD2)
        self._now_playing_var.set("Playback stopped  ♪")

        # Reset highlighted song card
        if self._current_playing_frame and self._current_playing_frame.winfo_exists():
            self._current_playing_frame.config(bg=BG_CARD2)
            self._current_playing_frame = None

    # ── Utility ────────────────────────────────────────────────────────────────
    def _add_hover(self, btn, normal_color, hover_color):
        btn.bind("<Enter>", lambda e: btn.config(bg=hover_color))
        btn.bind("<Leave>", lambda e: btn.config(bg=normal_color))

    def _on_close(self):
        self._cap_running = False
        self.engine.quit()
        self.root.destroy()


# ── Entry point ────────────────────────────────────────────────────────────────
def main():
    from pathlib import Path
    project_root = Path(__file__).resolve().parent.parent
    db_path      = project_root / "data" / "songs.db"
    model_path   = project_root / "models" / "emotion_model.pth"

    # Automatically set up/update the database to sync with songs.csv.txt and files in songs/
    try:
        from setup_db import setup_database
        setup_database()
    except Exception as e:
        print(f"[App] ⚠ Warning: Could not auto-update database: {e}")

    for path, label, hint in [
        (db_path,    "Song database", "python src/setup_db.py"),
        (model_path, "Emotion model", "python src/train.py"),
    ]:
        if not path.exists():
            print(f"[App] ⚠ {label} not found: {path}\n  → Run:  {hint}")

    root = tk.Tk()
    app  = EmotionMusicApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
