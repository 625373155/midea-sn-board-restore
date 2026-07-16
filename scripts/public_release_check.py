from __future__ import annotations

"""Fail closed when public source contains non-synthetic identity or private artifacts."""

import ast
import json
import re
import subprocess
import sys
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
GENERATOR = REPOSITORY / "skills" / "midea-sn-board-restore" / "scripts" / "new_restore_package.py"
CORPUS = REPOSITORY / "skills" / "midea-sn-board-restore" / "scripts" / "test_vectors.json"

SYNTHETIC_SN = "1234567890123456789012"
SYNTHETIC_SSID_HEX = "a1b2c3d4e5f6"
ALLOWED_LONG_ASCII_DIGITS = {
    "0000000000000000000000",
    "9999999999999999999999",
    "0123456789012345678909",
    SYNTHETIC_SN,
    SYNTHETIC_SN[:-1],
    SYNTHETIC_SN + "3",
    "000000" + SYNTHETIC_SN + "0000",
}
ALLOWED_LONG_FULLWIDTH_DIGITS = {"１２３４５６７８９０１２３４５６７８９０１２"}
ALLOWED_SERVICE_SUFFIXES = {
    SYNTHETIC_SSID_HEX,
    SYNTHETIC_SSID_HEX[:-1],
    SYNTHETIC_SSID_HEX + "0",
}
FORBIDDEN_FILE_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".zip", ".jsonl", ".log"}
TEXT_SUFFIXES = {
    "",
    ".cmd",
    ".gitattributes",
    ".gitignore",
    ".json",
    ".md",
    ".ps1",
    ".py",
    ".txt",
    ".tmpl",
    ".yaml",
    ".yml",
}

LONG_ASCII_DIGITS_RE = re.compile(r"(?<![0-9])[0-9]{21,32}(?![0-9])", re.ASCII)
LONG_FULLWIDTH_DIGITS_RE = re.compile(r"(?<![０-９])[０-９]{21,32}(?![０-９])")
SERVICE_ID_RE = re.compile(r"midea_test\s*_?\s*((?:[0-9A-Fa-f]\s*){8,20})", re.ASCII)
TOKEN_RE = re.compile(
    r"(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})",
    re.ASCII,
)
ABSOLUTE_USER_PATH_RE = re.compile(r"[A-Za-z]:[\\/]Users[\\/][^\\/\s]+[\\/]", re.IGNORECASE)


class ReleaseCheckError(RuntimeError):
    pass


def _text_from_bytes(data: bytes, label: str) -> str | None:
    if b"\x00" in data:
        raise ReleaseCheckError(f"NUL/binary content is forbidden in a declared text file: {label}")
    for encoding in ("utf-8-sig", "utf-8"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ReleaseCheckError(f"non-UTF-8 text is not allowed in public source: {label}")


def _scan_text(text: str, label: str) -> list[str]:
    issues: list[str] = []
    for match in LONG_ASCII_DIGITS_RE.finditer(text):
        if match.group(0) not in ALLOWED_LONG_ASCII_DIGITS:
            issues.append(f"{label}: non-allowlisted 21-32 digit sequence")
    for match in LONG_FULLWIDTH_DIGITS_RE.finditer(text):
        if match.group(0) not in ALLOWED_LONG_FULLWIDTH_DIGITS:
            issues.append(f"{label}: non-allowlisted full-width digit sequence")
    for match in SERVICE_ID_RE.finditer(text):
        suffix = re.sub(r"\s+", "", match.group(1)).lower()
        if suffix not in ALLOWED_SERVICE_SUFFIXES:
            issues.append(f"{label}: non-allowlisted Midea service-hotspot identity")
    if TOKEN_RE.search(text):
        issues.append(f"{label}: possible GitHub credential")
    if ABSOLUTE_USER_PATH_RE.search(text):
        issues.append(f"{label}: absolute Windows user path")
    return issues


def _worktree_files() -> list[Path]:
    files: list[Path] = []
    for path in REPOSITORY.rglob("*"):
        if path.is_symlink() or not path.is_file() or ".git" in path.relative_to(REPOSITORY).parts:
            continue
        files.append(path)
    return sorted(files)


def _scan_worktree() -> list[str]:
    issues: list[str] = []
    for candidate in sorted(REPOSITORY.rglob("*")):
        if ".git" in candidate.relative_to(REPOSITORY).parts:
            continue
        if candidate.is_symlink():
            issues.append(f"{candidate.relative_to(REPOSITORY).as_posix()}: symlinks are forbidden")
    for path in _worktree_files():
        relative = path.relative_to(REPOSITORY).as_posix()
        issues.extend(_scan_text(relative, f"path:{relative}"))
        if path.suffix.lower() in FORBIDDEN_FILE_SUFFIXES or path.name == "TARGET.json":
            issues.append(f"{relative}: private/generated artifact type is forbidden")
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES and not path.name.startswith("."):
            issues.append(f"{relative}: unreviewed file type")
            continue
        text = _text_from_bytes(path.read_bytes(), relative)
        if text is not None:
            issues.extend(_scan_text(text, relative))
    return issues


def _git_output(*arguments: str) -> bytes:
    return subprocess.run(
        ["git", *arguments],
        cwd=REPOSITORY,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout


def _scan_referenced_history() -> list[str]:
    try:
        revisions = _git_output("rev-list", "--all").decode("ascii").splitlines()
    except (FileNotFoundError, subprocess.CalledProcessError, UnicodeDecodeError):
        return []
    issues: list[str] = []
    for revision in revisions:
        entries = _git_output("ls-tree", "-r", revision).decode("utf-8").splitlines()
        for entry in entries:
            metadata, name = entry.split("\t", 1)
            mode = metadata.split(" ", 1)[0]
            issues.extend(_scan_text(name, f"git-path:{revision[:12]}:{name}"))
            if mode == "120000":
                issues.append(f"git:{revision[:12]}:{name}: symlinks are forbidden")
                continue
            suffix = Path(name).suffix.lower()
            if suffix in FORBIDDEN_FILE_SUFFIXES or Path(name).name == "TARGET.json":
                issues.append(f"git:{revision[:12]}:{name}: forbidden artifact in referenced history")
                continue
            if suffix not in TEXT_SUFFIXES and not Path(name).name.startswith("."):
                continue
            try:
                data = _git_output("show", f"{revision}:{name}")
                text = _text_from_bytes(data, f"git:{revision[:12]}:{name}")
            except (subprocess.CalledProcessError, ReleaseCheckError) as exc:
                issues.append(str(exc))
                continue
            if text is not None:
                issues.extend(_scan_text(text, f"git:{revision[:12]}:{name}"))
    try:
        commit_data = _git_output("log", "--all", "--format=%H%x00%B%x00")
        commit_parts = commit_data.decode("utf-8").split("\x00")
        for index in range(0, len(commit_parts) - 1, 2):
            revision = commit_parts[index].strip()
            message = commit_parts[index + 1]
            if revision:
                issues.extend(_scan_text(message, f"git-commit:{revision[:12]}"))

        ref_names = _git_output("for-each-ref", "--format=%(refname)").decode("utf-8").splitlines()
        for ref_name in ref_names:
            issues.extend(_scan_text(ref_name, f"git-ref:{ref_name}"))

        tag_data = _git_output(
            "for-each-ref", "refs/tags", "--format=%(refname)%00%(contents)%00"
        ).decode("utf-8")
        tag_parts = tag_data.split("\x00")
        for index in range(0, len(tag_parts) - 1, 2):
            tag_name = tag_parts[index].strip()
            tag_message = tag_parts[index + 1]
            if tag_name:
                issues.extend(_scan_text(tag_message, f"git-tag:{tag_name}"))
    except (subprocess.CalledProcessError, UnicodeDecodeError) as exc:
        issues.append(f"Git metadata scan failed: {exc}")
    return issues


def _check_empty_immutable_events() -> list[str]:
    tree = ast.parse(GENERATOR.read_text(encoding="utf-8"), filename=str(GENERATOR))
    for node in tree.body:
        target_name: str | None = None
        value: ast.expr | None = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            target_name = node.targets[0].id
            value = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            target_name = node.target.id
            value = node.value
        if target_name == "IMMUTABLE_PRIOR_EVENTS":
            if not isinstance(value, (ast.Tuple, ast.List)) or value.elts:
                return ["new_restore_package.py: IMMUTABLE_PRIOR_EVENTS must be an empty literal"]
            return []
    return ["new_restore_package.py: IMMUTABLE_PRIOR_EVENTS declaration is missing"]


def _check_corpus() -> list[str]:
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    issues: list[str] = []
    if corpus.get("data_classification") != "synthetic-only":
        issues.append("test_vectors.json: data_classification must be synthetic-only")
    for section in ("encoding_vectors", "counter_vectors"):
        for index, vector in enumerate(corpus.get(section, [])):
            if vector.get("synthetic") is not True:
                issues.append(f"test_vectors.json: {section}[{index}] lacks synthetic=true")
    if corpus.get("known_frame_vector", {}).get("synthetic") is not True:
        issues.append("test_vectors.json: known_frame_vector lacks synthetic=true")
    if corpus.get("app_evidence_example", {}).get("synthetic") is not True:
        issues.append("test_vectors.json: app_evidence_example lacks synthetic=true")
    return issues


def main() -> int:
    issues = _scan_worktree()
    issues.extend(_check_empty_immutable_events())
    issues.extend(_check_corpus())
    if "--skip-history" not in sys.argv[1:]:
        issues.extend(_scan_referenced_history())
    unique = sorted(set(issues))
    if unique:
        print("PUBLIC_RELEASE_CHECK_FAILED", file=sys.stderr)
        for issue in unique:
            print(f"- {issue}", file=sys.stderr)
        return 2
    print("public release check: PASS (synthetic identities only)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
