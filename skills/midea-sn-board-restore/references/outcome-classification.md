# Outcome classification

Classify an incident from the strongest integrity-checked evidence available. The classification describes what is known; it does not authorize another write.

## Evidence hierarchy

From strongest to weaker:

1. An integrity-checked protocol reply that decodes to the exact 22-digit target SN.
2. A cold-rebooted official App showing an explicitly model-compatible normalized target identity, with device functions operating normally.
3. A complete integrity-checked acknowledgement or non-target readback.
4. Raw received bytes, TCP connection status, socket close, timeout, or zero bytes.

Only item 1 proves exact protocol readback. Item 2 can support a separate App-verified outcome when its strict conditions pass. Items 3 and 4 never prove the target SN was written.

## States

| State | Required evidence | Required action |
|---|---|---|
| `READ_ONLY_ALREADY_CORRECT` | Before any write reservation, a read-only query returns a complete integrity-checked response that decodes to the exact target SN. | Create and preserve package/global permanent no-write markers. Stop; do not write. |
| `READ_ONLY_INVALID_ENCODING` | Before any write reservation, a complete CRC/checksum-valid compatible response contains a 22-byte identity payload that cannot decode to exactly 22 ASCII digits. | Create and preserve package/global `READ-INVALID-DO-NOT-WRITE` markers. Stop; do not write; obtain authorized service review. |
| `DIAGNOSTIC_ZERO_RESPONSE` | A structurally read-only query receives zero usable response bytes and no write reservation exists. | Record the result. Explain that it is compatible with several conditions and does not prove a blank board. Continue only through all eligibility gates. |
| `WRITE_RESERVED` | Atomic package/global markers were created and the runtime has not yet recorded whether send began. | Treat the incident as consumed. Recover audit facts, never delete the reservation, and do not rerun the write. |
| `WRITE_SENT_READBACK_VERIFIED` | Exactly one write was sent, then a later read-only reply passes transport, padding, inner CRC/checksum, decoding, and exact target comparison. | Stop. Preserve evidence; never rerun the write. |
| `WRITE_SENT_APP_VERIFIED` | Exactly one write may have been sent; after a cold power cycle the official App shows the expected identity under an explicitly verified compatible model, and normal device controls work. No contradictory integrity-checked readback exists. | Record the App evidence and compatibility basis. Stop; never rerun the write. |
| `WRITE_SENT_UNKNOWN` | Send began or may have begun, but no exact integrity-checked target readback and no qualifying App verification exists. This includes timeout, zero bytes, partial send, exception, crash, or only an acknowledgement. | Treat the write as possibly applied. Do not retry for this incident. Use only read-only checks, cold reboot, App verification, or authorized service diagnostics. |
| `WRITE_SENT_MISMATCH` | After the write attempt, an integrity-checked read-only response decodes to a valid SN different from the exact target, or trusted App evidence shows a contradictory identity. | Stop immediately. Preserve all bytes and metadata. Do not attempt to overwrite it; escalate to authorized service review. |
| `WRITE_NOT_SENT_BUT_LOCKED` | The durable reservation was created, but local audit evidence proves failure occurred before the socket write began. | Preserve the lock and incident record. Do not unlock automatically; require manual code/audit review and a separately authorized remediation decision. |

`WRITE_RESERVED` is a transient/audit state. Once evidence establishes whether send began, refine it to `WRITE_NOT_SENT_BUT_LOCKED`, `WRITE_SENT_UNKNOWN`, `WRITE_SENT_READBACK_VERIFIED`, `WRITE_SENT_APP_VERIFIED`, or `WRITE_SENT_MISMATCH` without deleting the original reservation fact.

## Rules for zero-byte diagnostics

`RAW_RECEIVED_BYTES=0` means only that the client received no bytes during the bounded observation. It can be consistent with a blank replacement board, a protocol/version mismatch, timing, a module that accepts but does not answer that query, routing/interface behavior, or another implementation detail.

Therefore:

- do not label the board blank;
- do not label a write failed;
- do not retry a write after zero-byte verification;
- use the explicit confirmation phrase `ZERO-BYTES-IS-NOT-PROOF` before a first eligible write.

## App-verified classification

Use `WRITE_SENT_APP_VERIFIED` only when all of these are documented:

1. The write attempt belongs to the same incident, appliance, target body SN, service hotspot, and model.
2. The appliance was fully powered off and cold-started after the attempt.
3. The official App connected to that appliance after the reboot.
4. The displayed SN matches a normalization already verified for that exact compatible model/firmware family.
5. Normal controls work and no trusted evidence contradicts the target.

For the documented compatible case, the App displayed:

```text
000000 + target-22-digit-body-SN + 0000
```

This is a historical verification relationship, not a generic parser or generator input rule. Do not automatically remove six leading and four trailing zeroes from a different App value. Do not assume every model uses this representation.

Store App evidence as human-observed evidence with timestamp, model, screenshot reference, target comparison, cold-reboot confirmation, and functional-check notes. Do not relabel it as protocol readback.

## Interpreting common log lines

- `Connected ... to 192.168.1.1:6444` proves a TCP connection only.
- `ONE_WRITE_REQUEST_SENT` means the implementation began its one allowed send. It does not prove receipt, persistence, or correct value.
- `WRITE_ACK_COUNT=1` is acknowledgement evidence only.
- `COMPLETE_FRAMES=0` means no complete parsable transport frame was available.
- `RAW_RECEIVED_BYTES=0` is absence of received bytes, not a device state.
- `No SN response after three read attempts` is an inconclusive read-only result.
- `WRITE_RESULT_UNKNOWN` must be taken literally: do not rerun write mode.

## Decision sequence

1. Determine whether a write reservation exists.
2. If none exists, check whether a pre-write read-only result proves the exact target, a valid mismatch, or an invalid encoded identity. All three are terminal no-write states for that incident.
3. If a reservation exists, determine from append-only audit facts whether send began.
4. If send began, look first for exact integrity-checked readback, then qualifying App evidence, then contradiction.
5. If none exists, classify unknown; do not infer success or failure from acknowledgement or silence.
6. Preserve the most conservative lock state for the incident in every branch.

## Subsequent physical board replacement

A later real board replacement is a new incident, not a retry. Before generating anything, require the previous incident ID, fresh evidence of the later board replacement, the current live hotspot, exact model, and the trusted original 22-digit body SN. The new incident receives new markers and never modifies or reuses the old incident's locks.
