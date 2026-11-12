import argparse
import sys

from . import netguard


def main():
    netguard.install()  # najpierw: zero sieci w tym procesie

    import dbus.mainloop.glib
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

    from .app import VERSION, App

    ap = argparse.ArgumentParser(prog="linux-imessage", description="iMessage z iPhone'a przez Bluetooth")
    ap.add_argument("--demo", action="store_true", help="fikcyjne dane, bez Bluetootha")
    ap.add_argument("--device", metavar="MAC", help="adres Bluetooth iPhone'a")
    ap.add_argument("--version", action="version", version=f"Linux iMessage {VERSION}")
    args = ap.parse_args()
    sys.exit(App(demo=args.demo, device=args.device).run([sys.argv[0]]))


if __name__ == "__main__":
    main()
