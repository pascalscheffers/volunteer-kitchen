# Writing effective Bornhack recipes

How we write recipes for the volunteer kitchen so anyone can cook them well —
including people who have never really cooked. Same spirit as the short version
in [`../CLAUDE.md`](../CLAUDE.md), with the reasoning and examples.

## Who you're writing for

Volunteers. Sharp, curious, mostly comfortable with computers and code — so you
can be a little nerdy and they'll keep up. But **don't assume they can cook.**
Plenty of brilliant people have never browned an onion or wondered why bread
needs to rest. Write so a complete beginner succeeds and an experienced cook
isn't bored.

The golden rule: **never make anyone feel stupid for not knowing.** Drop
"obviously", "simply", "just", "everyone knows". State the thing plainly and
move on.

## Drafting with AI — and checking its work

Drafting a recipe with an AI tool is fine, and most contributors will. But an
AI draft is a **starting point, never the final word.** The hard rule is in
[`../CLAUDE.md`](../CLAUDE.md): never let a from-memory draft into the archive
unchecked. Here's why, and how.

### How AI gets recipes wrong

AI recipes are confidently plausible and quietly off. The characteristic
failure modes — scrutinise these first:

- **Timid ratios.** It averages toward a bland median, softening the bold ratios
  good cooks actually use. Our first hummus draft had roughly *half* the tahini
  the benchmark recipes use.
- **Dropped technique.** The step that makes the dish — and that isn't in every
  copy online — goes missing. We left out mellowing the garlic in lemon, a
  near-universal professional move.
- **Generic seasoning.** Spices drift to a safe, often wrong, default. We
  over-cumin'd; traditional hummus uses a pinch or none.
- **Confident round numbers.** "1 tsp", "30 minutes", "serves 4" sound
  authoritative but are frequently just plausible guesses. Distrust round,
  unsourced numbers.
- **Invented specifics.** Brand names, regional claims, and exact temperatures
  stated with total confidence may be fabricated.
- **Reads right, cooks wrong.** A method can flow nicely on the page yet have an
  order a real cook would never follow. Check the logic, not just the prose.

The three things to check hardest, because they fail most and matter most: the
**load-bearing ratio**, the **signature technique**, and the **seasoning level**.

### Validating a draft

1. **Draft** — from AI or memory. Fine as a starting point.
2. **Pick sources** — find the gold-standard references for the dish (see
   [`trusted-sources.md`](trusted-sources.md)) and choose **2+ independent**
   ones.
3. **Read them.** If a site blocks you, use
   [`../scripts/fetch-page.sh`](../scripts/) — human session only, never crawl.
   Never substitute memory for a source.
4. **Compare on the axes that matter** — key ratio(s), technique, seasoning,
   times/temps. Where the trusted sources agree and your draft differs, the
   draft is probably wrong.
5. **Adjust, and record what changed** and why — a short note so the reasoning
   stays visible (see the hummus history).
6. **Cite the sources** in a **References** section at the foot of the recipe —
   link every trusted source you cross-checked, so a reader can re-verify. Link
   what you actually read; if a site blocks automated access (Serious Eats does),
   name it rather than linking a guessed URL. And respect image licences (the
   hummus photo is CC BY and carries its credit).

## Keep it lean

If it's clear from context or doesn't change the result, cut it. A recipe is a
bit like code: you wouldn't write `i++ // add one to i`, so don't re-explain
"dice" every time it appears, or add a paragraph describing a table column whose
blank cells already speak for themselves.

Lean isn't the same as cryptic — keep every word that changes what lands on the
plate, drop the rest.

## Spell out the craft

The flip side of lean: the non-obvious technique that *does* change the outcome
has to be on the page, because a beginner won't know it. Worth stating plainly:

- **Don't crowd the pan or tray when browning.** Food packed in a heap steams in
  its own moisture and turns grey; spread out in a single loose layer it browns.
  Cook in batches if you need to.
- **Salt in stages and taste as you go** — salt added only at the end just sits
  on the surface.
- **Preheat properly** — a pan or oven that isn't hot yet sticks and stews
  instead of searing.
- **Rest meat and bread after cooking** so they don't dry out or turn gummy when
  cut.

When in doubt about whether a beginner would know it, say it.

## Explain the why — briefly

A short reason makes a step stick and lets people adapt when something's off.
Keep it to a clause or a sentence, never a chemistry lecture:

> Add 1 tsp baking soda to the cooking water — it raises the pH so the chickpea
> skins soften, which is what makes the hummus creamy.

Give the why when it changes how they'd do it. Skip it when it doesn't.

## One linear thread

Write the method as a single sequence: do this, then this, then this — like a
children's recipe. People cook with their hands full and their attention
divided, and every "meanwhile, in a separate bowl…" is a chance to lose the
thread.

- Keep the **main method on one track** — order the steps so the cook finishes
  one thing before starting the next.
- Anything that must **start early** (overnight soak, dough proof, defrost) goes
  at the very top — the first step, or a "the day before" line — never sprung at
  step 6.
- If two things genuinely have to overlap, say so simply ("while that simmers,
  …") and keep it rare.

## Structure

Start from [`TEMPLATE.md`](TEMPLATE.md). The shape:

- **Title + one line** — what it is, when you'd serve it.
- **Tags** — cuisine, course, dietary, make-ahead.
- **Yields & scaling** — Bornhack means big, shifting headcounts. Give a base
  batch, say how it scales, and say where it stops (pot size, oven trays, prep
  that doesn't scale).
- **Equipment** — only the non-obvious kit.
- **Ingredients** — a table. Add the local-name column (DA · DE · FR · NL) only
  where the English name would defeat a shopper, and flag genuine traps (Danish
  *natron* is baking soda; *spidskommen* is cumin, not caraway).
- **Method** — the single linear thread above.
- **Garnishes / variations** — including the vegan-base-plus-protein pattern:
  the base dish stays vegan and meat or dairy layers on top, so one pot feeds
  everyone.
- **Make-ahead / cross-day notes** — what freezes, what keeps, what tonight's
  leftovers become tomorrow.
- **References** — links to the trusted sources you cross-checked against, so the
  recipe can be re-verified. One source per line; name (don't link) any that
  block automated access.
- **Photo** — a thumbnail (see the template for the `<img>` trick).

## Bornhack realities to keep in mind

- **Scale is large and moves.** Cook for 50–100, and headcounts drift day to
  day. Recipes that scale cleanly win.
- **Budget is tight.** Flag the expensive ingredient and how to dial it up or
  down.
- **Make-ahead is gold.** Much prep happens in volunteers' kitchens the week
  before — note what travels and what freezes.
- **Shopping is in Danish** (and sometimes German/French/Dutch). The local-name
  column and trap warnings save a wrong-tin disaster.
- **Nothing wasted.** Point each dish's leftovers at the next day's meal.

---

These conventions are still settling. If writing a recipe teaches you a better
way to write recipes, update this guide, [`../CLAUDE.md`](../CLAUDE.md), and
[`TEMPLATE.md`](TEMPLATE.md) together.
