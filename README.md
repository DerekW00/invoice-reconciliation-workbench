# Invoice Reconciliation Workbench

An accounts-payable review desk for exact identifier reconciliation, versioned exception decisions and frozen approved CSV ledgers. Newly authored Python/Django application with PostgreSQL persistence and a server-rendered interface. No payment is sent, and no live model or external financial service is called.

## Run a local demo

Use Python 3.12, uv and PostgreSQL 16. Each checkout has its own .venv.

1. Create a PostgreSQL database named invoice_recon and a role allowed to create a test database. Set PGHOST, PGPORT, PGDATABASE, PGUSER (and PGPASSWORD if your local database requires it).
2. Copy .env.example to .env and edit the local database settings. Export them with: set -a; . ./.env; set +a
3. Run uv sync --frozen, then uv run python manage.py demo.
4. Open http://127.0.0.1:8102 and sign in as reviewer / local-demo-2026. A second account, other-reviewer / local-demo-2026, owns a separate synthetic organization.

DEMO_MODE=1 is required for account seeding. The demo command migrates, seeds idempotently, processes one explanation job and starts Django's local development server bound to 127.0.0.1:8102. Use uv run python manage.py demo --check for setup without starting the server. These are deliberately public local-demo passwords, never external account credentials.

compose.yaml documents an optional user-local PostgreSQL route: docker compose up -d postgres. It was not used for verification. Do not start it when another database already owns local port 15532. The actual verified environment uses a private source-built PostgreSQL 16.15 instance with Unix sockets, peer authentication and no TCP listener. For that environment, source /Users/dw/code/portfolio-python/execution/runtime-env.sh and export PGHOST=/Users/dw/code/portfolio-python/.runtime/pg16/invoice/socket PGPORT=15532 PGDATABASE=invoice_recon PGUSER=dw; do not set PGPASSWORD.

## Walk through the review

- INV-204 shows partial delivery, a price difference and a duplicate fingerprint. The duplicate INV-206 also makes cumulative invoiced quantity exceed the order.
- INV-205 shows a USD invoice against a EUR purchase order. No conversion occurs.
- INV-207 has no matching PO. Identifiers are explicit; no fuzzy matching.
- Open the same invoice in two tabs. Record a resolution with a note in the first tab; attempt approval in the second. The old revision is rejected. Reload, approve the current version and download its frozen ledger.
- INV-203 is a clean approved GBP ledger. Subsequent imports never mutate its approved snapshot.
- Queue an explanation and run uv run python manage.py worker --once in another terminal. The persisted activity records claim/completion and exact exception fact IDs. The worker command without --once polls every two seconds; Ctrl-C stops it. It performs no live provider calls.

The review interface accepts all currently listed discrepancies together, with one required reviewer note; source amounts are never editable. Resolution is acceptance of a discrepancy, not correction of the invoice or authorization to transfer funds.

## Import contract

UTF-8 CSV, exact ordered headers, 256 KiB and 500 data rows maximum. Quoted CSV text is supported. Empty/NUL-containing fields, malformed rows, extra/missing/duplicate headers, duplicate row keys, unsupported currencies and invalid decimals are rejected. Identifiers are case-sensitive and preserved exactly. Newlines in quoted identifiers are preserved and spreadsheet-safe on export.

| Type | Exact header |
|---|---|
| po | vendor,po,line,currency,quantity,unit_price |
| receipt | vendor,po,line,receipt,quantity |
| invoice | vendor,invoice,po,line,currency,quantity,unit_price |

Only USD, EUR and GBP are supported. Quantities/prices are finite, nonnegative Decimals, at most four decimal places and at most 1,000,000,000. Extended line amounts round once to 0.01 using ROUND_HALF_UP; 3 × 0.335 = 1.01. Totals sum rounded line amounts separately by currency. Currency disagreement becomes an exception. There is no FX conversion or implicit mixed-currency sum.

Canonical row ordering and decimal spelling determine the batch digest. An identical retry returns the prior batch. An existing business key under different content is rejected atomically; invoice numbers cannot be overwritten even before approval. Receipts have explicit receipt IDs and may accumulate. All invoice quantities with the same organization/vendor/PO/line are counted conservatively, including unapproved invoices. New source records increase the organization's source revision and invalidate unapproved review acceptance on the next review/approval.

## Verify

Run make verify against a real PostgreSQL database with test-database creation permission. It checks the frozen dependency lock, Django/migration drift, Ruff lint/format, mypy, the entire default pytest suite and eight frozen functional fixture evaluations. SQLite is not supported.

Install the pinned Playwright browser with uv run playwright install chromium (and the documented system libraries for your machine), then run make browser. In the verified VPS environment the browser/runtime already exists: source the runtime-env.sh above. Browser tests use Django's local live server and a private test database, then write screenshots and a downloaded ledger to a newly created writable temporary directory. To retain artifacts use BROWSER_EVIDENCE_DIR="$PWD/.browser-evidence" make browser (ignored locally), or choose any writable destination. Verified VPS gates explicitly supply the canonical external evidence directory; shared runtime infrastructure is unchanged.

See docs/architecture.md, docs/tradeoffs.md, docs/verification.md, docs/data-provenance.md and docs/contributions.md. This is a local portfolio product, with observed checks documented separately from unmeasured production behavior and live-model quality.

Same-host demo cookies use `invoice_recon_session` and `invoice_recon_csrf`, so the three loopback products can retain separate sessions and CSRF forms across ports. Cookie domain/path and CSRF enforcement retain their normal Django scope.
