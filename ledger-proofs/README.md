# ledger-proofs/

OpenTimestamps proofs for the sealed forecast ledger ([FORECASTS.md](../FORECASTS.md)), written by
`schelling seal` (Session 17, D17.2). Each proof is content-addressed by the ledger's SHA-256:
`FORECASTS.md-<sha12>.ots` stamps the exact ledger bytes present at that seal.

A proof is a Bitcoin-anchored timestamp: it proves the ledger content existed at or before a given
time and cannot be backdated — not even by the repository owner. To verify one:

```sh
pip install opentimestamps-client
ots upgrade ledger-proofs/FORECASTS.md-<sha12>.ots      # once the Bitcoin attestation confirms
ots verify ledger-proofs/FORECASTS.md-<sha12>.ots -f FORECASTS.md
```

Proofs are committed as part of the audit trail. If the `ots` client is unavailable when a seal
runs, anchoring is a logged no-op and no proof is written for that seal — the SHA-256 commitment in
FORECASTS.md still stands on its own.
