# Contributing

Use Python 3.12 and PostgreSQL 16, with a dedicated local database. Follow the [README setup](README.md#local-setup), then run `make verify` and the separate `make browser` gate for workflow changes. Keep changes focused and explain the behavior and verification in your pull request.

Use newly synthetic fixtures only. Preserve exact-money, tenant, stale-review and frozen-export invariants; keep the fixture provider separate from financial authority. Do not include credentials, employer code or private transaction data. Preserve third-party license notices.

See [architecture](docs/architecture.md), [tradeoffs](docs/tradeoffs.md) and [contribution provenance](docs/contributions.md). Contributions are made under the project [MIT License](LICENSE).
