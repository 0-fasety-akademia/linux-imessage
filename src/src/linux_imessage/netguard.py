"""Blokada sieci w procesie aplikacji.

Linux iMessage rozmawia z iPhone'em wyłącznie przez Bluetooth (BlueZ/obexd przez
lokalne gniazda D-Bus AF_UNIX). Żeby żaden kod (nasz ani biblioteki Pythona)
nie mógł przypadkiem otworzyć połączenia sieciowego, podmieniamy gniazda IPv4/IPv6
i rozwiązywanie nazw na wersje rzucające wyjątek.
"""
import socket

_BLOCKED_FAMILIES = {socket.AF_INET, socket.AF_INET6}
_installed = False


class NetworkBlocked(PermissionError):
    pass


def _blocked(*_a, **_k):
    raise NetworkBlocked("Linux iMessage: połączenia sieciowe są zablokowane")


class _GuardedSocket(socket.socket):
    def __init__(self, family=-1, type=-1, proto=-1, fileno=None):
        fam = socket.AF_INET if family == -1 else family
        if fileno is None and fam in _BLOCKED_FAMILIES:
            _blocked()
        super().__init__(family, type, proto, fileno)


def install():
    global _installed
    if _installed:
        return
    socket.socket = _GuardedSocket
    socket.SocketType = _GuardedSocket
    socket.create_connection = _blocked
    socket.getaddrinfo = _blocked
    socket.gethostbyname = _blocked
    socket.gethostbyname_ex = _blocked
    _installed = True


def is_installed():
    return _installed
