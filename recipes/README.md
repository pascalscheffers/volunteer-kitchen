# Recipes

Reusable, year-agnostic recipe cards — one `.md` per dish. A year's meal plan
links to these with a relative link (e.g. `../recipes/focaccia.md`); recipes
themselves stay free of any single event's specifics so they can be cooked
again next year.

## Index

| Recipe | Cuisine | Course | Notes |
|---|---|---|---|
| [Hummus](hummus.md) | Levantine | Lunch / spread | Vegan base, GF; make-ahead |
| [Baba ganoush](baba-ganoush.md) | Levantine | Lunch / spread | Vegan, GF; make-ahead |
| [Kanelsnegle](kanelsnegle.md) | Danish / Nordic | 4 o'clock / baking | Quick yeast dough; multiple fillings; make-ahead |

## Adding a recipe

Read the house style first: [`writing-guide.md`](writing-guide.md).

1. Copy [`TEMPLATE.md`](TEMPLATE.md) to `recipes/<slug>.md` (lowercase,
   hyphenated — e.g. `garlic-focaccia.md`).
2. Fill it in. Drop any photo into [`images/`](images/) and reference it by
   relative path inside the card (`![dish](images/<slug>.jpg)`).
3. Add a row to the index table above.
