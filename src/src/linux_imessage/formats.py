"""bMessage (MAP) i vCard (PBAP) – budowanie i parsowanie."""
import quopri
import re


def norm_addr(addr):
    """Klucz rozmowy: numer bez spacji/myślników albo e-mail małymi literami."""
    a = str(addr or "").strip()
    if "@" in a:
        return a.lower()
    plus = a.startswith("+")
    digits = re.sub(r"\D", "", a)
    if not digits:
        return a
    return ("+" if plus else "") + digits


def match_key(addr):
    """Klucz do dopasowania kontaktu: ostatnie 9 cyfr (PL bez/z +48)."""
    a = norm_addr(addr)
    if "@" in a:
        return a
    d = re.sub(r"\D", "", a)
    return d[-9:] if len(d) >= 9 else d


def build_bmessage(number, text):
    text = text.replace("\r\n", "\n").replace("\n", "\r\n")
    body = f"BEGIN:MSG\r\n{text}\r\nEND:MSG\r\n"
    return ("BEGIN:BMSG\r\nVERSION:1.0\r\nSTATUS:UNREAD\r\nTYPE:SMS_GSM\r\n"
            "FOLDER:TELECOM/MSG/OUTBOX\r\n"
            "BEGIN:BENV\r\nBEGIN:VCARD\r\nVERSION:2.1\r\n"
            f"N:{number}\r\nTEL:{number}\r\nEND:VCARD\r\n"
            "BEGIN:BBODY\r\nCHARSET:UTF-8\r\n"
            f"LENGTH:{len(body.encode('utf-8'))}\r\n{body}"
            "END:BBODY\r\nEND:BENV\r\nEND:BMSG\r\n")


def parse_bmessage_body(raw):
    parts = re.findall(r"BEGIN:MSG\r?\n(.*?)\r?\nEND:MSG", raw, re.S)
    if not parts:
        return None
    return "\n".join(p.replace("\r\n", "\n") for p in parts).strip()


def parse_bmessage(raw):
    """Treść + nadawca (vCard „originator” przed BEGIN:BENV)."""
    head = raw.split("BEGIN:BENV", 1)[0]
    cards = parse_vcard_fields(head)
    addr = name = ""
    if cards:
        name, addrs = cards[0]
        addr = addrs[0] if addrs else ""
    return {"body": parse_bmessage_body(raw), "addr": addr, "name": name}


def _unfold(raw):
    return re.sub(r"\r?\n[ \t]", "", raw)


def _decode(params, value):
    p = params.upper()
    if "QUOTED-PRINTABLE" in p:
        value = quopri.decodestring(value.encode()).decode("utf-8", "replace")
    return value


def parse_vcards(raw):
    """Zwraca listę (nazwa, [numery/e-maile]) – tylko wpisy z nazwą i adresem."""
    return [(n, a) for n, a in parse_vcard_fields(raw) if n and a]


def parse_vcard_fields(raw):
    out = []
    for card in re.findall(r"BEGIN:VCARD(.*?)END:VCARD", _unfold(raw), re.S | re.I):
        name, n_field, addrs = "", "", []
        for line in card.splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            base = key.split(";")[0].upper()
            value = _decode(key, value.strip())
            if base == "FN":
                name = value
            elif base == "N":
                bits = [b for b in value.split(";") if b]
                n_field = " ".join(reversed(bits[:2])) if bits else ""
            elif base in ("TEL", "EMAIL") and value:
                addrs.append(value)
        out.append((name or n_field, addrs))
    return out
