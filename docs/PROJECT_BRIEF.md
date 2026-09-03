# Kervansaray — Car Park Entry/Exit Intelligence

**Project brief** · repo: `kervansaray`

> A caravanserai was a roadside inn where travellers and their animals stopped
> for the night, and where a record was kept of who arrived and who departed.
> That is this system's domain, several centuries later. The name is not tied to
> hotels — a caravanserai is any waypoint people pass through, which is equally
> a shopping centre, a factory gate or a residential compound.
>
> This document is the handoff context for continuing work in Claude Code.
> It records **what is being built, what has already been decided, and what has
> been explicitly rejected**. The rejected-approaches section is not optional
> reading — several of those options look attractive on first inspection and
> have already been evaluated and ruled out for concrete reasons.

---

## 1. What this is

A fixed-camera system that reads vehicle licence plates at a car park entrance
and exit, turns each vehicle movement into a structured event, stores those
events, and exposes them through:

- a **natural-language query interface** for the operator ("who entered between
  02:00 and 04:00 on 3 March?", "which unregistered vehicles came more than
  three times this week?"), and
- **active push notifications** to the operator's desktop for rule-based
  conditions (unregistered vehicle, blacklist hit, overstay, known guest
  arriving).

The motivating real-world target is a 5-star hotel car park with no plate
recognition today, but nothing in the design is hotel-specific — the same system
fits any gated site with arrivals and departures. The strongest business case there is **guest experience**
(a returning guest's car is recognised at the gate, the front desk is notified
before they reach the door), not security — security is one line item among
several, not the headline.

### Current phase

**Student development project, internship scope, synthetic data only.**

No cameras, no hotel deployment, no real personal data. This is a deliberate
choice, not a limitation: synthetic events mean ground truth is known exactly,
which is what makes the evaluation set (§9) possible.

---

## 2. Architecture: two tracks joined by one contract

```
[video / images] → TRACK A: vision → { JSON event } → TRACK B: store + query → answers / alerts
                                          ↑
                                    the contract
```

Fixing the JSON event schema (§6) splits the system into two halves that are
developed and tested **independently**:

- **Track A** has a camera and a GPU and knows nothing about the database.
- **Track B** knows nothing about cameras. Its entire world is the incoming
  JSON stream.

Both run locally. Neither requires a Jetson or a cloud account during
development.

### Build order: Track B first

Counter-intuitive but deliberate:

1. Track B needs no hardware, no data collection, no permissions — it can start
   today.
2. Track B is where the **actual uncertainty** lives. ALPR is a solved problem;
   we know it will work. Whether an LLM layer over event data answers reliably
   is the open question.
3. Writing the synthetic event generator forces the JSON schema to be thought
   through end-to-end, which then correctly constrains Track A.
4. A working panel driven by synthetic data is the artefact that gets a real
   pilot approved. Demoing beats describing.

---

## 3. Track B — event store and query layer

### 3.1 The core design rule

> The LLM decides **which query to run**. The database **computes the answer**.
> The LLM then narrates the result.

The model never reads rows and produces a number. Counts, ranges, rankings and
joins are all computed in SQL, exactly.

### 3.2 Tool calling, not free-form SQL

The LLM is given a small set of typed, parameterised tools rather than raw SQL
access:

```
query_events(plate?, start, end, direction?, registered?, limit)
aggregate_events(group_by, metric, start, end)
vehicle_history(plate)
find_anomalies(rule, window)
search_notes(query)          # this one is genuine vector retrieval
```

Rationale: safety (no destructive or exfiltrating statements possible),
reliability (the model chooses parameters, not syntax), testability (each tool
is unit-testable in isolation), and access control enforced at the tool
boundary. The database user is read-only regardless.

Three things materially raise accuracy and should be built in from the start:

- **A semantic view.** Expose a denormalised `v_events` with human-meaningful
  column names and pre-joined vehicle/person context. Do not expose raw
  normalised tables — most model errors are join errors.
- **An explicit vocabulary.** Put actual enum values in the prompt
  (`direction: 'entry' | 'exit'`, status codes, province code range). Most
  text-to-SQL failures are wrong guessed literals.
- **10–15 few-shot examples** covering the real question distribution. Highest
  leverage prompt work in the project.

### 3.3 Guardrails

- Cap rows returned to the model (~50). Beyond that, force an aggregate call.
  The model must be structurally unable to "count by eye".
- Render the actual query result as a table in the UI next to the model's
  prose. The narration is convenience; the table is the truth.
- Every answer carries provenance (the tool call and the event IDs behind it).

### 3.4 Self-correcting loop

If a tool call errors or returns zero rows, feed the error back and let the
model retry, bounded at 2–3 attempts. Small change, real feedback loop,
measurable accuracy gain. This is also the point at which the system becomes
defensibly *agentic* rather than just tool-calling (see §11).

### 3.5 Turkish input handling — resolve deterministically, before the model

- **Relative dates**: "dün", "geçen hafta", "bu ay", "hafta sonu", "dün gece"
  → resolve to absolute ranges against the current timestamp in code. Do not
  ask the model to do date arithmetic; it produces silent errors.
- **Plate normalisation**: "34 abc 123", "34-ABC-123", "34abc123" → canonical
  form before lookup.

### 3.6 Where genuine RAG lives

Vector retrieval is used in exactly two places, both of them free text:

1. **Unstructured documents** — operating procedures, incident reports, shift
   handover notes, guest preference notes.
2. **Nightly natural-language summaries.** A cron job generates a prose summary
   of each day ("14 March: 87 entries, 3 unregistered vehicles, one stayed 4
   hours, unusual entry cluster around 02:40, longest stay 6h20m") and embeds
   *those*. Unlike raw event rows, daily summaries are semantically diverse, so
   fuzzy temporal questions ("when was there unusual activity last month?")
   become retrievable. This is the trick that makes vector search work over
   event data — by changing what gets embedded.

The resulting router has three paths: **relational** (numeric / temporal /
exact), **vector** (semantic / free text), **daily summary** (fuzzy temporal).

### 3.7 Notifications

A **deterministic rules engine** evaluates every incoming event and decides
whether to fire. The LLM only writes the human-readable message text.

An LLM must never be the trigger for an alert — latency, cost and
non-determinism all disqualify it. Deliberately *not* putting agency here is a
design decision worth stating explicitly when presenting the project.

### 3.8 Plate reconciliation

Matching an observed plate to a known vehicle is a **key lookup**, not a search:

```sql
SELECT * FROM vehicles WHERE plate = ?;
```

When OCR output does not match exactly, fall back to bounded fuzzy matching
(RapidFuzz / Levenshtein). A match at edit distance 1 is **never auto-accepted**
— it is flagged as a probable match and queued for human confirmation with the
plate crop attached. This review queue is the system's primary trust mechanism,
and its corrections double as training data.

---

## 4. Track A — vision pipeline

Not started. Development target is the local RTX 4070 laptop; the Jetson is a
deployment target only (§5).

```
frame → vehicle detection (YOLO) → ByteTrack (vehicle identity)
      → plate detection (YOLO) → plate OCR
      → grammar-constrained decoding + multi-frame voting
      → virtual line crossing → direction
      → one event per track (never per frame)
```

### 4.1 The two levers that make OCR work

**Grammar-constrained decoding.** A Turkish plate is a very narrow language:

```
province code : 01–81
then          : 1 letter + 4 digits
              | 2 letters + 3 digits
              | 3 letters + 2 digits
```

Apply the constraint *inside* decoding, not as a post-filter. Character
confusions then resolve themselves by position: a `0` where a letter is
expected is `O`; a `B` where a digit is expected is `8`. Diplomatic, military
and temporary plates use other formats — handle separately or flag as
`UNKNOWN_FORMAT`.

**Multi-frame confidence-weighted voting.** A vehicle crossing the field of
view yields 30–60 OCR readings. Vote **per character position**, weighted by
confidence. This is the single largest accuracy lever and it requires
ByteTrack (readings must accumulate per vehicle track, not per frame — which
also prevents one car generating 60 "entry" events).

> This is structurally identical to the `TemporalSmoother` in the existing
> inventory-verification project: noisy per-frame observations reduced to a
> stable reading by temporal agreement. Same pattern, different payload.

### 4.2 Camera matters more than the model

Most hobby ALPR projects fail here, not in the network:

- Plates are **retroreflective**. An IR illuminator plus an IR-pass filter makes
  the plate glow while the rest of the scene goes dark — this is how the night
  case is solved. Dedicated ANPR cameras work for exactly this reason.
- Short exposure to avoid motion blur (helped by vehicles slowing at a gate).
- Mounting angle under 30° horizontally and vertically.
- If a barrier exists, use its loop detector as a capture trigger instead of
  processing continuously.

### 4.3 Data sources

- **Roboflow Universe / Kaggle** — Turkish plate datasets, immediately
  available; fastest start.
- **UFPR-ALPR** (Brazilian) — contains **frame sequences per vehicle**, which
  makes it the one public set suitable for testing multi-frame voting. Access
  by request form.
- **CCPD** (Chinese, ~300k) — useful for detection pretraining, wrong alphabet
  for OCR.
- **OpenALPR benchmark**, **AOLP** — small, useful for quick sanity checks.

Check licences: many academic sets are research-only, which matters if this
ever becomes a commercial product.

**Split the data strategy:** detection needs **real** images (backgrounds,
angles, context). OCR can be trained on **synthetic** crops — the plate font and
grammar are standardised, so procedurally generated plates with domain
randomisation (perspective warp, blur, noise, glare, dirt, day/night) transfer
well.

For video, filming a real car park entrance with a phone for 30 minutes (day
and night) gives exactly the test footage needed, and recorded video is
replayable — which live cameras are not.

---

## 5. Hardware — deliberately deferred

The Jetson answers exactly one question: **throughput at INT8 on that SoC.**
Nothing else changes.

Critically, **INT8 accuracy loss is essentially hardware-independent** and can
be measured entirely on the RTX 4070. Combined with published Jetson benchmarks
for FPS, the board can be selected without buying it first.

Sizing note if/when it is bought: two lanes (entry + exit) of YOLO + OCR needs
an Orin Nano 8GB class device. The original Jetson Nano will struggle.

---

## 6. The event contract

The seam between the two tracks. Fix this early; everything else depends on it.

```json
{
  "schema_version": "1.0",
  "event_id": "b7f3a1e2-...",
  "device_id": "jetson-01",
  "camera_id": "entry-1",
  "ts": "2026-09-03T14:32:07+03:00",
  "plate": "34ABC123",
  "plate_confidence": 0.94,
  "char_confidences": [0.99, 0.98, 0.71, 0.95, 0.99, 0.88, 0.92, 0.97],
  "direction": "entry",
  "track_id": 4127,
  "crop_ref": "s3://.../b7f3a1e2.jpg",
  "model_version": "yolo-plate-v3"
}
```

Non-negotiable details:

- **`event_id` is an idempotency key.** The edge device buffers events while
  offline and replays them on reconnect; without it, duplicates inflate every
  count — and the LLM layer will report the inflated number confidently.
- **Timestamps carry timezone.** Always.
- **One event per vehicle track**, not per frame.
- **Parse into typed relational columns.** Do not store the payload as a JSONB
  blob and ask the model to parse it later — indexed columns on
  `(plate, ts)` are what make the queries both fast and correct.

---

## 7. Data model — first cut

To be refined; this is a starting point, not a finished schema.

```
persons          id, name, kind (guest|staff|vendor), room_no?, created_at
vehicles         id, plate (unique, canonical), person_id?, label?, is_blacklisted
registrations    id, vehicle_id, person_id, valid_from, valid_to
events           id, event_id (unique), device_id, camera_id, ts, vehicle_id?,
                 raw_plate, plate_confidence, direction, track_id, crop_ref,
                 model_version, match_status (exact|fuzzy|unmatched|pending)
sessions         id, vehicle_id, entry_event_id, exit_event_id?, duration
notes            id, ts, author, body, embedding        -- free text, vector
daily_summaries  id, day, body, embedding               -- generated nightly
```

**Keep person and plate data in their own tables**, referenced by ID from
`events`. This is correct normalisation anyway, and it is also the seam that
makes pseudonymisation, encryption or a retention policy a one-table change
later rather than a migration nightmare.

`sessions` is derived (entry paired with exit) and is where the messiest real
data problem shows up — see §8.

Expose **`v_events`**, a denormalised view with readable column names, as the
only surface the tool layer queries.

---

## 8. Synthetic event generator

Generates months of realistic JSON events. Requirements:

- ~200 vehicles: registered guests, staff, vendors, unknown.
- Realistic rhythm: check-in peak 14:00–18:00, checkout morning, staff shift
  patterns, weekday/weekend difference.
- Injected anomalies: a vehicle staying three days; an unregistered vehicle
  returning five nights running; a 03:00 entry; a blacklisted plate.

**Deliberately inject dirt.** A system built on clean events falls apart in the
field. The generator must produce:

- **Missing exit events** — the number one real-world data quality problem in
  car parks. A vehicle enters, the camera misses the exit, and it stays
  "inside" forever. Ask "how many cars are here now?" and this surfaces
  immediately.
- Duplicate events (store-and-forward replay).
- OCR errors — plates with one corrupted character, to exercise the fuzzy
  reconciliation path.
- Out-of-order arrivals and clock skew.

**Dummy plate convention:** generate the bulk of test data with real province
codes (01–81) so it flows through the real validation path. Reserve codes
**82–99** (which do not exist in Turkey) for plates that are unmistakably
synthetic and for exercising the invalid-province rejection path.

---

## 9. Evaluation

The system is not deliverable at "the chatbot seems to work".

Build a **gold set of ~50 questions**: question, expected tool call, expected
answer. Because the event data is synthetic and self-generated, the expected
answers are **computed by script**, not hand-labelled — this is the main
methodological advantage of starting synthetic.

Run the gold set on every prompt or tool-schema change. Report accuracy the way
the CILEKAI retrieval work was reported (0.15 → 0.95); that table is the
project's strongest evidence.

---

## 10. Deployment shape

```
[Jetson] ──HTTPS──> [server] ──HTTPS──> [LLM API]
                       │ Postgres (bound to localhost only)
                       │ tool-calling layer + panel
                       └──WebSocket──> [operator desktop]
```

- **The model runs via API, never on the server.** CPU inference of a 7B model
  is unusable (~2–5 tok/s); a GPU VPS is 10–20× the cost of API calls at this
  query volume (tens of questions per day). Prompt caching removes most of the
  repeated schema/few-shot cost.
- **The tool-calling layer is glue code and lives with the database.** Queries
  stay local, and Postgres is never exposed to the internet — only the HTTPS
  API is.
- **Sizing:** 2–4 vCPU, 4–8 GB RAM, 40–80 GB SSD is ample. Event volume
  (~10k rows/month) is trivial for Postgres; **plate crops** are what fill the
  disk, so put them in object storage and apply a retention policy.
- Embeddings for notes and daily summaries run fine on CPU as a nightly batch;
  `pgvector` in the same Postgres avoids a second service entirely.
- **The edge keeps working if the server dies.** Store-and-forward means a
  server outage costs the query interface and notifications temporarily, never
  data.
- For a **single site**, an on-premises mini PC is a legitimate alternative to a
  VPS: lower friction, no data leaving the building, and a stronger sales
  argument. A VPS is the right call if remote access is required or if multiple
  sites are anticipated.

---

## 11. On the word "agent"

As specified, the query layer is **tool-calling**, not an agent: the control
flow is fixed and the model chooses a call within it.

It becomes genuinely agentic with two additions, both worth building:

1. **The self-correcting loop** (§3.4) — a real feedback loop.
2. **A nightly investigator** — a job that decides on its own what is worth
   looking into, chains several tool calls, and writes the report. Nobody asks
   it a question; it forms its own plan. This also produces the daily summaries
   that §3.6 depends on, so it earns its place twice.

When describing the project, prefer precision over the label. "Tool-calling
query layer with a self-correcting loop and an autonomous nightly anomaly
reporter" says considerably more than "agent", and it survives the follow-up
question "what did it decide autonomously?".

---

## 12. Explicitly rejected — do not re-propose

Each of these was considered and ruled out for a stated reason.

| Rejected | Why |
|---|---|
| **Vector search / RAG for plate → person matching** | It is an exact key lookup. `34ABC123` and `34ABC124` have cosine similarity ≈ 0.99 — vector search cannot distinguish precisely what must be distinguished, and it returns confident wrong matches. |
| **Naive RAG over raw event rows** | Event records are maximally homogeneous, so their embeddings collapse together and top-k retrieval is effectively random among them. It also cannot count, and time is a range filter, not a similarity. |
| **Free-form text-to-SQL** | Loses safety, reliability, testability and the access-control boundary. Typed tools instead. |
| **Letting the LLM produce numbers** | Counts and aggregates come from SQL. The model narrates. |
| **LLM as notification trigger** | Latency, cost, non-determinism. Deterministic rules engine fires; the model only phrases. |
| **Forking the CILEKAI repo as a base** | Inheriting its structure bends this problem into a document-retrieval shape. Copy deliberately, file by file, into a new repo instead — every line that comes over should be a decision, not an inheritance. |
| **CILEKAI's retrieval stack** (BM25 + RRF + cross-encoder reranker, dual Qdrant+FAISS store, mtime/SHA-256 incremental indexing, semantic cache) | Built for thousands of documents and hundreds of users. Here the corpus is a few hundred procedure docs plus daily summaries, and the query volume is tens per day. `pgvector` in the existing Postgres is sufficient. |
| **Self-hosting the LLM on a cheap VPS** | CPU inference unusable; GPU VPS is 10–20× API cost at this volume. |
| **Controlling the barrier in v1** | A read error in a read-only system is a bad log row. In a barrier-controlling system it is a guest stuck at the gate or an unauthorised entry. Run read-only until field accuracy is proven. |
| **Buying a Jetson before development** | It answers one question (FPS at INT8) that can be estimated; INT8 accuracy loss is measurable on the local GPU. |

---

## 13. Components to carry over from CILEKAI

The existing CILEKAI codebase (internship learning project, no reuse
restrictions) is kept open as a **reference**, not imported as a dependency —
it is an application, not a library.

**Carry over:** LLM client + provider fallback chain; Docker Compose skeleton;
observability/metrics setup; RBAC pattern; Turkish text normalisation helpers;
fuzzy matching utilities.

**Do not carry over:** the entire retrieval pipeline (see §12).

Estimated effort for the operational scaffolding, copying freely: 2–3 days.
Most of the time goes to the project-specific parts — schema, ingestion API,
tool layer, synthetic generator.

**On extracting a shared library:** do not build it first. Write this project,
copy what is needed, get it working, and *then* look back and see which files
came over unchanged. Those are the library. A library is not designed up front;
it emerges once a second real consumer has shaped it — which is exactly what
this project is.

---

## 14. Out of scope for this phase

- Security hardening and KVKK compliance work — no real personal data is
  involved while the system runs on synthetic plates. (It returns the moment a
  camera points at a real car park; §7's table separation is the cheap seam
  that keeps that from being a rewrite.)
- Real deployment, hotel installation, barrier integration.
- Jetson procurement and edge optimisation.
- Multi-site / multi-tenant support.

---

## 15. Immediate next steps

1. Data model — finalise the schema in §7 and the `v_events` view.
2. Ingestion API — accept the §6 event contract, enforce idempotency.
3. Synthetic generator — including the injected dirt from §8.
4. Gold set — ~50 questions with script-computed answers.
5. Tool layer — the five tools in §3.2, with the guardrails in §3.3.
6. Operational scaffolding — carried over per §13.

Steps 1–4 have no dependency on any LLM work and define the shape of everything
that follows.
