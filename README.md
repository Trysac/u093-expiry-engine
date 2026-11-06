# expiry-engine

[![PyPI version](https://img.shields.io/pypi/v/trysac-expiry-engine)](https://pypi.org/project/trysac-expiry-engine/)
[![License: MIT](https://img.shields.io/pypi/l/trysac-expiry-engine)](LICENSE)
[![CI](https://github.com/Trysac/u093-expiry-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/Trysac/u093-expiry-engine/actions/workflows/ci.yml)

Track expirations by date, usage count or time after first use, generate reminders from rules and export them as RFC 5545 iCalendar

## Problem

Describe in two or three sentences the concrete problem this utility solves, who hits it, and what
they do today without it. Replace this paragraph when the first real feature lands.

## Install

```sh
pip install trysac-expiry-engine
# or
uv add trysac-expiry-engine
```

Requires Python 3.10 or newer. No runtime dependencies.

## Usage

```python
import expiry_engine

# normalize() trims surrounding whitespace and lower-cases the text.
print(expiry_engine.normalize("  Hello World "))  # -> "hello world"

# Blank input is rejected explicitly instead of returning an empty string.
try:
    expiry_engine.normalize("   ")
except ValueError as exc:
    print(f"rejected: {exc}")
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md) and [decisions](docs/decisions/)
- [Testing](docs/TESTING.md) and [security](docs/SECURITY.md)
- [Project record](docs/PROJECT.md) and [stack](docs/STACK.md)
- [Changelog](CHANGELOG.md) and [contributing guide](CONTRIBUTING.md)

## License

[MIT](LICENSE) (c) 2026 Miguel Gomez
