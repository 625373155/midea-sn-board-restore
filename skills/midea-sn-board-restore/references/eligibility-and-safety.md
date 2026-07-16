# Eligibility and safety policy

This plugin supports a narrow repair workflow: restoring the original body SN to one owner-authorized Midea air-conditioner main board after a physical replacement. It is not a general-purpose identity writer.

## Every gate must pass

A write-capable package may be generated only when all of these are established:

1. **Authorization:** the requester owns the appliance or is explicitly authorized to repair it.
2. **Supported product and model:** the target is a Midea air conditioner whose exact model appears in the generator's independently reviewed allowlist. The public v0.2.0 allowlist contains only `KFR-26G/WXAA2@`. Do not infer compatibility from a similar hotspot or extend this workflow to another model, firmware family, or appliance category without separate protocol evidence and audit.
3. **New physical board event:** the main board was actually replaced and this package corresponds to that specific replacement incident.
4. **Trusted original identity:** the complete original body SN is available from one of the accepted sources below.
5. **Live target network:** the current replacement board is advertising the exact service hotspot supplied for the package.
6. **Model evidence:** the exact appliance model and evidence tying the replacement event to that appliance are available.
7. **History check:** no write was reserved or possibly sent for this incident. Reuse of either a prior SN or prior hotspot is allowed only for a later physical board replacement with its own incident ID and a link to the previous incident.

If one gate fails, remain read-only. Explain what is missing instead of weakening the gate.

## Accepted identity evidence

The body SN must come from at least one of these sources:

- a customer-service record for the target appliance;
- the target appliance's original factory label;
- a historical official-App record for the target appliance;
- a reliable read from the target appliance's old board.

Record the source in `TARGET.json`. Prefer corroboration from a second source when available.

Do not accept:

- a guessed code, model-derived code, suffix, or partial number;
- another appliance's label, QR code, screenshot, or board contents;
- an identity offered for cloning, resale preparation, fleet provisioning, or account evasion;
- a number obtained by taking the middle 22 characters of an App-displayed 32-digit value.

## Exact input rules

### Body SN

The input is exactly 22 ASCII characters in the range `0` through `9`, matching `^[0-9]{22}$`.

- Preserve leading zeroes.
- Reject 21 or 23 digits.
- Reject full-width or other Unicode digits.
- Reject spaces, tabs, line breaks, hyphens, labels, and surrounding text.
- Reject 32-digit App SNs. Do not silently normalize or slice them.

The previously observed App display `000000 + body-SN + 0000` is evidence for one verified compatible model only. It is not a universal conversion rule and never changes the required generator input.

### Service hotspot

The hotspot must be observed live from the current board and normalize exactly to:

```text
midea_test_<12 lowercase hexadecimal characters>
```

Case may be normalized to lowercase, but do not add, remove, or infer characters. For example, a synthetic visually spaced transcription such as `midea_test _a1b2c3d4 e5f6` must not be accepted until the user confirms the exact live SSID shown by the operating system.

Record the BSSID when it is available. A supplied BSSID must match at runtime. If the platform cannot provide one, make that limitation explicit; the exact SSID and bound interface remain mandatory.

### Model and event evidence

Record the exact model as observed on the target appliance or in its trusted service record. Evidence of a different appliance of the same model does not identify the target appliance.

Record a concise new-board event description, evidence source, and UTC creation time. Do not treat a blank response, an App pairing failure, or an SSID by itself as proof that a board is new or blank.

## Incident identity and immutable history

Each generation receives a new opaque incident ID. The device key is derived from the exact 22-digit body SN and normalized service SSID; it is not user-selectable.

Use both safeguards:

- a global per-device/per-incident append-only ledger under `%LOCALAPPDATA%\MideaSnBoardRestore\devices\<device-key>\incidents\<incident-id>\WRITE-ONCE.jsonl`;
- a package-side append-only `WRITE-ATTEMPTED-DO-NOT-RERUN.jsonl` marker.

Read-only terminal results use the same package/global pattern: exact target readback creates an `ALREADY-CORRECT` no-write marker, while an integrity-checked non-target SN creates a `MISMATCH` no-write marker. Both are permanent for that incident and take precedence over a later zero-byte diagnostic receipt.

Create write reservations atomically before opening the target TCP connection. Append audit facts durably and never rewrite history to make an incident eligible again.

If either the same SN or the same service hotspot appeared before, require:

1. the latest previous incident ID;
2. the additional `--later-physical-board-event-confirmed` attestation that another physical board replacement occurred afterward;
3. independently reviewed fresh model/event evidence (the generator rejects an identical or whitespace-variant reference) and a new incident ID.

The extra flag and evidence hash are fail-closed friction, not physical proof. The skill must inspect the supplied evidence; a reworded string does not establish that a board was replaced.

Never delete an old lock, reuse an old incident ID, or provide an unlocked copy of an earlier package. If a write may have been sent, uncertainty is final for that incident even if the board returned no bytes.

These locks are best-effort software safeguards. Copying files to a different computer can evade local state; the documentation must state this honestly and rely on authorization plus incident evidence as well as locks.

On Windows, resolve the generator history root with the Known Folder API rather than trusting the process `LOCALAPPDATA` environment variable. Environment-variable redirection must not hide same-user history. A user with filesystem control can still delete local state, so this remains a best-effort safeguard rather than tamper-proof storage.

## Generator boundary

The plugin and its generator may create and validate package files. They must not:

- join the service hotspot;
- connect to `192.168.1.1:6444` or any appliance endpoint;
- run a generated launcher;
- send diagnostic, read, or write frames;
- operate the official App or alter a cloud account.

Only the owner or authorized repairer runs a validated generated package locally after reviewing `TARGET.json`.

## Prohibited expansions

Refuse requests to:

- write an arbitrary, invented, or other-device identity;
- accept a list of SNs, clone one identity to multiple boards, or add a batch mode;
- bypass account binding, ownership checks, regional controls, cloud registration, or service credentials;
- add arbitrary hosts, ports, product types, protocol opcodes, or hidden retry switches;
- remove confirmations, markers, audit records, SSID/interface checks, integrity checks, or the one-write limit;
- rerun the write because acknowledgement was absent or verification was inconclusive.

Read-only inspection and explanation can continue when generation is refused.
