"""Most do iPhone'a: BlueZ + obexd (MAP – wiadomości, PBAP – kontakty).

Wszystkie blokujące wywołania D-Bus idą w jednym wątku roboczym na prywatnym
połączeniu. Wyniki wracają do wątku GTK przez GLib.idle_add(on_event, ...).
Sygnały o nowych wiadomościach (MAP MNS) odbiera wątek główny.
"""
import datetime
import os
import queue
import re
import tempfile
import threading
import time

import dbus
from gi.repository import GLib

from . import formats

BLUEZ = "org.bluez"
OBEX = "org.bluez.obex"
OM = "org.freedesktop.DBus.ObjectManager"
PROPS = "org.freedesktop.DBus.Properties"
MAP_MAS = "00001132-0000-1000-8000-00805f9b34fb"


def parse_ts(ts):
    m = re.match(r"(\d{8}T\d{6})", str(ts or ""))
    if not m:
        return int(time.time())
    try:
        return int(datetime.datetime.strptime(m.group(1), "%Y%m%dT%H%M%S").timestamp())
    except ValueError:
        return int(time.time())


def handle_of(path):
    return str(path or "").rstrip("/").rsplit("/", 1)[-1]


def message_from_props(props, folder, path=None):
    outgoing = folder in ("sent", "outbox")
    if outgoing:
        addr = props.get("RecipientAddress") or props.get("Recipient") or ""
    else:
        addr = props.get("SenderAddress") or props.get("Sender") or ""
    ts_raw = str(props.get("Timestamp", ""))
    subject = str(props.get("Subject", ""))
    addr = formats.norm_addr(addr)
    return {
        "key": f"h|{handle_of(path)}" if path else f"{ts_raw}|{addr}|{int(outgoing)}|{subject[:40]}",
        "addr": addr,
        "ts": parse_ts(ts_raw),
        "outgoing": outgoing,
        "subject": subject,
        "read": bool(props.get("Read", False)) or outgoing,
        "type": str(props.get("Type", "")),
    }


class Backend:
    def __init__(self, on_event, address=None):
        self.on_event = on_event
        self.address = address
        self.session_path = None
        self.q = queue.Queue()
        self._sys = None
        self._ses = None
        self._mas = None
        self._client = None
        threading.Thread(target=self._run, name="bt-worker", daemon=True).start()
        self._watch_signals()

    # ---------------------------------------------------------- API -----
    def connect(self):
        self.q.put(("connect",))

    def refresh(self, count=50):
        self.q.put(("refresh", count))

    def fetch_body(self, path, key):
        self.q.put(("body", path, key))

    def send(self, local_key, number, text):
        self.q.put(("send", local_key, number, text))

    def load_contacts(self):
        self.q.put(("contacts",))

    # ------------------------------------------------------ plumbing ----
    def _emit(self, *event):
        GLib.idle_add(self._dispatch, event)

    def _dispatch(self, event):
        self.on_event(*event)
        return False

    def _run(self):
        self._sys = dbus.SystemBus(private=True)
        self._ses = dbus.SessionBus(private=True)
        while True:
            op, *args = self.q.get()
            try:
                getattr(self, "_op_" + op)(*args)
            except dbus.DBusException as e:
                msg = e.get_dbus_message() or e.get_dbus_name()
                self._emit("error", op, msg)
                if op in ("refresh", "send", "body") and self._session_gone(e):
                    self._drop_session()
            except Exception as e:  # noqa: BLE001
                self._emit("error", op, str(e))

    @staticmethod
    def _session_gone(e):
        name = e.get_dbus_name() or ""
        return "UnknownObject" in name or "NotConnected" in name or "Disconnected" in str(e)

    def _drop_session(self):
        self.session_path = None
        self._mas = None
        self._emit("status", "disconnected", None)

    def _wait_transfer(self, tpath, timeout=30):
        props = dbus.Interface(self._ses.get_object(OBEX, tpath), PROPS)
        end = time.time() + timeout
        while time.time() < end:
            try:
                st = str(props.Get("org.bluez.obex.Transfer1", "Status"))
            except dbus.DBusException:
                return True
            if st == "complete":
                return True
            if st == "error":
                return False
            time.sleep(0.15)
        return False

    def _find_device(self):
        om = dbus.Interface(self._sys.get_object(BLUEZ, "/"), OM)
        devs = [(str(p), i["org.bluez.Device1"]) for p, i in om.GetManagedObjects().items()
                if "org.bluez.Device1" in i]
        if self.address:
            for p, d in devs:
                if str(d.get("Address", "")).upper() == self.address.upper():
                    return p, d
            return None, None
        paired = [(p, d) for p, d in devs if d.get("Paired")]
        for p, d in paired:
            if "iphone" in str(d.get("Name", "")).lower():
                return p, d
        for p, d in paired:
            if MAP_MAS in [str(u).lower() for u in d.get("UUIDs", [])]:
                return p, d
        return None, None

    # ----------------------------------------------------------- ops ----
    def _op_connect(self):
        self._emit("status", "connecting", None)
        path, dev = self._find_device()
        if not dev:
            self._emit("status", "no-device", None)
            return
        name, addr = str(dev.get("Name", "iPhone")), str(dev["Address"])
        devprops = dbus.Interface(self._sys.get_object(BLUEZ, path), PROPS)
        if not dev.get("Trusted"):
            try:
                devprops.Set("org.bluez.Device1", "Trusted", True)
            except dbus.DBusException:
                pass
        if not dev.get("Connected"):
            try:
                dbus.Interface(self._sys.get_object(BLUEZ, path), "org.bluez.Device1").Connect(timeout=20)
            except dbus.DBusException:
                pass
        self._client = dbus.Interface(self._ses.get_object(OBEX, "/org/bluez/obex"), "org.bluez.obex.Client1")
        if self.session_path:
            try:
                self._client.RemoveSession(self.session_path)
            except dbus.DBusException:
                pass
        try:
            self.session_path = str(self._client.CreateSession(addr, {"Target": "map"}, timeout=30))
        except dbus.DBusException as e:
            self.session_path = None
            self._emit("status", "map-failed", e.get_dbus_message())
            return
        self._mas = dbus.Interface(self._ses.get_object(OBEX, self.session_path),
                                   "org.bluez.obex.MessageAccess1")
        self._mas.SetFolder("telecom")
        self._mas.SetFolder("msg")
        self._emit("status", "connected", {"name": name, "session": self.session_path})

    def _op_refresh(self, count):
        if not self._mas:
            return
        folders = [str(f["Name"]) for f in self._mas.ListFolders({})]
        batch = []
        for folder in ("inbox", "sent"):
            if folder not in folders:
                continue
            for mpath, props in self._mas.ListMessages(folder, {"MaxCount": dbus.UInt16(count)}):
                m = message_from_props(props, folder, mpath)
                m["path"] = str(mpath)
                batch.append(m)
        self._emit("messages", batch)

    def _op_new(self, path, folder):
        """Nowa wiadomość z MNS: zdarzenie niesie tylko uchwyt – resztę dociągamy."""
        try:
            props = dbus.Interface(self._ses.get_object(OBEX, path), PROPS).GetAll("org.bluez.obex.Message1")
        except dbus.DBusException:
            props = {}
        m = message_from_props(props, folder, path)
        m["path"] = None  # treść pobieramy tutaj
        parsed = self._get_bmessage(path)
        if parsed:
            if not m["addr"]:
                m["addr"] = formats.norm_addr(parsed["addr"])
            m["sender_name"] = parsed["name"]
            if parsed["body"] is not None:
                m["subject"] = parsed["body"]
        if not props.get("Timestamp"):
            m["ts"] = int(time.time())
        m["live"] = True
        self._emit("messages", [m])

    def _get_bmessage(self, path):
        msg = dbus.Interface(self._ses.get_object(OBEX, path), "org.bluez.obex.Message1")
        fd, tmp = tempfile.mkstemp(prefix="limsg-", suffix=".bmsg")
        os.close(fd)
        try:
            tpath, _ = msg.Get(tmp, False)
            if not self._wait_transfer(str(tpath)):
                return None
            with open(tmp, encoding="utf-8", errors="replace") as f:
                return formats.parse_bmessage(f.read())
        except dbus.DBusException:
            return None
        finally:
            os.unlink(tmp)

    def _op_body(self, path, key):
        parsed = self._get_bmessage(path)
        if parsed and parsed["body"] is not None:
            self._emit("body", key, parsed["body"], formats.norm_addr(parsed["addr"]))

    def _op_send(self, local_key, number, text):
        if not self._mas:
            self._emit("sent", local_key, False)
            return
        fd, tmp = tempfile.mkstemp(prefix="limsg-", suffix=".bmsg")
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(formats.build_bmessage(number, text))
        try:
            tpath, _ = self._mas.PushMessage(tmp, "outbox", {"Charset": "utf8"})
            self._emit("sent", local_key, self._wait_transfer(str(tpath)))
        except dbus.DBusException:
            self._emit("sent", local_key, False)
            raise
        finally:
            os.unlink(tmp)

    def _op_contacts(self):
        path, dev = self._find_device()
        if not dev:
            return
        client = dbus.Interface(self._ses.get_object(OBEX, "/org/bluez/obex"), "org.bluez.obex.Client1")
        spath = client.CreateSession(str(dev["Address"]), {"Target": "pbap"}, timeout=30)
        fd, tmp = tempfile.mkstemp(prefix="limsg-", suffix=".vcf")
        os.close(fd)
        try:
            pb = dbus.Interface(self._ses.get_object(OBEX, spath), "org.bluez.obex.PhonebookAccess1")
            pb.Select("int", "pb")
            tpath, _ = pb.PullAll(tmp, {"Format": "vcard30"})
            if self._wait_transfer(str(tpath), timeout=90):
                with open(tmp, encoding="utf-8", errors="replace") as f:
                    self._emit("contacts", formats.parse_vcards(f.read()))
        finally:
            os.unlink(tmp)
            try:
                client.RemoveSession(spath)
            except dbus.DBusException:
                pass

    # ----------------------------------------------- MNS (main thread) --
    def _watch_signals(self):
        bus = dbus.SessionBus()

        def added(path, ifaces):
            props = ifaces.get("org.bluez.obex.Message1")
            if not props or not self.session_path or not str(path).startswith(self.session_path):
                return
            folder = str(props.get("Folder", "inbox")).rsplit("/", 1)[-1].lower() or "inbox"
            self.q.put(("new", str(path), folder))

        bus.add_signal_receiver(added, "InterfacesAdded", OM, OBEX)
