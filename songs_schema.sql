-- songs_schema.sql
-- ─────────────────────────────────────────────────────────────────────────────
-- Schema for the Emotion-Based Music Player song database.
-- Run this via:   python src/setup_db.py
-- Or manually:   sqlite3 data/songs.db < songs_schema.sql
-- ─────────────────────────────────────────────────────────────────────────────

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ── Main table ────────────────────────────────────────────────────────────────
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
    file_path   TEXT    DEFAULT ''     -- local path to .mp3 / .wav
);

-- ── Indices for fast filtered queries ─────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_emotion  ON songs(emotion_tag);
CREATE INDEX IF NOT EXISTS idx_language ON songs(language);
CREATE INDEX IF NOT EXISTS idx_era      ON songs(era);
CREATE INDEX IF NOT EXISTS idx_combined ON songs(emotion_tag, language, era);

-- ─────────────────────────────────────────────────────────────────────────────
-- Sample INSERT statements (representative subset — full DB built via setup_db.py)
-- ─────────────────────────────────────────────────────────────────────────────

-- Telugu / Happy / New
INSERT OR IGNORE INTO songs (title, artist, language, genre, era, emotion_tag, file_path) VALUES
  ('Butta Bomma',              'Armaan Malik',       'Telugu', 'Pop',    'new', 'happy', ''),
  ('Samajavaragamana',         'Sid Sriram',          'Telugu', 'Melody', 'new', 'happy', ''),
  ('Ramuloo Ramulaa',          'Anurag Kulkarni',     'Telugu', 'Folk',   'new', 'happy', ''),
  ('Naatu Naatu',              'Rahul Sipligunj',     'Telugu', 'Folk',   'new', 'happy', ''),
  ('Oo Antava',                'Indravathi Chauhan',  'Telugu', 'Mass',   'new', 'happy', '');

-- Telugu / Happy / Old
INSERT OR IGNORE INTO songs (title, artist, language, genre, era, emotion_tag, file_path) VALUES
  ('Bangaru Kodipetta',        'SP Balasubrahmanyam', 'Telugu', 'Folk',   'old', 'happy', ''),
  ('Aaresukoboyi Paresukunnanu','SP Balasubrahmanyam','Telugu', 'Folk',   'old', 'happy', '');

-- Hindi / Sad / New
INSERT OR IGNORE INTO songs (title, artist, language, genre, era, emotion_tag, file_path) VALUES
  ('Tum Hi Ho',                'Arijit Singh',        'Hindi',  'Romantic','new', 'sad',  ''),
  ('Channa Mereya',            'Arijit Singh',        'Hindi',  'Romantic','new', 'sad',  ''),
  ('Agar Tum Saath Ho',        'Alka Yagnik',         'Hindi',  'Melody', 'new', 'sad',  '');

-- English / Angry / New
INSERT OR IGNORE INTO songs (title, artist, language, genre, era, emotion_tag, file_path) VALUES
  ('Believer',                 'Imagine Dragons',     'English','Rock',   'new', 'angry',''),
  ('Enemy',                    'Imagine Dragons',     'English','Rock',   'new', 'angry',''),
  ('Warriors',                 'Imagine Dragons',     'English','Rock',   'new', 'angry','');

-- English / Angry / Old
INSERT OR IGNORE INTO songs (title, artist, language, genre, era, emotion_tag, file_path) VALUES
  ('In The End',               'Linkin Park',         'English','Rock',   'old', 'angry',''),
  ('Numb',                     'Linkin Park',         'English','Rock',   'old', 'angry',''),
  ('Lose Yourself',            'Eminem',              'English','Hip-Hop','old', 'angry','');

-- Telugu / Neutral / Old (classical)
INSERT OR IGNORE INTO songs (title, artist, language, genre, era, emotion_tag, file_path) VALUES
  ('Jagadananda Karaka',       'SP Balasubrahmanyam', 'Telugu', 'Classical','old','neutral',''),
  ('Brahmam Okate',            'SP Balasubrahmanyam', 'Telugu', 'Devotional','old','neutral',''),
  ('Endaro Mahanubhavulu',     'MS Subbulakshmi',     'Telugu', 'Classical','old','neutral','');

-- English / Neutral / New
INSERT OR IGNORE INTO songs (title, artist, language, genre, era, emotion_tag, file_path) VALUES
  ('Perfect',                  'Ed Sheeran',          'English','Pop',    'new', 'neutral',''),
  ('Photograph',               'Ed Sheeran',          'English','Pop',    'new', 'neutral',''),
  ('Yellow',                   'Coldplay',             'English','Rock',   'old', 'neutral','');

-- Telugu / Fear / New
INSERT OR IGNORE INTO songs (title, artist, language, genre, era, emotion_tag, file_path) VALUES
  ('Baahubali Theme',          'MM Keeravani',        'Telugu', 'Orchestral','new','fear',''),
  ('RRR Theme',                'MM Keeravani',        'Telugu', 'Orchestral','new','fear',''),
  ('Komuram Bheemudo',         'Kaala Bhairava',      'Telugu', 'Folk',   'new', 'fear','');

-- Hindi / Surprise / New
INSERT OR IGNORE INTO songs (title, artist, language, genre, era, emotion_tag, file_path) VALUES
  ('Kesariya',                 'Arijit Singh',        'Hindi',  'Romantic','new','surprise',''),
  ('Hawayein',                 'Arijit Singh',        'Hindi',  'Romantic','new','surprise',''),
  ('Love You Zindagi',         'Jasleen Royal',       'Hindi',  'Pop',    'new', 'surprise','');

-- English / Disgust / New (break-up / heartbreak mood)
INSERT OR IGNORE INTO songs (title, artist, language, genre, era, emotion_tag, file_path) VALUES
  ('Drivers License',          'Olivia Rodrigo',      'English','Pop',    'new', 'disgust',''),
  ('Easy On Me',               'Adele',               'English','Pop',    'new', 'disgust',''),
  ('Someone You Loved',        'Lewis Capaldi',       'English','Pop',    'new', 'disgust','');

-- Telugu / Sad / New
INSERT OR IGNORE INTO songs (title, artist, language, genre, era, emotion_tag, file_path) VALUES
  ('Ninnila Ninnila',          'Sid Sriram',          'Telugu', 'Melody', 'new', 'sad',  ''),
  ('Undiporaadhey',            'Sid Sriram',          'Telugu', 'Melody', 'new', 'sad',  ''),
  ('Yenti Yenti',              'Chinmayi',            'Telugu', 'Romantic','new','sad',  '');

-- English / Happy / New
INSERT OR IGNORE INTO songs (title, artist, language, genre, era, emotion_tag, file_path) VALUES
  ('Happy',                    'Pharrell Williams',   'English','Pop',    'new', 'happy',''),
  ('Uptown Funk',              'Mark Ronson',         'English','Funk',   'new', 'happy',''),
  ('Can''t Stop The Feeling',  'Justin Timberlake',   'English','Pop',    'new', 'happy','');

-- English / Fear / Old
INSERT OR IGNORE INTO songs (title, artist, language, genre, era, emotion_tag, file_path) VALUES
  ('Thriller',                 'Michael Jackson',     'English','Pop',    'old', 'fear', ''),
  ('Zombie',                   'The Cranberries',     'English','Rock',   'old', 'fear', ''),
  ('My Immortal',              'Evanescence',         'English','Ballad', 'old', 'fear', '');

-- English / Surprise / New
INSERT OR IGNORE INTO songs (title, artist, language, genre, era, emotion_tag, file_path) VALUES
  ('Viva La Vida',             'Coldplay',             'English','Rock',   'new', 'surprise',''),
  ('Wake Me Up',               'Avicii',               'English','EDM',    'new', 'surprise',''),
  ('Titanium',                 'David Guetta',         'English','EDM',    'new', 'surprise','');
