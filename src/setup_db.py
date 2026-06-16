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
    language    TEXT    NOT NULL,
    genre       TEXT,
    era         TEXT    NOT NULL,
    emotion_tag TEXT    NOT NULL,
    file_path   TEXT    DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_emotion  ON songs(emotion_tag);
CREATE INDEX IF NOT EXISTS idx_language ON songs(language);
CREATE INDEX IF NOT EXISTS idx_era      ON songs(era);
CREATE INDEX IF NOT EXISTS idx_combined ON songs(emotion_tag, language, era);
"""

INSERT_SQL = """
    INSERT OR IGNORE INTO songs
        (title, artist, language, genre, era, emotion_tag, file_path)
    VALUES (?, ?, ?, ?, ?, ?, ?)
"""


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
    cursor.executescript(CREATE_TABLE_SQL)
    conn.commit()
    print("[SetupDB] Schema applied ✓")

    # ── Import CSV ─────────────────────────────────────────────────────────────
    imported = 0
    skipped  = 0

    with open(str(CSV_PATH), newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                cursor.execute(INSERT_SQL, (
                    row['title'].strip(),
                    row['artist'].strip(),
                    row['language'].strip(),
                    row.get('genre', '').strip(),
                    row['era'].strip(),
                    row['emotion_tag'].strip(),
                    '',    # file_path — user fills in later
                ))
                imported += 1
            except Exception as e:
                print(f"[SetupDB] SKIP row {row} — {e}")
                skipped += 1

    conn.commit()
    conn.close()

    print(f"[SetupDB] Imported : {imported} songs")
    print(f"[SetupDB] Skipped  : {skipped} rows")
    print(f"[SetupDB] Done ✓  →  {DB_PATH}")

    # ── Summary by emotion ────────────────────────────────────────────────────
    conn2 = sqlite3.connect(str(DB_PATH))
    rows = conn2.execute(
        "SELECT emotion_tag, COUNT(*) FROM songs GROUP BY emotion_tag ORDER BY emotion_tag"
    ).fetchall()
    conn2.close()

    print("\n[SetupDB] Songs per emotion:")
    for emo, cnt in rows:
        print(f"  {emo:10s}: {cnt}")


if __name__ == "__main__":
    setup_database()
