"""Tryb demo (--demo): fikcyjne dane, bez Bluetootha. Do podglądu interfejsu."""
import time

from gi.repository import GLib


class DemoBackend:
    def __init__(self, on_event, address=None):
        self.on_event = on_event
        self.session_path = "/demo"

    def _later(self, ms, *event):
        GLib.timeout_add(ms, lambda: (self.on_event(*event), False)[1])

    def connect(self):
        self._later(300, "status", "connected", {"name": "iPhone (demo)", "session": "/demo"})

    def refresh(self, count=50):
        t = int(time.time())
        msgs = [
            ("+48500100200", t - 7200, False, "Hej! Widzimy się jutro o 10?"),
            ("+48500100200", t - 7000, True, "Tak, będę 👍"),
            ("+48500100200", t - 600, False, "Super, wezmę kawę ☕"),
            ("anna@example.com", t - 86400, False, "Wysłałam Ci zdjęcia z weekendu"),
            ("+48600300400", t - 3 * 86400, False, "Twój kod weryfikacyjny: 482913"),
        ]
        batch = [{"key": f"demo{i}", "addr": a, "ts": ts, "outgoing": o, "subject": s,
                  "read": o or i != 2, "path": None, "type": "im" if i < 3 else "sms-gsm"}
                 for i, (a, ts, o, s) in enumerate(msgs)]
        self._later(200, "messages", batch)

    def fetch_body(self, path, key):
        pass

    def send(self, local_key, number, text):
        self._later(700, "sent", local_key, True)

    def load_contacts(self):
        self._later(400, "contacts", [("Marek Kowalski", ["+48 500 100 200"]),
                                      ("Anna Nowak", ["anna@example.com", "+48 501 222 111"]),
                                      ("Łukasz Kowalczyk", ["+48 600 700 800"]),
                                      ("Katia", ["+48 511 222 333"]),
                                      ("Kamil Nowicki", ["+48 602 111 999"])])
