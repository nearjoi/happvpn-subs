#!/usr/bin/env python3
"""
Fetch the latest "Incy | v2box | v2raytun" subscription URL from the
public Telegram channel https://t.me/s/happvpn (web preview, no auth),
download the Xray JSON config behind that URL, convert every VLESS
outbound into a vless:// URL, and write the resulting list (one URL per
line) to subs/happvpn_incy.txt and a base64-wrapped copy to
subs/happvpn_incy.b64.

Runs on GitHub Actions every ~3 hours.
"""

import base64
import json
import pathlib
import re
import sys
import urllib.parse
import urllib.request

CHANNEL = "happvpn"
URL = f"https://t.me/s/{CHANNEL}"
MARKER = "Incy | v2box | v2raytun"
OUT_DIR = pathlib.Path("subs")
OUT_DIR.mkdir(parents=True, exist_ok=True)

BAD_PREFIXES = (
    "https://t.me/",
    "https://tghost.io/",
    "https://t.meproxy.",
    "https://telegram.me/",
)

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120 Safari/537.36"
)


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

def http_get(url: str, timeout: int = 30) -> tuple[int, bytes]:
    """Returns (status_code, body). 4xx/5xx bodies are still returned."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": UA, "Accept-Language": "ru,en;q=0.9"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        print(f"http_get error: {e}", file=sys.stderr)
        return 0, b""


# ---------------------------------------------------------------------------
# Telegram post parsing
# ---------------------------------------------------------------------------

def fetch_html() -> str:
    _, body = http_get(URL)
    return body.decode("utf-8", "ignore")


def find_sub_url(html: str) -> str | None:
    """t.me/s/<channel> lists posts oldest-first in DOM order, so iterate
    in reverse to find the newest post that contains the marker."""
    posts = re.split(r'tgme_widget_message_wrap', html)
    for p in reversed(posts):
        if MARKER not in p:
            continue
        m = re.search(r'tgme_widget_message_text[^>]*>(.*?)</div>', p, re.S)
        body = m.group(1) if m else p
        after = body.split(MARKER, 1)[1] if MARKER in body else ""
        text = re.sub(r"<[^>]+>", " ", after)
        text = (text.replace("&amp;", "&")
                    .replace("&quot;", '"')
                    .replace("&#39;", "'")
                    .replace("&lt;", "<")
                    .replace("&gt;", ">"))
        urls = re.findall(r'https?://[^\s<>"\'`]+', text)
        urls = [u.rstrip(",.;)") for u in urls
                if not u.startswith(BAD_PREFIXES)]
        if urls:
            return urls[0]
    return None


# ---------------------------------------------------------------------------
# Xray JSON -> vless:// URLs
# ---------------------------------------------------------------------------

def _q(value) -> str:
    """URL-encode a single query-string value."""
    return urllib.parse.quote(str(value), safe="")


def _frag(value) -> str:
    """URL-encode a fragment (allows a few more chars than query)."""
    return urllib.parse.quote(str(value), safe=":@/?#[]!$&'()*+,;=")


def build_vless_url(profile: dict, outbound: dict, idx: int) -> str | None:
    """Convert one vless outbound to a vless:// URL, or None if not vless."""
    if outbound.get("protocol") != "vless":
        return None

    vnext = outbound.get("settings", {}).get("vnext", [])
    if not vnext:
        return None
    v = vnext[0]
    addr = v.get("address")
    port = v.get("port")
    users = v.get("users", [])
    if not users or not addr or not port:
        return None
    u = users[0]
    uuid = u.get("id")
    if not uuid:
        return None

    ss = outbound.get("streamSettings", {}) or {}
    network = ss.get("network", "tcp")
    security = ss.get("security", "none")

    q: list[tuple[str, str]] = []
    q.append(("encryption", u.get("encryption") or "none"))
    if u.get("flow"):
        q.append(("flow", u["flow"]))
    q.append(("security", security))
    q.append(("type", network))

    if security == "tls":
        tls = ss.get("tlsSettings", {}) or {}
        if tls.get("serverName"):
            q.append(("sni", tls["serverName"]))
        if tls.get("fingerprint"):
            q.append(("fp", tls["fingerprint"]))
        if tls.get("alpn"):
            q.append(("alpn", ",".join(tls["alpn"])))
        if tls.get("allowInsecure"):
            q.append(("allowInsecure", "1"))
    elif security == "reality":
        rs = ss.get("realitySettings", {}) or {}
        if rs.get("serverName"):
            q.append(("sni", rs["serverName"]))
        if rs.get("fingerprint"):
            q.append(("fp", rs["fingerprint"]))
        if rs.get("publicKey"):
            q.append(("pbk", rs["publicKey"]))
        if rs.get("shortId"):
            q.append(("sid", rs["shortId"]))
        if rs.get("spiderX"):
            q.append(("spx", rs["spiderX"]))

    # transport-specific settings
    if network == "xhttp":
        xs = ss.get("xhttpSettings", {}) or {}
        if xs.get("path"):
            q.append(("path", xs["path"]))
        if xs.get("host"):
            q.append(("host", xs["host"]))
        if xs.get("mode") and xs["mode"] != "auto":
            q.append(("mode", xs["mode"]))
    elif network == "ws":
        ws = ss.get("wsSettings", {}) or {}
        if ws.get("path"):
            q.append(("path", ws["path"]))
        if ws.get("headers", {}).get("Host"):
            q.append(("host", ws["headers"]["Host"]))
    elif network == "grpc":
        gs = ss.get("grpcSettings", {}) or {}
        if gs.get("serviceName"):
            q.append(("serviceName", gs["serviceName"]))
        if gs.get("mode") and gs["mode"] != "gun":
            q.append(("mode", gs["mode"]))
    elif network in ("raw", "tcp"):
        # raw/tcp have no extra query params in vless URL format
        pass

    query_str = "&".join(f"{k}={_q(v)}" for k, v in q)

    # Friendly name: use profile remarks, disambiguate when profile has many
    name = profile.get("remarks") or outbound.get("tag") or f"server-{idx}"
    # If profile has more than one outbound, append the tag to differentiate
    if len(profile.get("outbounds", [])) > 1 and outbound.get("tag"):
        name = f"{name} [{outbound['tag']}]"

    return f"vless://{uuid}@{addr}:{port}?{query_str}#{_frag(name)}"


def json_to_vless_list(content: bytes) -> list[str]:
    """Parse the Xray JSON config and return a list of vless:// URLs."""
    try:
        data = json.loads(content.decode("utf-8", "replace"))
    except json.JSONDecodeError as e:
        print(f"json parse error: {e}", file=sys.stderr)
        return []

    if isinstance(data, dict):
        data = [data]

    urls: list[str] = []
    seen = set()
    idx = 0
    for profile in data:
        if not isinstance(profile, dict):
            continue
        for o in profile.get("outbounds", []):
            idx += 1
            if not isinstance(o, dict):
                continue
            url = build_vless_url(profile, o, idx)
            if url and url not in seen:
                seen.add(url)
                urls.append(url)
    return urls


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    html = fetch_html()
    sub_url = find_sub_url(html)
    if not sub_url:
        print("Incy block not found in the latest posts", file=sys.stderr)
        return 1
    print(f"sub url from channel (newest post): {sub_url}")

    status, content = http_get(sub_url, timeout=30)
    print(f"sub fetch: HTTP {status}, {len(content)} bytes")
    if not content:
        print("empty body, keeping previous file", file=sys.stderr)
        return 0

    # Detect the "Пользователь не найден" stub or HTML challenge page
    # and refuse to overwrite a previously good file with garbage.
    head = content.lstrip()[:200].lower()
    if head.startswith(b"<") and b"vless://" not in content and b"[" not in content[:5]:
        print("body looks like HTML, keeping previous file", file=sys.stderr)
        return 0

    # Parse the Xray JSON into vless:// URLs
    if content.lstrip()[:1] == b"[":
        urls = json_to_vless_list(content)
    elif b"vless://" in content:
        # Already a vless list (plain text), use as-is
        urls = [ln.strip() for ln in content.decode("utf-8", "replace").splitlines() if ln.strip().startswith("vless://")]
    else:
        # Maybe base64-encoded vless list
        try:
            decoded = base64.b64decode(content).decode("utf-8", "replace")
            urls = [ln.strip() for ln in decoded.splitlines() if ln.strip().startswith("vless://")]
        except Exception:
            urls = []

    if not urls:
        print("no vless:// URLs produced from sub content", file=sys.stderr)
        print(f"preview: {content[:200]!r}", file=sys.stderr)
        return 0

    plain = "\n".join(urls) + "\n"
    b64 = base64.b64encode(plain.encode()).decode() + "\n"

    txt_path = OUT_DIR / "happvpn_incy.txt"
    b64_path = OUT_DIR / "happvpn_incy.b64"
    txt_path.write_text(plain, encoding="utf-8")
    b64_path.write_text(b64, encoding="utf-8")

    print(f"saved {len(urls)} vless configs")
    print(f"  -> {txt_path}")
    print(f"  -> {b64_path}")
    print(f"first url: {urls[0]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
