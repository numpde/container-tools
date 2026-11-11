# linux-idmap 0.3.3

This release reconciles the source-quality and process-cleanup fixes published in 0.3.2 with the optional resource policy developed in PR #4. The published 0.3.2 tag and assets retain their original meaning; the earlier 0.3.2.dev0 candidate is not a released alternative.

The canonical public resource type is `linux_idmap.probe.ProbeResources`. An optional final `ProbeRequest.resources` field selects exact memory and swap, process-count and CPU ceilings. Omitting it preserves existing request construction and Docker options. The CLI requires all three resource flags together; invalid or partial policies fail before dispatch. Selected ceilings must match integer inspect evidence before the probe starts. A confinement mismatch cannot return maps and preserves the existing conservative retirement and recovery-handle behavior.

The combined implementation retains the 0.3.2 exception chains, process reaping, isolation, ownership checks and repository policy rules. Resource tests cover constructor boundaries and types, old positional requests, complete CLI selection, inspected mismatches and exact fractional CPU conversion. Release preparation records qualification of the exact wheel and source archive; real-engine evidence records the selected daemon and its observed coverage separately.
