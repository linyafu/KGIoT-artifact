# Knowledge-Parity (+DK) Prompt Injection

The `+DK` ablation gives **baselines** the same *template-level* dependency/interlock rules that inform KGIoT's general KG construction— as **plain text**, not as a graph and not as per-request oracle TAP answers.

**KGIoT does not use this block.** It derives constraints from structured KG edges instead.

Canonical source file (also in this repo):

`../domain_knowledge/GENERAL_DOMAIN_KNOWLEDGE.txt`

At runtime, every `${domain_knowledge}` placeholder in prompt templates is substituted with the **verbatim block below** (character-for-character identical to that file).

---

## Verbatim domain knowledge block

This is the exact text injected as `${domain_knowledge}`:

```
Use these general domain rules in addition to the user request and device context.
They are plain-text rules converted from the general KG construction templates used by KGIoT. They are not a KG, not a graph, and not ground-truth answers.
Apply them only when the relevant service/property is available in the provided device context.

Operational dependency rule:
- If a service has a writable power-control property identified from platform metadata, then other writable numeric or enum-like properties in the same service depend on that power-control property.
- Rationale: configuration/control properties are ineffective when the corresponding device or service is off.
- In TAP generation, such dependencies are prerequisite actions and should appear in the action field before the dependent action.

Environmental interlock rule:
- For climate-control or heater-control actions, if the same room/area as the controlled device has a relevant contact or magnet sensor, require that sensor to indicate the corresponding door/window is closed.
- In TAP generation, such interlocks are safety/environment guards and should appear in the condition field.

Value semantics rules:
- For magnet/contact sensors, contact_state=false means open and contact_state=true means closed.
- For curtain position properties, position 0 means closed and position 100 means open.

Use only device ids, services, and properties that appear in the provided device context. Do not invent devices or properties.
```

---

## Where +DK is injected (by method)

| Method | Stage | System message changes | User message: `${domain_knowledge}` location |
|--------|-------|------------------------|---------------------------------------------|
| **Vanilla** | `vanilla_zero_shot_tap` | Adds rule: apply domain knowledge; mentions domain knowledge in task description | **Last section** after `---HA raw device context---` → `---Domain_knowledge---` |
| **ChatIoT** | `preprocess` | Input item 3 + workflow line for dependency/interlock properties | After `---Context---` → `---Domain_knowledge---` |
| **ChatIoT** | `generate` | Input item 4 + workflow/format rules for dependencies & interlocks | After `---Context---` → `---Domain_knowledge---` |
| **ChatIoT** | `evaluate` | Input item 4 + workflow step applying DK on correction | After `---Context---` → `---Domain_knowledge---` |
| **Sasha** | `clarify`, `filter` | **No +DK** (unchanged from standard) | **No +DK** |
| **Sasha** | `plan_tap` | Adds apply-domain-knowledge instruction before JSON output | After `---Relevant device context---` → `---Domain_knowledge---` |
| **HomeGenii** | `goal_entity` | **No +DK** | **No +DK** |
| **HomeGenii** | `generate_tap` | Input item 4 + apply-domain-knowledge in workflow | After `---Home device context---` → `---Domain_knowledge---` |
| **AutoIoT** | `generate` | Input item 4 + apply-domain-knowledge line in body | After `---Home device context---` → `---Domain_knowledge---` |
| **AutoIoT** | `repair` | Input item 3 (domain knowledge) + apply when repairing | After `---Home device context---`, **before** `---Draft TAP---` |
| **KGIoT** | all stages | **Not used** | **Not used** |

---

## Illustrative expanded user message (ChatIoT generator)

Template variables `${user_request}`, `${property_list}`, `${device_list}` are filled at runtime. For +DK runs, the **tail** of the user message looks like this (ellipsis omits dynamic context):

```
---User_request---
When the bedroom temperature exceeds 25°C, turn on the bedroom air conditioner.
---Property_list---
["3.temperature_sensor.temperature", "5.air_conditioner.on", ...]
---Context---
[{ "id": 3, "name": "...", "services": { ... } }, ...]
---Domain_knowledge---
Use these general domain rules in addition to the user request and device context.
They are plain-text rules converted from the general KG construction templates used by KGIoT. ...
[remainder identical to Verbatim domain knowledge block above]
```

The same `---Domain_knowledge---` tail pattern applies to every row in the table that lists a user-message location.

---

## System vs user split

- **User message:** always carries the **full verbatim** `${domain_knowledge}` block under `---Domain_knowledge---` (when +DK is enabled for that stage).
- **System message:** adds **short instructions** telling the model how to use that block (e.g., dependencies → `action`, interlocks → `condition`). The rules themselves are **not** duplicated inside the system prompt— they appear only in the user message section above.

Each method's `+DK` prompt file sections show **complete system and user templates** for audit.
