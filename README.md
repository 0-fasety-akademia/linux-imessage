# Linux iMessage 0.2.4

iMessage i SMS z Twojego iPhone'a na Ubuntu, przez Bluetooth.
Bez Maca, bez chmury, bez sieci.

Created by: JGu
Supported by Claude

*English version below.*

---

## Jak to działa

Linux iMessage nie łączy się z serwerami Apple. Rozmawia **tylko z Twoim iPhone'em, przez Bluetooth**,
tak jak zestaw głośnomówiący w samochodzie albo Phone Link na Windowsie:

```
 Laptop (Ubuntu)                      iPhone                       Odbiorca
┌──────────────────┐   Bluetooth   ┌──────────────┐   iMessage    ┌──────────┐
│ Linux iMessage   │ ◄───────────► │  Wiadomości  │ ◄───────────► │          │
│ BlueZ + obexd    │  MAP / PBAP   │  Kontakty    │  (Apple, E2E) │          │
└──────────────────┘               └──────────────┘               └──────────┘
```

- **MAP** (Message Access Profile): odbiór i wysyłka wiadomości. iPhone sam decyduje,
  czy wiadomość pójdzie jako iMessage (niebieski dymek), czy jako SMS.
- **PBAP** (Phone Book Access Profile): kontakty, żeby zamiast numerów widzieć imiona.
- O nowej wiadomości iPhone powiadamia od razu. Dodatkowo aplikacja co 45 s sprawdza skrzynkę,
  na wypadek gdyby powiadomienie nie dotarło.

## Pierwsze uruchomienie, krok po kroku (Ubuntu 24.04+)

1. **Zainstaluj paczkę** (zależności dociągną się same). Najnowszy plik
   `linux-imessage_<wersja>_all.deb` pobierz ze [strony Releases](https://github.com/jgu-linux-apps/linux-imessage/releases/latest):
   ```sh
   sudo apt install ./linux-imessage_<wersja>_all.deb
   ```
2. **Sparuj iPhone'a z laptopem:** Ustawienia Ubuntu → Bluetooth → wybierz iPhone'a →
   potwierdź ten sam kod na obu urządzeniach.
3. **Daj laptopowi dostęp na iPhonie:** Ustawienia → Bluetooth → ikona **(i)** przy nazwie
   laptopa → włącz:
   - **„Pokazuj powiadomienia”**, żeby były wiadomości (bez tego aplikacja pokaże „Brak dostępu do wiadomości”)
   - **„Synchronizuj kontakty”**, żeby zamiast numerów były imiona
4. **Uruchom Linux iMessage** z menu aplikacji. Jeśli wcześniej był wyłączony któryś przełącznik
   z kroku 3, kliknij ☰ → „Połącz ponownie z iPhone'em” albo „Odśwież kontakty”.
5. Gotowe. Nową wiadomość zaczynasz ikoną ołówka albo skrótem **Ctrl+N**. Wpisz 2 litery
   imienia lub nazwiska i wybierz osobę z podpowiedzi.

Interfejs możesz obejrzeć bez telefonu: `linux-imessage --demo`.

## Funkcje

- Lista rozmów z imionami z kontaktów iPhone'a, licznik nieprzeczytanych.
- Wysyłanie wiadomości (Enter albo przycisk ↑).
- **Podpowiedzi kontaktów** po 2 literach imienia lub nazwiska, także bez polskich znaków
  („luk” → Łukasz), albo po fragmencie numeru.
- **Oznaczenie „iMessage”** w podpowiedziach, opisane niżej.
- **Powiadomienia** o nowych wiadomościach (treść w powiadomieniu można ukryć).
- **Ikona w zasobniku:** zamknięcie okna chowa je do zasobnika, z menu ikony wybierasz
  „Zakończ”. Przy nieprzeczytanych ikona ma kropkę.
- **Jasny i ciemny motyw** zgodny z systemem. Ikona aplikacji też ma wariant jasny i ciemny,
  a ikona w zasobniku dopasowuje się do panelu.
- **Polski albo angielski** zależnie od języka systemu. Wymuszenie:
  `LINUX_IMESSAGE_LANG=en linux-imessage`.
- Wersja i data wydania w lewym dolnym rogu, nad nią „Created by: JGu” i „Supported by Claude”.
  Te same informacje są w oknie „O programie”.

### Oznaczenie „iMessage” przy kontaktach

iPhone przez Bluetooth **nie zdradza, kto ma iMessage**. Aplikacja oznacza więc tylko osoby,
od których przyszła już wiadomość jako iMessage:
- wiadomości z adresu e-mail (Apple ID), które zawsze są iMessage,
- wiadomości, które iOS oznacza typem „IM”, o ile iOS ten typ w ogóle podaje.

Brak oznaczenia **nie znaczy**, że ktoś nie ma iMessage. Przy wysyłce iPhone i tak sam
wybierze iMessage, jeśli to możliwe.

## Ograniczenia (wynikają z iOS, nie z aplikacji)

- **Wiadomości wysłane bezpośrednio z iPhone'a nie są widoczne.** Widać odebrane i wysłane
  z laptopa.
- **Brak starszej historii.** iPhone udostępnia głównie wiadomości od momentu włączenia dostępu,
  więc historia buduje się od teraz.
- **Brak załączników** (zdjęć), reakcji, potwierdzeń odczytu, wskaźnika pisania i czatów grupowych.
- Laptop i iPhone muszą być w zasięgu Bluetooth.

## Prywatność

- Komunikacja odbywa się **wyłącznie z iPhone'em przez Bluetooth**: BlueZ/obexd na tym komputerze, lokalny D-Bus.
- Nie ma serwera, konta, telemetrii, raportów błędów ani sprawdzania aktualizacji.
- **Sieć jest zablokowana** w procesie aplikacji (gniazda IPv4/IPv6 i DNS, `netguard.py`).
  Status sprawdzisz w ☰ → „Jak chronione są dane?”, a z terminala poleceniem
  `ss -tunp | grep python` (przy działającej aplikacji nie powinno nic pokazać).
- Kontakty są trzymane **tylko w RAM**.
- Historia jest w SQLite z `secure_delete`: katalog 0700, plik 0600.
  Zapis na dysk wyłączysz w ☰ → „Zapisuj historię na tym komputerze”,
  a wszystko usuniesz przez ☰ → „Usuń lokalne dane…”.
- Same iMessage wysyła iPhone przez szyfrowaną end-to-end usługę Apple, tak jak zawsze.

Pliki aplikacji w Twoim katalogu domowym:

| Plik | Co zawiera |
|---|---|
| `~/.local/share/linux-imessage/messages.db` | historia wiadomości (jeśli włączona) |
| `~/.config/linux-imessage/settings.json` | ustawienia z menu |
| `~/.local/share/icons/hicolor/scalable/apps/pl.jaro.LinuxIMessage.svg` | aktualny wariant ikony (jasny/ciemny) |

## Gdy coś nie działa

| Objaw | Co zrobić |
|---|---|
| „Brak iPhone'a” | Sparuj iPhone'a w Ustawieniach → Bluetooth (krok 2). |
| „Brak dostępu do wiadomości” | Na iPhonie włącz „Pokazuj powiadomienia” (krok 3), odblokuj telefon, ☰ → „Połącz ponownie”. |
| Numery zamiast imion | Włącz „Synchronizuj kontakty”, potem ☰ → „Odśwież kontakty”. |
| Brak ikony w zasobniku | `sudo apt install gnome-shell-extension-appindicator`, wyloguj się i zaloguj. |
| Inne | Uruchom `linux-imessage-diagnose` i wyślij `~/linux-imessage-diagnoza.txt` (numery i treści są częściowo zamaskowane). Możesz też uruchomić `linux-imessage` z terminala i przeczytać komunikaty. |

## Aktualizacja i odinstalowanie

- Aktualizacja: ikona w zasobniku → Zakończ, potem `sudo apt install ./linux-imessage_<wersja>_all.deb`.
- Odinstalowanie: `sudo apt remove linux-imessage`. Dane w katalogu domowym (tabela wyżej)
  zostają. Usuń je z menu przed odinstalowaniem albo ręcznie.

## Historia zmian

- **0.2.4:** bez zmian w aplikacji. Kod w repozytorium w katalogu `src/`, paczka `.deb` na stronie GitHub Releases (budowana automatycznie dla każdego tagu wersji); README: instalacja z Releases.
- **0.2.3:** oparta na 0.2.0, bez usuwania z 0.2.1/0.2.2, które iOS ignoruje. Dodano „Created by: JGu / Supported by Claude” w oknie i w „O programie”. Przy starcie aplikacja czyści resztki po usuwaniu z 0.2.1/0.2.2.
- **0.2.0:** angielski/polski wg systemu; ikona aplikacji jasna/ciemna; oznaczenie „iMessage”
  w podpowiedziach; wersja i data w oknie.
- **0.1.3:** podpowiedzi kontaktów przy nowej wiadomości.
- **0.1.2:** poprawiona ikona nieprzeczytanych w zasobniku.
- **0.1.1:** poprawny nadawca nowych wiadomości, kolejne wiadomości nie znikają, ponawianie pobierania kontaktów.
- **0.1.0:** pierwsza wersja.

## Budowanie z kodu

Kod źródłowy jest w katalogu `src/` repozytorium; paczek `.deb` nie ma w gicie, są w [Releases](https://github.com/jgu-linux-apps/linux-imessage/releases).
Wypchnięcie tagu `vX.Y.Z` zgodnego z `VERSION` w `src/linux_imessage/app.py` uruchamia GitHub Actions
(`.github/workflows/release.yml`), które budują paczkę i publikują wydanie. W katalogu `src/`:

```sh
./build-deb.sh   # → dist/linux-imessage_<wersja>_all.deb
```
Python 3 + GTK 4 / libadwaita (PyGObject) + dbus-python, bez innych zależności.

---

## English

**Linux iMessage** brings iMessage and SMS from your iPhone to Ubuntu over Bluetooth
(MAP for messages, PBAP for contacts). It needs no Mac, no cloud and no network: network
access is blocked inside the app.

**First run:**
1. Download the newest `.deb` from the [Releases page](https://github.com/jgu-linux-apps/linux-imessage/releases/latest) and run `sudo apt install ./linux-imessage_<version>_all.deb`
2. Pair the iPhone in Ubuntu Settings → Bluetooth.
3. On the iPhone, go to Settings → Bluetooth → **(i)** next to the laptop and turn on
   **Show Notifications** and **Sync Contacts**.
4. Start **Linux iMessage**. Press Ctrl+N to write a new message: type 2 letters of a name
   and pick the person.

The UI follows the system language (Polish/English) and the light/dark theme.

**Limitations (iOS):** messages sent directly from the iPhone and older history are not shown.
There are no attachments, reactions, read receipts or group chats.

**Troubleshooting:** run `linux-imessage-diagnose` and check `~/linux-imessage-diagnoza.txt`.
