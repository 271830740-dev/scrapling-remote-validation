# Scrapling remote parser validation

Public synthetic fixtures only. This repository performs an offline parser check of Scrapling 0.4.15 on a GitHub-hosted Ubuntu runner. It does not contact travel websites, collect hotel prices, solve challenges, or use account credentials. No crawling or parser test runs on the operator's computer.

Run the `Offline parser validation` workflow manually. It pins the script's exact commit, records the GitHub run/job identity and runner environment, installs only the parser distribution from PyPI, and publishes its raw result and hashes as a one-day artifact. A passed check proves only the covered synthetic parser behavior, not production data quality or platform access.

`guarded_extraction.py` additionally rejects ambiguous cards, conflicting source supplier/hotel/room/rate IDs, duplicate prices, unknown or conflicting currencies and malformed amounts. `remote_quote_guard_check.py` checks these failure cases against fictional HTML on the same remote runner. Its data attributes are a synthetic source contract, not a travel-site adapter. Even a valid extracted amount explicitly remains a candidate requiring complete request, stay, guests, meals, cancellation, final-price, fee, eligibility, freshness and original-source verification.
