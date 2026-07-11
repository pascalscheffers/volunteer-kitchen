# Volunteer Kitchen — working notes

Planning and a reusable recipe archive for the volunteer kitchen (read on
GitHub; plain Markdown, no build). Structure is in the [README](README.md).

**This repo is standalone.** It's public and self-contained — never reference
external workspaces, private planning tools, or their files by name. Content
brought in from elsewhere must be rewritten to stand on its own here.

## Sourcing recipes — critical

**Never write a recipe from memory alone.** A model's recollection of a recipe
is a plausible guess, not a tested formula — ratios and techniques drift, and a
wrong ratio cooked for 80 people is a real failure. Every recipe must be
validated against trusted external sources before it enters the archive, the way
we did for [hummus](recipes/hummus.md) (Solomonov/Zahav, Ottolenghi, Serious
Eats, ATK).

- **Cross-check against 2+ independent trusted sources** wherever possible —
  agreement between separate cooks is the signal. Prefer recognised cooks, test
  kitchens, and established food sites over content farms; see
  [`recipes/trusted-sources.md`](recipes/trusted-sources.md). The full workflow
  and AI failure modes are in
  [`recipes/writing-guide.md`](recipes/writing-guide.md).
- **Note what changed** versus the from-memory draft, so the reasoning stays
  visible (see the hummus history).
- **List the sources.** Every recipe ends with a **References** section linking
  the trusted sources it was cross-checked against, so a reader can re-verify.
  Link each source you actually read; if a site blocks automated access, name it
  anyway rather than linking a guessed URL.
- **Some sites block crawlers.** Use [`scripts/fetch-page.sh`](scripts/), which
  fetches like a real browser (platform-correct User-Agent, accepts cookies,
  follows redirects). If a JavaScript bot-wall still defeats it, open the page in
  a real browser and save the HTML — do **not** fall back to memory.
- **Hard rule: don't crawl.** The circumvention scripts are only ever used
  **in connection with a real human session** — a person present, looking up a
  page or two at human pace. Never in a loop, never bulk, never scheduled,
  automated, or background. One page, on demand, as a person would. If there's
  no human in the loop, don't fetch.

## Writing recipes

House style for everything under `recipes/`. Full version, with examples and
reasoning: [`recipes/writing-guide.md`](recipes/writing-guide.md). The short of
it:

- **Reader:** smart, probably writes code — so a little nerdy is fine — but
  **assume zero cooking knowledge.** Spell out craft that isn't obvious (food
  heaped in a pan steams instead of browning; salt in stages and taste; let
  dough actually proof). Never imply they should already know. No "obviously",
  "simply", "just". Nobody feels dumb here.
- **Lean.** Cut anything clear from context or that doesn't change the result —
  the `i++ // add one to i` of recipes. A blank cell in the ingredient table
  needs no paragraph explaining it.
- **Explain the why, briefly,** when it changes technique or outcome — a clause,
  not a lecture (baking soda raises the pH → skins soften → creamier). Skip the
  why when it doesn't matter.
- **One linear thread.** Method steps run in order with minimal context-
  switching, like a kids' recipe: do this, then this. Anything that must start
  early (overnight soak, defrost) is step 1, not sprung halfway through.
- **Proof against the kit we actually have.** A recipe is only useful if it can
  be cooked with the equipment on hand. Check every recipe's required gear
  against the event's equipment list (for this year:
  [`2026/equipment.md`](2026/equipment.md) — what's on site plus what members
  bring). If a method needs kit we don't have, either flag it or give an
  alternative using what we do — don't assume a tool that isn't on the list.
- **Start from** [`recipes/TEMPLATE.md`](recipes/TEMPLATE.md).

## How we build software here

Most of this repo is Markdown, but some work is real software (see
[`tools/`](tools/)). When it is, we build it a particular way — tuned to keep an
AI session effective over long, interrupted work rather than fast-then-slow:

- **Opus orchestrates; fresh-context workers do the work.** Opus (this session)
  plans, decides, and evaluates. The actual coding of a bounded job is handed to
  a **fresh-context worker** (a Sonnet subagent) that starts empty, does one
  closed job, verifies it, commits, and returns a short **summary**. Opus reads
  the summary — not the diff, not the build logs — and dispatches the next job.
  This keeps file-dumps and logs out of the orchestrating context, which is what
  goes wrong when a session starts sharp and slowly bogs down.
- **The altitude call.** Trivial edits, docs, exploration, or anything ambiguous
  or needing tight human steering: do it inline. Anything that can be written as
  a **closed work-order** — a self-contained, specifiable, verifiable job — gets
  dispatched to a worker. If you can't specify it yet, investigate first (inline
  or via a read-only Explore subagent so dumps stay out of context), *then*
  specify, *then* dispatch.
- **Memory lives in the repo, not the chat.** A software effort keeps a plan +
  running progress log as a committed file (e.g. [`tools/PLAN.md`](tools/PLAN.md)):
  what's done, current state, what's next. It's the first thing a resuming
  session reads. Progress travels across machines and cleared contexts because
  it's in git, not in a conversation.
- **Expect interrupted sessions and context clearing between phases.** Every
  phase ends **green + committed + logged** so the next session can resume cold
  from the repo alone. No phase depends on remembering the previous chat.
- **The per-phase loop:** Specify → Implement (reuse first, minimum code) →
  Verify against an explicit gate → Commit (one atomic change) → append a Log
  entry. Don't move to the next phase until the current one's gate is green.
- **Licensing.** Code in this repo is **MIT**; prefer permissive/public-domain
  dependencies and keep tools dependency-light. Record any third-party component
  and its license.

## Standing note

These rules are young. **Keep refining them as we go** — when writing a recipe
teaches us a better way to write recipes, update the guide, this file, and the
template together.
