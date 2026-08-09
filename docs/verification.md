# Verification

The required gate is make verify; the focused real-browser gate is make browser. Both run inside the repository's own .venv via uv. PostgreSQL is required; SQLite is deliberately absent.

Behavioral contracts cover ROUND_HALF_UP, non-finite/negative/overprecision values, canonical retries, duplicate/conflicting keys, malformed late rows, byte/row/header caps, missing PO, partial receipt, currency mismatch, price discrepancy, duplicate fingerprints, cumulative quantities, required notes, stale review/approval, frozen exports, real two-thread approval/resolve/import races, tenant object scoping, CSRF, formula injection including Unicode whitespace, durable fixture jobs, invalid citations, explicit recorded missing/unknown usage, cancellation, reclaim, lease/deadline expiry and clock rechecking after a real lock wait.

The Playwright Chromium journey logs in, imports all three synthetic CSV types, inspects source exceptions, records acceptance, opens a stale approval conflict, approves a refreshed version, downloads a frozen ledger and checks persistence after reload. Screenshots include the requested 1200×900 quality-70 JPEG workflow view.

Actual verification uses CPython 3.12.15 and private source-built PostgreSQL 16.15 at the project socket, TCP disabled. Playwright 1.64.1 Chromium and source-built browser libraries are provided by the project runtime. No container runtime, shared database, live provider call or public listener is used.

RED/GREEN logs and screenshots live outside the repository in /Users/dw/code/portfolio-python/python-evidence/invoice-reconciliation-workbench. See implementation-report.md there for exact final commands/counts/HEAD and any limitations. Infrastructure/setup failures are not counted as behavioral RED; initial missing service stubs and absent UI/commands are labeled explicitly. The default pytest run excludes the browser marker so make verify does not silently require browser system libraries; make browser must also pass for delivery.
