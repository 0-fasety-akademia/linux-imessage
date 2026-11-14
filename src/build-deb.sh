#!/bin/sh
# Buduje dist/linux-imessage_<wersja>_all.deb
set -e
cd "$(dirname "$0")"
VER=$(sed -n 's/^VERSION = "\(.*\)"/\1/p' src/linux_imessage/app.py)
PKG=build/linux-imessage_${VER}_all
rm -rf build && mkdir -p "$PKG/DEBIAN" "$PKG/usr/bin" "$PKG/usr/lib/linux-imessage" \
  "$PKG/usr/share/applications" "$PKG/usr/share/doc/linux-imessage" dist
cp -r src/linux_imessage src/diagnose.py "$PKG/usr/lib/linux-imessage/"
find "$PKG" -name __pycache__ -prune -exec rm -rf {} +
cp -r data/icons "$PKG/usr/share/"
cp data/pl.jaro.LinuxIMessage.desktop "$PKG/usr/share/applications/"
# icon follows light/dark also while the app is closed (session autostart helper)
install -D -m 0755 data/icon-watch.sh "$PKG/usr/lib/linux-imessage/icon-watch.sh"
install -D -m 0644 data/autostart/pl.jaro.LinuxIMessage-icon.desktop "$PKG/etc/xdg/autostart/pl.jaro.LinuxIMessage-icon.desktop"
cat > "$PKG/usr/bin/linux-imessage" <<'SH'
#!/bin/sh
exec /usr/bin/python3 -I -c 'import sys; sys.path.insert(0, "/usr/lib/linux-imessage"); from linux_imessage.__main__ import main; main()' "$@"
SH
printf '#!/bin/sh\nexec /usr/bin/python3 -I /usr/lib/linux-imessage/diagnose.py "$@"\n' > "$PKG/usr/bin/linux-imessage-diagnose"
chmod 755 "$PKG/usr/bin/"*
cp LICENSE "$PKG/usr/share/doc/linux-imessage/copyright"
cp README.md "$PKG/usr/share/doc/linux-imessage/README.md"
SIZE=$(du -sk "$PKG/usr" | cut -f1)
cat > "$PKG/DEBIAN/control" <<CTL
Package: linux-imessage
Version: $VER
Section: net
Priority: optional
Architecture: all
Installed-Size: $SIZE
Depends: python3 (>= 3.10), python3-gi, python3-dbus, gir1.2-gtk-4.0 (>= 4.12), gir1.2-adw-1 (>= 1.5), bluez, bluez-obexd
Recommends: gnome-shell-extension-appindicator
Maintainer: Jaro <jaro@localhost>
Description: iMessage i SMS z iPhone'a na Ubuntu przez Bluetooth
 Linux iMessage łączy się z Twoim iPhone'em wyłącznie przez Bluetooth
 (profile MAP i PBAP). Bez Maca, bez serwerów, bez telemetrii.
 Połączenia sieciowe są zablokowane w procesie aplikacji.
CTL
dpkg-deb --root-owner-group -Zxz --build "$PKG" dist/ >/dev/null
echo "dist/linux-imessage_${VER}_all.deb"
