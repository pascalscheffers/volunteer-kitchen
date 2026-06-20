# scripts/

Small helpers for maintaining the archive. Code in a recipe repo is fine when
it serves the recipes — keep it simple and dependency-light.

## fetch-page.sh

Fetches a web page while looking like a real browser, so recipe sources that
block plain scrapers still hand over the page. Used when validating recipes
against trusted sources — see [`../CLAUDE.md`](../CLAUDE.md): we never write
recipes from memory.

```sh
scripts/fetch-page.sh https://example.com/some-recipe        # → stdout
scripts/fetch-page.sh https://example.com/some-recipe out.html
```

It sends a User-Agent matching the current machine's OS (Safari on macOS,
Firefox on Linux), accepts and replays cookies (clearing most cookie-consent
walls), follows redirects, and decompresses gzip. It will **not** defeat a full
JavaScript bot-wall (Cloudflare "checking your browser"); for those, open the
page in a real browser and save the HTML.

Needs only `curl` and `bash` — both already on macOS and Linux.

## Planned

- **`scaling-calculator.html`** — one self-contained HTML page (no server, no
  build) with calculators for scaling recipes to group sizes, tied to the meal
  planning under `<year>/`. A bit nerdy by design.
