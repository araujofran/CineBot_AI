import json
import sqlite3
from pathlib import Path

class SQLiteStore:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY, user TEXT, role TEXT, content TEXT,
                    created REAL DEFAULT (unixepoch()));
                CREATE TABLE IF NOT EXISTS inbox (
                    id TEXT PRIMARY KEY, payload TEXT, status TEXT DEFAULT 'pending',
                    attempts INTEGER DEFAULT 0, response TEXT, next_try REAL DEFAULT 0);
            """)

    def connect(self):
        return sqlite3.connect(self.path, timeout=10)

    def history(self, user):
        with self.connect() as db:
            db.execute('DELETE FROM history WHERE created < unixepoch() - 2592000')
            rows = db.execute('SELECT role,content FROM (SELECT * FROM history WHERE user=? ORDER BY id DESC LIMIT 20) ORDER BY id', (user,)).fetchall()
        return [dict(role=r, content=c) for r, c in rows]

    def append(self, user, role, text):
        with self.connect() as db:
            db.execute('INSERT INTO history(user,role,content) VALUES(?,?,?)', (user, role, text))

    def forget(self, user):
        with self.connect() as db:
            db.execute('DELETE FROM history WHERE user=?', (user,))
            for ident, payload in db.execute('SELECT id,payload FROM inbox').fetchall():
                if json.loads(payload).get('user') == user:
                    db.execute('DELETE FROM inbox WHERE id=?', (ident,))

    def enqueue(self, ident, user, text):
        with self.connect() as db:
            db.execute('INSERT OR IGNORE INTO inbox(id,payload) VALUES(?,?)', (ident, json.dumps(dict(user=user, text=text))))

    def pending(self):
        with self.connect() as db:
            return db.execute("SELECT id,payload,response FROM inbox WHERE status='pending' AND next_try <= unixepoch() ORDER BY rowid LIMIT 1").fetchone()

    def save_response(self, ident, text):
        with self.connect() as db:
            db.execute('UPDATE inbox SET response=? WHERE id=?', (text, ident))

    def done(self, ident):
        with self.connect() as db:
            db.execute("UPDATE inbox SET status='done',payload='{}',response=NULL WHERE id=?", (ident,))

    def retry(self, ident):
        with self.connect() as db:
            db.execute("UPDATE inbox SET attempts=attempts+1,next_try=unixepoch()+60,status=CASE WHEN attempts>=4 THEN 'failed' ELSE 'pending' END WHERE id=?", (ident,))
