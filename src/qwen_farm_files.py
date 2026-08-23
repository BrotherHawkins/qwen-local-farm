from __future__ import annotations

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
        sample.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def should_skip_file(path: Path, root: Path) -> bool:
    return has_skipped_dir(path, root) or has_skipped_suffix(path) or not is_probably_text_file(path)


def discover_text_files(input_dir: Path) -> DiscoveryResult:
    if not input_dir.exists():
        raise FileNotFoundError(f"Input folder does not exist: {input_dir}")
    if not input_dir.is_dir():
        raise NotADirectoryError(f"Input path must be a folder: {input_dir}")

    files: list[DiscoveredFile] = []
    skipped: list[str] = []

    for path in sorted(input_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = relative_to(path, input_dir)
        if should_skip_file(path, input_dir):
            skipped.append(rel)
            continue
        files.append(DiscoveredFile(path=path, relative_path=rel))

    return DiscoveryResult(files=files, skipped=skipped)
