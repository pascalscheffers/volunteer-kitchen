# Volunteer Kitchen

Planning and a reusable recipe archive for the volunteer kitchen. This is a
knowledge repo, not a program — everything is human-readable Markdown, read
straight off GitHub. There's no build step, nothing to install, no dependencies.

## Layout

```
.
├── recipes/        # reusable, year-agnostic recipe cards — one .md per dish
│   ├── README.md   # the recipe index + how to add one
│   ├── TEMPLATE.md # copy this to start a new recipe
│   └── images/     # committed photos, referenced by relative path
└── <year>/         # event-specific planning + the meal plan for that year
    └── 2026/       # e.g. this year's event
```

- **`recipes/`** — the archive. Each recipe is a standalone card, written to
  be cooked in any year. A year's meal plan links to a recipe with a relative
  link, e.g. `../recipes/focaccia.md`. Recipes don't know about events; events
  point at recipes.
- **`<year>/`** — one directory per year, holding that year's planning and meal
  plan. It's free to grow whatever sub-structure it needs (`menu/`, per-day
  files, quantities, shopping lists) — no fixed schema is imposed. See
  [`2026/`](2026/) for the convention.
- **`recipes/images/`** — photos live here as committed files.

## Conventions

- **Markdown for everything.** Notes, plans, lists, recipes — all `.md`.
- **Small, scannable files over big ones.** A long document is better split
  into linked pieces than left as one wall of text.
- **Relative links between files** so they resolve both locally and on GitHub
  (`../recipes/foo.md`, not absolute paths or URLs).
- **Images are committed as files** and kept web-sized.

## License

Dual-licensed by content type (see [`LICENSE`](LICENSE) for the details):

- **Text** (recipes, planning, docs, images) — **CC0 1.0**, public domain, no
  attribution required.
- **Code** (anything under [`scripts/`](scripts/)) — **MIT**.

## How GitHub renders this

- GitHub-flavoured Markdown **renders images inline**: `![alt text](path)`
  shows up in the README, in the file view, and in the repo browser.
- **The images can be files in this repo** — commit them under
  `recipes/images/` and reference them by *relative path*
  (e.g. `recipes/images/focaccia.jpg`). No external image host is needed.
- Keep images web-sized (a sensible JPEG/PNG, not a 24-megapixel original):
  git keeps every version of every file forever, so large binaries bloat the
  repo permanently. [Git LFS](https://git-lfs.com) exists if a lot of large
  media ever lands here, but for a recipe archive plain committed files are
  simpler and entirely sufficient.
