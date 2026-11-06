# Pure, injected-clock expiry engine with a hand-written RFC 5545 writer

Status: accepted (generated, pending human review)

## Context

Teams track certifications, licences and consumables whose expiry depends on a date, a usage count or time after first use. Calendar libraries write ics files but know nothing about expiry rules. The output must be reproducible byte for byte and safe against hostile text, and the library should have no runtime dependencies.

## Decision

Model items and rules as frozen, validated dataclasses and implement evaluation, reminder generation and usage recording as pure functions that take today and dtstamp as arguments. Write the small RFC 5545 subset needed (VCALENDAR, VEVENT, VALARM) by hand: CRLF endings, octet-based folding that never splits a UTF-8 sequence, TEXT escaping with control characters removed, and UIDs derived with uuid5 from a fixed namespace and the item id, date and kind. Every entry point enforces named size limits and raises a single ExpiryError type with a stable code.

## Consequences

Output is deterministic and easy to test with golden text, there are no dependencies to audit, and hostile input cannot inject content lines or exhaust memory. The cost is a deliberately narrow iCalendar feature set (dates only, no recurrence, no time zones, no parsing) and the maintenance of a small writer instead of relying on a third-party library.
