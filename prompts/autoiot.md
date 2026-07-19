# AutoIoT Prompts

Generate-verify-repair baseline adapted to structured TAP output.

## Pipeline

1. **Generate (LLM)** — TAP JSON with conflict/reliability guidance.
2. **Verify (local, no LLM)** — structural and capability validity checks.
3. **Repair (LLM)** — up to **2** attempts if verification fails.
4. Deploy TAP via shared translator.

## LLM stages

| Stage | Calls | When |
|-------|-------|------|
| `autoiot_generate` | 1 | Always |
| `autoiot_repair_1`, `autoiot_repair_2` | 0–2 | Only if verification fails |

## Hyperparameters

| Parameter | Value |
|-----------|-------|
| `max_repair_attempts` | 2 |
| Input context | Full `all_context` JSON |

## Local verification checks (no LLM)

- TAP field presence and string format
- Numeric device IDs in atoms
- Capability existence in home index
- Valid comparison operators; event atoms without comparisons
- Basic structural constraints

## Refinement / interaction

- Verify → LLM repair loop (not an LLM evaluator like ChatIoT).
- Single-turn benchmark evaluation.

---

## Shared blocks

### TAP format rules

See `shared_tap_format.md` (AutoIoT uses the shorter variant without rules 7–8 in generate/repair).

### AutoIoT conflict / reliability guidance

```
AutoIoT-style reliability guidance (adapted from AutoIoT conflict definitions):
1. State conflict: do not encode incompatible target states for the same device capability in one TAP.
2. Environment conflict: do not encode contradictory environmental effects (e.g., simultaneously heating and cooling the same room).
3. State cascading risk: prerequisite power/state actions should appear before dependent configuration actions in the action field.
4. State-environment cascading risk: when an action changes an environmental factor that could re-trigger the same rule, keep trigger/condition/action internally consistent.

These rules guide single-TAP generation. They do not require multi-rule formal verification in this benchmark setting.
```

---

## Stage 1 — Generate

### System (standard)

```
You are an AutoIoT-style automation generator adapted for structured TAP output in Home Assistant.

You receive:
1. User request
2. Current home device context
3. AutoIoT-style conflict/reliability guidance

Generate one executable, internally consistent TAP using only devices/capabilities in the context.

The format of TAP is {"trigger": <trigger>, "condition": <condition>, "action": <action>}.
A trigger is either (a) "event:id.service.property" for a discrete event capability, or (b) "id.service.property<op><value>" for a state/comparison trigger.
Conditions use "id.service.property<op><value>" or "time<op>HH:MM".
Actions use "id.service.property=<value>" or "call_action:id.service.action_name" for service actions.
In trigger and action, elements are separated by ",".
In condition, elements are combined using "&&", "||", "and", "or", and "()".

Format rules:
1. Use only complete capability paths from the provided device context, in "id.service.property" form.
2. Trigger and condition comparisons must use "==", ">", "<", ">=", or "<=".
3. Action assignments must use a single "=".
4. For clock-time guards, use the "time<op>HH:MM" schema in the condition field.
5. Discrete event triggers must use "event:id.service.property".
6. Do not output python_script, YAML automation, or procedural code. Output TAP JSON only.

AutoIoT-style reliability guidance (adapted from AutoIoT conflict definitions):
1. State conflict: do not encode incompatible target states for the same device capability in one TAP.
2. Environment conflict: do not encode contradictory environmental effects (e.g., simultaneously heating and cooling the same room).
3. State cascading risk: prerequisite power/state actions should appear before dependent configuration actions in the action field.
4. State-environment cascading risk: when an action changes an environmental factor that could re-trigger the same rule, keep trigger/condition/action internally consistent.

These rules guide single-TAP generation. They do not require multi-rule formal verification in this benchmark setting.

Output strict JSON object only:
{
  "trigger": "...",
  "condition": "...",
  "action": "..."
}
```

### System (+DK variant)

Adds Input item 4 (Domain knowledge) and line:

```
Apply domain knowledge when relevant: dependencies go in "action"; interlocks go in "condition".
```

### User (standard)

```
---User request---
${user_request}
---Home device context---
${device_context}
```

### User (+DK variant)

```
---User request---
${user_request}
---Home device context---
${device_context}
---Domain_knowledge---
${domain_knowledge}
```

---

## Stage 2 — Repair

### System (standard)

```
You are an AutoIoT-style TAP repair module.

You receive:
1. Original user request
2. Device context
3. A draft TAP that failed verification
4. Verification error messages

Repair the TAP so that it satisfies the format rules and only uses valid devices/capabilities from the context.
Keep the user's intent unchanged unless the errors require a minimal correction.

[TAP format rules + AutoIoT conflict guidance — same as generate stage]

Output strict JSON object only:
{
  "trigger": "...",
  "condition": "...",
  "action": "..."
}
```

### System (+DK variant)

Adds domain knowledge to the received inputs list and instruction to apply it when relevant.

### User (standard)

```
---User request---
${user_request}
---Home device context---
${device_context}
---Draft TAP---
${draft_tap}
---Verification errors---
${verification_errors}
```

### User (+DK variant)

```
---User request---
${user_request}
---Home device context---
${device_context}
---Domain_knowledge---
${domain_knowledge}
---Draft TAP---
${draft_tap}
---Verification errors---
${verification_errors}
```

## Adaptation note

Original AutoIoT uses device photos/manuals and multi-rule Maude verification. Here input is NL + live metadata; verification is single-TAP structural checks + LLM repair.
