# Benchmark Construction Protocol

This document describes how the Home TAP benchmark was constructed, annotated, and validated. It is intended to support reproducibility and to clarify how benchmark design avoids bias toward any single TAP-generation method.

## Overview

The benchmark contains **60 natural-language TAP requests** across three simulated smart-home environments:

| Home ID | Scale | Requests |
|---------|-------|----------|
| `home_L` | Large | 20 |
| `home_M` | Medium | 20 |
| `home_S` | Small | 20 |

Each home uses the same category distribution:

| Index range | Category | Count per home |
|-------------|----------|----------------|
| 1–5 | Basic TAP | 5 |
| 6–10 | Conditional TAP | 5 |
| 11–15 | Multi-Action TAP | 5 |
| 16–20 | Constraint-Aware TAP | 5 |

## Construction Timeline (Bias-Control Design)

The benchmark was built in a fixed order to prevent requests and labels from being derived from KGIoT's grounding or planning pipeline:

1. **Simulated home setup.** Three Home Assistant environments were configured with real MiOT device models, room layouts, and capability metadata. Device inventories are summarized in `data/environments/home_*_graph_index.json`.
2. **Request drafting with LLM assistance.** Candidate requests were generated with LLM assistance using only the available device types, rooms, and capabilities in each home. The LLM was prompted for diverse, realistic user expressions—not for TAP answers.
3. **Manual curation.** Requests were manually filtered for naturalness, category coverage, executability, and absence of device hallucinations.
4. **Request finalization.** The 60 request texts were frozen before ground-truth TAP construction began.
5. **Ground-truth annotation.** Annotators wrote explicit-intent TAPs, implicit dependency/interlock labels, full executable TAPs, and acceptable variants under the protocol in `ANNOTATION_GUIDELINES.md`.
6. **Validation.** Each request was checked against the target home's device/capability inventory and Home Assistant deployability.

This ordering ensures that benchmark requests are **not optimized toward KGIoT's internal graph representation**.

## LLM Assistance for Request Generation

LLM assistance was used only in step 2 above. Its role was limited to:

- Proposing varied natural-language phrasings (imperative, conditional, colloquial).
- Suggesting category-balanced candidates across rooms and device types.
- Exploring multi-action and time-based formulations.

The LLM was **not** used to:

- Produce final TAP ground truth.
- Decide implicit dependencies or interlocks.
- Select evaluation labels or scoring targets.
- Optimize requests toward any method's prompt format or KG schema.

All final request strings were manually edited and approved before annotation.

## Constraint-Aware Request Design

For `Constraint-Aware TAP` requests (indices 16–20 in each home):

- The **natural-language request states only the user's desired outcome**.
- Operational dependencies (e.g., power-on before brightness/fan-level changes) and environmental interlocks (e.g., closed window before AC) are **intentionally omitted** from the request text.
- These omitted constraints are recorded separately in `implicit_constraints` and included in the full executable `tap`.

This design reflects realistic smart-home usage: users describe outcomes, not device-level execution prerequisites.

## Explicit vs. Implicit Decomposition

Each benchmark entry separates:

- **`explicit_tap` / `explicit_labels`**: atoms directly implied by the user request.
- **`implicit_constraints`**: dependencies (action atoms) and interlocks (condition atoms) required for executable or safe behavior but not stated in the request.
- **`tap`**: the full executable target combining both layers.
- **`acceptable_taps`**: semantically equivalent executable variants.

This decomposition allows evaluation under multiple targets (explicit-intent satisfaction, implicit-constraint completion, executable correctness) without conflating them.

## Knowledge-Parity (+DK) Setting

To test whether performance gains come from structured constraint knowledge rather than better TAP generation, baselines can be evaluated under a **knowledge-parity** setting:

- The plain-text template in `domain_knowledge/GENERAL_DOMAIN_KNOWLEDGE.txt` is injected into baseline prompts.
- These rules are **template-level operational guidance**, not a knowledge graph, not per-request oracle answers, and not the benchmark ground truth.
- KGIoT does not use this injected block; it derives constraints from its own structured grounding and planning mechanism.

Researchers implementing +DK baselines should use the released template verbatim to ensure parity with the paper's ablation.

## Quality Checks

Before release, each entry was verified for:

1. **Executability**: full `tap` references only devices/capabilities present in the target home.
2. **Category correctness**: Basic / Conditional / Multi-Action / Constraint-Aware labels match the request structure.
3. **Implicit label necessity**: Constraint-Aware entries include at least one non-empty dependency or interlock annotation.
4. **Explicit label purity**: `explicit_tap` contains no atoms that require information not present in the request text.
5. **Scoring consistency**: automatic scores from `scripts/score_outputs.py` match manual inspection on representative cases.

## Files in This Release

| Artifact | Path |
|----------|------|
| Natural-language requests + all labels | `data/ground_truth_home_{L,M,S}.json` |
| Simulated-home capability indices | `data/environments/home_*_graph_index.json` |
| Annotation protocol and scoring rules | `docs/ANNOTATION_GUIDELINES.md` |
| Construction protocol (this file) | `docs/CONSTRUCTION_PROTOCOL.md` |
| +DK domain-knowledge template | `domain_knowledge/GENERAL_DOMAIN_KNOWLEDGE.txt` |
| Offline scoring scripts | `scripts/` |
| Request preview table | `examples/preview.csv` |
| Sample submission format | `examples/sample_submission.jsonl` |

## Version

- **Benchmark version**: 1.0
- **Schema version**: `tap-benchmark-v1`
