# ACC-BETA13-SSH-002: healthy SFTP fails when recovery is disabled

**P1 / release acceptance blocker.** With core 2.9.0b24 and Paramiko
4.0.0, an isolated zero-recovery check failed even on a healthy SFTP
connection. The shared worker remained configured with 900 seconds of
recovery; this was not a change to that configuration.

## Failure and evidence

`retry()` bypasses recovery at zero, but `sftp_timeout()` still sets the
channel operation timeout to zero. Paramiko treats zero as non-blocking, so
even a healthy SFTP operation can raise `TimeoutError`.

A fresh-client, zero-only reproduction ruled out state left by an earlier
probe. A diagnostic-process guard for disabled recovery restored healthy
script publication. It was not a product fix and did not patch installed
files. Positive-recovery publication succeeded without the guard.

## Proposed correction

In the core `sftp_timeout()` helper, when recovery is disabled, yield the
SFTP client without changing its channel timeout. The helper also covers
download paths, which need equivalent regression coverage.

## Acceptance

- With fresh clients and zero recovery, preserve both an unset and a positive
  pre-existing SFTP timeout; healthy upload and download must work.
- A genuinely closed transport must receive exactly one attempt at zero
  recovery.
- Positive recovery and its native timeout bounds must continue to work.
- Repeat the check against the published package and deployed runtime;
  diagnostic guards alone do not constitute product acceptance.
