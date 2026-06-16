"""
setup_db.py
-----------
One-time setup script:
  1. Creates data/songs.db
  2. Applies the schema (songs_schema.sql)
  3. Imports all 420 songs from songs.csv.txt

Run once before starting the app:
    python src/setup_db.py
"""

import csv
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH      = PROJECT_ROOT / "data" / "songs.db"
CSV_PATH     = PROJECT_ROOT / "songs.csv.txt"
SCHEMA_PATH  = PROJECT_ROOT / "songs_schema.sql"


CREATE_TABLE_SQL = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS songs (
    song_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT    NOT NULL,
    artist      TEXT    NOT NULL,
    language    TEXT    NOT NULL CHECK(language    IN ('Telugu','Hindi','English')),
    genre       TEXT,
    era         TEXT    NOT NULL CHECK(era         IN ('old','new')),
    emotion_tag TEXT    NOT NULL CHECK(emotion_tag IN (
                            'happy','sad','angry','neutral',
                            'fear','surprise','disgust')),
    mood        TEXT    NOT NULL CHECK(mood        IN (
                            'happy','sad','angry','calm',
                            'romantic','energetic','anxious','surprised')),
    file_path   TEXT    DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_emotion  ON songs(emotion_tag);
CREATE INDEX IF NOT EXISTS idx_mood     ON songs(mood);
CREATE INDEX IF NOT EXISTS idx_language ON songs(language);
CREATE INDEX IF NOT EXISTS idx_era      ON songs(era);
CREATE INDEX IF NOT EXISTS idx_combined ON songs(emotion_tag, language, era);
"""

INSERT_SQL = """
    INSERT OR IGNORE INTO songs
        (title, artist, language, genre, era, emotion_tag, mood, file_path)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
"""


def find_song_file(project_root: Path, title: str, artist: str, language: str, mood: str) -> str:
    """
    Search the songs/ directory for a matching MP3 file.
    Priority order:
      1. songs / mood / language /
      2. songs / * / language /
      3. songs / ** / *.mp3
    """
    import re
    def normalize(s: str) -> str:
        return re.sub(r'[^a-zA-Z0-9]', '', s).lower()

    norm_title = normalize(title)
    if not norm_title:
        return ""

    # Search in exact mood/language folder first
    exact_dir = project_root / "songs" / mood.strip().lower() / language.strip()
    if exact_dir.exists():
        for f in exact_dir.glob("*.mp3"):
            norm_fname = normalize(f.stem)
            if norm_title in norm_fname or norm_fname in norm_title:
                return str(f.relative_to(project_root)).replace('\\', '/')

    # Search in other mood folders but same language
    songs_dir = project_root / "songs"
    if songs_dir.exists():
        for mood_folder in songs_dir.iterdir():
            if mood_folder.is_dir() and mood_folder.name.lower() != mood.strip().lower():
                lang_dir = mood_folder / language.strip()
                if lang_dir.exists():
                    for f in lang_dir.glob("*.mp3"):
                        norm_fname = normalize(f.stem)
                        if norm_title in norm_fname or norm_fname in norm_title:
                            return str(f.relative_to(project_root)).replace('\\', '/')

    # Fallback: search recursively anywhere in songs/
    if songs_dir.exists():
        for f in songs_dir.rglob("*.mp3"):
            norm_fname = normalize(f.stem)
            if norm_title in norm_fname or norm_fname in norm_title:
                return str(f.relative_to(project_root)).replace('\\', '/')

    return ""


def parse_filename_to_meta(file_path: Path, project_root: Path) -> dict:
    """Parse filename and path structure to extract title, artist, language, and mood."""
    parts = file_path.parts
    mood = "neutral"
    language = "Telugu"
    for i in range(len(parts) - 1, 0, -1):
        if parts[i] in ["Telugu", "Hindi", "English"]:
            language = parts[i]
            mood = parts[i-1]
            break

    stem = file_path.stem
    
    # Map mood to emotion_tag
    mood_to_emotion = {
        "happy": "happy",
        "sad": "sad",
        "angry": "angry",
        "calm": "neutral",
        "romantic": "sad",
        "energetic": "happy",
        "anxious": "fear",
        "surprised": "surprise"
    }
    emotion_tag = mood_to_emotion.get(mood.lower(), "neutral")
    
    # Clean up title
    words = stem.split('_')
    clean_words = []
    noise_words = {
        'telugu', 'hindi', 'english', 'song', 'songs', 'happy', 'sad', 'calm', 
        'romantic', 'energetic', 'anxious', 'surprised', 'official', 'audio', 
        'video', 'title', 'version', 'mp3', 'by', 'featuring', 'feat', 'soundtrack', 'ost'
    }
    for w in words:
        if w.lower() not in noise_words and w.strip():
            clean_words.append(w)
            
    title = " ".join(clean_words).title()
    if not title:
        title = stem.replace('_', ' ').title()
        
    # Artist heuristics
    artist = "Unknown Artist"
    artists_db = ["Arijit Singh", "Sid Sriram", "Armaan Malik", "Anurag Kulkarni", "SP Balasubrahmanyam", "Chinmayi", "Karthik", "Ed Sheeran", "Adele", "Coldplay", "Imagine Dragons", "Linkin Park", "Eminem", "Bruno Mars"]
    for a in artists_db:
        if a.lower() in title.lower():
            artist = a
            title = title.replace(a, "").strip()
            # Clean up double spaces
            title = " ".join(title.split())
            
    # Default era
    era = "new"
    if "old" in stem.lower() or "classic" in stem.lower() or "retro" in stem.lower():
        era = "old"
    elif "spb" in stem.lower() or "balasubrahmanyam" in stem.lower() or "chitra" in stem.lower():
        era = "old"
        
    return {
        "title": title,
        "artist": artist,
        "language": language,
        "genre": "Melody" if mood.lower() in ["calm", "romantic"] else "Pop",
        "era": era,
        "emotion_tag": emotion_tag,
        "mood": mood.lower(),
        "file_path": str(file_path.relative_to(project_root)).replace('\\', '/')
    }


def setup_database():
    # ── Create data/ directory ────────────────────────────────────────────────
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    print(f"[SetupDB] Database path : {DB_PATH}")
    print(f"[SetupDB] CSV path      : {CSV_PATH}")

    if not CSV_PATH.exists():
        print(f"[SetupDB] ERROR: songs.csv.txt not found at {CSV_PATH}")
        sys.exit(1)

    # ── Connect and apply schema ───────────────────────────────────────────────
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    # Drop existing table if exists to regenerate schema with new mood column
    cursor.execute("DROP TABLE IF EXISTS songs;")
    
    cursor.executescript(CREATE_TABLE_SQL)
    conn.commit()
    print("[SetupDB] Schema applied ✓")

    # ── Import CSV ─────────────────────────────────────────────────────────────
    imported = 0
    skipped  = 0
    matched_files = set()

    with open(str(CSV_PATH), newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                title = row.get('song_title', '').strip()
                if not title:
                    title = row.get('title', '').strip()
                artist = row.get('artist', '').strip()
                language = row.get('language', '').strip()
                genre = row.get('genre', '').strip()
                era = row.get('era', '').strip()
                emotion_tag = row.get('emotion_tag', '').strip()
                mood = row.get('mood', '').strip()

                # Find file path
                matched_file = find_song_file(PROJECT_ROOT, title, artist, language, mood)
                if matched_file:
                    matched_files.add(matched_file)

                cursor.execute(INSERT_SQL, (
                    title,
                    artist,
                    language,
                    genre,
                    era,
                    emotion_tag,
                    mood,
                    matched_file,
                ))
                imported += 1
            except Exception as e:
                print(f"[SetupDB] SKIP row {row} — {e}")
                skipped += 1

    # ── Scan and import remaining MP3 files ────────────────────────────────────
    songs_dir = PROJECT_ROOT / "songs"
    extra_imported = 0
    if songs_dir.exists():
        for f in songs_dir.rglob("*.mp3"):
            rel_path = str(f.relative_to(PROJECT_ROOT)).replace('\\', '/')
            if rel_path not in matched_files:
                try:
                    meta = parse_filename_to_meta(f, PROJECT_ROOT)
                    cursor.execute(INSERT_SQL, (
                        meta["title"],
                        meta["artist"],
                        meta["language"],
                        meta["genre"],
                        meta["era"],
                        meta["emotion_tag"],
                        meta["mood"],
                        meta["file_path"],
                    ))
                    extra_imported += 1
                    matched_files.add(rel_path)
                except Exception as e:
                    print(f"[SetupDB] Failed to parse extra file {rel_path}: {e}")

    conn.commit()
    conn.close()

    print(f"[SetupDB] Imported : {imported} songs from CSV")
    print(f"[SetupDB] Imported : {extra_imported} extra songs from files")
    print(f"[SetupDB] Skipped  : {skipped} rows")
    print(f"[SetupDB] Done ✓  →  {DB_PATH}")

    # ── Summary by emotion ────────────────────────────────────────────────────
    conn2 = sqlite3.connect(str(DB_PATH))
    rows = conn2.execute(
        "SELECT emotion_tag, COUNT(*) FROM songs WHERE file_path != '' GROUP BY emotion_tag ORDER BY emotion_tag"
    ).fetchall()
    matched_count = conn2.execute("SELECT COUNT(*) FROM songs WHERE file_path != ''").fetchone()[0]
    total_count = conn2.execute("SELECT COUNT(*) FROM songs").fetchone()[0]
    conn2.close()

    print("\n[SetupDB] Playable songs per emotion:")
    for emo, cnt in rows:
        print(f"  {emo:10s}: {cnt}")
        
    print(f"\n[SetupDB] Matched {matched_count} / {total_count} songs with audio files in 'songs/'")

    # Write summary to log file for debugging
    log_path = PROJECT_ROOT / "db_match_log.txt"
    try:
        with open(log_path, "w", encoding="utf-8") as log_f:
            log_f.write(f"Database setup run\n")
            log_f.write(f"Imported from CSV: {imported} songs\n")
            log_f.write(f"Imported from files: {extra_imported} songs\n")
            log_f.write(f"Matched: {matched_count} / {total_count} songs\n\n")
            
            log_f.write("Matched songs sample:\n")
            conn3 = sqlite3.connect(str(DB_PATH))
            conn3.row_factory = sqlite3.Row
            matched_rows = conn3.execute("SELECT title, artist, file_path FROM songs WHERE file_path != '' LIMIT 20").fetchall()
            for r in matched_rows:
                log_f.write(f"  {r['title']} - {r['artist']} -> {r['file_path']}\n")
            conn3.close()
        print(f"[SetupDB] Wrote debug log to: {log_path}")
    except Exception as le:
        print(f"[SetupDB] Warning: Could not write log file: {le}")


if __name__ == "__main__":
    setup_database()
