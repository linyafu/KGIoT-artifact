# Home TAP Benchmark (Anonymous Artifact)

> Anonymous benchmark artifact for double-blind review.

This repository contains the complete evaluation benchmark for natural-language smart-home **Trigger-Action Program (TAP)** generation used in the accompanying paper. The benchmark has **60 requests** across three simulated homes (`home_L`, `home_M`, `home_S`), with executable ground truth, explicit/implicit constraint annotations, scoring scripts, and construction documentation.

## Contents

```
home-tap-benchmark/
├── data/
│   ├── ground_truth_home_L.json      # 20 requests + labels
│   ├── ground_truth_home_M.json
│   ├── ground_truth_home_S.json
│   └── environments/
│       ├── home_L_graph_index.json   # device/capability inventory
│       ├── home_M_graph_index.json
│       └── home_S_graph_index.json
├── docs/
│   ├── ANNOTATION_GUIDELINES.md      # annotation + scoring rules
│   └── CONSTRUCTION_PROTOCOL.md      # how the benchmark was built
├── domain_knowledge/
│   └── GENERAL_DOMAIN_KNOWLEDGE.txt  # +DK knowledge-parity template
├── scripts/
│   ├── benchmark_utils.py
│   ├── score_outputs.py
│   └── summarize_results.py
└── examples/
    ├── preview.csv                   # 60-request overview
    └── sample_submission.jsonl       # scoring input format
```

## Request Categories (RC1–RC4)

Each home has 20 requests with a fixed distribution:

| Category | Count | Description |
|----------|-------|-------------|
| Basic TAP | 5 | Single trigger + single action |
| Conditional TAP | 5 | Explicit condition + action |
| Multi-Action TAP | 5 | Multiple explicit actions |
| Constraint-Aware TAP | 5 | Requires implicit dependency or interlock |

## Scoring Targets

The evaluator reports separate metrics to disentangle user-intent satisfaction from constraint knowledge:

- **Explicit-intent score**: match atoms stated in the user request (`explicit_tap`).
- **Implicit-constraint completion**: recall over annotated dependencies/interlocks (primarily aggregated over `Constraint-Aware TAP`).
- **Executable correctness**: exact match against the full executable `tap`.
- **Platform validity**: well-formed TAP referencing real home devices/capabilities and deployable on the target platform.
- **Grounding precision/recall** (optional): device- and capability-level precision/recall when a method exposes retrieved context.

See `docs/ANNOTATION_GUIDELINES.md` for full scoring rules.

## Quick Start (No Home Assistant Required)

Score the included sample submission:

```bash
cd scripts

python3 score_outputs.py \
  --raw ../examples/sample_submission.jsonl \
  --ground-truth ../data/ground_truth_home_S.json \
  --output /tmp/sample_scores.jsonl

python3 summarize_results.py \
  --scores /tmp/sample_scores.jsonl \
  --output-dir /tmp/sample_summary
```

This writes `main_metrics.csv`, `category_breakdown.csv`, `per_case_scores.csv`, and `failure_cases.md` under `/tmp/sample_summary/`.

## Scoring Your Own Outputs

Prepare a JSONL file where each line contains at minimum:

```json
{
  "request_id": "HS_BASIC_001",
  "home_id": "home_S",
  "request": "When motion is detected in the bathroom, turn on the bathroom light.",
  "method": "your_method_name",
  "response_text": "Optional natural language.\n{'trigger': '...', 'condition': '', 'action': '...'}"
}
```

The scorer extracts the TAP dict from `response_text`. Then run:

```bash
python3 score_outputs.py \
  --raw your_outputs.jsonl \
  --ground-truth ../data/ground_truth_home_S.json \
  --output your_scores.jsonl

python3 summarize_results.py \
  --scores your_scores.jsonl \
  --output-dir your_summary/
```

Repeat for `ground_truth_home_L.json` and `ground_truth_home_M.json` to evaluate all 60 requests.

## Ground-Truth Schema

Each entry in `data/ground_truth_home_*.json` contains:

| Field | Meaning |
|-------|---------|
| `request` | Natural-language user instruction |
| `category` | RC1–RC4 category label |
| `explicit_tap` | TAP implied directly by the request |
| `implicit_constraints` | Dependencies (action) and interlocks (condition) omitted from the request |
| `tap` | Full executable ground truth |
| `acceptable_taps` | Semantically equivalent variants |

A full schema example is in `docs/ANNOTATION_GUIDELINES.md`.

## Knowledge-Parity (+DK) Baselines

For fair comparison on constraint-aware requests, baselines may be evaluated with the plain-text domain rules in `domain_knowledge/GENERAL_DOMAIN_KNOWLEDGE.txt` injected into their prompts. This provides template-level operational guidance without giving per-request oracle answers or a knowledge graph.

## License

This benchmark artifact is released under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). See `LICENSE`.
