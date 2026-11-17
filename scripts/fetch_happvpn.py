#!/usr/bin/env python3
"""
Fetch the latest "Incy | v2box | v2raytun" subscription URL from the
public Telegram channel https://t.me/s/happvpn (web preview, no auth
required), download the subscription content behind that URL, and write
the raw response (a vless:// list) to subs/happvpn_incy.txt and a
base64-wrapped copy to subs/happvpn_incy.b64.

Runs on GitHub Actions every ~3 hours.
"""

import base64
import pathlib
import re
import sys
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


def http_get(url: str, timeout: int = 30) -> tuple[int, bytes]:
    """Returns (status_code, body). 4xx/5xx bodies are still returned
    because some subscription servers return a vless:// 'user not found'
    stub with HTTP 404 — that body is still useful for the client."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": UA, "Accept-Language": "ru,en;q=0.9"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def fetch_html() -> str:
    _, body = http_get(URL)
    return body.decode("utf-8", "ignore")


def find_sub_url(html: str) -> str | None:
    posts = re.split(r'tgme_widget_message_wrap', html)
    for p in posts:
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


def main() -> int:
    html = fetch_html()
    sub_url = find_sub_url(html)
    if not sub_url:
        print("Incy block not found in the latest posts", file=sys.stderr)
        return 1
    print(f"sub url from channel: {sub_url}")

    # Download the actual subscription content behind that URL.
    # Some endpoints return plain vless:// lines, others base64 —
    # we store the raw response and let the client figure it out.
    status, content = http_get(sub_url, timeout=30)
    print(f"sub fetch: HTTP {status}, {len(content)} bytes")

    if not content:
        # Network failure / empty body — keep the previous file.
        print("empty body, keeping previous file", file=sys.stderr)
        return 0

    # If body is HTML (e.g. a Cloudflare challenge page), don't overwrite
    # a previously good vless:// file with garbage.
    looks_like_html = content.lstrip()[:1] in (b"<",) and b"vless://" not in content
    if looks_like_html:
        print("body looks like HTML, keeping previous file", file=sys.stderr)
        return 0

    txt_path = OUT_DIR / "happvpn_incy.txt"
    b64_path = OUT_DIR / "happvpn_incy.b64"

    txt_path.write_bytes(content)
    b64_path.write_text(
        base64.b64encode(content).decode() + "\n",
        encoding="utf-8",
    )

    preview = content[:200].decode("utf-8", "replace").replace("\n", " ")
    print(f"saved {len(content)} bytes")
    print(f"  -> {txt_path}")
    print(f"  -> {b64_path}")
    print(f"preview: {preview}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
