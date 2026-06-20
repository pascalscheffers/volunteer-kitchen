# Volunteer Kitchen — working notes

Planning and a reusable recipe archive for the volunteer kitchen (read on
GitHub; plain Markdown, no build). Structure is in the [README](README.md).

## Sourcing recipes — critical

**Never write a recipe from memory alone.** A model's recollection of a recipe
is a plausible guess, not a tested formula — ratios and techniques drift, and a
wrong ratio cooked for 80 people is a real failure. Every recipe must be
validated against trusted external sources before it enters the archive, the way
we did for [hummus](recipes/hummus.md) (Solomonov/Zahav, Ottolenghi, Serious
Eats, ATK).

- **Cross-check against 2+ independent trusted sources** wherever possible —
  agreement between separate cooks is the signal. Prefer recognised cooks, test
  kitchens, and established food sites over content farms.
- **Note what changed** versus the from-memory draft, so the reasoning stays
  visible (see the hummus history).
- **Some sites block crawlers.** Use [`scripts/fetch-page.sh`](scripts/), which
  fetches like a real browser (platform-correct User-Agent, accepts cookies,
  follows redirects). If a JavaScript bot-wall still defeats it, open the page in
  a real browser and save the HTML — do **not** fall back to memory.

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
- **Start from** [`recipes/TEMPLATE.md`](recipes/TEMPLATE.md).

## Standing note

These rules are young. **Keep refining them as we go** — when writing a recipe
teaches us a better way to write recipes, update the guide, this file, and the
template together.
