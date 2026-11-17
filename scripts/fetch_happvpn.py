#!/usr/bin/env python3
"""
Fetch the latest "Incy | v2box | v2raytun" subscription URL from
the public Telegram channel https://t.me/s/happvpn (web preview,
no auth required) and write it to subs/happvpn_incy.txt (+ .b64).

Designed to run on GitHub Actions every ~3 hours.
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

# URLs we never want to pick up as the "subscription" link
BAD_PREFIXES = (
    "https://t.me/",
    "https://tghost.io/",
    "https://t.meproxy.",
    "https://telegram.me/",
)


def fetch_html() -> str:
    req = urllib.request.Request(
        URL,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120 Safari/537.36"
            ),
            "Accept-Language": "ru,en;q=0.9",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "ignore")


def extract_links(html: str) -> list[str]:
    """Return all subscription-looking URLs that appear in the post
    containing the MARKER, in order."""
    # t.me/s/ splits each post into a separate widget wrapper
    posts = re.split(r'tgme_widget_message_wrap', html)
    found = []
    for p in posts:
        if MARKER not in p:
            continue
        # text/code block of the message
        m = re.search(r'tgme_widget_message_text[^>]*>(.*?)</div>', p, re.S)
        body = m.group(1) if m else p
        # everything *after* the marker
        after = body.split(MARKER, 1)[1] if MARKER in body else ""
        # strip HTML tags but keep URL text
        text = re.sub(r"<[^>]+>", " ", after)
        # unescape a few common entities
        text = (text.replace("&amp;", "&")
                    .replace("&quot;", '"')
                    .replace("&#39;", "'")
                    .replace("&lt;", "<")
                    .replace("&gt;", ">"))
        urls = re.findall(r'https?://[^\s<>"\'`]+', text)
        urls = [u.rstrip(",.;)") for u in urls
                if not u.startswith(BAD_PREFIXES)]
        found.extend(urls)
    return found


def main() -> int:
    html = fetch_html()
    links = extract_links(html)
    if not links:
        print("Incy block not found in the latest posts", file=sys.stderr)
        return 1

    # posts are newest-first on t.me/s/, so the first hit is the freshest
    sub_url = links[0]

    txt_path = OUT_DIR / "happvpn_incy.txt"
    b64_path = OUT_DIR / "happvpn_incy.b64"

    txt_path.write_text(sub_url + "\n", encoding="utf-8")
    b64_path.write_text(
        base64.b64encode((sub_url + "\n").encode()).decode() + "\n",
        encoding="utf-8",
    )
    print(f"saved: {sub_url}")
    print(f"  -> {txt_path}")
    print(f"  -> {b64_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
