# linux-idmap 0.3.2

This release makes the shared identity package conform to its consumers' strict
source checks. The public Python API, CLI values and JSON formats, exit statuses,
runtime dependencies, and probe isolation policy are unchanged.

Startup failures retain their original exception or explicitly chain a translated
error. If a supervised process group has vanished, cleanup still reaps its owned
leader. Shell value output keeps its exact single-line representation.

Source qualification passed 245 package tests, with two isolated-user-namespace
cases skipped because the checker blocks `unshare`, and all 417 repository
checks. The unchanged consumer Ruff checks also pass. Exact wheel and source
archive qualification is recorded in the prepared release artifact receipts.
