# happvpn-subs

Auto-fetched `Incy | v2box | v2raytun` subscription link from the public
Telegram channel <https://t.me/happvpn>. A GitHub Actions cron job runs
every 3 hours, scrapes the public web preview of the channel
(`https://t.me/s/happvpn` — no auth, no API, no Telethon), finds the
post containing the marker `Incy | v2box | v2raytun`, extracts the
first subscription URL after that marker, and commits it to `subs/`.

## Files

```
scripts/fetch_happvpn.py            # the scraper
.github/workflows/fetch-happvpn.yml # cron + commit
subs/happvpn_incy.txt               # plaintext URL (auto-generated)
subs/happvpn_incy.b64               # base64-wrapped URL (auto-generated)
```

## Subscribe in your client

Use whichever your VPN client expects:

```
https://raw.githubusercontent.com/<your-nick>/happvpn-subs/main/subs/happvpn_incy.txt
https://raw.githubusercontent.com/<your-nick>/happvpn-subs/main/subs/happvpn_incy.b64
```

## First-time setup after pushing to GitHub

1. Open the repo on GitHub → **Settings → Actions → General**.
2. Scroll to **Workflow permissions** → choose
   *Read and write permissions* → Save.
3. Go to **Actions** tab → if there is a banner saying workflows are
   disabled, click *I understand my workflows, go ahead and enable them*.
4. Click the `fetch-happvpn` workflow in the left sidebar →
   **Run workflow** manually once, so you don't have to wait 3 hours.
5. After the run finishes, your `subs/happvpn_incy.txt` will contain
   the fresh URL.

## Notes / troubleshooting

- `t.me/s/<channel>` shows only the latest ~20 messages. Posts appear
  roughly every 3 hours, so the relevant post is always present.
- The scraper picks the **first** `https?://` URL that appears *after*
  the `Incy | v2box | v2raytun` marker inside the post body, skipping
  `t.me/` and similar non-subscription URLs.
- If Telegram starts rate-limiting GitHub IPs and serves a challenge
  page instead of HTML, switch to a Telethon-based userbot or to a
  Cloudflare Worker proxy in front of `t.me/s/happvpn`.
- This repo is self-contained; it does **not** depend on
  `indelingDanil/MyAppVPN-subs`.
