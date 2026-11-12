"""Ikona w zasobniku: StatusNotifierItem + com.canonical.dbusmenu (bez GTK3).

Działa z rozszerzeniem AppIndicator w Ubuntu (włączone domyślnie).
"""
import os

import dbus
import dbus.service

SNI = "org.kde.StatusNotifierItem"
MENU = "com.canonical.dbusmenu"
WATCHER = "org.kde.StatusNotifierWatcher"
PROPS = "org.freedesktop.DBus.Properties"


class _Menu(dbus.service.Object):
    def __init__(self, bus, items):
        # items: list of (id, label or None for separator, callback)
        super().__init__(bus, "/MenuBar")
        self.items = items
        self.revision = 1

    def _props(self, item):
        _id, label, _cb = item
        if label is None:
            return dbus.Dictionary({"type": "separator"}, signature="sv")
        return dbus.Dictionary({"label": label, "enabled": True, "visible": True}, signature="sv")

    @dbus.service.method(MENU, in_signature="iias", out_signature="u(ia{sv}av)")
    def GetLayout(self, parent_id, depth, names):
        children = dbus.Array(
            [dbus.Struct((i[0], self._props(i), dbus.Array([], signature="v")), signature="ia{sv}av")
             for i in self.items], signature="v")
        root = dbus.Struct((0, dbus.Dictionary({"children-display": "submenu"}, signature="sv"), children),
                           signature="ia{sv}av")
        return dbus.UInt32(self.revision), root

    @dbus.service.method(MENU, in_signature="aias", out_signature="a(ia{sv})")
    def GetGroupProperties(self, ids, names):
        return dbus.Array([dbus.Struct((i[0], self._props(i)), signature="ia{sv}")
                           for i in self.items if not ids or i[0] in ids], signature="(ia{sv})")

    @dbus.service.method(MENU, in_signature="is", out_signature="v")
    def GetProperty(self, _id, name):
        return ""

    @dbus.service.method(MENU, in_signature="isvu", out_signature="")
    def Event(self, _id, event_id, data, timestamp):
        if event_id == "clicked":
            for i in self.items:
                if i[0] == _id and i[2]:
                    i[2]()

    @dbus.service.method(MENU, in_signature="a(isvu)", out_signature="ai")
    def EventGroup(self, events):
        for e in events:
            self.Event(e[0], e[1], e[2], e[3])
        return dbus.Array([], signature="i")

    @dbus.service.method(MENU, in_signature="i", out_signature="b")
    def AboutToShow(self, _id):
        return False

    @dbus.service.method(MENU, in_signature="ai", out_signature="aiai")
    def AboutToShowGroup(self, ids):
        return dbus.Array([], signature="i"), dbus.Array([], signature="i")

    @dbus.service.signal(MENU, signature="ui")
    def LayoutUpdated(self, revision, parent):
        pass

    @dbus.service.method(PROPS, in_signature="ss", out_signature="v")
    def Get(self, iface, prop):
        return self.GetAll(iface)[prop]

    @dbus.service.method(PROPS, in_signature="s", out_signature="a{sv}")
    def GetAll(self, iface):
        return dbus.Dictionary({"Version": dbus.UInt32(3), "TextDirection": "ltr", "Status": "normal",
                                "IconThemePath": dbus.Array([], signature="s")}, signature="sv")


class Tray(dbus.service.Object):
    def __init__(self, app_id, title, icon, attention_icon, on_activate, menu_items):
        self.bus = dbus.SessionBus()
        self.bus_name_str = f"org.kde.StatusNotifierItem-{os.getpid()}-1"
        self._sni_busname = dbus.service.BusName(self.bus_name_str, self.bus)
        super().__init__(self.bus, "/StatusNotifierItem")
        self.menu = _Menu(self.bus, menu_items)
        self.app_id, self.title = app_id, title
        self.icon, self.attention_icon = icon, attention_icon
        self.status = "Active"
        self.unread = False
        self.icon_theme_path = ""
        self.tooltip = title
        self.on_activate = on_activate
        self.available = False
        self.bus.add_signal_receiver(self._owner_changed, "NameOwnerChanged",
                                     "org.freedesktop.DBus", arg0=WATCHER)
        self._register()

    def _owner_changed(self, name, old, new):
        if new:
            self._register()
        else:
            self.available = False

    def _register(self):
        try:
            w = self.bus.get_object(WATCHER, "/StatusNotifierWatcher")
            dbus.Interface(w, WATCHER).RegisterStatusNotifierItem(self.bus_name_str)
            self.available = True
        except dbus.DBusException:
            self.available = False

    def set_attention(self, on, tooltip=None):
        """Nieprzeczytane = inna ikona, ale Status zostaje „Active”.
        (Tryb NeedsAttention rozszerzenie AppIndicator rysuje w złym rozmiarze.)"""
        if tooltip and tooltip != self.tooltip:
            self.tooltip = tooltip
            self.NewToolTip()
        if on != self.unread:
            self.unread = on
            self.NewIcon()

    # ---- SNI ----
    @dbus.service.method(SNI, in_signature="ii")
    def Activate(self, x, y):
        self.on_activate()

    @dbus.service.method(SNI, in_signature="ii")
    def SecondaryActivate(self, x, y):
        self.on_activate()

    @dbus.service.method(SNI, in_signature="ii")
    def ContextMenu(self, x, y):
        pass

    @dbus.service.method(SNI, in_signature="is")
    def Scroll(self, delta, orientation):
        pass

    @dbus.service.signal(SNI)
    def NewIcon(self):
        pass

    @dbus.service.signal(SNI)
    def NewAttentionIcon(self):
        pass

    @dbus.service.signal(SNI)
    def NewToolTip(self):
        pass

    @dbus.service.signal(SNI, signature="s")
    def NewStatus(self, status):
        pass

    @dbus.service.method(PROPS, in_signature="ss", out_signature="v")
    def Get(self, iface, prop):
        return self.GetAll(iface)[prop]

    @dbus.service.method(PROPS, in_signature="s", out_signature="a{sv}")
    def GetAll(self, iface):
        icon = self.attention_icon if self.unread else self.icon
        empty_pix = dbus.Array([], signature="(iiay)")
        return dbus.Dictionary({
            "Category": "Communications",
            "Id": self.app_id,
            "Title": self.title,
            "Status": self.status,
            "IconName": icon,
            "AttentionIconName": "",
            "IconThemePath": self.icon_theme_path,
            "ItemIsMenu": False,
            "Menu": dbus.ObjectPath("/MenuBar"),
            "ToolTip": dbus.Struct(("", empty_pix, self.title, self.tooltip), signature="sa(iiay)ss"),
        }, signature="sv")
