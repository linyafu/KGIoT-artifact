# Prompt Templates

This directory contains the **exact prompt templates** used in our paper experiments. Template variables (`${user_request}`, `${device_list}`, etc.) are substituted at runtime.

## Files

| File | Method | LLM stages |
|------|--------|------------|
| `vanilla.md` | Vanilla zero-shot | 1 |
| `chatiot.md` | ChatIoT (+ optional compression) | 3 (preprocess, generate, evaluate) |
| `sasha.md` | Sasha | 3 (clarify, filter, plan) |
| `homegenii.md` | HomeGenii | 2 (goal/entity, generate) |
| `autoiot.md` | AutoIoT | 1–3 (generate + up to 2 repairs) |
| `kgiot.md` | KGIoT (proposed) | 2 (parse, plan) |
| `shared_tap_format.md` | Shared TAP syntax rules | — |
| **`domain_knowledge_injection.md`** | **+DK verbatim block & injection map** | — |

## Knowledge-parity (+DK) variants

**Do not skip** [`domain_knowledge_injection.md`](domain_knowledge_injection.md). It contains:

1. The **full verbatim** `${domain_knowledge}` text (same as `../domain_knowledge/GENERAL_DOMAIN_KNOWLEDGE.txt`)
2. A **table** of which stage injects +DK in **system** vs **user** message
3. An **expanded user-message example** showing exactly where `---Domain_knowledge---` appears

Each baseline prompt file lists **complete +DK system and user templates** (not “same as standard, plus one line”). **KGIoT does not use +DK.**

## What is not duplicated here

- **Runtime device context** — see `examples/metadata_schema_example.json` and `data/environments/`.
- **KGIoT subgraph text** (`${kg_subgraph}`) — generated per request.
- **HomeGenii retrieved rules** — selected per request from Enhanced-TAP-derived rulebase.
