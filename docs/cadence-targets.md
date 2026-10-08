# Cadence targets

Cadence is not a default training compliance metric.

For ordinary cycling sessions, absence of a cadence target means cadence is
self-selected by the athlete.

Recorded cadence remains telemetry only and must not:
- reduce compliance,
- create a training deviation,
- influence Coach Decision.

An explicit cadence target is used only when cadence itself is part of the
training stimulus.

Supported cadence modes:
- self_selected
- range

Supported cadence intents for range targets:
- low_cadence
- high_cadence
- technique
- custom

Example range target:

    {
      "cadence": {
        "mode": "range",
        "min_rpm": 55,
        "max_rpm": 65,
        "intent": "low_cadence"
      }
    }

The intent is explicit and must not be inferred from universal RPM thresholds.

For structured workouts, cadence targets should normally be attached to the
specific workout step that carries the intended cadence stimulus.

Future interval analysis must assess cadence from the matching time-series
segment.

Whole-session average cadence must not be used to judge cadence-specific
intervals.
