from __future__ import annotations

import codecs
import fnmatch
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


FARM_SCHEMA_VERSION = "0.1"
FARM_HOME_ENV = "QWEN_FARM_HOME"
DEFAULT_FARM_HOME = Path(".run") / "farm"

SKIP_DIRS = {
    ".git",
    "__pycache__",
    "bin",
    "build",
    "dist",
    "node_modules",
    "obj",
}

SKIP_SUFFIXES = {
    ".7z",
    ".avif",
    ".bmp",
    ".doc",
    ".docx",
    ".exe",
    ".gif",
    ".gz",
    ".heic",
    ".ico",
    ".jpeg",
    ".jpg",
    ".min.css",
    ".min.js",
    ".mp3",
    ".mp4",
    ".pdf",
    ".png",
    ".ppt",
    ".pptx",
    ".rar",
    ".tar",
    ".webp",
    ".xls",
    ".xlsx",
    ".zip",
}


@dataclass(frozen=True)
class DiscoveredFile:
    path: Path
    relative_path: str


@dataclass(frozen=True)
class DiscoveryResult:
    files: list[DiscoveredFile]
    skipped: list[str]
    skipped_details: list[dict[str, str]] | None = None


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def farm_home(root: Path) -> Path:
    override = os.environ.get(FARM_HOME_ENV)
    if override:
        return Path(override).expanduser()
    return root / DEFAULT_FARM_HOME


def make_run_id(now: datetime | None = None, suffix: str | None = None) -> str:
    timestamp = (now or datetime.now()).strftime("%Y-%m-%d-%H%M%S")
    random_suffix = suffix or secrets.token_hex(2)
    return f"farm-run-{timestamp}-{random_suffix}"


def create_run_dir(farm_root: Path, output_dir: Path | None = None, now: datetime | None = None) -> tuple[str, Path]:
    base_dir = output_dir if output_dir is not None else farm_root
    base_dir.mkdir(parents=True, exist_ok=True)

    for _ in range(10):
        run_id = make_run_id(now=now)
        run_dir = base_dir / run_id
        try:
            run_dir.mkdir(parents=True, exist_ok=False)
            return run_id, run_dir
        except FileExistsError:
            continue

    raise RuntimeError("Could not create a unique farm run directory.")


def job_id_for(index: int) -> str:
    return f"job-{index:04d}"


def relative_to(path: Path, base: Path) -> str:
    try:
        return path.relative_to(base).as_posix()
    except ValueError:
        return path.as_posix()


def has_skipped_dir(path: Path, root: Path) -> bool:
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        parts = path.parts
    return any(part in SKIP_DIRS for part in parts[:-1])


def has_skipped_suffix(path: Path) -> bool:
    name = path.name.lower()
    return any(name.endswith(suffix) for suffix in SKIP_SUFFIXES)


def is_probably_text_file(path: Path, sample_size: int = 8192) -> bool:
    try:
        with path.open("rb") as handle:
            sample = handle.read(sample_size)
    except OSError:
        return False

    if b"\x00" in sample:
        return False

    try:
        decoder = codecs.getincrementaldecoder("utf-8")()
        decoder.decode(sample, final=False)
        return True
    except UnicodeDecodeError:
        return False


def built_in_skip_reason(path: Path, root: Path) -> str | None:
    if has_skipped_dir(path, root):
        return "built_in_skipped_dir"
    if has_skipped_suffix(path):
        return "built_in_skipped_suffix"
    if not is_probably_text_file(path):
        return "built_in_non_text"
    return None


def should_skip_file(path: Path, root: Path) -> bool:
    return built_in_skip_reason(path, root) is not None


def normalize_pattern(pattern: str) -> str:
    return pattern.replace("\\", "/").strip()


def normalize_patterns(patterns: list[str] | tuple[str, ...] | None) -> list[str]:
    return [normalize_pattern(pattern) for pattern in (patterns or []) if normalize_pattern(pattern)]


def match_path_pattern(path: str, pattern: str) -> bool:
    normalized_path = path.replace("\\", "/")
    normalized_pattern = normalize_pattern(pattern)
    if os.name == "nt":
        normalized_path = normalized_path.lower()
        normalized_pattern = normalized_pattern.lower()
    if fnmatch.fnmatchcase(normalized_path, normalized_pattern):
        return True
    if normalized_pattern.startswith("**/"):
        return fnmatch.fnmatchcase(normalized_path, normalized_pattern[3:])
    return False


def first_matching_pattern(path: str, patterns: list[str]) -> str | None:
    for pattern in patterns:
        if match_path_pattern(path, pattern):
            return pattern
    return None


def discover_text_files(
    input_dir: Path,
    *,
    include: list[str] | tuple[str, ...] | None = None,
    exclude: list[str] | tuple[str, ...] | None = None,
) -> DiscoveryResult:
    if not input_dir.exists():
        raise FileNotFoundError(f"Input folder does not exist: {input_dir}")
    if not input_dir.is_dir():
        raise NotADirectoryError(f"Input path must be a folder: {input_dir}")

    files: list[DiscoveredFile] = []
    skipped: list[str] = []
    skipped_details: list[dict[str, str]] = []
    include_patterns = normalize_patterns(include)
    exclude_patterns = normalize_patterns(exclude)

    for path in sorted(input_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = relative_to(path, input_dir)
        reason = built_in_skip_reason(path, input_dir)
        if reason is not None:
            skipped.append(rel)
            skipped_details.append({"path": rel, "reason": reason})
            continue
        include_pattern = first_matching_pattern(rel, include_patterns) if include_patterns else None
        if include_patterns and include_pattern is None:
            skipped.append(rel)
            skipped_details.append({"path": rel, "reason": "not_included_by_pattern"})
            continue
        exclude_pattern = first_matching_pattern(rel, exclude_patterns)
        if exclude_pattern is not None:
            skipped.append(rel)
            skipped_details.append({"path": rel, "reason": "excluded_by_pattern", "pattern": exclude_pattern})
            continue
        files.append(DiscoveredFile(path=path, relative_path=rel))

    return DiscoveryResult(files=files, skipped=skipped, skipped_details=skipped_details)
