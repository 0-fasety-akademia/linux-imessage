"""Lokalny magazyn wiadomości (SQLite). Tylko na tym komputerze, prawa 0600."""
import json
import os
import sqlite3
import time

APP = "linux-imessage"
DATA_DIR = os.path.join(os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share")), APP)
CONF_DIR = os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")), APP)
DB_PATH = os.path.join(DATA_DIR, "messages.db")
SETTINGS_PATH = os.path.join(CONF_DIR, "settings.json")

DEFAULTS = {
    "persist_history": True,     # zapis historii na dysku (tylko lokalnie)
    "notifications": True,
    "notification_preview": True,  # treść w powiadomieniu
}


def _private_dir(path):
    os.makedirs(path, mode=0o700, exist_ok=True)
    os.chmod(path, 0o700)


def load_settings():
    s = dict(DEFAULTS)
    try:
        with open(SETTINGS_PATH, encoding="utf-8") as f:
            s.update({k: v for k, v in json.load(f).items() if k in DEFAULTS})
    except (OSError, ValueError):
        pass
    return s


def save_settings(s):
    _private_dir(CONF_DIR)
    tmp = SETTINGS_PATH + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(s, f, indent=2)
    os.replace(tmp, SETTINGS_PATH)


COLS = "key, addr, ts, outgoing, text, read, status, handle, kind"

SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
  key TEXT PRIMARY KEY,
  addr TEXT NOT NULL,
  ts INTEGER NOT NULL,
  outgoing INTEGER NOT NULL,
  text TEXT,
  read INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'ok',
  handle TEXT,
  kind TEXT
);
CREATE INDEX IF NOT EXISTS idx_addr_ts ON messages(addr, ts);
"""


class Store:
    def __init__(self, persist):
        self.persist = persist
        self._open()

    def _open(self):
        if self.persist:
            _private_dir(DATA_DIR)
            old_umask = os.umask(0o077)
            try:
                self.db = sqlite3.connect(DB_PATH)
            finally:
                os.umask(old_umask)
            for p in (DB_PATH, DB_PATH + "-wal", DB_PATH + "-shm", DB_PATH + "-journal"):
                if os.path.exists(p):
                    os.chmod(p, 0o600)
            self.db.execute("PRAGMA secure_delete=ON")
        else:
            self.db = sqlite3.connect(":memory:")
        self.db.executescript(SCHEMA)
        cols = [r[1] for r in self.db.execute("PRAGMA table_info(messages)")]
        if "kind" not in cols:  # migracja z 0.1.0–0.1.3
            self.db.execute("ALTER TABLE messages ADD COLUMN kind TEXT")
        self.db.execute("DELETE FROM messages WHERE addr=''")  # śmieci z 0.1.0
        if "deleted" in [r[1] for r in self.db.execute("PRAGMA table_info(messages)")]:
            self.db.execute("DELETE FROM messages WHERE deleted=1")  # resztki po wersjach 0.2.1/0.2.2
        self.db.commit()

    def set_persist(self, persist):
        if persist == self.persist:
            return
        rows = self.db.execute(f"SELECT {COLS} FROM messages").fetchall()
        self.db.close()
        if not persist:
            self._remove_files()
        self.persist = persist
        self._open()
        self.db.executemany(f"INSERT OR IGNORE INTO messages ({COLS}) VALUES (?,?,?,?,?,?,?,?,?)", rows)
        self.db.commit()

    def _remove_files(self):
        for p in (DB_PATH, DB_PATH + "-wal", DB_PATH + "-shm", DB_PATH + "-journal"):
            try:
                os.remove(p)
            except FileNotFoundError:
                pass

    def wipe(self):
        self.db.execute("DELETE FROM messages")
        self.db.commit()
        if self.persist:
            self.db.execute("VACUUM")

    def imessage_addrs(self):
        """Adresy, od których przyszła wiadomość oznaczona przez iOS jako iMessage
        (typ „im”) albo z adresu e-mail (Apple ID – to zawsze iMessage)."""
        rows = self.db.execute("SELECT DISTINCT addr, kind FROM messages WHERE outgoing=0").fetchall()
        return {a for a, k in rows if "@" in a or str(k or "").lower() in ("im", "imessage")}

    def has(self, key):
        return self.db.execute("SELECT 1 FROM messages WHERE key=?", (key,)).fetchone() is not None

    def add(self, key, addr, ts, outgoing, text, read, status="ok", handle=None, kind=None):
        cur = self.db.execute(f"INSERT OR IGNORE INTO messages ({COLS}) VALUES (?,?,?,?,?,?,?,?,?)",
                              (key, addr, int(ts), int(outgoing), text, int(read), status, handle, kind))
        self.db.commit()
        return cur.rowcount > 0

    def has_local_dup(self, addr, ts, text):
        """Czy wiadomość z folderu 'sent' to ta sama, którą wysłaliśmy stąd?"""
        prefix = (text or "")[:20]
        return self.db.execute(
            "SELECT 1 FROM messages WHERE addr=? AND outgoing=1 AND key LIKE 'local|%' "
            "AND ABS(ts-?)<600 AND substr(text,1,?)=?",
            (addr, int(ts), len(prefix), prefix)).fetchone() is not None

    def has_similar(self, addr, outgoing, ts, text):
        """Ta sama wiadomość zapisana wcześniej pod innym kluczem (np. inna sesja MAP)."""
        prefix = (text or "")[:30]
        if not prefix:
            return False
        return self.db.execute(
            "SELECT 1 FROM messages WHERE addr=? AND outgoing=? AND ABS(ts-?)<180 "
            "AND substr(text,1,?)=?",
            (addr, int(outgoing), int(ts), len(prefix), prefix)).fetchone() is not None

    def set_addr(self, key, addr):
        self.db.execute("UPDATE messages SET addr=? WHERE key=?", (addr, key))
        self.db.commit()

    def addr_of(self, key):
        r = self.db.execute("SELECT addr FROM messages WHERE key=?", (key,)).fetchone()
        return r[0] if r else None

    def set_text(self, key, text):
        self.db.execute("UPDATE messages SET text=? WHERE key=?", (text, key))
        self.db.commit()

    def set_status(self, key, status):
        self.db.execute("UPDATE messages SET status=? WHERE key=?", (status, key))
        self.db.commit()

    def mark_read(self, addr):
        self.db.execute("UPDATE messages SET read=1 WHERE addr=? AND read=0", (addr,))
        self.db.commit()

    def unread_total(self):
        return self.db.execute("SELECT COUNT(*) FROM messages WHERE read=0 AND outgoing=0").fetchone()[0]

    def conversations(self):
        return self.db.execute("""
            SELECT m.addr, m.ts, m.text, m.outgoing,
                   (SELECT COUNT(*) FROM messages u WHERE u.addr=m.addr AND u.read=0 AND u.outgoing=0)
            FROM messages m
            WHERE m.rowid = (SELECT rowid FROM messages x WHERE x.addr=m.addr
                             ORDER BY ts DESC, rowid DESC LIMIT 1)
            ORDER BY m.ts DESC, m.rowid DESC""").fetchall()

    def messages(self, addr):
        return self.db.execute(
            "SELECT key, ts, outgoing, text, status FROM messages WHERE addr=? ORDER BY ts, rowid",
            (addr,)).fetchall()


def now():
    return int(time.time())
