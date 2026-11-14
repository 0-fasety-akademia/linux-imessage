# Linux iMessage 0.2.10

iMessage and SMS from your iPhone on Ubuntu, over Bluetooth.
No Mac, no cloud, no network.

Created by: JGu
Supported by Claude

The interface is in Polish or English, following the system language.

---

## How it works

Linux iMessage does not connect to Apple servers. It talks **only to your iPhone, over Bluetooth**,
the same way a car hands-free kit or Phone Link on Windows does:

```
 Laptop (Ubuntu)                      iPhone                       Recipient
┌──────────────────┐   Bluetooth   ┌──────────────┐   iMessage    ┌──────────┐
│ Linux iMessage   │ ◄───────────► │  Messages    │ ◄───────────► │          │
│ BlueZ + obexd    │  MAP / PBAP   │  Contacts    │  (Apple, E2E) │          │
└──────────────────┘               └──────────────┘               └──────────┘
```

- **MAP** (Message Access Profile): receiving and sending messages. The iPhone itself decides
  whether a message goes out as iMessage (blue bubble) or as SMS.
- **PBAP** (Phone Book Access Profile): contacts, so you see names instead of numbers.
- The iPhone reports a new message right away. In addition, the app checks the inbox every 45 s
  in case a notification gets lost.

## First run, step by step (Ubuntu 24.04+)

1. **Install the package** (dependencies are pulled in automatically). Download the newest
   `linux-imessage_<version>_all.deb` from the [Releases page](https://github.com/jgu-linux-apps/linux-imessage/releases/latest):
   ```sh
   sudo apt install ./linux-imessage_<version>_all.deb
   ```
2. **Pair the iPhone with the laptop:** Ubuntu Settings → Bluetooth → choose the iPhone →
   confirm the same code on both devices.
3. **Give the laptop access on the iPhone:** Settings → Bluetooth → the **(i)** icon next to the
   laptop's name → turn on:
   - **Show Notifications**, to get messages (without it the app shows "No access to messages")
   - **Sync Contacts**, to see names instead of numbers
4. **Start Linux iMessage** from the app menu. If one of the switches from step 3 was off before,
   click ☰ → "Reconnect to iPhone" or "Refresh contacts".
5. Done. Start a new message with the pencil icon or **Ctrl+N**. Type 2 letters of a first or
   last name and pick the person from the suggestions.

You can look at the interface without a phone: `linux-imessage --demo`.

## Features

- Conversation list with names from the iPhone's contacts, unread counter.
- Sending messages (Enter or the ↑ button).
- **Contact suggestions** after 2 letters of a first or last name, also without Polish characters
  ("luk" → Łukasz), or after part of a number.
- **"iMessage" label** in the suggestions, described below.
- **Notifications** of new messages (the message text in the notification can be hidden).
- **Tray icon:** closing the window hides it to the tray; choose "Quit" from the icon's menu.
  The icon gets a dot when there are unread messages.
- **Light and dark theme** following the system, plus the **Aurora** theme (menu → Theme). The app
  icon has a light and a dark variant too, and the tray icon matches the panel.
- **Polish or English** depending on the system language. To force a language:
  `LINUX_IMESSAGE_LANG=en linux-imessage`.
- Version and release date in the bottom left corner, above them "Created by: JGu" and
  "Supported by Claude". The same information is in the About window.

### The "iMessage" label on contacts

Over Bluetooth the iPhone **does not reveal who has iMessage**. So the app only labels people
from whom a message has already arrived as iMessage:
- messages from an e-mail address (Apple ID), which are always iMessage,
- messages that iOS marks with the "IM" type, if iOS provides that type at all.

No label **does not mean** that someone has no iMessage. When sending, the iPhone picks
iMessage on its own whenever possible.

## Limitations (they come from iOS, not from the app)

- **Messages sent directly from the iPhone are not shown.** You see received messages and those
  sent from the laptop.
- **No older history.** The iPhone mainly shares messages from the moment access was turned on,
  so the history builds up from now on.
- **No attachments** (photos), reactions, read receipts, typing indicator or group chats.
- The laptop and the iPhone must be within Bluetooth range.

## Privacy

- Communication happens **only with the iPhone over Bluetooth**: BlueZ/obexd on this computer, local D-Bus.
- There is no server, account, telemetry, crash reporting or update checking.
- **Network access is blocked** inside the app process (IPv4/IPv6 sockets and DNS, `netguard.py`).
  Check the status in ☰ → "How is my data protected?", or from a terminal with
  `ss -tunp | grep python` (with the app running it should show nothing).
- Contacts are kept **in RAM only**.
- History is stored in SQLite with `secure_delete`: directory 0700, file 0600.
  Turn off saving to disk in ☰ → "Keep history on this computer",
  and delete everything with ☰ → "Delete local data…".
- iMessages themselves are sent by the iPhone through Apple's end-to-end encrypted service, as always.

App files in your home directory:

| File | Contents |
|---|---|
| `~/.local/share/linux-imessage/messages.db` | message history (if enabled) |
| `~/.config/linux-imessage/settings.json` | settings from the menu |
| `~/.local/share/icons/hicolor/scalable/apps/pl.jaro.LinuxIMessage.svg` | current icon variant (light/dark) |

## Troubleshooting

| Symptom | What to do |
|---|---|
| "No iPhone" | Pair the iPhone in Settings → Bluetooth (step 2). |
| "No access to messages" | On the iPhone turn on "Show Notifications" (step 3), unlock the phone, ☰ → "Reconnect to iPhone". |
| Numbers instead of names | Turn on "Sync Contacts", then ☰ → "Refresh contacts". |
| No tray icon | `sudo apt install gnome-shell-extension-appindicator`, log out and back in. |
| Anything else | Run `linux-imessage-diagnose` and send `~/linux-imessage-diagnoza.txt` (numbers and texts are partly masked). You can also run `linux-imessage` from a terminal and read the messages. |

## Updating and uninstalling

- Update: tray icon → Quit, then `sudo apt install ./linux-imessage_<version>_all.deb`.
- Uninstall: `sudo apt remove linux-imessage`. The data in your home directory (table above)
  stays. Delete it from the menu before uninstalling, or by hand.

## Version history

- **0.2.10:** dark app icon in the series style: the app's own symbol on a deep navy tile, the same as the other apps of the series.
- **0.2.8:** the app icon (dock, app menu) switches light/dark together with the system **also while the app is closed** (a small helper started at login).
- **0.2.7:** new **Aurora** theme (menu → Theme): pastel glass in light mode, an aurora glow on a deep navy background in dark mode – chosen automatically from the system; a violet → cyan gradient on the selection and the main buttons, a glow on hover. *System* keeps the usual look.
- **0.2.6:** fix for BlueZ 5.87 (Ubuntu 26.04+): the message list refreshes again – the newer obexd returns messages as a dictionary rather than a list of pairs, so every refresh failed with "too many values to unpack" every 45 s; when the iPhone refuses access (OBEX 0x43 / 0x41), the app explains what to do on the phone and reconnects by itself every 30 s; a refresh error is shown once, not every 45 s.
- **0.2.5:** license: the app is now published under the Freeware License (No Modifications), see `LICENSE` — free to use and share unmodified, modification is not permitted; no other changes in the app.
- **0.2.4:** no changes in the app. The code is in the `src/` directory of the repository, the `.deb` package is on the GitHub Releases page (built automatically for every version tag); README: installing from Releases.
- **0.2.3:** based on 0.2.0, without the deleting from 0.2.1/0.2.2, which iOS ignores. Added "Created by: JGu / Supported by Claude" in the window and in About. On start the app cleans up what was left by the deleting in 0.2.1/0.2.2.
- **0.2.0:** English/Polish following the system; light/dark app icon; "iMessage" label in the
  suggestions; version and date in the window.
- **0.1.3:** contact suggestions when writing a new message.
- **0.1.2:** fixed unread icon in the tray.
- **0.1.1:** correct sender of new messages, further messages no longer disappear, retrying contact download.
- **0.1.0:** first version.

## Building from source

The source code is in the `src/` directory of the repository; `.deb` packages are not kept in git, they are on [Releases](https://github.com/jgu-linux-apps/linux-imessage/releases).
Pushing a tag `vX.Y.Z` that matches `VERSION` in `src/linux_imessage/app.py` starts GitHub Actions
(`.github/workflows/release.yml`), which builds the package and publishes the release. In the `src/` directory:

```sh
./build-deb.sh   # → dist/linux-imessage_<version>_all.deb
```
Python 3 + GTK 4 / libadwaita (PyGObject) + dbus-python, no other dependencies.
