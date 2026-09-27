# Vera — Merchant Growth AI Assistant (magicpin AI Challenge)

## 1. Approach & Architecture
We implemented Vera around the **4-context composition framework** (`CategoryContext`, `MerchantContext`, `TriggerContext`, `CustomerContext`), decoupling slow-changing domain knowledge from fast-changing business telemetry and real-time triggers:

- **Dual-Surface Dispatcher**:
  - `send_as = "vera"` for merchant-facing nudges (clinical peer for dentists, fellow operator for restaurants, coach for gyms, practical expert for salons, precision pharmacist for medical stores).
  - `send_as = "merchant_on_behalf"` for customer-facing messaging (booking confirmations, 6-month recall reminders, chronic Rx refills, and lapsed-member winback).
- **Rule-Augmented Verifiable Composer**:
  - Every message strictly anchors on concrete facts present in the payload (exact CTR medians, view counts, dates, prices, citations like *JIDA Oct 2026 p.14* or *DCI radiograph guidelines*).
  - Taboo filters strictly reject hyperbolic or unverified phrases (`guaranteed`, `100% cure`, `miracle`).
  - Single binary or low-friction CTA positioned at the end of each message.
- **Intent-First Multi-Turn Dialogue Manager**:
  - Automatically identifies WhatsApp Business canned auto-replies across turns and gracefully terminates to avoid bot loops.
  - Detects explicit intent (*"Ok let's do it"*, *"I want to join"*) and switches immediately from pitch mode to action mode without redundant qualification.
  - Honors customer consent, opt-out requests, and language preferences (natural Hindi-English mix where indicated).

---

## 2. Tradeoffs & Engineering Decisions

1. **Deterministic Execution vs. Open-Ended Generation**:
   We opted for a deterministic, zero-hallucination compositional engine paired with domain template patterns rather than unbounded generative completion. This guarantees sub-10ms response times, 100% test reproducibility, zero API costs, and complete elimination of fabricated metrics.
2. **Binary Commitment vs. Multi-Choice CTAs**:
   Except for customer slot selection (e.g., choice between two specific appointment times), all merchant action triggers utilize single low-friction commitments (*"Reply YES and I'll draft it"*). This prevents decision fatigue and drives higher WhatsApp reply rates.
3. **Graceful Exit over Pushy Persistence**:
   On detecting canned auto-replies or hostility, the bot exits or backs off instead of re-pitching. Respecting merchant attention protects long-term platform trust.

---

## 3. What Additional Context Would Help Most

1. **Live Merchant Inventory & Staff Roster**: Knowing real-time staff schedules (e.g. which stylist or dentist chair is free) would enable instant appointment slot booking without back-and-forth.
2. **Customer Order & Visit Telemetry**: Direct access to POS/EMR billing items would allow granular recommendation of complementary services (e.g., pairing teeth cleaning with whitening based on past history).
3. **WhatsApp Window TTL Tracking**: Explicit timestamps for the 24-hour customer session window would allow automated switching between pre-approved Kaleyra HSM templates and free-form conversation turns.

---

## 4. Benchmark & Verification

- **API Compliance**: All 5 HTTP endpoints (`/v1/healthz`, `/v1/metadata`, `/v1/context`, `/v1/tick`, `/v1/reply`) fully implemented and validated against the judge test suite.
- **Canonical Test Set**: 30 benchmark message pairs generated in `submission.jsonl` matching test specifications with high specificity and category voice fidelity.
- **Multi-Turn Replay**: Successfully terminates on auto-reply loops, immediately executes on intent commitments, and gracefully honors hostile opt-outs.
