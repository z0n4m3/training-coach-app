# ADR 0001 — Canonical Session

Status: Accepted

## Context

Intervals.icu may contain several recordings of one physical session, e.g. Garmin + MyWhoosh or Garmin + Zwift. Choosing one complete file globally discards useful metrics that may exist only in the other recording.

## Decision

Introduce `canonical_sessions` as the representation of one physical workout. A canonical session can reference multiple `source_activities`. Metric selection is performed independently per metric and persisted in `session_metric_sources`.

## Consequences

- Weekly volume/load counts one canonical session, not every recording.
- Original source activities remain immutable/auditable.
- We can prefer Garmin for physiological metrics while taking distance from MyWhoosh.
- Manual duplicate decisions can be added later without destructive deletes.
