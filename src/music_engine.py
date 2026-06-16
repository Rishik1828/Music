"""
music_engine.py
---------------
Handles all song-related logic:
  • SQLite song database queries (with fallback chain)
  • pygame.mixer playback (fade-out / fade-in)
  • Currently-playing song metadata
"""

import sqlite3
import random
import threading
from pathlib import Path
from typing import Optional, Tuple

import pygame

# ── Paths ──────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH      = PROJECT_ROOT / "data" / "songs.db"

# ── pygame mixer settings ──────────────────────────────────────────────────────
SAMPLE_RATE  = 44100
CHANNELS     = 2       # stereo
BUFFER_SIZE  = 4096
FADE_MS      = 1500    # 1.5-second fade-out before switching songs

# Emotion → disgust fallback tag
DISGUST_FALLBACK = "neutral"


class MusicEngine:
    """
    Controls song selection and audio playback.

    Usage
    -----
    engine = MusicEngine()
    engine.set_preferences(language="Telugu", era="new")
    engine.play_for_emotion("happy")
    """

    def __init__(self, db_path: str = str(DB_PATH)):
        self.db_path       = db_path
        self.language      = "Telugu"
        self.era           = "new"
        self._current_song : Optional[dict] = None
        self._lock         = threading.Lock()
        self._mixer_ready  = False
        self._init_mixer()

    # ── Mixer init ─────────────────────────────────────────────────────────────
    def _init_mixer(self):
        try:
            pygame.mixer.pre_init(SAMPLE_RATE, -16, CHANNELS, BUFFER_SIZE)
            pygame.mixer.init()
            self._mixer_ready = True
            print("[MusicEngine] pygame.mixer initialised successfully.")
        except pygame.error as e:
            print(f"[MusicEngine] WARNING: Could not initialise pygame.mixer — {e}")
            print("[MusicEngine] Playback will be disabled (metadata still works).")

    # ── Preferences ────────────────────────────────────────────────────────────
    def set_preferences(self, language: str, era: str):
        """Update user language/era preferences (session-level)."""
        self.language = language
        self.era      = era
        print(f"[MusicEngine] Preferences set → language={language}, era={era}")

    # ── DB Query ───────────────────────────────────────────────────────────────
    def _query_song(
        self,
        emotion: str,
        language: str,
        era: str,
    ) -> Optional[dict]:
        """
        Returns one random song dict matching all filters, or None.
        Dict keys: song_id, title, artist, language, era, emotion_tag, file_path
        """
        sql = """
            SELECT song_id, title, artist, language, era, emotion_tag, file_path
            FROM songs
            WHERE emotion_tag = ?
              AND language    = ?
              AND era         = ?
            ORDER BY RANDOM()
            LIMIT 1
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(sql, (emotion, language, era)).fetchone()
                if row:
                    return dict(row)
        except sqlite3.Error as e:
            print(f"[MusicEngine] DB error: {e}")
        return None

    def _query_with_fallback(self, emotion: str) -> Optional[dict]:
        """
        Fallback chain:
          1. emotion + language + era                (exact match)
          2. emotion + language  (any era)
          3. emotion             (any language, any era)
          4. neutral + language  (disgust or no match)
        """
        # disgust → neutral mood
        effective_emotion = DISGUST_FALLBACK if emotion == "disgust" else emotion

        # 1 – exact
        song = self._query_song(effective_emotion, self.language, self.era)
        if song:
            return song

        # 2 – relax era
        sql_no_era = """
            SELECT song_id, title, artist, language, era, emotion_tag, file_path
            FROM songs
            WHERE emotion_tag = ?
              AND language    = ?
            ORDER BY RANDOM()
            LIMIT 1
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(sql_no_era,
                                   (effective_emotion, self.language)).fetchone()
                if row:
                    print("[MusicEngine] Fallback: relaxed era filter.")
                    return dict(row)
        except sqlite3.Error:
            pass

        # 3 – relax language too
        sql_any = """
            SELECT song_id, title, artist, language, era, emotion_tag, file_path
            FROM songs
            WHERE emotion_tag = ?
            ORDER BY RANDOM()
            LIMIT 1
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(sql_any, (effective_emotion,)).fetchone()
                if row:
                    print("[MusicEngine] Fallback: relaxed language + era filters.")
                    return dict(row)
        except sqlite3.Error:
            pass

        # 4 – ultimate fallback: neutral
        print("[MusicEngine] Fallback: using neutral emotion.")
        return self._query_song("neutral", self.language, self.era) or \
               self._query_song("neutral", self.language, "new")

    # ── Playback ───────────────────────────────────────────────────────────────
    def play_for_emotion(self, emotion: str) -> Optional[dict]:
        """
        Selects and plays the best matching song for the given emotion.
        If a song is already playing, fades it out first.

        Returns the song metadata dict (or None if nothing found / no file).
        """
        song = self._query_with_fallback(emotion)
        if not song:
            print(f"[MusicEngine] No song found for emotion='{emotion}'")
            return None

        with self._lock:
            self._current_song = song

        file_path = song.get("file_path", "")
        title     = song.get("title",     "Unknown")
        artist    = song.get("artist",    "Unknown")

        print(f"[MusicEngine] ♪  Now playing: {title} — {artist}")
        print(f"              File: {file_path}")

        if not self._mixer_ready:
            print("[MusicEngine] Mixer not ready — skipping audio playback.")
            return song

        if not file_path or not Path(file_path).exists():
            print(f"[MusicEngine] WARNING: File not found → {file_path}")
            print("[MusicEngine] Song metadata returned but no audio played.")
            return song

        try:
            if pygame.mixer.music.get_busy():
                pygame.mixer.music.fadeout(FADE_MS)
                pygame.time.wait(FADE_MS + 100)   # small buffer after fade

            pygame.mixer.music.load(file_path)
            pygame.mixer.music.set_volume(0.85)
            pygame.mixer.music.play()
        except pygame.error as e:
            print(f"[MusicEngine] Playback error: {e}")

        return song

    def stop(self):
        """Fade out and stop current playback."""
        if self._mixer_ready and pygame.mixer.music.get_busy():
            pygame.mixer.music.fadeout(FADE_MS)

    def get_current_song(self) -> Optional[dict]:
        """Returns metadata of the currently selected song."""
        with self._lock:
            return self._current_song

    def quit(self):
        """Release mixer resources."""
        self.stop()
        if self._mixer_ready:
            pygame.mixer.quit()


# ── Quick CLI test ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import time

    engine = MusicEngine()
    engine.set_preferences(language="Telugu", era="new")

    emotions_to_test = ["happy", "sad", "angry", "neutral", "fear", "surprise", "disgust"]
    for emo in emotions_to_test:
        print(f"\n── Testing emotion: {emo} ──")
        song = engine.play_for_emotion(emo)
        if song:
            print(f"   Selected → {song['title']} | {song['artist']} | {song['era']}")
        else:
            print("   No song returned.")
        time.sleep(2)

    engine.quit()
    print("\n[MusicEngine] Test complete.")
