# Receipt taxonomy — closed vocabularies

These are the **only** allowed values for the `category` and `type` columns in
enriched receipt CSVs (`2026/finance/csv/*.csv`). Keeping them closed is what
lets the reports group cleanly — "kg of protein" only works if every protein
item says exactly `protein`... er, `type = protein`. Add a value here first,
deliberately, before using it; don't invent one per receipt.

## `category` — what the line broadly is

| value | meaning | examples |
|---|---|---|
| `food` | anything eaten as food | flour, rice, cheese, olives, chocolate |
| `beverage` | anything drunk | tea, coffee, juice, soda |
| `non-food` | bought but not consumed | bags, foil, cleaning, cutlery |

## `type` — nutrition / role of a food item

Assign the item's **dominant** role. When genuinely split, pick the primary and
set `confidence = low` so a human can review.

| value | meaning | examples |
|---|---|---|
| `carbohydrate` | starches, grains, flour, sugar-as-staple | flour, rice, pasta, bread, cornmeal |
| `protein` | meat, fish, eggs, plant protein | chicken, tuna, tofu |
| `dairy` | milk-derived | milk, cheese, butter, yoghurt, cream |
| `fat-oil` | fats and oils | olive oil, margarine, mayonnaise |
| `vegetable` | vegetables (fresh/tinned/frozen) | onions, tomatoes, jalapeños |
| `fruit` | fruit incl. dried | apples, raisins, jam-as-fruit |
| `legume` | beans, lentils, chickpeas | kidney beans, black-eye beans, chickpeas |
| `condiment` | sauces, dressings, spreads | mustard, dressing, salsa, honey |
| `spice` | spices, herbs, seasoning blends | taco spice, black pepper, salt |
| `sweet` | confectionery, chocolate, dessert items | chocolate, marmalade-as-sweet |
| `beverage` | drink items (mirror of `category = beverage`) | tea, coffee |
| `other` | food that fits nothing above | mixed/prepared items, croutons |

Notes:
- `beverage` appears in both columns on purpose: `category` says it's a drink,
  `type` keeps the nutrition table complete so a drink still lands somewhere.
- Borderline calls (is honey `condiment` or `sweet`? tinned olives `fat-oil` or
  `vegetable`?) are fine — pick one, be consistent, flag `low` when unsure. The
  point is stable buckets, not nutritional precision.
