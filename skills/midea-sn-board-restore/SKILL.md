---
name: midea-sn-board-restore
description: "Generate, validate, and audit one-device write-once recovery packages for an owner-authorized Midea air-conditioner replacement board using a trusted 22-digit body SN and the live service hotspot. Use when a replaced AC board has lost its body SN, or when interpreting diagnostic/write logs and App evidence from such a repair. Reject SN-only requests, guessed or copied identities, batch/cloning work, cloud-account bypass, non-AC devices, and repeat writes for the same incident."
---

# Midea AC Board SN Restore

Create a package for one verified appliance and one physical replacement-board incident. The skill generates and audits files; it does not connect to the appliance or run a write command.

## Read the required references

Before taking any action, read `references/eligibility-and-safety.md` completely.

- For package generation, protocol review, or code changes, also read `references/protocol-contract.md` completely.
- For logs, errors, App screenshots, or deciding whether an earlier attempt succeeded, also read `references/outcome-classification.md` completely.

Treat these references as hard requirements. If any required evidence is missing, continue with read-only analysis or ask for the missing evidence; do not generate a write-capable package.

## Triage the request

Collect and independently validate all of the following:

1. The user owns the appliance or is authorized to repair it.
2. The target is a Midea air conditioner with a newly replaced physical main board, and its exact model is present in the generator's reviewed compatibility allowlist.
3. The original body SN is exactly 22 ASCII digits and comes from customer service, the original label, the old App record, or the old board.
4. The service hotspot is observed live from that board and exactly matches `midea_test_<12 hexadecimal characters>` after the documented normalization.
5. The exact model and evidence of the new-board event are available.
6. If either this SN or hotspot appeared in an earlier incident, the previous incident ID and explicit fresh evidence of a later physical board replacement are available.

An SN alone is never enough. Do not trim whitespace, remove separators, accept Unicode digits, infer missing digits, or extract a 22-digit substring from an App-displayed 32-digit value. Do not use another appliance's label or screenshot as the identity source.

## Classify existing attempts first

When the user supplies prior logs or App evidence, classify the incident before considering generation:

1. Read `references/outcome-classification.md`.
2. Determine the strongest supported state without treating a TCP acknowledgement, zero response bytes, or a connection as proof of a successful write.
3. If any write may have been sent or a write reservation exists, do not generate a retry for that incident.
4. Preserve all package markers and global ledger records. Never delete, weaken, or advise bypassing them.

Treat any locally recorded prior incident as final for that incident. Public source distributions contain no customer identity or preloaded repair event; use the append-only local history and user-supplied evidence, and never copy a private incident into source control.

## Generate a fresh package

Use only the bundled generator and inspect its current CLI before invocation:

```powershell
py -3 scripts\new_restore_package.py --help
```

Pass the exact verified values and explicit confirmation flags required by the CLI, including a one-line `--sn-source-reference` and a separate one-line `--new-board-evidence`. Use a new, empty output directory. If either the same SN or hotspot has history, supply the prior incident ID plus `--later-physical-board-event-confirmed` only after independently reviewing fresh evidence of the later replacement. A changed evidence string or a confirmation flag is an attestation, not proof.

The generator must:

- hardcode the verified SN, encoded bytes, hotspot, optional BSSID, model, incident ID, and protocol version;
- create a new incident record without modifying earlier records;
- make diagnostic/read-only launchers structurally incapable of sending opcode `0x41`;
- create at most one write-capable launcher, guarded by package and global atomic markers;
- avoid connecting to or executing against the appliance;
- refuse unresolved placeholders, invalid input, existing output, or an unqualified repeat incident.

Never hand-edit a generated package to change its identity or unlock it. Generate a new package only for a genuinely new eligible incident.

## Validate before handoff

Run the reference tests and the package validator:

```powershell
py -3 scripts\protocol_reference.py --self-test
py -3 scripts\validate_package.py <generated-package-directory> --require-archive
```

Do not hand off the package unless both succeed. The validator must require every runtime file to be the byte-for-byte rendering of this plugin release's audited template, in addition to checking the manifest, file/ZIP hashes, static invariants, and offline PowerShell SelfTest. Review `TARGET.json` with the user and have them confirm the model, full 22-digit body SN, service hotspot, source, and incident ID. Explain that software locks are best-effort safeguards on this computer, not hardware-enforced protection across copied files or other computers.

## Safe user handoff

Tell the user to follow the generated Chinese instructions in order:

1. Run the self-test.
2. Join only the verified service hotspot and run the ordinary read-only query first.
3. If the query returns the exact target SN, stop; no write is needed. If it returns a valid non-target SN, create the permanent mismatch stop. If an integrity-checked identity payload cannot decode to 22 ASCII digits, create the permanent invalid-encoding stop. Do not write in any of these states.
4. Only if the query has no usable response, run the raw read-only diagnostic. If it returns zero bytes, explain that this does not prove the board is blank. Continue only if all eligibility evidence remains valid.
5. Authorize the single write only once with the incident-specific confirmation phrases.
6. After any write reservation or send attempt, never run the write launcher again for that incident.
7. Cold-power-cycle the appliance, then use read-only verification and the official App. Classify the result from the reference rather than guessing.

The generated runtime must bind to the active service-network interface and use only `192.168.1.1:6444`. Do not infer compatibility from the hotspot alone or extend the model allowlist without independent protocol evidence and a separate audit. Do not add arbitrary target hosts, retries, loops around the write, batch input, or account/cloud-binding operations.

## Maintain the plugin

`scripts/protocol_reference.py` and `scripts/test_vectors.json` are the protocol oracle. Any protocol or template change must preserve every positive vector, reject every negative input, and keep exactly one static opcode-`0x41` send site outside all retry loops. Validate a generated disposable test package after each change; never use the user's successful incident as an unlocked test output.

Before a public release, run the repository privacy scanner and confirm that every committed SN, service SSID, App display value, and protocol vector is explicitly synthetic. Rewrite unpublished/private Git history before changing repository visibility if a previous commit contained a real identity.
