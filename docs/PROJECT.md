# Project record

## Objective

Provide a small, deterministic library that computes expiry state and reminders from dates, usage counts and time after first use, and exports the reminders as a standards-compliant RFC 5545 iCalendar document.

## Scope

- In scope: the public API documented in [README.md](../README.md), typed and tested.
- Out of scope: persistence, notifications, recurrence rules, time zones (dates only), parsing of `.ics` files, and anything that needs runtime dependencies or I/O without an accepted ADR.

## Timeline

| Date | Event |
|---|---|
| 2026 | Repository created from the factory utility template. |

## Effort metrics

Measured values only; a value that has not been measured stays "pending measurement".

| Metric | Value |
|---|---|
| Tokens (input / output) | 567464 / 84446 |
| Hours (human) | pending measurement |
| Cost (USD) | 0.7533 |

## Factory run u093 (measured from API usage)

| Phase | Model | Batch | Input | Output | Cache write | Cache read | Cost (USD) |
|---|---|---|---|---|---|---|---|
| generation | claude-sonnet-5-5 | yes | 2793 | 69623 | 0 | 4246 | 0.3513 |
| fix-1 | claude-sonnet-5-5 | no | 6 | 451 | 6187 | 40269 | 0.0240 |
| fix-2 | claude-sonnet-5-5 | no | 6 | 958 | 7684 | 41751 | 0.0330 |
| fix-3 | claude-sonnet-5-5 | no | 12 | 3041 | 9341 | 92049 | 0.0630 |
| fix-4 | claude-sonnet-5-5 | no | 6 | 699 | 7987 | 41836 | 0.0312 |
| fix-1 | claude-sonnet-5-5 | no | 10 | 1721 | 8333 | 74306 | 0.0455 |
| audit | claude-sonnet-5-5 | no | 10 | 2046 | 22699 | 89130 | 0.0861 |
| fix-2 | claude-sonnet-5-5 | no | 8 | 1590 | 10414 | 60149 | 0.0480 |
| docs | claude-haiku-5-5 | no | 120877 | 4317 | 0 | 0 | 0.0712 |

Total: $0.7533. Prices: Anthropic list prices.
