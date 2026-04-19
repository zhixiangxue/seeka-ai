---
name: general_memory_extraction
description: Extract high-quality memories from user input. Apply third-person perspective, resolve time references, and preserve completeness over brevity.
---

When extracting memories from the user's input, follow these rules strictly.

## 1. Perspective
Always write in **third-person**. Refer to the user as "The user" or by their name if mentioned.
- ✅ "The user prefers pour-over coffee in the morning."
- ❌ "I prefer pour-over coffee in the morning."

## 2. Time Resolution
Convert all relative time expressions to absolute dates when possible.
- "yesterday" → derive the actual date from the message timestamp
- "next Friday" → resolve to the specific calendar date
- If the exact date is uncertain, state it explicitly: "around June 2025", "exact date unclear"
- Always distinguish between **event time** and **message time**

## 3. Entity Resolution
- Resolve all pronouns to full names or identities: "she" → "Mary"
- Disambiguate people with the same name if context allows
- Include specific locations when mentioned

## 4. Completeness Over Brevity
- Do NOT omit details that the user is likely to remember
- Include key experiences, emotional responses, decisions, and plans — even minor ones
- Do NOT generalize or skip personally meaningful details
- Each distinct topic, hobby, or event should become a **separate memory fragment**

## 5. Attribution
- Only extract what the **user stated, acknowledged, or committed to**
- If the input contains assistant statements, include them only if the user explicitly agreed, and mark them: "[Assistant suggested...]"
- Never recast the assistant's viewpoint as the user's own preference

## 6. Output
Return each memory as a concise, self-contained statement that is independently understandable without additional context.
