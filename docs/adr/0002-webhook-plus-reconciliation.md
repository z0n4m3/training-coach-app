# ADR 0002 — Webhook plus reconciliation

Status: Accepted

## Context

Webhooks are useful for low-latency updates, but delivery cannot be treated as an exactly-once guarantee and some upstream source paths can behave differently.

## Decision

When webhooks are introduced, they are only triggers. The source of truth is recovered via idempotent API sync. The system will also run periodic delta sync and a full training-week reconciliation before weekly review.

## Consequences

- Missing or repeated webhook deliveries do not corrupt state.
- Sync jobs need stable provider IDs and upserts.
- Weekly review is based on reconciled data.
