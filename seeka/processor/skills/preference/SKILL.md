---
name: preference_memory_extraction
description: Extract user preference signals from input, focusing on attitudes, likes, dislikes, and implicit behavioral preferences — not events or facts.
---

Your job is to extract **preference signals** — not events, not plans, not facts.

A preference signal is something that reveals the user's **attitude, taste, or value judgment** toward a category of things.

## What to extract

**Explicit preferences** — directly stated:
- "I don't like X" → extract the dislike
- "I prefer X over Y" → extract the preference
- "I always choose X" → extract the pattern

**Implicit preferences** — inferred from behavior or choices:
- User buys cotton/linen repeatedly → prefers natural fabrics
- User avoids crowded places without saying why → likely prefers quiet environments  
- User picks budget options consistently → values cost over brand

## What NOT to extract

- Events: "went to Shanghai", "met a friend" → skip
- Plans: "will travel next week" → skip
- Neutral facts with no attitude: "has been learning guitar for 2 weeks" → skip (unless they expressed how they feel about it)

## Rules

1. **Only extract what the user stated or clearly implied** — do not invent preferences
2. **One preference per topic** — don't split the same preference into multiple entries
3. **For implicit inferences**: only extract when there is clear behavioral evidence; do not guess
4. **Write in third-person**, concise, attitude-forward
   - ✅ "The user dislikes milk tea, finding it too sweet"
   - ✅ "The user prefers natural fabrics (cotton, linen) based on repeated purchase behavior"
   - ❌ "The user went to a store and bought cotton shirts" (event, not preference)

## Output

Return one preference statement per item. Each statement should be self-contained and retrievable by semantic search on topics like "用户对咖啡的态度" or "用户的购物偏好".

## Graph Extraction

Extract a preference-focused knowledge graph. Only extract entities and relationships that reveal user **attitudes, tastes, or value judgments**.

### Entity Types
Focus on these preference-relevant types:
- **person** — the user or people whose preferences are discussed
- **product** — specific items (brands, models)
- **category** — product/service categories (coffee, fabric, cuisine)
- **brand** — company or brand names
- **attribute** — qualities the user cares about (sweetness, quietness, cost)

### Predicates (Relationship Verbs)
Use attitude-revealing verbs:
- prefers, dislikes, avoids, values, prioritizes
- chooses_over (subject prefers over object)
- tolerates, indifferent_to
- associated_with (brand→attribute or category→attribute)

### Rules
- Entity `id` must be a short, lowercase, hyphen-separated slug
- Only extract entities that participate in at least one preference-related triple
- Do NOT create triples for neutral facts (e.g. "bought X" without attitude)
- Implicit preferences: only extract when behavioral evidence is strong
- If user prefers A over B, create: `user --chooses_over--> B` AND `user --prefers--> A`
