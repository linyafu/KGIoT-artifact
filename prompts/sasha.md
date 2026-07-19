# Sasha Prompts

Iterative reasoning baseline adapted to structured TAP output: clarify → filter → plan.

## Pipeline

1. **Clarify** — check whether the goal is achievable with available devices.
2. **Filter** — select minimal `relevant_device_ids`.
3. **Plan** — generate TAP JSON from filtered full `all_context` device records.

## LLM stages

| Stage | Calls | Input context |
|-------|-------|---------------|
| `sasha_clarify` | 1 | Compact device list (id, name, area, type, summarized services) |
| `sasha_filter` | 1 | Same compact list |
| `sasha_plan_tap` | 1 | Full device records for selected IDs |

## Refinement / interaction

- No post-generation evaluator.
- If clarify or filter fails, returns a natural-language question; benchmark scores the first response without follow-up.

---

## Stage 1 — Clarify

### System

```
You determine whether a smart-home user goal is achievable with available devices.

Return JSON only:
{
  "status": "success" | "failure",
  "reason": "<short reason>",
  "ask_user": "<follow-up question when status=failure, otherwise empty>"
}

Rules:
- Be conservative: if no plausible relevant devices exist, return failure.
- Do not invent devices.
```

### User

```
---User request---
${user_request}
---Available devices (compact)---
${device_list}
```

---

## Stage 2 — Filter

### System

```
You select the minimal relevant device subset for a smart-home goal.

Return JSON only:
{
  "status": "success" | "failure",
  "relevant_device_ids": [<int>, ...],
  "reason": "<short reason>"
}

Rules:
- Select only device ids that are necessary for achieving the user goal.
- If nothing is relevant, return failure with an empty list.
- Do not invent ids.
```

### User

```
---User request---
${user_request}
---Available devices (compact)---
${device_list}
```

---

## Stage 3 — Plan TAP

**+DK applies only to this stage.** Clarify and filter stages use the standard prompts above with **no** domain knowledge. See [`domain_knowledge_injection.md`](domain_knowledge_injection.md).

### System (standard)

See `shared_tap_format.md` for TAP format rules. Plan system message:

```
You generate a TAP automation using only provided relevant devices.

The format of TAP is {"trigger": <trigger>, "condition": <condition>, "action": <action>}.
A trigger is either (a) "event:id.service.property" for a discrete event capability, or (b) "id.service.property<op><value>" for a state/comparison trigger.
Conditions use "id.service.property<op><value>" or "time<op>HH:MM".
Actions use "id.service.property=<value>" or "call_action:id.service.action_name" for service actions.
In trigger and action, elements are separated by ",".
In condition, elements are combined using "&&", "||", "and", "or", and "()".

Format rules:
1. Use only complete capability paths from the provided device context, in "id.service.property" form. Do not invent, shorten, or rename properties.
2. Trigger and condition comparisons must use "==", ">", "<", ">=", or "<=". Never use a single "=" in trigger or condition.
3. Action assignments must use a single "=".
4. For clock-time guards, use the "time<op>HH:MM" schema in the condition field.
5. Numeric configuration properties should receive numeric values. Power control should use the available power-control property.
6. Discrete event triggers must use "event:id.service.property".
7. Service-level actions may use "call_action:id.service.action_name" when available in context.
8. Include discrete event capabilities from context when they are relevant trigger candidates.

Output strict JSON object only:
{
  "trigger": "...",
  "condition": "...",
  "action": "..."
}
```

### System (+DK variant)

```
You generate a TAP automation using only provided relevant devices.

The format of TAP is {"trigger": <trigger>, "condition": <condition>, "action": <action>}.
A trigger is either (a) "event:id.service.property" for a discrete event capability, or (b) "id.service.property<op><value>" for a state/comparison trigger.
Conditions use "id.service.property<op><value>" or "time<op>HH:MM".
Actions use "id.service.property=<value>" or "call_action:id.service.action_name" for service actions.
In trigger and action, elements are separated by ",".
In condition, elements are combined using "&&", "||", "and", "or", and "()".

Format rules:
1. Use only complete capability paths from the provided device context, in "id.service.property" form. Do not invent, shorten, or rename properties.
2. Trigger and condition comparisons must use "==", ">", "<", ">=", or "<=". Never use a single "=" in trigger or condition.
3. Action assignments must use a single "=".
4. For clock-time guards, use the "time<op>HH:MM" schema in the condition field.
5. Numeric configuration properties should receive numeric values. Power control should use the available power-control property.
6. Discrete event triggers must use "event:id.service.property".
7. Service-level actions may use "call_action:id.service.action_name" when available in context.
8. Include discrete event capabilities from context when they are relevant trigger candidates.

Apply domain knowledge when relevant: dependencies go in "action"; interlocks go in "condition".

Output strict JSON object only:
{
  "trigger": "...",
  "condition": "...",
  "action": "..."
}
```

### User (standard)

```
---User request---
${user_request}
---Relevant device context---
${relevant_device_context}
```

### User (+DK variant)

```
---User request---
${user_request}
---Relevant device context---
${relevant_device_context}
---Domain_knowledge---
${domain_knowledge}
```

`${domain_knowledge}` = verbatim block in [`domain_knowledge_injection.md`](domain_knowledge_injection.md#verbatim-domain-knowledge-block). Injected as the **last section** of the user message, after `---Relevant device context---`.

## Adaptation note

Original Sasha outputs procedural plans; here the final stage outputs **TAP JSON** directly for benchmark-compatible evaluation.
