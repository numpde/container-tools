# linux-idmap 0.3.4

The CLI now rejects a successful exit when cancellation arrives while it emits
identity projections or restores the caller's signal handlers. It reports late
cancellation with the confirmed-retired probe identity and exits with status
130. Existing failures keep their original status, including status 3 when
retirement remains unresolved. The Python probe API and resource policy are
unchanged.

Consumers must check the final exit status before using stdout. Interrupted
publication can leave partial or complete output; those bytes do not authorize
filesystem grants or subsequent work.

Regression cases exercise SIGINT, SIGTERM and SIGHUP during publication and
handler restoration in both output modes. The containerized package suite
passes 255 tests with two skips, and all 211 repository quality checks pass.
Release preparation separately qualifies the exact built wheel and source
archive and retains its logs with the release artifacts.
