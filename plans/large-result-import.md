# ACC-BETA13-IMPORT-001: long default result imports fail

**P1 / release acceptance blocker.** Medium and large detached workflows
using default original-pixel comparison failed during OMERO result
registration. The observed runs used stack beta.13, core/scripts 2.9.0b24,
importer 1.5.0b12 and Shallower 0.1.0b9. The medium and large cases contained
846 and 2,844 images respectively.

## Failure and evidence

The Slurm analysis completed, result files were copied to permanent storage,
and extraction succeeded. The failure occurred during the subsequent OMERO
result import, after native shallow-plate registration resolved the result to
its managed source pixel backing. Both imports then reported
`Ice::ObjectNotExistException` on `getQueryService`.

The failing service-factory proxies were scoped to OMERO sessions that had
already timed out and had their servants removed. This establishes the direct
failure mechanism, but not why the importer allowed the sessions to expire.
There is no evidence that wrong field mapping, changed pixels, a missing
canonical source, or a verification exception caused these failures.

Result files and any partial registrations must be preserved and inventoried
before a supported finalization retry. Do not blindly retry registration or
rerun the analyses.

## Investigation and acceptance

1. Establish why the sessions expire and implement supported keepalive or
   reconnect behavior without retaining stale service proxies. Preserve and
   verify the intended session group.
2. Inventory partially registered objects for the affected import orders,
   preserve evidence, and reconcile ownership before retrying finalization.
3. Demonstrate long processing followed by successful native registration,
   without stale proxies and with the intended session group preserved.
4. Verify mandatory provenance, complete image and WellSample mapping, all
   decoded reference pixels and native labels, exactly one result registration,
   and terminal source-event durability. Record recovered imports as recovered,
   not as clean performance observations.
5. Obtain clean medium and large default-comparison measurements on corrected,
   released components; recovery of an existing result is not a fresh
   end-to-end run.

A separate error while recording the large workflow failure involved an
external descriptor fetch exhausting retries. It was not the cause of the
earlier import exception; terminal event and projection durability still need
independent investigation.
