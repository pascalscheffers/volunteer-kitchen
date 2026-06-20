#!/usr/bin/env bash
#
# fetch-page.sh — fetch a web page while looking like a real browser.
#
# Why: we NEVER write recipes from memory (see ../CLAUDE.md) — every recipe is
# cross-checked against trusted sources first. Some of those sites block plain
# scrapers and agents. This sends a real browser's User-Agent and headers,
# accepts and replays cookies (clearing most cookie-consent walls), follows
# redirects and handles gzip, so the page comes back the way it would in a
# browser.
#
# Usage:
#   scripts/fetch-page.sh <url>              # prints HTML to stdout
#   scripts/fetch-page.sh <url> out.html     # writes to a file
#
# Limits: it will NOT beat a full JavaScript bot-wall (e.g. Cloudflare
# "checking your browser"). For those, open the page in a real browser and save
# the HTML — do not fall back to writing from memory.
#
# HARD RULE — don't crawl: use this only in connection with a real human
# session (a person present, looking up a page or two at human pace). Never in a
# loop, bulk, scheduled, automated, or background. One page, on demand, as a
# person would. No human in the loop -> don't fetch.

set -euo pipefail

if [ $# -lt 1 ]; then
  echo "usage: $0 <url> [output-file]" >&2
  exit 2
fi

url="$1"
out="${2:-}"

# A User-Agent matching THIS machine's OS, so we blend in with normal traffic.
case "$(uname -s)" in
  Darwin)
    ua='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Safari/605.1.15' ;;
  Linux)
    ua='Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0' ;;
  *)
    ua='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36' ;;
esac

# Per-run cookie jar, discarded on exit.
jar="$(mktemp)"
trap 'rm -f "$jar"' EXIT

# Browser-like request headers.
headers=(
  -H 'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8'
  -H 'Accept-Language: en-US,en;q=0.9,da;q=0.8'
  -H 'Upgrade-Insecure-Requests: 1'
)

origin="$(printf '%s' "$url" | sed -E 's#^(https?://[^/]+).*#\1#')"

curl_common=(--silent --show-error --location --compressed
  --max-time 30 --retry 2 --retry-delay 1
  --user-agent "$ua" "${headers[@]}"
  --cookie "$jar" --cookie-jar "$jar")

# Warm up on the site root first to pick up consent/session cookies, the way a
# person landing on the homepage would. Failures here are non-fatal.
curl "${curl_common[@]}" --output /dev/null "$origin/" 2>/dev/null || true

# The real fetch — cookies now seeded, with a plausible Referer.
if [ -n "$out" ]; then
  curl "${curl_common[@]}" -H "Referer: $origin/" --output "$out" "$url"
  echo "saved: $out" >&2
else
  curl "${curl_common[@]}" -H "Referer: $origin/" "$url"
fi
