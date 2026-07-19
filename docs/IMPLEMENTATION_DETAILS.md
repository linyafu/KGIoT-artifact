# Implementation Details for Baseline Comparison

This document specifies the **exact experimental setup** used to compare KGIoT against Vanilla, ChatIoT, Sasha, HomeGenii, and AutoIoT on the Home TAP benchmark. It is intended to address reproducibility and **fair-comparison** concerns: all methods target the same TAP task, share the same LLM decoding settings, and are evaluated under the same single-turn protocol.

> **Note:** Reviewers asked for implementation details (prompts, metadata schema, LLM settings, refinement loops, interaction policy, TAP-format adaptation). They did **not** require releasing full baseline **source code**. This artifact therefore publishes prompts, schemas, and protocol specifications; it does not include the Home Assistant integration codebase.

**Related files in this repository:**

| Content | Location |
|---------|----------|
| Verbatim prompt templates | [`../prompts/`](../prompts/) |
| Knowledge-parity (+DK) text block | [`../domain_knowledge/GENERAL_DOMAIN_KNOWLEDGE.txt`](../domain_knowledge/GENERAL_DOMAIN_KNOWLEDGE.txt) |
| Device metadata example | [`../examples/metadata_schema_example.json`](../examples/metadata_schema_example.json) |
| Home inventories (capability indices) | [`../data/environments/`](../data/environments/) |
| Scoring rules | [`ANNOTATION_GUIDELINES.md`](ANNOTATION_GUIDELINES.md) |
| Benchmark construction | [`CONSTRUCTION_PROTOCOL.md`](CONSTRUCTION_PROTOCOL.md) |

---

## 1. Shared Experimental Protocol

### 1.1 Evaluation mode

All methods were evaluated in **single-turn batch mode**:

1. One natural-language benchmark request is sent per case.
2. Each case uses a **fresh conversation ID** (no cross-case dialogue history).
3. The **first agent response** is recorded and scored.
4. If a method returns a clarification question (`AskUser`), **no follow-up answer is provided**; that response is scored as-is.

This prevents interactive clarification from confounding TAP quality comparisons.

### 1.2 LLM configuration (identical across all methods)

| Setting | Value |
|---------|-------|
| Model | **`gpt-4o`** (OpenAI Chat Completions API) |
| Temperature | **`0`** |
| Max output tokens | **`1024`** |
| Response format | JSON object mode (`response_format={"type":"json_object"}`) for structured stages |
| Retry policy | Up to **6 attempts** per API call (`tenacity`); **no retry** on `BadRequestError`; exponential backoff on transient errors |

### 1.3 Shared device metadata

All methods read the same live home inventory for each simulated home (`home_L`, `home_M`, `home_S`), built from Home Assistant device registry + MiOT capability metadata into an **`all_context`** list.

See [Section 2](#2-device-metadata-schema) and `examples/metadata_schema_example.json`.

### 1.4 Shared TAP output format and deployment

Every method was adapted to output the **same TAP JSON** (see [`../prompts/shared_tap_format.md`](../prompts/shared_tap_format.md)):

```json
{
  "trigger": "...",
  "condition": "...",
  "action": "..."
}
```

Generated TAPs were deployed through a **common translator** mapping TAP atoms to Home Assistant automations. The offline scorer (`scripts/score_outputs.py`) extracts TAP JSON from agent responses and applies the same metrics to all methods.

---

## 2. Device Metadata Schema

Each device in `all_context` has:

| Field | Description |
|-------|-------------|
| `id` | Numeric device ID used in TAP atoms |
| `name` | Human-readable device name |
| `area` | Room / area label |
| `type` | Device type (e.g., `light`, `motion_sensor`) |
| `services` | Nested map: service → property/event/action → metadata (`format`, `access`, `value-range`, `type`, …) |
| `entities` | Home Assistant entity IDs |

**What each method actually feeds to the LLM:**

| Method | Context form |
|--------|--------------|
| Vanilla | Full **raw** MiOT metadata per device |
| ChatIoT | Compressed or full `all_context`, then **property-sliced** subset |
| Sasha | **Filtered** full device records after device-ID selection |
| HomeGenii | Top-**5** full device records after lexical retrieval |
| AutoIoT | Full `all_context` JSON |
| KGIoT | Top-**10** recalled devices + **formatted KG subgraph** (stem-index action space) |

Inventory summaries: `data/environments/home_{L,M,S}_graph_index.json`.

---

## 3. Adaptation to Common TAP Format

Each baseline was originally designed for a different output modality. For fair comparison, all were adapted to structured TAP JSON while preserving each method's core mechanism (retrieval, compression, RAG, verification, or KG planning).

| Method | Original output (paper/system) | Benchmark adaptation |
|--------|-------------------------------|----------------------|
| **Vanilla** | General LLM automation | Single-shot TAP JSON from full raw metadata |
| **ChatIoT** | Multi-agent HA control + TAP | Router bypassed; TAP-only pipeline; optional context compression |
| **Sasha** | Clarify → filter → plan | Final plan stage outputs TAP JSON directly |
| **HomeGenii** | Retrieved rules → python_script / applet | Final stage outputs TAP JSON; device-level top-K retrieval |
| **AutoIoT** | NL rules + multi-rule Maude verification | Single-TAP structural verification + LLM repair (≤2 attempts) |
| **KGIoT** | (proposed) | Structured subgraph + constrained `TAP_fill` planning |

Full prompt templates: [`../prompts/`](../prompts/).

---

## 4. Baseline Fairness Summary

| Method | LLM calls (typical) | Refinement / verification | +DK ablation | User interaction in benchmark |
|--------|----------------------|----------------------------|--------------|------------------------------|
| Vanilla | 1 | None | Plain-text rules injected | Single-turn |
| ChatIoT | 3 | **LLM evaluator** (1 pass) | Plain-text rules injected | Single-turn |
| ChatIoT-nocomp | 3 | LLM evaluator (1 pass) | Plain-text rules injected | Single-turn; no compression |
| Sasha | 3 | None | Plain-text rules injected | Single-turn; may return clarify question |
| HomeGenii | 2 | None (+ non-LLM rule retrieval) | Plain-text rules injected | Single-turn |
| AutoIoT | 1–3 | **Local verify → LLM repair** (≤2) | Plain-text rules injected | Single-turn |
| **KGIoT** | 2 | **Deterministic** TAP_fill assembly | **Structured KG** (not +DK text) | Single-turn; parsing `ask_user` ignored |

### 4.1 Why this is not task-mismatched

- All methods solve **TAP generation** on the same 60 requests.
- All methods use the **same TAP syntax**, translator, and scorer.
- Vanilla receives the **largest raw metadata** exposure; ChatIoT includes an **evaluator refinement loop**; AutoIoT includes **verify-repair**; Sasha runs **three LLM stages** including clarification.

### 4.2 Why baselines are not knowledge-disadvantaged (without +DK)

The benchmark separates **explicit user intent** from **implicit operational constraints** (see `ANNOTATION_GUIDELINES.md`). Baselines are not given per-request oracle answers. The **`+DK` ablation** additionally injects template-level dependency/interlock rules equivalent to KGIoT's general construction templates—but as **plain text**, not as a graph. KGIoT's gains under +DK comparisons therefore reflect **structured grounding and constrained planning**, not access to exclusive natural-language hints.

### 4.3 Why baselines are not under-tuned

- **Same LLM, temperature, token cap, and retry policy** for every method.
- **ChatIoT compression thresholds** (`0.10` / `0.20`) were selected by offline sweep over all three homes.
- **HomeGenii** uses published-style top-K settings (`context_top_k=5`, `top_k=3`).
- **AutoIoT** retains its core verify-repair loop (up to 2 repairs).

---

## 5. Per-Method Specifications

Detailed prompts are in [`../prompts/`](../prompts/). Below is a compact specification of pipelines, hyperparameters, and refinement behavior.

### 5.1 Vanilla

- **Pipeline:** raw metadata → 1× LLM → TAP JSON.
- **Prompts:** [`../prompts/vanilla.md`](../prompts/vanilla.md)
- **Refinement:** none.
- **Context advantage:** full raw MiOT spec per device (strongest unstructured metadata exposure).

### 5.2 ChatIoT

- **Pipeline:** compress (optional) → preprocess → generate → **evaluator** → deploy.
- **Prompts:** [`../prompts/chatiot.md`](../prompts/chatiot.md)
- **Compression (default):** `all-MiniLM-L6-v2`; DBSCAN `eps=0.05`, `min_samples=1`; cluster threshold **0.10**; service threshold **0.20**.
- **Variants:** `chatiot` (with compression), `chatiot_nocomp` (full context).
- **Refinement:** exactly **one LLM evaluator pass** after generation.
- **Parse retry:** preprocessor gets one format-correction retry on invalid JSON.

### 5.3 Sasha

- **Pipeline:** clarify → filter → plan (TAP JSON).
- **Prompts:** [`../prompts/sasha.md`](../prompts/sasha.md)
- **Refinement:** none after planning.
- **Interaction:** clarify/filter may return a question; benchmark does not answer it.

### 5.4 HomeGenii

- **Pipeline:** goal/entity LLM → lexical device top-5 → rule top-3 → generate TAP.
- **Prompts:** [`../prompts/homegenii.md`](../prompts/homegenii.md)
- **Retrieval:** lexical token overlap (device descriptions); rule retrieval from Enhanced-TAP-derived rulebase.
- **Refinement:** none.
- **Adaptation:** TAP JSON output instead of python_script / applet.

### 5.5 AutoIoT

- **Pipeline:** generate → **local verify** → up to **2× LLM repair** → deploy.
- **Prompts:** [`../prompts/autoiot.md`](../prompts/autoiot.md)
- **Verification (local):** TAP structure, numeric device IDs, capability existence, operator validity.
- **Refinement:** verify-repair loop (not an LLM evaluator).
- **Adaptation:** single-TAP checks replace multi-rule Maude verification.

### 5.6 KGIoT (proposed)

- **Pipeline:** parse → KG recall (top-10) → subgraph → **TAP_fill plan** → deterministic assembly → deploy.
- **Prompts:** [`../prompts/kgiot.md`](../prompts/kgiot.md)
- **Constraint knowledge:** structured KG dependency/interlock edges in subgraph (not +DK plain text).
- **Refinement:** no LLM evaluator; deterministic post-processing validates and assembles TAP strings.
- **Router policy:** benchmark discards parsing-time `ask_user` and always proceeds to planning.

---

## 6. Knowledge-Parity (+DK) Setting

For `+DK` runs, the block in [`../domain_knowledge/GENERAL_DOMAIN_KNOWLEDGE.txt`](../domain_knowledge/GENERAL_DOMAIN_KNOWLEDGE.txt) is injected into baseline prompts. It provides **template-level** operational guidance (power-on dependencies, window interlocks, value semantics)—not per-request oracle TAP atoms and not a knowledge graph.

KGIoT is **not** evaluated with this injected block; it uses structured KG grounding instead.

See [`CONSTRUCTION_PROTOCOL.md`](CONSTRUCTION_PROTOCOL.md) § Knowledge-Parity Setting.

---

## 7. Reported Method Variants

| Run label | Meaning |
|-----------|---------|
| `vanilla_gpt4o` / `vanilla_dk_gpt4o` | Vanilla ± +DK |
| `chatiot_gpt4o` / `chatiot_dk_gpt4o` | ChatIoT with compression ± +DK |
| `chatiot_nocomp_gpt4o` / `chatiot_nocomp_dk_gpt4o` | ChatIoT without compression ± +DK |
| `sasha_gpt4o` / `sasha_dk_gpt4o` | Sasha ± +DK |
| `homegenii_gpt4o` / `homegenii_dk_gpt4o` | HomeGenii ± +DK |
| `autoiot_gpt4o` / `autoiot_dk_gpt4o` | AutoIoT ± +DK |
| `kgiot_gpt4o` | KGIoT (structured KG; no +DK text) |

---

## 8. What This Artifact Includes vs. Excludes

**Included (sufficient for fair-comparison audit):**

- Benchmark data, labels, and scoring scripts
- Exact prompt templates and +DK knowledge block
- Metadata schema example and home capability indices
- Implementation protocol (this document)

**Excluded (not required by reviewers; dynamic or codebase-specific):**

- Home Assistant integration / baseline source code
- Per-request LLM traces and token logs
- Runtime `all_context` dumps (derived from the same schema as the example)
- Request-specific KGIoT subgraph text and HomeGenii retrieved rule text

---

## 9. Response to Reviewer Concern (Suggested Wording)

> We have released exact implementation specifications for all compared methods in the artifact repository (`docs/IMPLEMENTATION_DETAILS.md` and `prompts/`). These documents provide the full prompt templates, shared metadata schema, LLM model (`gpt-4o`), temperature (0), retry policy (up to 6 attempts), evaluator/refinement behavior, single-turn user-interaction policy, and TAP-format adaptation for each baseline. A knowledge-parity (+DK) ablation injects plain-text domain rules equivalent to our general KG templates without providing graph structure or per-request oracle answers. The comparisons therefore isolate the effect of structured grounding and constrained planning rather than task mismatch, knowledge disadvantage, or under-tuned baselines.
