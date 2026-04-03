# OpenClaw Hanna Integration Contract

## Purpose

This document defines how OpenClaw integrates with WealthPulse as the Hanna research provider.

The intended model is:

- OpenClaw computes research snapshots on its own schedule
- OpenClaw pushes those snapshots into WealthPulse through ingest APIs
- WealthPulse reads stored research snapshots locally during live runtime
- WealthPulse does not call OpenClaw synchronously on the critical trading path

This is the required direction for the current architecture.

## Core Concept

Hanna is not:

- a stock picker
- a direct order API
- a buy/sell command engine
- a runtime dependency inside the execution path

Hanna is:

- an external research scorer
- a producer of structured research snapshots
- a provider of `research_score`, `components`, `warnings`, `tags`, and optional operator-facing summary

## Why This Model Exists

The WealthPulse live path is layered:

- Layer A: Universe / Scanner
- Layer B: Quant Strategy Score
- Layer C: Hanna Research Score
- Layer D: Risk / Execution Gate
- Layer E: Final Action

Layer C must remain a supporting layer.

That means:

- OpenClaw can enrich a candidate
- OpenClaw cannot create the final trading decision
- Risk Gate always keeps final veto power
- external network availability must not control live entry timing

For that reason, OpenClaw must push data in advance instead of being queried per-symbol in real time.

## High-Level Data Flow

1. OpenClaw cron job runs on a fixed schedule.
2. OpenClaw computes research snapshots for symbols/markets/buckets.
3. OpenClaw sends the snapshots to WealthPulse using ingest APIs.
4. WealthPulse validates and stores the payload.
5. During live scanning, WealthPulse looks up the latest stored research snapshot for each candidate.
6. Layer D evaluates risk.
7. Layer E produces one final state:
   - `review_for_entry`
   - `watch_only`
   - `blocked`
   - `do_not_touch`

## Required Role Boundaries

OpenClaw must do:

- produce structured research scores
- produce stable warning codes
- produce tags
- optionally produce a human-readable summary
- provide freshness metadata

OpenClaw must not do:

- send `BUY`, `SELL`, `BUY_NOW`, `STRONG_BUY`, `ENTER`, or similar commands
- send direct position sizing instructions
- override WealthPulse risk decisions
- bypass Layer D
- send free-form warning strings outside the approved taxonomy

## Required API Shape

The recommended contract is push-based.

### 1. Bulk Ingest API

`POST /api/research/ingest/bulk`

Purpose:

- OpenClaw pushes precomputed research snapshots into WealthPulse

Recommended request:

```json
{
  "provider": "openclaw",
  "schema_version": "v1",
  "run_id": "cron-2026-04-03T09:30:00+09:00",
  "generated_at": "2026-04-03T09:30:05+09:00",
  "items": [
    {
      "symbol": "005930",
      "market": "KR",
      "bucket_ts": "2026-04-03T09:30:00+09:00",
      "research_score": 0.61,
      "components": {
        "freshness_score": 0.80,
        "evidence_strength": 0.67,
        "theme_persistence_score": 0.55,
        "contrarian_risk_score": 0.22,
        "hype_risk_score": 0.41
      },
      "warnings": [
        "already_extended_intraday"
      ],
      "tags": [
        "earnings",
        "semiconductor"
      ],
      "summary": "실적/업황 관련 이슈는 유효하지만 장중 과열 흔적이 있어 추격 주의",
      "ttl_minutes": 120
    }
  ]
}
```

Recommended response:

```json
{
  "ok": true,
  "provider": "openclaw",
  "run_id": "cron-2026-04-03T09:30:00+09:00",
  "accepted": 1,
  "received_valid": 1,
  "deduped_count": 0,
  "rejected": 0,
  "errors": []
}
```

Notes:

- `accepted` is the number of snapshots actually written/replaced in storage.
- `received_valid` is the number of items that passed schema validation.
- `deduped_count` is `received_valid - accepted` (existing-snapshot + in-batch dedupe effects).

### 2. Provider Status API

`GET /api/research/status`

Purpose:

- check whether the latest OpenClaw ingest is fresh enough for live usage

Recommended fields:

- `provider`
- `last_received_at`
- `last_generated_at`
- `last_run_id`
- `freshness`
- `accepted_last_run`
- `rejected_last_run`
- `received_valid_last_run`
- `deduped_count_last_run`
- `source_of_truth`
- `status`

Recommended status values:

- `healthy`
- `degraded`
- `stale_ingest`
- `missing`

### 3. Snapshot Lookup API

`GET /api/research/snapshots/latest?symbol=005930&market=KR`

Purpose:

- operator inspection
- debug support
- UI detail page support

This API is optional for the first phase if the live engine can read directly from storage.

## Required Stored Snapshot Shape

Each stored research snapshot should contain:

- `provider`
- `schema_version`
- `run_id`
- `symbol`
- `market`
- `bucket_ts`
- `generated_at`
- `ingested_at`
- `research_score`
- `components`
- `warnings`
- `tags`
- `summary`
- `ttl_minutes`

Recommended uniqueness key:

- `provider + symbol + market + bucket_ts`

## Warning Code Rules

Warnings must be stable codes, not free-form text.

Recommended codes:

- `headline_stronger_than_body`
- `already_extended_intraday`
- `low_evidence_density`
- `theme_recycled`
- `contrarian_flow_risk`
- `policy_uncertainty`
- `liquidity_mismatch`
- `too_many_similar_news`

`research_unavailable` is a WealthPulse runtime state and should generally be generated by WealthPulse when no usable stored snapshot exists.

## Freshness and Staleness Rules

OpenClaw must provide:

- `generated_at`
- `ttl_minutes`

WealthPulse should derive runtime state as:

- `fresh`: snapshot exists and TTL is valid
- `stale`: snapshot exists but TTL expired
- `missing`: no matching snapshot found

Important:

- stale or missing research must not stop the quant path
- stale or missing research must not directly force a buy or sell
- stale or missing research should degrade Layer C only

## Runtime Interpretation Rules

WealthPulse should interpret OpenClaw output like this:

- `research_score` is a supporting score
- `warnings` can reduce confidence or bias toward `watch_only`
- `summary` is for UI/operator explanation only
- `summary` must not be the primary machine decision input

Examples:

- high quant + fresh research + no warnings => can move toward `review_for_entry`
- high quant + strong warnings => likely `watch_only`
- risk blocked => always `blocked`
- research missing => quant-only continue, with degraded Layer C state

## Explicit Non-Goals

OpenClaw is not responsible for:

- position sizing
- order routing
- account-aware risk logic
- market exposure rules
- duplicate position prevention
- final entry veto

Those belong to WealthPulse.

## Security and Trust Expectations

Recommended protections for ingest APIs:

- shared secret or signed token
- provider field fixed to `openclaw`
- schema version validation
- strict numeric validation for component scores
- strict warning code validation
- payload size limits

## Recommended Implementation Sequence

Phase 1:

- add `POST /api/research/ingest/bulk`
- add storage for research snapshots
- add `GET /api/research/status`
- replace runtime HTTP pull with local stored snapshot lookup

Phase 2:

- add lookup/debug APIs
- add provider heartbeat
- add operator visibility for stale/missing states

## Final Decision

For this project, the correct integration model is:

- OpenClaw pushes
- WealthPulse stores
- WealthPulse reads locally at runtime

The incorrect model for this project is:

- WealthPulse calling OpenClaw synchronously for each candidate on the live path

That pull-based design conflicts with the Layer C concept and weakens execution-path determinism.
