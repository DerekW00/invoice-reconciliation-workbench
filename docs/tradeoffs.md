# Decisions and limits

- A single organization row serializes imports, reconciliation and reviews. This keeps the lock graph easy to inspect and avoids approval/import races; high-volume organizations would need measured narrower locking.
- Any successful new source batch invalidates all unapproved versions in that organization. This is conservative and can require a fresh note for an unrelated import. Approved ledgers stay historical and frozen.
- Invoice numbers are unique per vendor/organization. Different invoice numbers with identical normalized financial fingerprints create duplicate exceptions. Business-key conflicts reject rather than overwrite or silently merge.
- All imported invoice quantities count toward PO/receipt consumption, even before approval. Potential duplicate drafts can therefore produce additional quantity exceptions. Reviewers can see and explicitly accept them.
- One note accepts every exception shown in that invoice version. There is no partial acceptance, payment execution, tax calculation, FX, credit note workflow, OCR or arbitrary document extraction. Corrections arrive with new explicit business identifiers.
- Mixed-currency invoices have per-currency totals and an exception. Approval can record an explicit acceptance but never converts or sums the currencies.
- Imported identifier case and spacing remain exact. CSV is a documented synthetic schema; arbitrary vendor formats are outside this release.
- App-level append-only versions/audit are not a tamper-proof external accounting record. A privileged database administrator can change data. No compliance certification is claimed.
- Jobs are at-least-once computations with fenced publication. Fixture work is deterministic, short and effect-free. A future external provider may complete after cancellation; a late result cannot publish, but remote billing/cancellation would need separate accounting. Unknown usage is not treated as zero.
- The UI uses Django development serving for the local demo, with local HTMX. Production hosting, TLS, operational monitoring, database backup/recovery and live-model quality are unmeasured and outside this delivery.
