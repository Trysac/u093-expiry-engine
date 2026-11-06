# Security notes

## Threat model

`trysac-expiry-engine` is a pure library without I/O.

Defended:

- **Invalid input**: every public entry point validates types and ranges and raises `ExpiryError` with a stable code. Item and Rule validate in `__post_init__`.
- **Oversized input**: items (100,000), rules (1,000), reminders (100,000), horizon (3660 days), offsets per rule (10) and text fields have hard caps; exceeding them raises code `limit` or `invalid_rule`.
- **Control characters in text**: TEXT values in iCalendar output have backslash, semicolon, comma and newline escaped, and other C0 control characters and DEL are removed.
- **Error message leakage**: messages are clipped to 200 characters.
- **Non-deterministic output**: clocks are injected, so the same input yields the same text.

Not defended:

- **Supply chain**: a compromised dependency or CI action. Mitigation: no runtime dependencies, Dependabot updates, actions pinned to major versions, minimal workflow permissions.
- **Leaked secrets**: tokens committed by mistake. Mitigation: `gitleaks` runs in the local gates and in CI; `.env` files are git-ignored.
- **Calendar consumers**: the library does not sanitize content for the program that opens the `.ics` file.
- **Resource use within limits**: an input close to the caps can still use substantial memory and time.

## Publishing

Releases are published to PyPI with trusted publishing (OIDC) when available, never with a long-lived token stored in the repository.

To report a vulnerability, see [SECURITY.md](../SECURITY.md).
