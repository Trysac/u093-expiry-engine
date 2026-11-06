# Testing

## Running

```sh
uv run pytest --cov=expiry_engine   # tests with coverage report
uv run python scripts/check.py      # every gate, as CI and the factory run it
```

## Policy

- Branch coverage of `src/expiry_engine` must stay at or above 80 %; the gate fails below it.
- Tests exercise the public API (`import expiry_engine`) and assert observable effects: return values, raised exceptions and their codes.
- Tests are deterministic: no network, no wall clock, no dependence on test order.

## Layout

- `tests/test_expiry_engine.py`: tests of the public API, covering the acceptance literals for evaluate, record_use, upcoming_reminders, to_ical, folding, UID derivation and the `invalid_item` and `limit` errors.
