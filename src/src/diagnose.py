#!/usr/bin/env python3
"""
linux-imessage-diagnose (z paczki linux-imessage)
Sprawdza, czy Ubuntu + BlueZ potrafi czytać i wysyłać iMessage/SMS
z sparowanego iPhone'a przez Bluetooth MAP (oraz kontakty przez PBAP).

Użycie:
  linux-imessage-diagnose                     # diagnostyka + ostatnie wiadomości
  linux-imessage-diagnose --watch 120         # nasłuch nowych wiadomości przez 120 s
  linux-imessage-diagnose --send +48123456789 "test z Linuksa"
  linux-imessage-diagnose --no-redact         # pokaż pełne numery i treści w raporcie

Wymaga: bluez, bluez-obexd, python3-dbus, python3-gi
  sudo apt install bluez bluez-obexd python3-dbus python3-gi
"""
import argparse
import os
import re
import sys
import tempfile
import time

try:
    import dbus
    import dbus.mainloop.glib
    from gi.repository import GLib
except ImportError as e:
    sys.exit(f"Brak modułu ({e}). Zainstaluj: sudo apt install python3-dbus python3-gi")

BLUEZ = "org.bluez"
OBEX = "org.bluez.obex"
OM_IFACE = "org.freedesktop.DBus.ObjectManager"
PROPS_IFACE = "org.freedesktop.DBus.Properties"
UUIDS = {
    "00001132-0000-1000-8000-00805f9b34fb": "MAP MAS (serwer wiadomości)",
    "00001133-0000-1000-8000-00805f9b34fb": "MAP MNS",
    "00001134-0000-1000-8000-00805f9b34fb": "MAP",
    "0000112f-0000-1000-8000-00805f9b34fb": "PBAP PSE (kontakty)",
    "0000111f-0000-1000-8000-00805f9b34fb": "HFP Audio Gateway",
    "7905f431-b5ce-4e99-a40f-4b1e122d00d0": "ANCS (powiadomienia BLE)",
}
MAP_MAS = "00001132-0000-1000-8000-00805f9b34fb"

REDACT = True
REPORT = []


def out(line=""):
    print(line)
    REPORT.append(line)


def mask_num(s):
    s = str(s)
    if not REDACT:
        return s
    return re.sub(r"\d(?=\d{3})", "•", s)


def mask_text(s, keep=15):
    s = str(s).replace("\r", " ").replace("\n", " ")
    if not REDACT or len(s) <= keep:
        return s
    return s[:keep] + f"… ({len(s)} zn.)"


# ---------------------------------------------------------------- BlueZ ---

def find_iphone(sysbus, address=None):
    om = dbus.Interface(sysbus.get_object(BLUEZ, "/"), OM_IFACE)
    devices = []
    for path, ifaces in om.GetManagedObjects().items():
        d = ifaces.get("org.bluez.Device1")
        if d:
            devices.append((str(path), d))
    if address:
        for path, d in devices:
            if str(d.get("Address", "")).upper() == address.upper():
                return path, d
        return None, None
    paired = [(p, d) for p, d in devices if d.get("Paired")]
    for p, d in paired:
        if "iphone" in str(d.get("Name", "")).lower():
            return p, d
    for p, d in paired:
        if MAP_MAS in [str(u) for u in d.get("UUIDs", [])]:
            return p, d
    out("Sparowane urządzenia:")
    for p, d in paired:
        out(f"  {d.get('Address')}  {d.get('Name')}")
    return None, None


def doctor(sysbus, sessbus, address):
    out("== 1. BlueZ / iPhone ==")
    path, dev = find_iphone(sysbus, address)
    if not dev:
        out("✗ Nie znalazłem sparowanego iPhone'a. Sparuj go w Ustawieniach → Bluetooth")
        out("  albo podaj adres: --device AA:BB:CC:DD:EE:FF")
        return None
    addr = str(dev["Address"])
    out(f"✓ {dev.get('Name')}  [{addr if not REDACT else addr[:8] + ':••:••:••'}]")
    for key in ("Paired", "Bonded", "Trusted", "Connected"):
        if key in dev:
            out(f"  {key}: {bool(dev[key])}")
    uuids = [str(u).lower() for u in dev.get("UUIDs", [])]
    out("  Profile iPhone'a:")
    for u, name in UUIDS.items():
        out(f"    {'✓' if u in uuids else '✗'} {name}")
    if not dev.get("Trusted"):
        try:
            dbus.Interface(sysbus.get_object(BLUEZ, path), PROPS_IFACE).Set(
                "org.bluez.Device1", "Trusted", True)
            out("  → ustawiłem Trusted=True")
        except dbus.DBusException as e:
            out(f"  ! nie udało się ustawić Trusted: {e.get_dbus_message()}")
    if not dev.get("Connected"):
        out("  → próbuję połączyć…")
        try:
            dbus.Interface(sysbus.get_object(BLUEZ, path), "org.bluez.Device1").Connect(timeout=20)
            out("  ✓ połączono")
        except dbus.DBusException as e:
            out(f"  ! Connect: {e.get_dbus_message()} (MAP może i tak zadziałać)")
    if MAP_MAS not in uuids:
        out("  ! iPhone nie ogłasza MAP. Na iPhonie: Ustawienia → Bluetooth → (i) przy")
        out("    komputerze → włącz „Pokazuj powiadomienia” i „Synchronizuj kontakty”.")

    out("\n== 2. obexd ==")
    dbus_iface = dbus.Interface(sessbus.get_object("org.freedesktop.DBus", "/org/freedesktop/DBus"),
                                "org.freedesktop.DBus")
    running = dbus_iface.NameHasOwner(OBEX)
    activatable = OBEX in [str(n) for n in dbus_iface.ListActivatableNames()]
    out(f"  obexd działa: {bool(running)}, aktywowalny przez D-Bus: {activatable}")
    if not running and not activatable:
        out("✗ Brak obexd. Zainstaluj: sudo apt install bluez-obexd")
        return None
    return addr


# ------------------------------------------------------------------ MAP ---

def wait_transfer(sessbus, tpath, timeout=30):
    props = dbus.Interface(sessbus.get_object(OBEX, tpath), PROPS_IFACE)
    end = time.time() + timeout
    while time.time() < end:
        try:
            st = str(props.Get("org.bluez.obex.Transfer1", "Status"))
        except dbus.DBusException:
            return True  # obiekt zniknął = transfer zakończony
        if st == "complete":
            return True
        if st == "error":
            return False
        time.sleep(0.2)
    return False


def parse_bmessage(raw):
    m = re.search(r"BEGIN:MSG\r?\n(.*?)\r?\nEND:MSG", raw, re.S)
    return m.group(1) if m else raw


def map_session(sessbus, addr):
    client = dbus.Interface(sessbus.get_object(OBEX, "/org/bluez/obex"), "org.bluez.obex.Client1")
    spath = client.CreateSession(addr, {"Target": "map"}, timeout=30)
    mas = dbus.Interface(sessbus.get_object(OBEX, spath), "org.bluez.obex.MessageAccess1")
    return client, spath, mas


def map_test(sessbus, addr, count):
    out("\n== 3. MAP – wiadomości ==")
    try:
        client, spath, mas = map_session(sessbus, addr)
    except dbus.DBusException as e:
        out(f"✗ Nie udało się otworzyć sesji MAP: {e.get_dbus_message()}")
        out("  Sprawdź przełącznik „Pokazuj powiadomienia” na iPhonie i odblokuj telefon.")
        return
    out(f"✓ Sesja MAP: {spath}")
    try:
        root = [str(f["Name"]) for f in mas.ListFolders({})]
        out(f"  Foldery /: {root}")
        mas.SetFolder("telecom")
        mas.SetFolder("msg")
        folders = [str(f["Name"]) for f in mas.ListFolders({})]
        out(f"  Foldery telecom/msg: {folders}")

        for folder in ("inbox", "sent"):
            if folder not in folders:
                continue
            msgs = mas.ListMessages(folder, {"MaxCount": dbus.UInt16(count)})
            out(f"\n  [{folder}] {len(msgs)} wiadomości (max {count}):")
            for i, (mpath, p) in enumerate(msgs):
                who = p.get("SenderAddress") or p.get("RecipientAddress") or p.get("Sender") or "?"
                out(f"   - {p.get('Timestamp', '')} {p.get('Type', '?'):8} od/do {mask_num(who)}"
                    f"  read={bool(p.get('Read', False))}  temat: {mask_text(p.get('Subject', ''))}")
                if i < 3:  # pełna treść dla pierwszych 3
                    body = fetch_body(sessbus, mpath)
                    out(f"       treść: {mask_text(body, 30) if body is not None else '✗ nie pobrano'}")
    except dbus.DBusException as e:
        out(f"✗ Błąd MAP: {e.get_dbus_message()}")
    finally:
        try:
            client.RemoveSession(spath)
        except dbus.DBusException:
            pass


def fetch_body(sessbus, mpath):
    msg = dbus.Interface(sessbus.get_object(OBEX, mpath), "org.bluez.obex.Message1")
    fd, tmp = tempfile.mkstemp(suffix=".bmsg")
    os.close(fd)
    try:
        tpath, _ = msg.Get(tmp, False)
        if not wait_transfer(sessbus, tpath):
            return None
        with open(tmp, encoding="utf-8", errors="replace") as f:
            return parse_bmessage(f.read())
    except dbus.DBusException:
        return None
    finally:
        os.unlink(tmp)


def build_bmessage(number, text):
    body = f"BEGIN:MSG\r\n{text}\r\nEND:MSG\r\n"
    return ("BEGIN:BMSG\r\nVERSION:1.0\r\nSTATUS:UNREAD\r\nTYPE:SMS_GSM\r\n"
            "FOLDER:TELECOM/MSG/OUTBOX\r\n"
            "BEGIN:BENV\r\nBEGIN:VCARD\r\nVERSION:2.1\r\n"
            f"N:{number}\r\nTEL:{number}\r\nEND:VCARD\r\n"
            "BEGIN:BBODY\r\nCHARSET:UTF-8\r\n"
            f"LENGTH:{len(body.encode('utf-8'))}\r\n{body}"
            "END:BBODY\r\nEND:BENV\r\nEND:BMSG\r\n")


def map_send(sessbus, addr, number, text):
    out("\n== MAP – wysyłanie ==")
    client, spath, mas = map_session(sessbus, addr)
    fd, tmp = tempfile.mkstemp(suffix=".bmsg")
    with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
        f.write(build_bmessage(number, text))
    try:
        mas.SetFolder("telecom")
        mas.SetFolder("msg")
        tpath, _ = mas.PushMessage(tmp, "outbox", {"Charset": "utf8"})
        ok = wait_transfer(sessbus, tpath)
        out(f"{'✓ wysłano' if ok else '✗ transfer nieudany'} → {mask_num(number)}")
        out("  Sprawdź na iPhonie, czy poszło jako niebieski dymek (iMessage).")
    except dbus.DBusException as e:
        out(f"✗ PushMessage: {e.get_dbus_message()}")
    finally:
        os.unlink(tmp)
        try:
            client.RemoveSession(spath)
        except dbus.DBusException:
            pass


def map_watch(sessbus, addr, seconds):
    out(f"\n== MAP – nasłuch nowych wiadomości przez {seconds} s ==")
    out("  Wyślij sobie teraz iMessage z innego urządzenia…")
    client, spath, _ = map_session(sessbus, addr)

    def on_added(path, ifaces):
        m = ifaces.get("org.bluez.obex.Message1")
        if m:
            who = m.get("SenderAddress") or m.get("Sender") or "?"
            out(f"  ★ NOWA {time.strftime('%H:%M:%S')} {m.get('Type', '')} od {mask_num(who)}:"
                f" {mask_text(m.get('Subject', ''))}")

    def on_props(iface, changed, invalidated, path=None):
        if iface == "org.bluez.obex.Message1":
            out(f"  ~ zmiana {path.rsplit('/', 1)[-1]}: {dict((str(k), str(v)) for k, v in changed.items())}")

    sessbus.add_signal_receiver(on_added, "InterfacesAdded", OM_IFACE, OBEX)
    sessbus.add_signal_receiver(on_props, "PropertiesChanged", PROPS_IFACE, OBEX, path_keyword="path")
    loop = GLib.MainLoop()
    GLib.timeout_add_seconds(seconds, loop.quit)
    try:
        loop.run()
    except KeyboardInterrupt:
        pass
    try:
        client.RemoveSession(spath)
    except dbus.DBusException:
        pass
    out("  koniec nasłuchu")


# ----------------------------------------------------------------- PBAP ---

def pbap_test(sessbus, addr):
    out("\n== 4. PBAP – kontakty ==")
    client = dbus.Interface(sessbus.get_object(OBEX, "/org/bluez/obex"), "org.bluez.obex.Client1")
    try:
        spath = client.CreateSession(addr, {"Target": "pbap"}, timeout=30)
        pb = dbus.Interface(sessbus.get_object(OBEX, spath), "org.bluez.obex.PhonebookAccess1")
        pb.Select("int", "pb")
        out(f"✓ Kontaktów w telefonie: {int(pb.GetSize())}")
        client.RemoveSession(spath)
    except dbus.DBusException as e:
        out(f"✗ PBAP: {e.get_dbus_message()}  (włącz „Synchronizuj kontakty” na iPhonie)")


# ----------------------------------------------------------------- main ---

def main():
    global REDACT
    ap = argparse.ArgumentParser(description="linux-imessage spike (MAP/PBAP)")
    ap.add_argument("--device", help="adres MAC iPhone'a")
    ap.add_argument("--count", type=int, default=10)
    ap.add_argument("--send", nargs=2, metavar=("NUMER", "TEKST"))
    ap.add_argument("--watch", type=int, metavar="SEKUNDY")
    ap.add_argument("--no-redact", action="store_true")
    args = ap.parse_args()
    REDACT = not args.no_redact

    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    sysbus, sessbus = dbus.SystemBus(), dbus.SessionBus()

    out(f"linux-imessage spike 0.0.1 — {time.strftime('%Y-%m-%d %H:%M')}")
    try:
        out(f"OS: {open('/etc/os-release').read().split('PRETTY_NAME=')[1].splitlines()[0]}")
    except Exception:
        pass
    addr = doctor(sysbus, sessbus, args.device)
    if addr:
        if args.send:
            map_send(sessbus, addr, *args.send)
        elif args.watch:
            map_watch(sessbus, addr, args.watch)
        else:
            map_test(sessbus, addr, args.count)
            pbap_test(sessbus, addr)

    report = os.path.expanduser("~/linux-imessage-diagnoza.txt")
    with open(report, "a", encoding="utf-8") as f:
        f.write("\n".join(REPORT) + "\n\n")
    print(f"\nRaport dopisany do: {report} — wklej mi go.")


if __name__ == "__main__":
    main()
