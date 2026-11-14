"""Interfejs GTK4/libadwaita."""
import os
import sys
import time
import unicodedata
import uuid

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from . import formats, netguard, theme  # noqa: E402
from .i18n import DATE_FMT, LANG, WEEKDAYS, T  # noqa: E402
from .store import Store, load_settings, save_settings  # noqa: E402

APP_ID = "pl.jaro.LinuxIMessage"
APP_NAME = "Linux iMessage"
VERSION = "0.2.8"
BUILD_DATE = "2026-11-14"
CREATED_BY = "Created by: JGu"
SUPPORTED_BY = "Supported by Claude"
POLL_SECONDS = 45
RECONNECT_SECONDS = 30

CSS = """
.bubble { border-radius: 18px; padding: 7px 12px; }
.bubble.in { background: alpha(currentColor, 0.09); }
.bubble.out { background: #0a84ff; color: white; }
.bubble.out.sending { opacity: 0.6; }
.bubble.out.failed { background: @error_bg_color; color: @error_fg_color; }
.meta { font-size: 0.8em; opacity: 0.55; }
.badge { background: #0a84ff; color: white; border-radius: 99px; padding: 1px 7px;
         font-size: 0.8em; font-weight: bold; }
.composer { padding: 8px 10px; }
.composer entry { border-radius: 99px; padding-left: 12px; }
.hint { font-size: 0.85em; opacity: 0.6; padding: 8px 18px; }
.imsg-chip { background: alpha(#0a84ff, 0.15); color: #0a84ff; border-radius: 99px;
             padding: 1px 8px; font-size: 0.75em; font-weight: bold; }
.version-footer { font-size: 0.75em; opacity: 0.5; padding: 6px 12px; }
.credits { font-size: 0.75em; padding: 0 12px; }
.credits.first { padding-top: 6px; }
.credits.last { opacity: 0.5; padding-bottom: 6px; }
"""




def fold(text):
    """Małe litery bez ogonków: „Łukasz” → „lukasz”."""
    t = unicodedata.normalize("NFKD", str(text).lower().replace("ł", "l"))
    return "".join(c for c in t if not unicodedata.combining(c))


def fmt_time(ts):
    t = time.localtime(ts)
    if time.strftime("%Y%m%d", t) == time.strftime("%Y%m%d"):
        return time.strftime("%H:%M", t)
    if time.time() - ts < 6 * 86400:
        return WEEKDAYS[LANG][t.tm_wday] + time.strftime(" %H:%M", t)
    return time.strftime(DATE_FMT[LANG], t)


class App(Adw.Application):
    def __init__(self, demo=False, device=None):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.demo = demo
        self.device = device
        self.settings = load_settings()
        self.store = Store(False if demo else self.settings["persist_history"])
        self.contacts = {}
        self.current = None
        self.connected = False
        self.connecting = False
        self.phone_name = None
        self.started = time.time()
        self.win = None
        self.tray = None
        self.backend = None
        self.contacts_loaded = False
        self.poll_id = None
        self.reconnect_id = None

    # ---------------------------------------------------------- setup ---
    def do_startup(self):
        Adw.Application.do_startup(self)
        Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.DEFAULT)
        prov = Gtk.CssProvider()
        prov.load_from_string(CSS) if hasattr(prov, "load_from_string") else prov.load_from_data(CSS.encode())
        from gi.repository import Gdk
        display = Gdk.Display.get_default()
        Gtk.StyleContext.add_provider_for_display(display, prov, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        src_icons = os.environ.get("LINUX_IMESSAGE_ICONS")
        if src_icons:
            theme = Gtk.IconTheme.get_for_display(display)
            for sub in ("hicolor/scalable/apps", "hicolor/symbolic/apps"):
                theme.add_search_path(os.path.join(src_icons, sub))
        self.src_icons = src_icons
        self.style = Adw.StyleManager.get_default()
        # motyw wyglądu: Systemowy albo Aurora (jasny/ciemny według systemu)
        from .aurora import AuroraTheme
        self.look = AuroraTheme()
        self.look.apply(self.settings.get("theme", "system"))
        self._actions()
        self._build_window()
        self.style.connect("notify::dark", lambda *_: self._apply_theme_icon())
        self._apply_theme_icon()
        self._setup_tray(src_icons)
        if self.demo:
            from .demo import DemoBackend
            self.backend = DemoBackend(self.on_event)
        else:
            from .backend import Backend
            self.backend = Backend(self.on_event, self.device)
        self.backend.connect()
        self.hold()

    def do_activate(self):
        self.show_window()

    def _actions(self):
        def add(name, cb, param=None, accel=None):
            a = Gio.SimpleAction.new(name, param)
            a.connect("activate", cb)
            self.add_action(a)
            if accel:
                self.set_accels_for_action("app." + name, [accel])

        def toggle(name, key):
            a = Gio.SimpleAction.new_stateful(name, None, GLib.Variant.new_boolean(self.settings[key]))
            a.connect("change-state", lambda act, v: self._set_setting(act, v, key))
            self.add_action(a)

        th = Gio.SimpleAction.new_stateful("theme", GLib.VariantType.new("s"),
                                           GLib.Variant("s", self.settings.get("theme", "system")))
        th.connect("activate", self._on_theme)
        self.add_action(th)
        add("quit", lambda *_: self.quit_app(), accel="<Control>q")
        add("refresh", lambda *_: self.backend.refresh(), accel="<Control>r")
        add("reconnect", lambda *_: self.reconnect())
        add("contacts", lambda *_: self.backend.load_contacts())
        add("new", lambda *_: self.new_conversation(), accel="<Control>n")
        add("wipe", lambda *_: self.confirm_wipe())
        add("privacy", lambda *_: self.show_privacy())
        add("about", lambda *_: self.show_about())
        add("open-conv", lambda _a, v: (self.show_window(), self.open_conversation(v.get_string())),
            GLib.VariantType.new("s"))
        toggle("persist-history", "persist_history")
        toggle("notifications", "notifications")
        toggle("notification-preview", "notification_preview")

    def _set_setting(self, action, value, key):
        action.set_state(value)
        self.settings[key] = value.get_boolean()
        if not self.demo:
            save_settings(self.settings)
        if key == "persist_history":
            self.store.set_persist(self.settings[key] and not self.demo)
            self.toast(T("Historia zapisywana lokalnie") if self.settings[key]
                       else T("Historia tylko w pamięci – plik na dysku usunięty"))

    def app_icon(self):
        return theme.variant_name(APP_ID, Adw.StyleManager.get_default().get_dark())

    def _apply_theme_icon(self):
        dark = self.style.get_dark()
        self.placeholder.set_icon_name(self.app_icon())
        self.win.set_icon_name(self.app_icon())
        if self.demo:
            return
        extra = [os.path.join(self.src_icons, "hicolor", "scalable", "apps")] if self.src_icons else []
        try:
            theme.apply_launcher_icon(APP_ID, dark, extra)
        except OSError as e:
            print(f"[theme] {e}", file=sys.stderr)

    def _setup_tray(self, src_icons):
        try:
            from .tray import Tray
            self.tray = Tray(APP_ID, APP_NAME, APP_ID + "-symbolic", APP_ID + "-unread-symbolic",
                             self.show_window,
                             [(1, T("Pokaż {app}", app=APP_NAME), self.show_window), (2, None, None),
                              (3, T("Zakończ"), self.quit_app)])
            if src_icons:
                self.tray.icon_theme_path = os.path.join(src_icons, "hicolor", "symbolic", "apps")
        except Exception as e:  # noqa: BLE001
            print(f"[tray] niedostępny: {e}", file=sys.stderr)
            self.tray = None

    # --------------------------------------------------------- window ---
    def _build_window(self):
        win = Adw.ApplicationWindow(application=self, title=APP_NAME, icon_name=APP_ID)
        win.set_default_size(980, 680)
        win.set_size_request(360, 420)
        win.connect("close-request", self._on_close)
        self.win = win
        self.toasts = Adw.ToastOverlay()

        # sidebar
        self.side_title = Adw.WindowTitle(title=T("Wiadomości"), subtitle=T("Łączenie…"))
        side_header = Adw.HeaderBar(title_widget=self.side_title)
        new_btn = Gtk.Button(icon_name="document-edit-symbolic", tooltip_text=T("Nowa wiadomość (Ctrl+N)"),
                             action_name="app.new")
        side_header.pack_start(new_btn)
        side_header.pack_end(self._menu_button())
        self.banner = Adw.Banner(title="", button_label=T("Połącz ponownie"), revealed=False)
        self.banner.set_action_name("app.reconnect")
        self.conv_list = Gtk.ListBox(css_classes=["navigation-sidebar"])
        self.conv_list.connect("row-activated", lambda _l, row: self.open_conversation(row.addr))
        self.empty_side = Adw.StatusPage(icon_name="mail-unread-symbolic", title=T("Brak wiadomości"),
                                         description=T("Wiadomości z iPhone'a pojawią się tutaj."))
        self.empty_side.add_css_class("compact")
        self.side_stack = Gtk.Stack()
        self.side_stack.add_named(Gtk.ScrolledWindow(child=self.conv_list, vexpand=True), "list")
        self.side_stack.add_named(self.empty_side, "empty")
        side_tv = Adw.ToolbarView(content=self.side_stack)
        side_tv.add_top_bar(side_header)
        side_tv.add_top_bar(self.banner)
        d = time.strptime(BUILD_DATE, "%Y-%m-%d")
        footer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        footer.append(Gtk.Label(label=CREATED_BY, xalign=0, css_classes=["credits", "first", "dim-label"]))
        footer.append(Gtk.Label(label=SUPPORTED_BY, xalign=0, css_classes=["credits", "dim-label"]))
        footer.append(Gtk.Label(label=T("Wersja {v} · {d}", v=VERSION, d=time.strftime(DATE_FMT[LANG], d)),
                                xalign=0, css_classes=["version-footer"]))
        side_tv.add_bottom_bar(footer)
        sidebar = Adw.NavigationPage(title=T("Wiadomości"), child=side_tv)

        # content
        self.conv_title = Adw.WindowTitle(title=APP_NAME, subtitle="")
        content_header = Adw.HeaderBar(title_widget=self.conv_title)
        self.msg_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, css_classes=["background"])
        self.msg_scroll = Gtk.ScrolledWindow(child=self.msg_list, vexpand=True)
        self.entry = Gtk.Entry(placeholder_text="iMessage", hexpand=True)
        self.entry.connect("activate", lambda *_: self.send_current())
        self.send_btn = Gtk.Button(icon_name="go-up-symbolic", tooltip_text=T("Wyślij"),
                                   css_classes=["circular", "suggested-action"], valign=Gtk.Align.CENTER)
        self.send_btn.connect("clicked", lambda *_: self.send_current())
        composer = Gtk.Box(spacing=8, css_classes=["composer"])
        composer.append(self.entry)
        composer.append(self.send_btn)
        conv_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        conv_box.append(self.msg_scroll)
        conv_box.append(Gtk.Separator())
        conv_box.append(composer)
        self.placeholder = placeholder = Adw.StatusPage(icon_name=self.app_icon(), title=APP_NAME,
                                     description=T("Wybierz rozmowę albo napisz nową wiadomość."))
        self.content_stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        self.content_stack.add_named(placeholder, "empty")
        self.content_stack.add_named(conv_box, "conv")
        content_tv = Adw.ToolbarView(content=self.content_stack)
        content_tv.add_top_bar(content_header)
        self.content_page = Adw.NavigationPage(title=APP_NAME, child=content_tv)

        self.split = Adw.NavigationSplitView(sidebar=sidebar, content=self.content_page,
                                             min_sidebar_width=280, max_sidebar_width=360)
        self.toasts.set_child(self.split)
        win.set_content(self.toasts)
        bp = Adw.Breakpoint.new(Adw.BreakpointCondition.parse("max-width: 620sp"))
        bp.add_setter(self.split, "collapsed", True)
        win.add_breakpoint(bp)
        self.render_conversations()

    def _on_theme(self, action, value):
        action.set_state(value)
        self.look.apply(value.get_string())
        self.settings["theme"] = value.get_string()
        save_settings(self.settings)

    def _menu_button(self):
        menu = Gio.Menu()
        s1 = Gio.Menu()
        s1.append(T("Odśwież wiadomości"), "app.refresh")
        s1.append(T("Odśwież kontakty"), "app.contacts")
        s1.append(T("Połącz ponownie z iPhone'em"), "app.reconnect")
        menu.append_section(None, s1)
        s2 = Gio.Menu()
        s2.append(T("Powiadomienia"), "app.notifications")
        s2.append(T("Treść w powiadomieniach"), "app.notification-preview")
        s2.append(T("Zapisuj historię na tym komputerze"), "app.persist-history")
        s2.append(T("Usuń lokalne dane…"), "app.wipe")
        menu.append_section(T("Prywatność"), s2)
        look = Gio.Menu()
        look.append(T("Systemowy"), "app.theme::system")
        look.append("Aurora", "app.theme::aurora")
        menu.append_submenu(T("Motyw"), look)
        s3 = Gio.Menu()
        s3.append(T("Jak chronione są dane?"), "app.privacy")
        s3.append(T("O programie {app}", app=APP_NAME), "app.about")
        s3.append(T("Zakończ"), "app.quit")
        menu.append_section(None, s3)
        return Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu, primary=True)

    def _on_close(self, win):
        if self.tray and self.tray.available:
            win.set_visible(False)
            return True
        self.quit_app()
        return True

    def show_window(self):
        self.win.set_visible(True)
        self.win.present()

    def quit_app(self):
        self.release()
        self.quit()

    def toast(self, text):
        self.toasts.add_toast(Adw.Toast(title=text, timeout=3))

    # ---------------------------------------------------------- render --
    def name_for(self, addr):
        if addr == "nieznany nadawca":
            return T("nieznany nadawca")
        return self.contacts.get(formats.match_key(addr)) or addr

    def render_conversations(self):
        self.conv_list.remove_all()
        convs = self.store.conversations()
        self.side_stack.set_visible_child_name("list" if convs else "empty")
        selected = None
        for addr, ts, text, outgoing, unread in convs:
            row = Gtk.ListBoxRow()
            row.addr = addr
            name = self.name_for(addr)
            box = Gtk.Box(spacing=10, margin_top=6, margin_bottom=6, margin_start=4, margin_end=4)
            box.append(Adw.Avatar(size=40, text=name, show_initials=name != addr))
            col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True, valign=Gtk.Align.CENTER)
            top = Gtk.Box(spacing=6)
            title = Gtk.Label(label=name, xalign=0, hexpand=True, ellipsize=3)
            title.add_css_class("heading")
            top.append(title)
            top.append(Gtk.Label(label=fmt_time(ts), css_classes=["meta"]))
            col.append(top)
            bottom = Gtk.Box(spacing=6)
            preview = (T("Ty: ") if outgoing else "") + (text or "").replace("\n", " ")
            bottom.append(Gtk.Label(label=preview, xalign=0, hexpand=True, ellipsize=3, css_classes=["dim-label"]))
            if unread:
                bottom.append(Gtk.Label(label=str(unread), css_classes=["badge"], valign=Gtk.Align.CENTER))
            col.append(bottom)
            box.append(col)
            row.set_child(box)
            self.conv_list.append(row)
            if addr == self.current:
                selected = row
        if selected:
            self.conv_list.select_row(selected)
        self.update_tray()

    def render_messages(self):
        if not self.current:
            return
        self.msg_list.remove_all()
        hint = Gtk.Label(label=T("Wiadomości wysłane bezpośrednio z iPhone'a nie są tu widoczne "
                                 "(ograniczenie iOS). Widać te odebrane i wysłane z tego komputera."),
                         wrap=True, justify=Gtk.Justification.CENTER, css_classes=["hint"])
        self.msg_list.append(Gtk.ListBoxRow(child=hint, activatable=False))
        last_ts = 0
        for key, ts, outgoing, text, status in self.store.messages(self.current):
            if ts - last_ts > 3600:
                self.msg_list.append(Gtk.ListBoxRow(
                    child=Gtk.Label(label=fmt_time(ts), css_classes=["meta"], margin_top=10),
                    activatable=False))
            last_ts = ts
            bubble = Gtk.Label(label=text or "…", wrap=True, wrap_mode=2, xalign=0, selectable=True,
                               max_width_chars=48, css_classes=["bubble", "out" if outgoing else "in"])
            if outgoing and status in ("sending", "failed"):
                bubble.add_css_class(status)
            wrap = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, margin_start=14, margin_end=14,
                           margin_top=2, margin_bottom=2,
                           halign=Gtk.Align.END if outgoing else Gtk.Align.START)
            wrap.append(bubble)
            if outgoing and status != "ok":
                wrap.append(Gtk.Label(label=T("Wysyłanie…") if status == "sending" else T("Nie wysłano"),
                                      css_classes=["meta"], halign=Gtk.Align.END))
            self.msg_list.append(Gtk.ListBoxRow(child=wrap, activatable=False))
        GLib.idle_add(self._scroll_bottom)

    def _scroll_bottom(self):
        adj = self.msg_scroll.get_vadjustment()
        adj.set_value(adj.get_upper())
        return False

    def open_conversation(self, addr):
        addr = formats.norm_addr(addr)
        self.current = addr
        self.store.mark_read(addr)
        name = self.name_for(addr)
        self.conv_title.set_title(name)
        self.conv_title.set_subtitle(addr if name != addr else "")
        self.content_page.set_title(name)
        self.content_stack.set_visible_child_name("conv")
        self.split.set_show_content(True)
        self.render_messages()
        self.render_conversations()
        self.entry.grab_focus()
        self.withdraw_notification(f"msg-{addr}")

    def update_tray(self):
        if self.tray:
            n = self.store.unread_total()
            self.tray.set_attention(n > 0, T("Nieprzeczytane: {n}", n=n) if n else APP_NAME)

    # ----------------------------------------------------------- actions -
    def send_current(self):
        text = self.entry.get_text().strip()
        if not text or not self.current:
            return
        if not self.connected:
            self.toast(T("iPhone nie jest połączony"))
            return
        key = f"local|{uuid.uuid4()}"
        self.store.add(key, self.current, time.time(), True, text, True, status="sending")
        self.entry.set_text("")
        self.backend.send(key, self.current, text)
        self.render_messages()
        self.render_conversations()

    def new_conversation(self):
        entry = Gtk.SearchEntry(placeholder_text=T("Imię, nazwisko, numer albo e-mail"), hexpand=True)
        results = Gtk.ListBox(css_classes=["boxed-list"], selection_mode=Gtk.SelectionMode.SINGLE)
        scroll = Gtk.ScrolledWindow(child=results, propagate_natural_height=True, max_content_height=300,
                                    hscrollbar_policy=Gtk.PolicyType.NEVER, visible=False)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, width_request=340)
        box.append(entry)
        box.append(scroll)
        dlg = Adw.AlertDialog(heading=T("Nowa wiadomość"), body=T("Do kogo?"))
        dlg.set_extra_child(box)
        dlg.add_response("cancel", T("Anuluj"))
        dlg.add_response("ok", T("Dalej"))
        dlg.set_response_appearance("ok", Adw.ResponseAppearance.SUGGESTED)
        dlg.set_close_response("cancel")

        def pick(addr):
            dlg.close()
            self.open_conversation(addr)

        def update(*_):
            results.remove_all()
            matches = self.search_contacts(entry.get_text())
            imsg = self.imessage_keys()
            for name, addr in matches:
                row = Adw.ActionRow(title=GLib.markup_escape_text(name),
                                    subtitle=GLib.markup_escape_text(addr), activatable=True)
                row.add_prefix(Adw.Avatar(size=32, text=name, show_initials=True))
                if formats.match_key(addr) in imsg:
                    row.add_suffix(Gtk.Label(label="iMessage", css_classes=["imsg-chip"],
                                             valign=Gtk.Align.CENTER,
                                             tooltip_text=T("Ta osoba pisała już do Ciebie przez iMessage")))
                row.addr = addr
                results.append(row)
            scroll.set_visible(bool(matches))
            if matches:
                results.select_row(results.get_row_at_index(0))

        def activate_entry(*_):
            row = results.get_selected_row()
            if row is not None:
                pick(row.addr)
            else:
                dlg.emit("response", "ok")
                dlg.close()

        def key(_ctl, keyval, _code, _state):
            from gi.repository import Gdk
            if keyval not in (Gdk.KEY_Down, Gdk.KEY_Up):
                return False
            row = results.get_selected_row()
            i = row.get_index() if row else -1
            nxt = results.get_row_at_index(i + (1 if keyval == Gdk.KEY_Down else -1))
            if nxt:
                results.select_row(nxt)
            return True

        keyctl = Gtk.EventControllerKey()
        keyctl.connect("key-pressed", key)
        entry.add_controller(keyctl)
        entry.connect("search-changed", update)
        entry.connect("activate", activate_entry)
        results.connect("row-activated", lambda _l, row: pick(row.addr))

        def done(d, resp):
            q = entry.get_text().strip()
            if resp != "ok" or not q:
                return
            row = results.get_selected_row()
            addr = row.addr if row is not None else self._resolve(q)
            if addr:
                self.open_conversation(addr)
            else:
                self.toast(T("Nie znaleziono kontaktu „{q}”", q=q))
        dlg.connect("response", done)
        dlg.present(self.win)
        entry.grab_focus()

    def imessage_keys(self):
        return {formats.match_key(a) for a in self.store.imessage_addrs()}

    def search_contacts(self, query, limit=8):
        """Podpowiedzi po kilku literach: początek imienia/nazwiska, bez polskich znaków."""
        q = fold(query.strip())
        if len(q) < 2:
            return []
        digits = "".join(c for c in q if c.isdigit())
        scored, seen = [], set()
        imsg = self.imessage_keys()
        for name, addrs in getattr(self, "contact_list", []):
            n = fold(name)
            words = n.split()
            if any(w.startswith(q) for w in words) or n.startswith(q):
                score = 0
            elif q in n:
                score = 1
            elif len(digits) >= 3 and any(digits in "".join(c for c in a if c.isdigit()) for a in addrs):
                score = 2
            else:
                continue
            for a in addrs:
                addr = formats.norm_addr(a)
                if addr not in seen:
                    seen.add(addr)
                    first = 0 if formats.match_key(addr) in imsg else 1
                    scored.append((score, name.lower(), first, name, addr))
        scored.sort()
        return [(name, addr) for _s, _n, _f, name, addr in scored[:limit]]

    @staticmethod
    def _is_placeholder(addr):
        return not addr or not ("@" in addr or any(c.isdigit() for c in addr))

    def _resolve_name(self, name):
        if not name:
            return None
        for n, addrs in getattr(self, "contact_list", []):
            if n == name and addrs:
                return formats.norm_addr(addrs[0])
        return None

    def _resolve(self, q):
        if "@" in q or any(c.isdigit() for c in q):
            return formats.norm_addr(q)
        ql = q.lower()
        for name, addrs in getattr(self, "contact_list", []):
            if ql in name.lower():
                return formats.norm_addr(addrs[0])
        return None

    def confirm_wipe(self):
        dlg = Adw.AlertDialog(heading=T("Usunąć lokalne dane?"),
                              body=T("Historia wiadomości zapisana na tym komputerze zostanie usunięta. "
                                     "Wiadomości na iPhonie pozostaną nietknięte."))
        dlg.add_response("cancel", T("Anuluj"))
        dlg.add_response("wipe", T("Usuń"))
        dlg.set_response_appearance("wipe", Adw.ResponseAppearance.DESTRUCTIVE)

        def done(d, resp):
            if resp == "wipe":
                self.store.wipe()
                self.current = None
                self.content_stack.set_visible_child_name("empty")
                self.render_conversations()
                self.toast(T("Usunięto lokalne dane"))
        dlg.connect("response", done)
        dlg.present(self.win)

    def show_privacy(self):
        guard = T("aktywna ✓") if netguard.is_installed() else T("NIEAKTYWNA")
        dlg = Adw.AlertDialog(heading=T("Prywatność"), body=T("PRIVACY") + "\n\n" + T("Blokada sieci: {s}", s=guard))
        dlg.add_response("ok", "OK")
        dlg.present(self.win)

    def show_about(self):
        about = Adw.AboutDialog(application_name=APP_NAME, application_icon=self.app_icon(), version=VERSION,
                                developer_name=CREATED_BY + "\n" + SUPPORTED_BY,
                                developers=["JGu"], license_type=Gtk.License.CUSTOM,
                                license="Freeware License (No Modifications).\nFree to use and to share unmodified; modification is not permitted.\nSee /usr/share/doc/linux-imessage/copyright.",
                                comments=T("iMessage i SMS z Twojego iPhone'a przez Bluetooth. Bez Maca, bez chmury, bez sieci."))
        about.present(self.win)

    def reconnect(self):
        if not self.connecting:
            self.backend.connect()

    # ------------------------------------------------------------ events -
    def on_event(self, kind, *data):
        getattr(self, "_ev_" + kind.replace("-", "_"))(*data)

    def _ev_status(self, state, info):
        self.connecting = state == "connecting"
        self.connected = state == "connected"
        messages = {
            "connecting": (T("Łączenie z iPhone'em…"), None),
            "connected": (None, None),
            "disconnected": (T("Rozłączono"), T("Połączenie z iPhone'em zostało przerwane.")),
            "no-device": (T("Brak iPhone'a"), T("Nie znaleziono sparowanego iPhone'a. Sparuj go w Ustawieniach → Bluetooth.")),
            "map-failed": (T("Brak dostępu do wiadomości"),
                           T("Na iPhonie: Bluetooth → (i) przy komputerze → włącz „Pokazuj powiadomienia”.")),
            "map-denied": (T("iPhone odmówił dostępu"),
                           T("iPhone jest połączony, ale nie zezwala na wiadomości. Odblokuj go i w Ustawieniach → "
                             "Bluetooth → (i) przy komputerze włącz „Pokazuj powiadomienia” (jeśli już jest włączone – "
                             "wyłącz i włącz ponownie). Aplikacja połączy się sama w ciągu 30 s.")),
        }
        if state == "map-failed" and isinstance(info, str) and ("0x43" in info or "0xc3" in info.lower()
                                                                   or "0x41" in info or "0xc1" in info.lower()):
            state, info = "map-denied", None      # OBEX Forbidden / Unauthorized – decyzja po stronie iPhone'a
        subtitle, banner = messages.get(state, (state, None))
        if state == "map-failed" and isinstance(info, str) and info:
            banner = banner + "\n" + T("Szczegóły: {e}", e=info)
        if self.connected:
            self.phone_name = info.get("name") if info else "iPhone"
            subtitle = T("{phone} • połączono", phone=self.phone_name)
            self.backend.refresh()
            if not self.contacts_loaded:
                self.contacts_loaded = True
                self.backend.load_contacts()
            if not self.poll_id:
                self.poll_id = GLib.timeout_add_seconds(POLL_SECONDS, self._poll)
        self.side_title.set_subtitle(subtitle)
        self.banner.set_title(banner or "")
        self.banner.set_revealed(bool(banner))
        if state in ("disconnected", "no-device", "map-failed", "map-denied") and not self.reconnect_id:
            self.reconnect_id = GLib.timeout_add_seconds(RECONNECT_SECONDS, self._auto_reconnect)

    def _poll(self):
        if self.connected:
            self.backend.refresh(20)
        return True

    def _auto_reconnect(self):
        self.reconnect_id = None
        if not self.connected:
            self.reconnect()
        return False

    def _ev_messages(self, batch):
        changed = False
        for m in batch:
            if not m["addr"]:
                m["addr"] = (self._resolve_name(m.get("sender_name")) or "nieznany nadawca")
            if m.get("sender_name") and formats.match_key(m["addr"]) not in self.contacts:
                self.contacts[formats.match_key(m["addr"])] = m["sender_name"]
            if self.store.has(m["key"]):
                if self._is_placeholder(self.store.addr_of(m["key"])) and not self._is_placeholder(m["addr"]):
                    self.store.set_addr(m["key"], m["addr"])
                    changed = True
                continue
            if m["outgoing"] and self.store.has_local_dup(m["addr"], m["ts"], m["subject"]):
                continue
            if self.store.has_similar(m["addr"], m["outgoing"], m["ts"], m["subject"]):
                continue
            read = m["read"] or (m["addr"] == self.current and self.win.is_active())
            if self.store.add(m["key"], m["addr"], m["ts"], m["outgoing"], m["subject"], read,
                              handle=m.get("path"), kind=m.get("type")):
                changed = True
                if m.get("path"):
                    self.backend.fetch_body(m["path"], m["key"])
                if not m["outgoing"] and not read and (m.get("live") or m["ts"] >= self.started - 120):
                    self.notify(m["addr"], m["subject"])
        if changed:
            self.render_conversations()
            if self.current:
                self.render_messages()

    def _ev_body(self, key, text, addr=None):
        self.store.set_text(key, text)
        if addr and self._is_placeholder(self.store.addr_of(key)):
            self.store.set_addr(key, addr)
        self.render_conversations()
        if self.current:
            self.render_messages()

    def _ev_sent(self, key, ok):
        self.store.set_status(key, "ok" if ok else "failed")
        if not ok:
            self.toast(T("Nie udało się wysłać wiadomości"))
        if self.current:
            self.render_messages()

    def _ev_contacts(self, contacts):
        self.contact_list = contacts
        self.contacts = {}
        for name, addrs in contacts:
            for a in addrs:
                self.contacts[formats.match_key(a)] = name
        self.render_conversations()
        if self.current:
            self.open_conversation(self.current)

    def _ev_error(self, op, msg):
        print(f"[{op}] {msg}", file=sys.stderr)
        if op == "connect":
            self._ev_status("map-failed", msg)
        elif op == "refresh":
            if not getattr(self, "_refresh_err_shown", False):     # raz na sesję, nie co 45 s
                self._refresh_err_shown = True
                self.toast(T("Nie udało się odświeżyć listy wiadomości: {e}", e=msg))
        elif op == "contacts":
            self.contacts_loaded = False
            self.toast(T("Nie udało się pobrać kontaktów – włącz „Synchronizuj kontakty” na iPhonie"))
            GLib.timeout_add_seconds(60, lambda: (self._retry_contacts(), False)[1])

    def _retry_contacts(self):
        if self.connected and not self.contacts_loaded:
            self.contacts_loaded = True
            self.backend.load_contacts()

    def notify(self, addr, text):
        if not self.settings["notifications"]:
            return
        n = Gio.Notification.new(self.name_for(addr))
        n.set_body(text if self.settings["notification_preview"] else T("Nowa wiadomość"))
        n.set_icon(Gio.ThemedIcon.new(self.app_icon()))
        n.set_default_action_and_target("app.open-conv", GLib.Variant.new_string(addr))
        self.send_notification(f"msg-{addr}", n)
