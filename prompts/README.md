# Prompt Templates

This directory contains the **exact prompt templates** used in our paper experiments for each evaluated method. Template variables (`${user_request}`, `${device_list}`, etc.) are substituted at runtime with live benchmark inputs.

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

## Knowledge-parity (+DK) variants

For `+DK` ablations, inject the verbatim block in `../domain_knowledge/GENERAL_DOMAIN_KNOWLEDGE.txt`. Each prompt file documents where the block is appended (system vs user message). **KGIoT does not use this block.**

## What is not duplicated here

- **Runtime device context** (`all_context` JSON per home) — see `examples/metadata_schema_example.json` and `data/environments/`.
- **KGIoT subgraph text** (`${kg_subgraph}`) — generated per request from the recalled subgraph.
- **HomeGenii retrieved rules** — selected per request from a rulebase derived from HomeGenii `Enhanced TAP.txt`.

These are dynamic inputs, not static prompts.
