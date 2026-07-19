# Shared TAP Output Format

All evaluated methods (Vanilla, ChatIoT, Sasha, HomeGenii, AutoIoT, KGIoT) were adapted to emit the **same structured TAP JSON** for fair comparison. This block is included verbatim (or equivalent) in most baseline generation prompts.

## Target JSON shape

```json
{
  "trigger": "<trigger atoms>",
  "condition": "<condition atoms or empty string>",
  "action": "<action atoms>"
}
```

## Atom syntax

| Field | Syntax |
|-------|--------|
| State/comparison trigger | `id.service.property<op><value>` with `<op>` ∈ `{==, >, <, >=, <=}` |
| Event trigger | `event:id.service.property` |
| Condition | `id.service.property<op><value>`, `time<op>HH:MM`, combined with `&&`, `\|\|`, `and`, `or`, `()` |
| Property action | `id.service.property=<value>` |
| Service action | `call_action:id.service.action_name` |
| Multi-atom fields | Comma-separated **strings** in `trigger` and `action` (not JSON arrays) |

## Extended format rules (Sasha / HomeGenii / AutoIoT)

```
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
```

## Knowledge-parity (+DK) injection

When evaluating `+DK` variants, append the plain-text block in `../domain_knowledge/GENERAL_DOMAIN_KNOWLEDGE.txt` to the user message (or system message, depending on method). KGIoT does **not** use this block; it uses structured KG edges instead.
