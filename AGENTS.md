# Training Coach App — engineering rules

## Product purpose
This application is a coaching workflow layer above Intervals.icu:

plan -> execution -> athlete response -> interpretation -> decision -> next plan

Intervals.icu remains the main upstream source of training and wellness data.

## Core domain rules
- A real training session is represented by CanonicalSession.
- Multiple source activities may represent one CanonicalSession.
- Duplicate handling must merge data at metric level, not simply choose one complete source activity.
- Preserve provenance for every selected canonical metric.
- Garmin, MyWhoosh, Zwift, Wahoo and other sources must not be assumed universally superior; source quality is metric-specific.
- Duplicate detection must be idempotent.
- Late-arriving duplicate activities must enrich/rebuild the existing physical session rather than create a second one.
- Planned training and coaching decisions will later be separate from source activity storage.

## AI architecture
- LLMs must not be the primary calculator of training metrics.
- Deterministic analytics calculate metrics first.
- AI interprets structured evidence and proposes coaching decisions.
- Important plan, FTP and zone changes require athlete approval.

## Security
- Never commit .env files, API keys, OAuth tokens or other secrets.
- Intervals credentials are backend-only.
- Tests and CI must never require the real athlete API key.

## Development
Before considering a change complete:
1. backend tests must pass,
2. Alembic migrations must apply to PostgreSQL,
3. FastAPI health endpoint must respond,
4. frontend must build successfully when affected.

Prefer small, testable changes.
