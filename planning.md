# ProvenanceMail

## Project Overview
In today's corporate world, much of our commmunication, whether it be documentation, Slack messages, emails, etc. have been outsourced to AI.ProvenanceMail is an AI detection engine designed for corporate communication pipelines. Its goal is to validate whether an email draft reflects human expression or carries elements that reflect AI generation. We do this by analyzing the provided text in multiple ways, using both an LLM (Groq) and semantic signals.

## Detection Signals
ProvenanceMail uses a 3-signal weighted pipeline to evaluate emails. Each signal is meant to target a particular quality of LLM generated text (in this case, emails). 

1. Semantic Tropes with Groq LLM
Using Groq LLM to evaluate the email text, we are aiming to measure holistic semantic uniformity, predictable transitions, and standard corparate AI boilerplate. For example, LLM email generation often relies on predictable conversational paths ("Furthermore", "In conclusion", "I hope this email finds you well"). Human writing is much more irregular, asymmetrical, and posesses greater colloqual transitions.

Output Format: A normalized floating-point number between 0.0 (Highly Conversational Human) and 1.0 (Pure Machine Signature).

Implementation logic: The text is passed to the `llama-3.3-70b-versatile` model via Groq with a temperature of `0.0`. The system prompt instructs the model to return a strict, minified JSON block matching this layout: `{"score": 0.85, "reasoning": "Observed boilerplate corporate transitions and textbook paragraph symmetry."}`. The reasoning string is extracted and preserved within the immutable event log.

Signal Blind Spot: High-stakes corporate updates, executive briefs, or HR compliance templates naturally share highly structured semantic frameworks, which can trigger a false machine classification.

2. Stylometric heuristic #1: Contraction Density
Using a Python script, we will compute the frequency of linguistic contractions (ex. "can't", "won't") relative to total word count. AI text generators often default to fully expanded text ("I am", "do not", etc.). Humans naturally drop into contractions.

Output Format: A normalized floating-point number between 0.0 (High Contraction Density / Highly Human) and 1.0 (Zero Contractions / Highly Robotic).

Implementation Logic: The script parses the text using regular expressions to count explicit English contractions. We establish a baseline where a natural human workplace email expects a contraction rate of at least 5% (1 contraction per 20 words). The normalized score is calculated using a floor logic threshold:

$$\text{Contraction Score} = \max\left(0.0, 1.0 - \frac{\text{Contraction Count}}{\text{Total Words} \times 0.05}\right)$$

Signal Blind Spot (Legal Boilerplate): Formal contracts or legal company updates explicitly prohibit the use of contractions, driving this heuristic automatically to a machine-like 1.0.

3. Stylometric heuristic #2: Selective punctuation usage ⭐ STRETCH FEATURE (Ensemble Detection)
Here we plan to measure the presence of a few punctuations that are more indicative of human-written text. We will compute a ratio of the following three punctuation usages compared to total punctuation usage.
a. The exclamation mark is very human-indicative.
b. Paranethetical side thoughts (for example: "blah blah (something here)")
c. Conversational ellipsis: "..." indicates trailing off or shifting between ideas in an ongoing thread, a very human thing!

Output Format: A normalized floating-point number where 0.0 represents an active human punctuation signature and 1.0 represents rigid machine uniformity.

Implementation Logic: Rather than a strict percentage curve (which gets heavily diluted in short emails), the code evaluates a baseline presence. If the text contains at least two instance variations of these tone-buffering markers, the score instantly returns 0.0. If it contains zero expressive marks, it defaults to 1.0. One marker type present returns 0.5 (interpolated midpoint not in original spec — added during implementation to avoid a binary cliff).

Signal Blind Spot (Copyedited Drafts): Text put through an executive review or a strict grammar linter will have its casual punctuation stripped away, mimicking automated precision.

### Combining The 3 Signals
To compile the individual assessments into a single, cohesive metric, the system applies a weighted linear calculation. The Groq semantic engine carries the primary weight, supported by our two structural stylometric baselines:

$$\text{Combined Confidence Score} = (0.50 \times \text{Signal 1}) + (0.30 \times \text{Signal 2}) + (0.20 \times \text{Signal 3})$$

#### Calibrated Score Tiers
Our system maps the combined score to one of three tiers:

Combined Score Range (C)System Meaning / InterpretationAssigned Category$0.00 \leq C < 0.40$High stylistic variance, loose conversational phrasing, and organic human markers are highly present. High-Confidence Human Original$0.40 \leq C \leq 0.75$Mixed, borderline style profile. Employs rigid professional structures or standard templates that blur the clear separation of provenance. Verification Uncertain$0.75 < C \leq 1.00$Strong mathematical uniformity, standard AI boilerplate, and zero colloquial markers. High-Confidence AI-Generated

### Uncertainty Representation & Calibration
The table above delineates the threshold and how we represent uncertainty in this context. 

A combined confidence score of 0.60 does not mean the system is "60% sure the text is AI." Instead, it indicates a highly conflicted stylistic signature.

In our three-signal model, a 0.60 occurs when an email exhibits opposing linguistic behaviors. For example:

The text might completely lack conversational contractions (driving the Signal 2 score to 1.0), which looks robotic.

Simultaneously, the human author might have explicitly included expressive exclamation points or conversational parenthetical side thoughts (driving the Signal 3 score to 0.0), which looks human.

The Groq semantic engine (Signal 1) returns a middling score because the prose sits on the boundary between clean corporate writing and structured automation.

Rather than forcing a high-stakes binary classification ("Human" or "AI") on a mixed signature, the system treats this zone as a distinct state of operational ambiguity. To balance this vulnerability, the system implements an appeals workflow.


## Transparency Label Design
ProvenanceMail surfaces a specific text block for each tier. These descriptions explain why the system arrived at its conclusion based on the underlying signals:

Variant A: High-Confidence Human Original
User Display Text: "High-Confidence Human Original: Our system indicates this content aligns closely with natural human writing patterns, colloquial conversational flow, and structural stylistic variance. This text is classified as a human-authored draft."

Variant B: Verification Uncertain
User Display Text: "Verification Uncertain: This text features mixed stylistic markers. It utilizes rigid, highly structured professional phrasings often found in standard corporate templates, heavily edited drafts, or collaborative human-AI setups. Classification cannot be definitively determined automatically."

Variant C: High-Confidence AI-Generated
User Display Text: "AI-Generated Notification: This text displays high statistical uniformity, a complete lack of conversational contractions, and structural boilerplate highly characteristic of automated language models. The system has classified this content as machine-generated."

## Appeals Workflow
Because stylistic heuristics can misclassify high-stakes professional writing (such as rigid legal drafts or non-native English writing), ProvenanceMail implements an asynchronous, friction-free appeals mechanism to track edge cases and flag entries for review.

1. Who Can Submit an Appeal & What Information is Provided
Only the author associated with the original content submission can trigger an appeal. To prevent arbitrary disputes and compile useful debugging data, the creator must provide specific structural context rather than an open-ended complaint. In a more thorough produciton-grade application, we would supplement this with auth, a GET endpoint which would leverage the user token to get only the submissions provided by this user. Since that is out of scope for this project we will instead just require the content_id that was minted + returned as part of the submission flow.

When submitting a POST /appeal, the user must provide:

- content_id (UUID): The unique identifier returned during the initial classification.

- creator_reasoning (String): A free-text explanation of why the classification is incorrect. Originally planned as a structured enum (BUSINESS_FORMAL, NON_NATIVE_SPEAKER, COLLABORATIVE_DRAFT, OTHER) with a separate creator_comment field — simplified to a single free-text field during implementation because enforcing an enum without a frontend form made the API unnecessarily rigid for a demo context. The categorical intent is preserved in the field name; bucketing can be added at the UI layer.

2. System Back-End Processing & State Transitions
When the system receives a valid payload at the /appeal endpoint, it executes an atomic append-only state update. Instead of modifying or overwriting the original submission record, the engine appends a completely new, independent transaction line to audit.jsonl containing an APPEAL_FILED event type.

The system captures and logs the following explicit details:

The unique event type flag (APPEAL_FILED).

The targeting content_id UUID to link the appeal back to the original text and pipeline scores.

The updated system status tracking flag, shifting the document state from classified to under_review.

The appeal metadata: the creator_reasoning string provided by the author.

A UTC timestamp recording when the appeal entry hit the ledger.

3. The Human Reviewer Administrative Queue View
When a system administrator or human auditor queries the backend state using the GET /log endpoint, the system reads the append-only log file from top to bottom, compiles the rows into an active state map, and presents a clean queue.

A human reviewer opening this consolidated queue will see an array of active disputes sorted chronologically. Each entry displays:

The unique tracking identifier and exact submission timestamp.

The current state flag highlighting that the document is actively UNDER REVIEW.

The full suite of original pipeline metrics, including the final combined confidence score, the individual contraction and punctuation scores, and the exact linguistic reasoning string returned by the Groq LLM semantic engine.

The author's appeal reasoning string and the timestamp when the appeal was filed.

## Anticipated Edge Cases

Because our architecture relies on structural, stylometric shortcuts rather than absolute semantic comprehension, certain specific writing styles and document structures will inherently cause the pipeline to generate false or misleading confidence scores.

### Scenario 1: Automated Technical Data & Code Snippets inside Emails
* The Vulnerability: An engineer copies and pastes a terminal log file, a JSON database snippet, or a Python script into an email to coordinate a bug fix with their team.
* Heuristic Failure Mechanics: * **Signal 2 (Contraction Density):** Code blocks and system outputs contain zero conversational contractions (`I'm`, `don't`), driving the contraction heuristic score immediately to a robotic `1.0`. **Signal 3 (Punctuation Spark):** While code uses dense punctuation, it completely lacks the conversational, tone-buffering markers our heuristic looks for (such as an exclamation point to project warmth or an ellipsis to shift topics). This drives the punctuation score to a rigid `1.0`.
* System Outcome: Even if the Groq LLM semantic engine detects mixed technical phrasing, the heavily weighted math of the two structural heuristics will pull the unrounded combined score past the `0.75` threshold, resulting in an inaccurate `High-Confidence AI-Generated` flag for a purely functional human message.

### Scenario 2: Rigidly Mandated Executive Briefings or Legal Templates
* The Vulnerability: A manager drafts a high-stakes corporate compliance update, a performance review self-rebuttal, or a legal non-disclosure notification. 
* Heuristic Failure Mechanics:
  * **Signal 1 (Groq LLM):** Formal corporate prose intentionally uses highly structured, safe, and uniform transition patterns (*"Furthermore," "Consequently," "Please note that"*). The Groq semantic tracker will flag this as standard corporate AI boilerplate.
  * **Signal 2 (Contraction Density):** Professional workplace standards strictly forbid the use of casual shortcuts. The author will write out every single word fully (*"I am writing to notify you that we will not..."*), scoring a machine-like `1.0`.
  * **Signal 3 (Punctuation Spark):** Strict professional boundaries eliminate expressive tone-buffering. Exclamation marks and conversational ellipses are completely stripped to maintain an executive corporate tone, returning another machine-like `1.0`.
* System Outcome: The complete absence of casual human markers combined with highly uniform phrasing forces the pipeline to output a near-perfect machine signature ($C > 0.90$), misclassifying highly polished human dedication as a robotic generation. 

### Scenario 3: Non-Native English Textbook Phrasing
* The Vulnerability: An email authored by a non-native English speaker who relies heavily on traditional textbook structures and hyper-correct grammar rules to communicate in a corporate setting.
* Heuristic Failure Mechanics: Non-native speakers who learned English in formal educational environments often avoid informal contractions and casual tone-buffering markers (`!`, `...`) entirely to minimize the risk of making an error. They write with high grammatical uniformity and rely on safe, predictable transitional phrasing.
* System Outcome: Because the text matches the exact statistical profiles used to train LLMs (flawless grammar, zero contractions, uniform structure), the pipeline will strip the human signature and incorrectly categorize the email as an automated generation.

## Architecture
The submission flow begins when raw text is transmitted to the POST /submit endpoint, running it through parallel signal engines to calculate individual signal scores that are combined into a final confidence tier, logged dynamically, and returned as a structured response. If a user disputes an uncertain or automated machine classification, the appeal flow is initiated via the POST /appeal endpoint with a specific reason category. This action updates the internal document state tracking flag to under_review and appends an independent tracking transaction to the append-only audit ledger without overwriting the historical event record.

========================================================================================
                         PROVENANCEMAIL WORKFLOW ARCHITECTURE
========================================================================================

1) SUBMISSION FLOW
──────────────────
 [ POST /submit ]
        │
        │ (raw text)
        ▼
 ┌─────────────────────────────────────────────────────────────────┐
 │ Pipeline Engines:                                               │
 │  ├── Signal 1: Groq LLM ----------> (signal score: float 0-1) ──┤
 │  ├── Signal 2: Contraction Density -> (signal score: float 0-1) ──┤
 │  └── Signal 3: Punctuation Spark --> (signal score: float 0-1) ──┤
 └─────────────────────────────────────────────────────────────────┘
        │
        │ (all 3 signal scores)
        ▼
 [ Confidence Scoring ]
        │
        │ (combined score)
        ▼
 [ Transparency Label ]
        │
        │ (label text)
        ▼
 [    Audit Log     ]
        │
        │ (response payload)
        ▼
 [ Client Response  ]


2) APPEAL FLOW
──────────────
 [  POST /appeal  ]
        │
        │ (content_id & reason category)
        ▼
 [  Status Update ]
        │
        │ (status change event)
        ▼
 [    Audit Log     ]
        │
        │ (response payload)
        ▼
 [ Client Response  ]


 ## AI Tool Plan
This plan outlines the specific prompt context, generation instructions, and acceptance gates for utilizing Claude to implement the ProvenanceMail architecture across three distinct developmental phases.

1. Milestone 3: Submission Endpoint & First Signal
Context Provided to Claude: Provide the full Workflow Architecture ASCII Diagram, the integrated workflow narrative block, and the Semantic & Behavioral Tropes (Signal 1) subset from the Detection Signals section.

Generation Prompt Objectives: Instruct Claude to generate a production-ready Python Flask application skeleton containing a stubbed boilerplate for the POST /submit endpoint. Request the complete integration logic for the llama-3.3-70b-versatile model via the Groq Cloud SDK, including the zero-temperature parameter setting, structural system instructions, and JSON error handling to pull the score and reasoning keys securely.

Verification Gates: Test the core API function in isolation using a direct Python terminal script before mounting it into the Flask routing map. Execute the function against three hardcoded sample strings (a textbook corporate introductory paragraph, an unformatted informal sentence, and a mismatched data string) to confirm that the Groq engine extracts a valid float between 0.0 and 1.0 along with an explicit reason string without crashing the server thread.

2. Milestone 4: Second Signal & Confidence Scoring
Context Provided to Claude: Provide the full Workflow Architecture ASCII Diagram, the complete Detection Signals section (Signals 1 and 2), and the Uncertainty Representation & Calibration threshold tables.

Generation Prompt Objectives: Instruct Claude to implement the pure Python algorithmic function for Stylometric Heuristic 1 (Contraction Density regular expression logic). Request the ensemble arbitration formula wrapper that multiplies the two live signal scores by their weights (0.50, 0.30), normalized over 0.80 until Signal 3 lands, to compute the partial confidence metric.

Verification Gates: Pass explicit, contrasting test inputs through the pipeline and assert that the float outputs vary meaningfully. Verify that hyper-formal text with zero contractions yields a combined score well past 0.75, whereas a casual draft with contractions yields a score below 0.40.

2b. Milestone 4b: Third Signal & Full Ensemble ⭐ STRETCH FEATURE (Ensemble Detection — +1pt)
Context Provided to Claude: Provide the Detection Signals section (Signal 3 spec), the Uncertainty Representation thresholds, and the partial confidence formula from Milestone 4.

Generation Prompt Objectives: Instruct Claude to implement Stylometric Heuristic 2 (Punctuation Spark marker verification rule) and swap the normalized partial formula for the full three-signal weighted formula: (0.50 × S1) + (0.30 × S2) + (0.20 × S3).

Verification Gates: Confirm all three signal scores appear independently in the response and audit log. Verify that the same four reference inputs produce meaningfully different scores from the two-signal version, particularly for texts with expressive punctuation.

3. Milestone 5: Production Layer & Mitigation Loop
Context Provided to Claude: Provide the full Workflow Architecture ASCII Diagram, the exact text string blocks from the Transparency Label Design section, and the entire Appeals Workflow & Mitigation Loop engineering layout.

Generation Prompt Objectives: Instruct Claude to generate the conditional control blocks mapping the unrounded combined score directly into one of the three explicit classification categories, pairing each tier with its exact, literal display text string variant. Request the complete implementation of the POST /appeal routing structure, ensuring it executes schema validation on incoming payload variables and appends the structured transaction logs cleanly to the append-only audit.jsonl ledger.

Verification Gates: Trigger API test cycles using Postman or cURL to confirm all three structural display text blocks are reachable based on arbitrary mock numerical values. Execute a valid appeal submission payload targeting an active UUID to verify that the endpoint changes the status flag mapping to under_review and appends an independent transactional event entry into the local storage log without mutating the historical baseline entry.