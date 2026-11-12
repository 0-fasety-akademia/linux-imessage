"""Ikona aplikacji jasna/ciemna zgodnie z motywem systemu.

GNOME nie przełącza ikon aplikacji wg motywu, więc podmieniamy lokalnie (tylko w Twoim
katalogu domowym) plik ~/.local/share/icons/hicolor/scalable/apps/<APP_ID>.svg na wariant
jasny lub ciemny. Dock i menu aplikacji odświeżają ikonę po zmianie motywu.
"""
import os

SYSTEM_DIRS = ["/usr/share/icons/hicolor/scalable/apps"]
USER_DIR = os.path.join(os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share")),
                        "icons", "hicolor", "scalable", "apps")


def variant_name(app_id, dark):
    return f"{app_id}-{'dark' if dark else 'light'}"


def _find(name, extra_dirs=()):
    for d in list(extra_dirs) + SYSTEM_DIRS:
        p = os.path.join(d, name + ".svg")
        if os.path.exists(p):
            return p
    return None


def apply_launcher_icon(app_id, dark, extra_dirs=()):
    src = _find(variant_name(app_id, dark), extra_dirs)
    if not src:
        return False
    with open(src, "rb") as f:
        data = f.read()
    dst = os.path.join(USER_DIR, app_id + ".svg")
    try:
        with open(dst, "rb") as f:
            if f.read() == data:
                return True
    except OSError:
        pass
    os.makedirs(USER_DIR, exist_ok=True)
    tmp = dst + ".tmp"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, dst)
    # zmiana mtime katalogu motywu = sygnał dla GNOME Shell, by przeładować ikony
    hicolor = os.path.dirname(os.path.dirname(USER_DIR))
    for d in (USER_DIR, os.path.dirname(USER_DIR), hicolor):
        try:
            os.utime(d, None)
        except OSError:
            pass
    return True
