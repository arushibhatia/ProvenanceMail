# ProvenanceMail

Demo: https://www.loom.com/share/2c60151565054ba6b479dc48d3442ebd

ProvenanceMail is an AI detection engine for corporate email. It accepts a raw text draft and runs it through a three-signal weighted pipeline to estimate whether the writing reflects human expression or automated generation. Each submission returns a structured attribution result, a confidence score, and a plain-language transparency label. Disputed classifications can be appealed; every event is appended to an immutable audit log.

---

## Architecture Overview

A submission travels through the following path:

```
POST /submit  (text + creator_id)
      │
      ▼
  mint content_id (UUID)
      │
      ├──── Signal 1: Groq LLM ──────────► llm_score (0.0 – 1.0)
      │       llama-3.3-70b-versatile
      │       temperature=0.0
      │
      ├──── Signal 2: Contraction Density ► contraction_score (0.0 – 1.0)
      │       regex over explicit contraction list
      │
      └──── Signal 3: Punctuation Spark ──► punctuation_score (0.0 – 1.0)
              count distinct expressive marker types (!  (...)  ...)
                    │
                    ▼
        confidence = (0.50 × S1) + (0.30 × S2) + (0.20 × S3)
                    │
                    ▼
        tier classification
          < 0.40  → human_original
          0.40–0.75 → uncertain
          > 0.75  → likely_ai
                    │
                    ▼
        transparency label text selected (3 variants)
                    │
                    ├── append event to audit.jsonl
                    │
                    └── return JSON response to caller
                          content_id, attribution, confidence,
                          label, signals{}
```

Appeals follow a separate path:

```
POST /appeal  (content_id + creator_reasoning)
      │
      ├── validate content_id exists in log
      │
      ├── append APPEAL_FILED event to audit.jsonl
      │     (original SUBMISSION row never mutated)
      │
      └── return confirmation  (status: under_review)
```

`GET /log` compiles the append-only ledger top-to-bottom into a current-state map: `SUBMISSION` events seed each entry; `APPEAL_FILED` events overlay `status`, `appeal_reasoning`, and `appeal_timestamp` onto the existing record.

---

## Content Submission Endpoint

**`POST /submit`** accepts `text` and `creator_id` and returns a structured JSON response.

```bash
curl -s -X POST http://localhost:5000/submit \
  -H "Content-Type: application/json" \
  -d '{
    "text": "I hope this email finds you well. I am writing to inform you that the quarterly deliverables have been completed. Furthermore, please note that the attached report outlines the key performance indicators for Q3.",
    "creator_id": "demo-user-1"
  }' | python -m json.tool
```

**Response:**

```json
{
    "attribution": "likely_ai",
    "confidence": 0.95,
    "content_id": "b19228be-e549-4fa1-8e6e-744cb8b0e257",
    "creator_id": "demo-user-1",
    "label": "AI-Generated Notification: This text displays high statistical uniformity, a complete lack of conversational contractions, and structural boilerplate highly characteristic of automated language models. The system has classified this content as machine-generated.",
    "signals": {
        "signal1": {
            "reasoning": "The text exhibits a high degree of semantic uniformity and predictable corporate transitions, indicative of AI-generated content.",
            "score": 0.9
        },
        "signal2": {
            "score": 1.0
        },
        "signal3": {
            "score": 1.0
        }
    }
}
```

The response includes:
- `content_id` — a UUID minted at submission time, required for filing an appeal
- `attribution` — machine-readable tier (`human_original`, `uncertain`, `likely_ai`)
- `confidence` — the combined weighted score (0.0–1.0)
- `label` — a plain-language transparency label (see [Transparency Labels](#transparency-labels))
- `signals` — individual scores from each of the three detection engines

---

## Multi-Signal Detection Pipeline

ProvenanceMail runs three independent signals in parallel and combines them into a single confidence score.

### Signal 1 — Semantic Tropes (Groq LLM)

**What it captures:** Holistic semantic uniformity. The `llama-3.3-70b-versatile` model runs at `temperature=0.0` with a system prompt that instructs it to evaluate whether the prose relies on predictable AI transition patterns — "Furthermore," "I hope this email finds you well," "In conclusion" — or whether it exhibits the irregular, asymmetric cadence of human writing. The model returns a float between 0.0 (strongly human) and 1.0 (strongly machine) alongside a one-sentence explanation.

**Why this signal:** Stylometric heuristics alone can't detect semantic register. A short email with no contractions might be human; a long email full of contractions might still read like templated output. The LLM is the only signal that evaluates what the text is actually saying and how ideas are sequenced.

**What it misses:** High-stakes corporate communication — executive briefings, HR compliance notices, legal notifications — intentionally adopts uniform, safe, structured prose. The LLM correctly identifies it as machine-like, even when a human wrote every word.

### Signal 2 — Contraction Density

**What it captures:** The frequency of informal English contractions (e.g., "can't", "I've", "won't") relative to total word count. Language models overwhelmingly produce fully expanded prose ("I am," "do not," "we will"), because their training data skews toward edited, formal text. Humans in casual workplace communication naturally drop into contractions.

**Implementation:** The script uses a regex against an explicit enumeration of English contractions to avoid false positives from possessives ("John's report"). The normalized score applies the spec formula:

```
score = max(0.0, 1.0 − (contraction_count / (total_words × 0.05)))
```

A baseline contraction rate of 5% (1 per 20 words) drives the score to 0.0. Zero contractions drives it to 1.0.

**What it misses:** Formal contracts, legal documents, and executive memos explicitly prohibit contractions. This signal gives them a robotic `1.0` regardless of authorship — a known and documented blind spot.

### Signal 3 — Punctuation Spark

**What it captures:** The presence of three punctuation markers that are disproportionately human: exclamation marks (`!`), parenthetical asides `(like this)`, and conversational ellipses `...`. These markers signal warmth, digression, and trailing thought — things language models suppress in favor of clean, uniform prose.

**Implementation:** Rather than a percentage (which dilutes badly in short emails), the heuristic counts how many distinct marker *types* appear and maps to a score:

| Distinct expressive types present | Score |
|---|---|
| 0 | 1.0 — rigid machine uniformity |
| 1 | 0.5 — partial human signal |
| 2 or more | 0.0 — active human punctuation signature |

**What it misses:** Text run through grammar linters (Grammarly, executive editing) has its casual punctuation stripped, producing a machine-like `1.0` on formally polished human drafts.

### Ensemble Weighting

The three scores are combined into a single confidence score using a fixed weighted formula:

```
confidence = (0.50 × S1) + (0.30 × S2) + (0.20 × S3)
```

Signal 1 carries the majority weight because semantic register is the hardest thing to fake and the hardest for heuristics to catch. Signals 2 and 3 are structural checks that reinforce or counterbalance the LLM verdict. When signals agree, the combined score moves toward the extremes; when they disagree, the score lands in the uncertain middle zone, which is intentional — that ambiguity triggers the appeals pathway rather than forcing a false binary classification.

**Conflict resolution example:** A non-native English speaker writes a heartfelt email with perfect grammar, zero contractions, and no casual punctuation. S2 and S3 both return `1.0`. But if S1 detects irregular phrasing and non-standard transitions, it returns a low score that pulls the combined confidence below `0.75`, potentially saving it from a false AI classification.

---

## Confidence Scoring with Uncertainty

### Score Tiers

| Combined Score (C) | Attribution | Meaning |
|---|---|---|
| 0.00 ≤ C < 0.40 | `human_original` | High stylistic variance, conversational markers present |
| 0.40 ≤ C ≤ 0.75 | `uncertain` | Mixed profile — borderline or conflicted signals |
| 0.75 < C ≤ 1.00 | `likely_ai` | Uniform structure, boilerplate phrasing, no colloquial markers |

A score of 0.60 does not mean "60% probability of AI." It means the signals are in active conflict — one or more signals look human while others look machine. The system treats this as a distinct operational state, not a weak AI verdict.

### Validation: Two Contrasting Submissions

**High-confidence AI (score: 0.95):**
```json
{
  "text": "Please be advised that this communication serves as formal notification of the upcoming policy amendment. All stakeholders are required to review the attached documentation.",
  "attribution": "likely_ai",
  "confidence": 0.95,
  "signals": { "signal1": {"score": 0.9}, "signal2": {"score": 1.0}, "signal3": {"score": 1.0} }
}
```

**Lower-confidence human (score: 0.30):**
```json
{
  "text": "ok so i finally tried that new ramen place downtown (never again)! the broth was fine but they put WAY too much sodium in it... probably wont go back",
  "attribution": "human_original",
  "confidence": 0.30,
  "signals": { "signal1": {"score": 0.0}, "signal2": {"score": 1.0}, "signal3": {"score": 0.0} }
}
```

In the human example, S1 detects strongly colloquial language (0.0) and S3 detects exclamation, parenthetical, and ellipsis (0.0), pulling the combined score to 0.30 despite S2 returning 1.0 (no contractions in the literal text). This demonstrates meaningful variation: the pipeline does not collapse everything into the middle.

---

## Transparency Labels

The label returned by the API changes based on the confidence score. All three variants use plain language — no statistical jargon.

**Variant A — High-Confidence Human Original** (confidence < 0.40)

> "High-Confidence Human Original: Our system indicates this content aligns closely with natural human writing patterns, colloquial conversational flow, and structural stylistic variance. This text is classified as a human-authored draft."

**Variant B — Verification Uncertain** (0.40 ≤ confidence ≤ 0.75)

> "Verification Uncertain: This text features mixed stylistic markers. It utilizes rigid, highly structured professional phrasings often found in standard corporate templates, heavily edited drafts, or collaborative human-AI setups. Classification cannot be definitively determined automatically."

**Variant C — High-Confidence AI-Generated** (confidence > 0.75)

> "AI-Generated Notification: This text displays high statistical uniformity, a complete lack of conversational contractions, and structural boilerplate highly characteristic of automated language models. The system has classified this content as machine-generated."

The label text is verified programmatically to match the spec verbatim — the constants in `app.py` are diff'd against the planning doc strings on every change.

---

## Appeals Workflow

When a creator believes their submission was misclassified, they can file an appeal using the `content_id` returned by `/submit`.

**Submitting an appeal:**
```bash
curl -s -X POST http://localhost:5000/appeal \
  -H "Content-Type: application/json" \
  -d '{
    "content_id": "159fea21-678c-4f19-931a-2c629402f3d7",
    "creator_reasoning": "I wrote this myself from personal experience. I am a non-native English speaker and my writing style may appear more formal than typical."
  }' | python -m json.tool
```

**Response:**
```json
{
    "content_id": "159fea21-678c-4f19-931a-2c629402f3d7",
    "message": "Appeal received. This submission has been flagged for human review.",
    "status": "under_review"
}
```

**Appeal visible in `GET /log`:**
```json
{
  "appeal_reasoning": "I wrote this myself from personal experience. I am a non-native English speaker and my writing style may appear more formal than typical.",
  "appeal_timestamp": "2026-06-30T05:00:50.850Z",
  "attribution": "likely_ai",
  "confidence": 0.875,
  "content_id": "159fea21-678c-4f19-931a-2c629402f3d7",
  "contraction_score": 1.0,
  "creator_id": "test-user-formal",
  "llm_score": 0.8,
  "punctuation_score": 1.0,
  "status": "under_review",
  "timestamp": "2026-06-30T04:58:00.911Z"
}
```

The audit log is append-only. Filing an appeal appends a separate `APPEAL_FILED` event; the original `SUBMISSION` row is never mutated. `GET /log` compiles both event types into a merged current-state view per `content_id`.

---

## Rate Limiting

**`POST /submit`** is protected by Flask-Limiter:

| Window | Limit | Reasoning |
|---|---|---|
| Per minute | 10 requests | A writer iterating on their own draft would realistically submit once at a time. 10/minute accommodates rapid back-and-forth revision without allowing a script to flood the Groq API, which is the real cost center. |
| Per day | 100 requests | Generous for a full workday of active use (~12 submissions/hour over 8 hours) while making bulk-scraping economically unattractive. |

Limits are keyed per IP address. `/appeal` and `/log` are not rate-limited — appeals are a low-frequency human action and the log is read-only.

**Rate limit test — 12 rapid requests (limit: 10/minute):**

127.0.0.1 - - [29/Jun/2026 22:08:55] "POST /submit HTTP/1.1" 200 -
127.0.0.1 - - [29/Jun/2026 22:08:56] "POST /submit HTTP/1.1" 200 -
127.0.0.1 - - [29/Jun/2026 22:08:56] "POST /submit HTTP/1.1" 200 -
127.0.0.1 - - [29/Jun/2026 22:08:56] "POST /submit HTTP/1.1" 200 -
127.0.0.1 - - [29/Jun/2026 22:08:57] "POST /submit HTTP/1.1" 200 -
127.0.0.1 - - [29/Jun/2026 22:08:57] "POST /submit HTTP/1.1" 200 -
127.0.0.1 - - [29/Jun/2026 22:08:58] "POST /submit HTTP/1.1" 200 -
127.0.0.1 - - [29/Jun/2026 22:08:58] "POST /submit HTTP/1.1" 200 -
127.0.0.1 - - [29/Jun/2026 22:08:58] "POST /submit HTTP/1.1" 200 -
127.0.0.1 - - [29/Jun/2026 22:08:59] "POST /submit HTTP/1.1" 200 -
127.0.0.1 - - [29/Jun/2026 22:08:59] "POST /submit HTTP/1.1" 429 -
127.0.0.1 - - [29/Jun/2026 22:08:59] "POST /submit HTTP/1.1" 429 -

The first 10 return `200 OK`; requests 11 and 12 return `429 Too Many Requests`.

---

## Audit Log

Every `/submit` call appends a structured JSON line to `audit.jsonl`. Every `/appeal` call appends a separate `APPEAL_FILED` event. `GET /log` compiles the append-only ledger into a merged current-state map — one entry per `content_id`, with appeal fields overlaid if an appeal has been filed.

### Log fields

| Field | Type | Description |
|---|---|---|
| `content_id` | UUID string | Unique ID minted at submission; links submissions to appeals |
| `creator_id` | string | Provided by the caller at submission time |
| `timestamp` | ISO 8601 UTC | When the submission hit the endpoint |
| `attribution` | enum | `human_original` / `uncertain` / `likely_ai` |
| `confidence` | float 0–1 | Weighted combined score |
| `llm_score` | float 0–1 | Signal 1 — Groq semantic tropes |
| `contraction_score` | float 0–1 | Signal 2 — contraction density |
| `punctuation_score` | float 0–1 | Signal 3 — punctuation spark |
| `status` | enum | `classified` or `under_review` |
| `appeal_reasoning` | string | Populated when an appeal is filed |
| `appeal_timestamp` | ISO 8601 UTC | When the appeal was filed |

### Sample entries (one per attribution tier)

```json
[
  {
    "event_type": "SUBMISSION",
    "content_id": "b19228be-e549-4fa1-8e6e-744cb8b0e257",
    "creator_id": "demo-user-1",
    "timestamp": "2026-06-30T05:10:11.156Z",
    "attribution": "likely_ai",
    "confidence": 0.9375,
    "llm_score": 0.9,
    "contraction_score": 1.0,
    "punctuation_score": 1.0,
    "status": "classified"
  },
  {
    "event_type": "SUBMISSION",
    "content_id": "e6028432-f580-49b7-a18b-b4d6b8474f03",
    "creator_id": "demo-user-2",
    "timestamp": "2026-06-30T05:10:11.640Z",
    "attribution": "uncertain",
    "confidence": 0.5,
    "llm_score": 0.2,
    "contraction_score": 1.0,
    "punctuation_score": 1.0,
    "status": "classified"
  },
  {
    "event_type": "SUBMISSION",
    "content_id": "4305a969-9d55-4c33-84e3-19da23c6577a",
    "creator_id": "demo-user-3",
    "timestamp": "2026-06-30T05:10:18.424Z",
    "attribution": "human_original",
    "confidence": 0.375,
    "llm_score": 0.0,
    "contraction_score": 1.0,
    "punctuation_score": 0.0,
    "status": "classified"
  }
]
```

### Entry with appeal filed

```json
{
  "event_type": "SUBMISSION",
  "content_id": "159fea21-678c-4f19-931a-2c629402f3d7",
  "creator_id": "test-user-formal",
  "timestamp": "2026-06-30T04:58:00.911Z",
  "attribution": "likely_ai",
  "confidence": 0.875,
  "llm_score": 0.8,
  "contraction_score": 1.0,
  "punctuation_score": 1.0,
  "status": "under_review",
  "appeal_reasoning": "I wrote this myself from personal experience. I am a non-native English speaker and my writing style may appear more formal than typical.",
  "appeal_timestamp": "2026-06-30T05:00:50.850Z"
}
```

---

## Known Limitations

### Rigidly Formal Human Writing

The system's most reliable false-positive category is professionally polished human text: executive briefings, legal notifications, HR compliance updates, and formal academic writing. All three signals treat these as machine-generated:

- **Signal 1** flags the uniform transition phrases ("Furthermore," "Please note that") as boilerplate.
- **Signal 2** returns `1.0` because professional standards prohibit contractions.
- **Signal 3** returns `1.0` because linters and editors strip exclamation marks and parentheticals.

The combined score for a carefully edited human memo can easily exceed `0.90`, producing a confident false `likely_ai` verdict. This is not a data problem or a threshold problem — it is a fundamental property of the signals. Formal writing genuinely shares statistical surface features with AI output. The appeals workflow exists specifically to handle this class of misclassification.

### Technical Content in Emails

Engineers who paste terminal logs, JSON payloads, or code snippets into emails will be misclassified. Code has zero contractions (Signal 2 → 1.0), no expressive punctuation (Signal 3 → 1.0), and Signal 1 may or may not detect the non-prose register depending on how much surrounding context the email contains. The combined score will almost always exceed `0.75`.

### Non-Native English Writers

Formal English education teaches expanded grammar and suppresses casual markers. A non-native speaker following textbook rules produces text that statistically resembles AI output across all three signals. This is one of the four `reason_category` values defined in the appeals workflow for exactly this reason.

---

## Spec Reflection

**Where the spec helped:** The explicit formula — `(0.50 × S1) + (0.30 × S2) + (0.20 × S3)` — and the three exact tier thresholds (`< 0.40`, `0.40–0.75`, `> 0.75`) were fully specified before implementation began. This made the scoring function a direct translation rather than a design decision, which kept calibration honest. The tier boundaries were validated against four deliberately chosen inputs before any of them were wired into the endpoint.

**Where implementation diverged:** The spec defines five `reason_category` enum values for appeals (`BUSINESS_FORMAL`, `NON_NATIVE_SPEAKER`, `COLLABORATIVE_DRAFT`, `OTHER`, and a mandatory `creator_comment` when `OTHER` is selected). The implemented endpoint collapsed this into a single `creator_reasoning` free-text field. The structured enum was dropped because enforcing it without a real frontend form would have made the appeals curl command artificially awkward to demonstrate, and the structured categories are more useful for a UI-driven workflow than a JSON API. The audit log preserves the reasoning string verbatim, so a human reviewer still gets the context; the categorical bucketing is just deferred to a future UI layer.

**What would change for production:** Signal 2 (contraction density) is too coarse for a real deployment. The 5% baseline and the binary floor logic mean any email under ~40 words gets a dramatically inflated score from a single contraction — or a 1.0 from having none. A production implementation would apply a minimum word-count gate before running Signal 2, or weight its contribution down for short submissions. Signal 3 has the same short-text problem in reverse: a two-word subject line with an exclamation mark would return 0.0 despite carrying no real human signal.

---

## AI Usage

### Instance 1 — Signal 1 (Groq Integration) and Flask Skeleton

I directed Claude to generate the Flask app skeleton with a `POST /submit` route stub and the complete Signal 1 function — passing the `llama-3.3-70b-versatile` system prompt specification, the zero-temperature requirement, and the exact JSON output schema from the planning doc.

Claude produced a working Groq integration and a `score_semantic_tropes()` function. What I revised: the initial system prompt Claude wrote described the task conversationally rather than giving the model strict behavioral constraints. I rewrote the system prompt to be explicit that the model must return only a minified JSON block with no surrounding explanation, and added the markdown fence stripping logic after observing that the model occasionally wrapped its output in code blocks despite the instruction.

### Instance 2 — Signal 2 (Contraction Density) and Test Suite

I directed Claude to implement the contraction density heuristic using the exact formula from the spec, and to write a test file for Signal 2 that tested it against all four reference inputs (clearly AI, clearly human, borderline formal, borderline edited AI) before wiring it into the endpoint.

Claude produced a regex-based implementation and five tests. What I caught and corrected: the initial regex used a broad apostrophe pattern (`\w+'\w+`) which would have matched possessives like "John's" and "the company's" as contractions, inflating the human signal on any email that referred to people or organizations by name. I directed Claude to replace it with an explicit enumeration of known English contractions, which is the correct approach for this use case even though it requires more maintenance.