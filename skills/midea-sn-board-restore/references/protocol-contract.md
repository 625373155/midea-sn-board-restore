# Protocol and package contract

This document defines the invariants for the verified Midea air-conditioner body-SN recovery implementation. `scripts/protocol_reference.py` is the executable oracle and `scripts/test_vectors.json` is the immutable regression corpus. A template or runtime that disagrees with either must not be shipped.

## Fixed scope and endpoint

- Reviewed model allowlist for public v0.2.0: `KFR-26G/WXAA2@` only. A service hotspot is not compatibility proof for another model or firmware family.
- Product type byte: `0xAC` (air conditioner).
- Target host and port: `192.168.1.1:6444` only.
- Network identity: the package's exact, case-preserved `midea_test_<12 hex>` SSID and, when captured, exact BSSID. Runtime Wi-Fi binding requires exact SSID equality. A separate lowercase/alphanumeric normalization is used only for device-key/history lookup; generation rejects spaced variants.
- Interface: bind the TCP client to the IPv4 address on that service WLAN route. Do not rely on the default route.
- Identity input: one hardcoded, trusted 22-ASCII-digit body SN. There is no runtime target-SN argument.

Do not generalize this contract to a different product type, endpoint, opcode, or cloud service.

## Body-SN encoding

Let `v[i] = ASCII(sn[i]) - 0x30` for the 22 validated digits. `S1`, `S2`, and the ten permutation rows `P` are defined exactly in `scripts/protocol_reference.py`.

1. For `i = 0..19`, compute `tmp[i] = S1[v[i+1]]`.
2. Set `k = min(v[21], 9)`.
3. For `i = 0..19`, assign `v[1 + P[k][i]] = tmp[i]`.
4. For `i = 1..20`, assign `out[i] = S2[v[i]]`.
5. Assign `out[0] = v[0] + 36` and `out[21] = v[21]`.

The result is exactly 22 bytes. Encoding must round-trip through the reference decoder and match every vector. Do not replace it with ASCII digits, BCD, a truncated App SN, or a model-specific guess.

The inverse used for verified replies is:

```text
original[i+1] = inverseS1[inverseS2[encoded[1 + P[k][i]]]]
```

with the first and last digits recovered from `encoded[0] - 36` and `encoded[21]`. Reject decoded values outside `0..9`.

## 37-byte inner frame

The inner message is fixed at 37 bytes:

| Offset | Length | Meaning |
|---:|---:|---|
| `0` | 1 | `0xAA` |
| `1` | 1 | `0x24` |
| `2` | 1 | product type `0xAC` |
| `3..7` | 5 | zero |
| `8` | 1 | `0x01` |
| `9` | 1 | `0x0F` |
| `10` | 1 | `0x80` |
| `11` | 1 | operation: read `0x40` or write `0x41` |
| `12..33` | 22 | encoded body SN for write; all zero for read |
| `34` | 1 | request counter |
| `35` | 1 | CRC-8 of offsets `10..34` |
| `36` | 1 | two's-complement checksum of offsets `1..35` |

The CRC lookup behavior and checksum implementation must match `protocol_reference.py`. Calculate both after all other fields are final.

Read-only code paths must not contain or construct operation `0x41`. The write operation may exist at one auditable static construction/send site only.

## Transport envelope

Encrypt the full inner frame with AES-128-ECB and PKCS#7 padding using the exact verified key in `protocol_reference.py`. A 37-byte inner frame produces 48 cipher bytes.

The transport frame is 104 bytes for this message:

| Offset | Length | Meaning |
|---:|---:|---|
| `0..3` | 4 | `5A 5A 01 00` |
| `4..5` | 2 | total frame length, unsigned little-endian |
| `6..7` | 2 | `0x0020`, little-endian |
| `8..11` | 4 | message ID, unsigned little-endian |
| `12..39` | 28 | zero/reserved |
| `40..87` | 48 | AES ciphertext |
| `88..103` | 16 | zero/reserved |

Never print the write frame as a user-editable field. Target-specific vectors may appear in signed/generated metadata and tests, not as mutable runtime input.

## Reply parsing and integrity

Treat the TCP stream as a stream, not a packet-per-read API.

1. Buffer bytes and find complete `5A 5A 01 00` frames.
2. Read and sanity-check the little-endian total length before slicing.
3. Reject truncation, impossible lengths, malformed padding, decrypt errors, wrong product type, and incomplete inner frames.
4. Recalculate both inner CRC and checksum before using a reply.
5. Decode an SN only from the defined encoded-SN field of an integrity-checked compatible response.
6. Require the decoded 22 digits to equal the package target exactly.

Do not accept an ASCII substring, a target number found elsewhere in raw bytes, a TCP acknowledgement, a connection close, or any unverified frame as readback success. Retain raw-byte counts and parser issues in the audit result without turning them into proof.

A pre-write read-only result is terminal when it returns an integrity-checked SN or an integrity-checked identity field that cannot decode to 22 ASCII digits. Exact target readback must atomically create package/global `READ-ONLY-ALREADY-CORRECT` markers; a valid non-target readback must atomically create package/global `READ-MISMATCH-DO-NOT-WRITE` markers; an undecodable identity must atomically create package/global `READ-INVALID-DO-NOT-WRITE` markers. Write mode checks all such markers twice and fails closed. Never delete them automatically.

## Write-once state machine

The write-capable path has these ordered gates:

1. Verify the hardcoded target metadata and package integrity.
2. Verify the active exact SSID, optional BSSID, local interface, and fixed route.
3. Require the full 22-digit SN confirmation.
4. Require `NEW-BOARD-AND-ORIGINAL-SN-CONFIRMED`.
5. Require `ZERO-BYTES-IS-NOT-PROOF` when the diagnostic had zero bytes.
6. Require the incident-specific phrase `WRITE-<last4-of-sn>-<last4-of-ssid>-<incident8>-ONCE`.
7. Create the global and package write markers atomically with create-new semantics, flush them durably, and set the in-memory attempted flag.
8. Only then open the TCP connection and issue exactly one write call containing exactly one `0x41` request.
9. Capture any acknowledgement for a bounded interval without retrying the write.
10. Send at most three read-only `0x40` verification queries on the allowed verification path. Never reconnect in order to resend the write.

The marker must survive every outcome after step 7. If reservation succeeds but the process fails before the send, record `WRITE_NOT_SENT_BUT_LOCKED`; do not silently unlock it. If the send begins, every exception, partial transfer, timeout, zero-byte result, or crash is a possible write for that incident.

No loop, retry policy, catch block, reconnect path, alternate launcher, hidden flag, or generated copy may reach a second write. An acknowledgement is audit data, not success proof.

## Read-only structural separation

Self-test, diagnostic, ordinary query, and post-write check modes must invoke functions that cannot accept a write operation. Their launchers must not pass a generic mode or opcode supplied by the user.

Static validation must establish:

- only the intended write launcher can select the write mode;
- only one source site constructs/sends operation `0x41`;
- the site is outside every retry/verification loop;
- no runtime `TargetSn`, host, port, operation, or unlock parameter exists;
- all template placeholders were resolved;
- target metadata and file hashes agree;
- every runtime, launcher, and instruction file is byte-for-byte equal to the rendering of this validator release's audited template. Updating a package manifest hash must not make a hand-edited runtime acceptable.

The runtime itself must parse `TARGET.json` and verify every declared generated-file SHA-256 at startup, then repeat the integrity check immediately before creating the write reservation. This is an accidental/tamper check within the best-effort local trust model, not a cryptographic signature against an attacker who can rewrite both code and manifest.

## Generation contract

Each package hardcodes at least:

- schema and protocol version;
- full 22-digit body SN and its encoded bytes;
- exact case-preserved service SSID, separate device-key normalization, and optional BSSID;
- exact model and trusted SN source;
- incident ID, device key, generation timestamp, and prior incident link when applicable;
- incident-specific confirmation phrase;
- hashes for generated runtime, launchers, and instructions.

The generator refuses an existing/non-empty output target and appends a conservative `PACKAGE_GENERATION_RESERVED` history fact before any unlocked package becomes visible. A crash or later generation failure leaves that reservation in place. On success it appends `PACKAGE_GENERATED_NOT_EXECUTED`; it never rewrites history, generates an unlocked version of an earlier incident, or connects to a device.

## Regression requirements

Before release or handoff:

1. Run `py -3 scripts\protocol_reference.py --self-test`.
2. Verify every positive and negative case in `scripts/test_vectors.json`.
3. Generate a disposable package using a non-customer test identity.
4. Run `py -3 scripts\validate_package.py <package> --require-archive`.
5. Run the generated PowerShell self-test without joining an appliance network.
6. Confirm static write-site count and launcher separation.

Any mismatch is a release blocker. Never repair a failing vector by changing the expected value unless the underlying independently verified protocol evidence changed and the change was separately audited.
