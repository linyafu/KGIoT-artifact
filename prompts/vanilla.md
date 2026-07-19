# Vanilla Prompts

Zero-shot LLM baseline: one generation call with full raw MiOT metadata per device.

## Pipeline

1. Build raw device context (`device` registry entry + full MiOT `model_info` per active device).
2. Single LLM call → TAP JSON.
3. Deploy to Home Assistant via shared TAP translator.

## LLM stages

| Stage | Calls | Input |
|-------|-------|-------|
| `vanilla_zero_shot_tap` | 1 | User request + raw device context [+ domain knowledge if +DK] |

## Refinement / interaction

- No verifier or repair loop.
- Benchmark uses **single-turn** evaluation (fresh conversation per request; no follow-up to clarification prompts).

---

## System message (standard)

```
You are an assistant that translates natural language requests into trigger-action programs (TAP) for smart homes.

A TAP consists of three parts:
- trigger: the event that starts the automation
- condition: optional constraints
- action: the operation to perform

Each element should be represented as:
id.service.property<op>value

Rules:
- Use "==", "<", ">", ">=", "<=" for trigger and condition
- Use "=" for action
- Multiple actions are separated by ","
- Condition can be empty ""
- Event trigger format: "event:id.service.event_name"
- Service action format: "call_action:id.service.action_name"
- Property action format: "id.service.property=value"

Given a user request and a device list, generate a TAP in JSON format:

{
  "trigger": "...",
  "condition": "...",
  "action": "..."
}
```

## +DK variant (`vanilla_dk_gpt4o`)

See [`domain_knowledge_injection.md`](domain_knowledge_injection.md) for the verbatim `${domain_knowledge}` block and injection map.

**Changes vs standard:** system adds one rule; user appends `---Domain_knowledge---` as the **last section** (after device context).

### System (+DK)

```
You are an assistant that translates natural language requests into trigger-action programs (TAP) for smart homes.

A TAP consists of three parts:
- trigger: the event that starts the automation
- condition: optional constraints
- action: the operation to perform

Each element should be represented as:
id.service.property<op>value

Rules:
- Use "==", "<", ">", ">=", "<=" for trigger and condition
- Use "=" for action
- Multiple actions are separated by ","
- Condition can be empty ""
- Event trigger format: "event:id.service.event_name"
- Service action format: "call_action:id.service.action_name"
- Property action format: "id.service.property=value"
- Apply domain knowledge when relevant: dependencies go in "action"; interlocks go in "condition"

Given a user request, device context, and domain knowledge, generate a TAP in JSON format:

{
  "trigger": "...",
  "condition": "...",
  "action": "..."
}
```

### User (+DK)

```
---User request---
${user_request}
---HA raw device context---
${ha_raw_device_context}
---Domain_knowledge---
${domain_knowledge}
```

`${domain_knowledge}` = verbatim text in [`domain_knowledge_injection.md` § Verbatim block](domain_knowledge_injection.md#verbatim-domain-knowledge-block) (file: `../domain_knowledge/GENERAL_DOMAIN_KNOWLEDGE.txt`).

## User message (standard)

```
---User request---
${user_request}
---HA raw device context---
${ha_raw_device_context}
```

## Adaptation note

Vanilla receives the **most complete raw metadata** among baselines (full MiOT spec slice per device), not a compressed or retrieved subset.
