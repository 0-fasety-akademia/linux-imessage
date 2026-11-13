"""Tłumaczenia PL/EN – język wybierany wg ustawień systemu (LANGUAGE/LC_ALL/LC_MESSAGES/LANG).

Kluczem jest tekst polski; dla każdego innego języka niż polski używany jest angielski.
Wymuszenie: LINUX_IMESSAGE_LANG=pl albo =en.
"""
import os


def _detect():
    forced = os.environ.get("LINUX_IMESSAGE_LANG")
    if forced:
        return "pl" if forced.lower().startswith("pl") else "en"
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        val = os.environ.get(var)
        if val and val not in ("C", "POSIX"):
            return "pl" if val.split(":")[0].lower().startswith("pl") else "en"
    return "en"


LANG = _detect()

EN = {
    # menu
    "Odśwież wiadomości": "Refresh messages",
    "Odśwież kontakty": "Refresh contacts",
    "Połącz ponownie z iPhone'em": "Reconnect to iPhone",
    "Powiadomienia": "Notifications",
    "Treść w powiadomieniach": "Message text in notifications",
    "Zapisuj historię na tym komputerze": "Keep history on this computer",
    "Usuń lokalne dane…": "Delete local data…",
    "Prywatność": "Privacy",
    "Jak chronione są dane?": "How is my data protected?",
    "O programie {app}": "About {app}",
    "Zakończ": "Quit",
    "Pokaż {app}": "Show {app}",
    # main window
    "Wiadomości": "Messages",
    "Łączenie…": "Connecting…",
    "Połącz ponownie": "Reconnect",
    "Nowa wiadomość (Ctrl+N)": "New message (Ctrl+N)",
    "Brak wiadomości": "No messages",
    "Wiadomości z iPhone'a pojawią się tutaj.": "Messages from your iPhone will appear here.",
    "Wybierz rozmowę albo napisz nową wiadomość.": "Pick a conversation or start a new one.",
    "Wyślij": "Send",
    "Ty: ": "You: ",
    "Wiadomości wysłane bezpośrednio z iPhone'a nie są tu widoczne (ograniczenie iOS). "
    "Widać te odebrane i wysłane z tego komputera.":
        "Messages sent directly from the iPhone are not shown here (iOS limitation). "
        "You see received messages and those sent from this computer.",
    "Wysyłanie…": "Sending…",
    "Nie wysłano": "Not sent",
    "Nieprzeczytane: {n}": "Unread: {n}",
    "nieznany nadawca": "unknown sender",
    "Wersja {v} · {d}": "Version {v} · {d}",
    "Ta osoba pisała już do Ciebie przez iMessage": "This person has already messaged you via iMessage",
    # actions / toasts
    "iPhone nie jest połączony": "iPhone is not connected",
    "Historia zapisywana lokalnie": "History is saved locally",
    "Historia tylko w pamięci – plik na dysku usunięty": "History kept in memory only – file on disk deleted",
    "Nie znaleziono kontaktu „{q}”": "No contact found for “{q}”",
    "Usunięto lokalne dane": "Local data deleted",
    "Nie udało się wysłać wiadomości": "Failed to send the message",
    "Nie udało się pobrać kontaktów – włącz „Synchronizuj kontakty” na iPhonie":
        "Couldn't load contacts – turn on “Sync Contacts” on your iPhone",
    "Nowa wiadomość": "New message",
    # dialogs
    "Do kogo?": "To whom?",
    "Imię, nazwisko, numer albo e-mail": "Name, surname, number or e-mail",
    "Anuluj": "Cancel",
    "Dalej": "Next",
    "Usunąć lokalne dane?": "Delete local data?",
    "Historia wiadomości zapisana na tym komputerze zostanie usunięta. "
    "Wiadomości na iPhonie pozostaną nietknięte.":
        "Message history stored on this computer will be deleted. "
        "Messages on your iPhone stay untouched.",
    "Usuń": "Delete",
    "Blokada sieci: {s}": "Network block: {s}",
    "aktywna ✓": "active ✓",
    "NIEAKTYWNA": "INACTIVE",
    "iMessage i SMS z Twojego iPhone'a przez Bluetooth. Bez Maca, bez chmury, bez sieci.":
        "iMessage and SMS from your iPhone over Bluetooth. No Mac, no cloud, no network.",
    "PRIVACY": (
        "• The app talks only to your iPhone, over Bluetooth (BlueZ on this computer).\n"
        "• There is no server, account, telemetry, crash reporting or update check.\n"
        "• Network connections (IPv4/IPv6) are blocked inside the app process.\n"
        "• Contacts are kept in RAM only and disappear when the app quits.\n"
        "• Message history can be stored locally (~/.local/share/linux-imessage, "
        "mode 0600) – you can turn this off in the menu.\n\n"
        "iMessage itself is still sent by your iPhone through Apple's end-to-end encrypted "
        "service – exactly as when you type on the phone."),
    # connection states
    "Łączenie z iPhone'em…": "Connecting to iPhone…",
    "Rozłączono": "Disconnected",
    "Połączenie z iPhone'em zostało przerwane.": "The connection to the iPhone was lost.",
    "Brak iPhone'a": "No iPhone",
    "Nie znaleziono sparowanego iPhone'a. Sparuj go w Ustawieniach → Bluetooth.":
        "No paired iPhone found. Pair it in Settings → Bluetooth.",
    "Brak dostępu do wiadomości": "No access to messages",
    "Motyw": "Theme",
    "Systemowy": "System",
    "iPhone odmówił dostępu": "The iPhone refused access",
    "iPhone jest połączony, ale nie zezwala na wiadomości. Odblokuj go i w Ustawieniach → Bluetooth → (i) przy komputerze włącz „Pokazuj powiadomienia” (jeśli już jest włączone – wyłącz i włącz ponownie). Aplikacja połączy się sama w ciągu 30 s.":
        "The iPhone is connected but does not allow messages. Unlock it and in Settings → Bluetooth → (i) next to this computer turn on “Show Notifications” (if it is already on, turn it off and on again). The app reconnects by itself within 30 s.",
    "Nie udało się odświeżyć listy wiadomości: {e}": "Could not refresh the message list: {e}",
    "Na iPhonie: Bluetooth → (i) przy komputerze → włącz „Pokazuj powiadomienia”.":
        "On the iPhone: Bluetooth → (i) next to this computer → turn on “Show Notifications”.",
    "Szczegóły: {e}": "Details: {e}",
    "{phone} • połączono": "{phone} • connected",
}

PL = {
    "PRIVACY": (
        "• Aplikacja łączy się wyłącznie z Twoim iPhone'em przez Bluetooth (BlueZ na tym komputerze).\n"
        "• Nie ma żadnego serwera, konta, telemetrii, raportów błędów ani sprawdzania aktualizacji.\n"
        "• Połączenia sieciowe (IPv4/IPv6) są zablokowane w procesie aplikacji.\n"
        "• Kontakty są trzymane tylko w pamięci RAM i znikają po zamknięciu.\n"
        "• Historia wiadomości może być zapisywana lokalnie (~/.local/share/linux-imessage, "
        "prawa 0600) – możesz to wyłączyć w menu.\n\n"
        "Same iMessage nadal wysyła Twój iPhone, przez szyfrowaną end-to-end usługę Apple – "
        "tak samo jak wtedy, gdy piszesz z telefonu."),
}

WEEKDAYS = {"pl": ["pon", "wt", "śr", "czw", "pt", "sob", "nd"],
            "en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]}
DATE_FMT = {"pl": "%d.%m.%Y", "en": "%Y-%m-%d"}


def T(text, **kw):
    s = PL.get(text, text) if LANG == "pl" else EN.get(text, text)
    return s.format(**kw) if kw else s
