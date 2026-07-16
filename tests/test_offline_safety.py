from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIRECTORY = ROOT / "skills" / "midea-sn-board-restore" / "scripts"
sys.path.insert(0, str(SCRIPT_DIRECTORY))
sys.path.insert(0, str(ROOT / "scripts"))

import new_restore_package as generator  # noqa: E402
import protocol_reference as protocol  # noqa: E402
import public_release_check as release_check  # noqa: E402
import validate_package as validator  # noqa: E402


SYNTHETIC_SN = "1234567890123456789012"
SYNTHETIC_SSID = "midea_test_a1b2c3d4e5f6"
SUPPORTED_MODEL = "KFR-26G/WXAA2@"


def arguments(output: Path, **overrides: object) -> argparse.Namespace:
    values: dict[str, object] = {
        "sn": SYNTHETIC_SN,
        "ssid": SYNTHETIC_SSID,
        "model": SUPPORTED_MODEL,
        "bssid": None,
        "sn_source": "original-label",
        "sn_source_reference": "synthetic label fixture",
        "new_board_evidence": "synthetic board evidence",
        "ownership_confirmed": True,
        "trusted_source_confirmed": True,
        "new_physical_board_confirmed": True,
        "later_physical_board_event_confirmed": False,
        "previous_incident_id": None,
        "output": str(output),
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def write_history(state: Path, *records: dict[str, object]) -> None:
    state.mkdir(parents=True, exist_ok=True)
    payload = "".join(json.dumps(record, sort_keys=True) + "\n" for record in records)
    (state / "events.jsonl").write_text(payload, encoding="utf-8")


class ProtocolTests(unittest.TestCase):
    def test_complete_protocol_self_test(self) -> None:
        protocol.self_test()

    def test_invalid_encoded_values_raise_value_error(self) -> None:
        invalid = bytearray(protocol.encode_sn(SYNTHETIC_SN))
        invalid[5] = 0x80
        with self.assertRaises(ValueError):
            protocol.decode_sn(bytes(invalid))

    def test_body_and_ssid_inputs_fail_closed(self) -> None:
        for value in (
            "000000" + SYNTHETIC_SN + "0000",
            SYNTHETIC_SN + "\n",
            "１２３４５６７８９０１２３４５６７８９０１２",
        ):
            with self.assertRaises(ValueError):
                protocol.validate_body_sn(value)
        with self.assertRaises(ValueError):
            protocol.validate_service_ssid("midea_test _a1b2c3d4 e5f6")


class GeneratorAndValidatorTests(unittest.TestCase):
    def test_public_source_has_no_embedded_prior_event(self) -> None:
        self.assertEqual(generator.IMMUTABLE_PRIOR_EVENTS, ())

    def test_unsupported_model_is_rejected_before_generation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with mock.patch.object(generator, "_local_state_directory", return_value=root / "state"):
                with self.assertRaisesRegex(generator.GenerationError, "compatibility allowlist"):
                    generator.generate(arguments(root / "out", model="UNREVIEWED-MODEL"))

    def test_synthetic_package_generation_and_full_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with mock.patch.object(generator, "_local_state_directory", return_value=root / "state"):
                result = generator.generate(arguments(root / "out"))
            validated = validator.validate(
                Path(result["packageDirectory"]),
                archive=None,
                timeout_seconds=60,
                require_archive=True,
            )
            self.assertEqual(validated["result"], "PACKAGE_VALID")
            self.assertFalse(validated["networkActionsPerformed"])

    def test_normalized_evidence_variant_cannot_create_later_event(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = root / "state"
            with mock.patch.object(generator, "_local_state_directory", return_value=state):
                first = generator.generate(
                    arguments(root / "out", new_board_evidence="Synthetic    Board Evidence")
                )
                with self.assertRaisesRegex(generator.GenerationError, "identical to a prior event"):
                    generator.generate(
                        arguments(
                            root / "out",
                            new_board_evidence="synthetic board evidence",
                            previous_incident_id=first["incidentId"],
                            later_physical_board_event_confirmed=True,
                        )
                    )

    def test_hashed_prior_requires_current_evidence_hash_version(self) -> None:
        for version in (None, "legacy-raw-v0"):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                state = root / "state"
                incident_id = "legacy-synthetic-event"
                prior: dict[str, object] = {
                    "incidentId": incident_id,
                    "targetSn": SYNTHETIC_SN,
                    "expectedServiceSsid": SYNTHETIC_SSID,
                    "newBoardEvidenceSha256": "0" * 64,
                }
                if version is not None:
                    prior["newBoardEvidenceHashVersion"] = version
                write_history(state, prior)

                with mock.patch.object(generator, "_local_state_directory", return_value=state):
                    with self.assertRaisesRegex(
                        generator.GenerationError, "manual history migration and audit"
                    ):
                        generator.generate(
                            arguments(
                                root / "out",
                                new_board_evidence="fresh synthetic board evidence",
                                previous_incident_id=incident_id,
                                later_physical_board_event_confirmed=True,
                            )
                        )

    def test_malformed_current_evidence_hash_requires_manual_audit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = root / "state"
            incident_id = "legacy-synthetic-event"
            write_history(
                state,
                {
                    "incidentId": incident_id,
                    "targetSn": SYNTHETIC_SN,
                    "expectedServiceSsid": SYNTHETIC_SSID,
                    "newBoardEvidenceSha256": "not-a-sha256",
                    "newBoardEvidenceHashVersion": generator.EVIDENCE_HASH_VERSION,
                },
            )

            with mock.patch.object(generator, "_local_state_directory", return_value=state):
                with self.assertRaisesRegex(
                    generator.GenerationError, "manual history migration and audit"
                ):
                    generator.generate(
                        arguments(
                            root / "out",
                            new_board_evidence="fresh synthetic board evidence",
                            previous_incident_id=incident_id,
                            later_physical_board_event_confirmed=True,
                        )
                    )

    def test_unhashed_legacy_prior_remains_eligible_for_reviewed_later_event(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = root / "state"
            incident_id = "legacy-synthetic-event"
            write_history(
                state,
                {
                    "incidentId": incident_id,
                    "targetSn": SYNTHETIC_SN,
                    "expectedServiceSsid": SYNTHETIC_SSID,
                },
            )

            with mock.patch.object(generator, "_local_state_directory", return_value=state):
                result = generator.generate(
                    arguments(
                        root / "out",
                        new_board_evidence="fresh synthetic board evidence",
                        previous_incident_id=incident_id,
                        later_physical_board_event_confirmed=True,
                    )
                )
            self.assertEqual(result["result"], "PACKAGE_GENERATED_NOT_EXECUTED")

    def test_template_tamper_fails_even_after_manifest_hash_update(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with mock.patch.object(generator, "_local_state_directory", return_value=root / "state"):
                result = generator.generate(arguments(root / "out"))
            package = Path(result["packageDirectory"])
            script = package / "midea_sn_restore.ps1"
            script.write_text(
                script.read_text(encoding="utf-8-sig") + "\n# synthetic tamper\n",
                encoding="utf-8-sig",
                newline="\n",
            )
            manifest_path = package / "TARGET.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"][script.name] = hashlib.sha256(script.read_bytes()).hexdigest()
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            with self.assertRaises(validator.ValidationError):
                validator.validate(package, archive=None, timeout_seconds=60, require_archive=False)


class PublicReleaseTests(unittest.TestCase):
    def test_worktree_privacy_gate(self) -> None:
        self.assertEqual(release_check._scan_worktree(), [])
        self.assertEqual(release_check._check_empty_immutable_events(), [])
        self.assertEqual(release_check._check_corpus(), [])


if __name__ == "__main__":
    unittest.main()
