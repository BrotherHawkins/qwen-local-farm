from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SCHEMA_DIR = Path("schemas")
SCHEMA_VALIDATION_SCHEMA_VERSION = 1
EXIT_VALID = 0
EXIT_INVALID = 1
EXIT_ERROR = 2


def load_json_object(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return data


def validate(instance: Any, schema: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    _validate_value(instance, schema, "$", errors)
    return errors


def validate_file(instance_path: Path, schema_path: Path) -> list[str]:
    return validate(load_json_object(instance_path), load_json_object(schema_path))


def load_schema_index(root: Path) -> dict[str, Any]:
    return load_json_object(root / SCHEMA_DIR / "index.json")


def schema_records(root: Path) -> list[dict[str, Any]]:
    index = load_schema_index(root)
    records = index.get("schemas") or []
    return [item for item in records if isinstance(item, dict)]


def resolve_schema_reference(root: Path, reference: str) -> dict[str, Any]:
    for record in schema_records(root):
        if reference == record.get("id") or reference == record.get("path"):
            return _schema_record(root, record, detected=False)

    schema_path = Path(reference)
    if not schema_path.is_absolute():
        schema_path = root / schema_path
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema not found: {reference}")

    schema = load_json_object(schema_path)
    return {
        "id": schema.get("$id"),
        "path": _display_path(root, schema_path),
        "detected": False,
    }


def detect_schema(root: Path, artifact: dict[str, Any]) -> dict[str, Any]:
    matches: list[str] = []
    schema_version = artifact.get("schema_version")
    limits = artifact.get("limits") if isinstance(artifact.get("limits"), dict) else {}
    artifacts = artifact.get("artifacts") if isinstance(artifact.get("artifacts"), dict) else {}

    if schema_version == 1 and artifact.get("scope") == "overview":
        matches.append("schemas/farm-status-overview.schema.json")
    if schema_version == 1 and artifact.get("scope") == "run":
        matches.append("schemas/farm-status-run.schema.json")
    if {"environment", "ollama", "checks", "recommendations", "report_paths"}.issubset(artifact):
        matches.append("schemas/farm-doctor.schema.json")
    if (
        schema_version == 1
        and {"resource_mode", "profile", "concurrency", "summarize", "evidence", "next_actions"}.issubset(artifact)
    ):
        matches.append("schemas/farm-recommendation.schema.json")
    if (
        schema_version == 1
        and {
            "dry_run",
            "recommendation_path",
            "config_path",
            "proposed_config",
            "changes",
            "not_applied",
        }.issubset(artifact)
    ):
        matches.append("schemas/farm-config-apply.schema.json")
    if schema_version == "0.1" and {"run_id", "jobs", "counts", "skipped_files"}.issubset(artifact):
        matches.append("schemas/farm-status.schema.json")
    if schema_version == "0.1" and {"job_id", "structured_valid", "result", "artifacts"}.issubset(artifact):
        matches.append("schemas/farm-job-result.schema.json")
    if (
        schema_version == "0.1"
        and {"run_id", "aggregate_by_call_kind", "slowest_jobs", "slowest_calls"}.issubset(artifact)
    ):
        matches.append("schemas/farm-timing-summary.schema.json")
    if (
        schema_version == 1
        and limits.get("source") == "selected"
        and {"snippets", "diagnostics", "counts"}.issubset(artifact)
    ):
        matches.append("schemas/farm-snippet-pack.schema.json")
    if (
        schema_version == 1
        and limits.get("snippet_source") == "selected"
        and {"items", "budget", "diagnostics", "counts"}.issubset(artifact)
    ):
        matches.append("schemas/farm-synthesis-bundle.schema.json")
    if (
        schema_version == 1
        and {"artifacts", "items", "diagnostics", "counts"}.issubset(artifact)
        and artifacts.get("manifest") == "farm-collection.json"
    ):
        matches.append("schemas/farm-collection.schema.json")
    if schema_version == 1 and artifact.get("mode") == "extract" and {"coverage", "items", "failures"}.issubset(artifact):
        matches.append("schemas/farm-extract-results.schema.json")
    if schema_version == 1 and {"source_run", "retry_run", "counts", "warnings", "errors"}.issubset(artifact):
        matches.append("schemas/farm-retry-failed.schema.json")
    if schema_version == 1 and {"recorded_at", "totals", "quality", "jobs"}.issubset(artifact):
        matches.append("schemas/farm-dogfood-record.schema.json")
    if schema_version == 1 and {"compared_at", "baseline", "candidate", "duration_ms", "jobs"}.issubset(artifact):
        matches.append("schemas/farm-dogfood-comparison.schema.json")
    if schema_version == 1 and {"default_band", "hardware_bands", "approval_boundaries"}.issubset(artifact):
        matches.append("schemas/model-installation.schema.json")
    if schema_version == 1 and artifact.get("command") == "skills install" and {"target", "skills", "summary"}.issubset(artifact):
        matches.append("schemas/skill-install-report.schema.json")

    if not matches:
        raise ValueError("Could not infer a schema for this artifact. Pass --schema to choose one explicitly.")
    if len(matches) > 1:
        raise ValueError(f"Artifact matches multiple schemas: {', '.join(matches)}. Pass --schema to choose one.")

    wanted = matches[0]
    for record in schema_records(root):
        if record.get("path") == wanted:
            return _schema_record(root, record, detected=True)
    raise FileNotFoundError(f"Detected schema is not listed in schemas/index.json: {wanted}")


def validate_artifact(root: Path, artifact_path: Path, schema_reference: str | None = None) -> dict[str, Any]:
    artifact_display = _display_path(root, artifact_path)
    schema_info: dict[str, Any] | None = None
    try:
        artifact = load_json_object(artifact_path)
        schema_info = (
            resolve_schema_reference(root, schema_reference)
            if schema_reference
            else detect_schema(root, artifact)
        )
        schema_path = root / str(schema_info["path"])
        errors = validate(artifact, load_json_object(schema_path))
        return validation_result(
            valid=not errors,
            artifact_path=artifact_display,
            schema=schema_info,
            errors=errors,
            exit_code=EXIT_VALID if not errors else EXIT_INVALID,
        )
    except json.JSONDecodeError as exc:
        return validation_result(
            valid=False,
            artifact_path=artifact_display,
            schema=schema_info,
            errors=[f"Invalid JSON: {exc.msg} at line {exc.lineno} column {exc.colno}."],
            exit_code=EXIT_ERROR,
        )
    except Exception as exc:
        return validation_result(
            valid=False,
            artifact_path=artifact_display,
            schema=schema_info,
            errors=[str(exc)],
            exit_code=EXIT_ERROR,
        )


def validation_result(
    *,
    valid: bool,
    artifact_path: str,
    schema: dict[str, Any] | None,
    errors: list[str],
    exit_code: int,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VALIDATION_SCHEMA_VERSION,
        "valid": valid,
        "artifact_path": artifact_path,
        "schema": schema,
        "errors": errors,
        "exit_code": exit_code,
    }


def render_validation_result(result: dict[str, Any]) -> str:
    status = "Valid" if result.get("valid") else "Invalid"
    schema = result.get("schema") if isinstance(result.get("schema"), dict) else {}
    lines = [
        f"{status}: {result.get('artifact_path', '')}",
        f"Schema: {schema.get('path') or ''}",
        f"Errors: {len(result.get('errors') or [])}",
    ]
    for error in result.get("errors") or []:
        lines.append(f"- {error}")
    return "\n".join(lines)


def _schema_record(root: Path, record: dict[str, Any], *, detected: bool) -> dict[str, Any]:
    path = str(record.get("path") or "")
    schema_path = root / path
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema listed in index does not exist: {path}")
    return {
        "id": record.get("id"),
        "path": _display_path(root, schema_path),
        "detected": detected,
    }


def _display_path(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _validate_value(value: Any, schema: dict[str, Any], path: str, errors: list[str]) -> None:
    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: expected constant {schema['const']!r}, got {value!r}")

    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: expected one of {schema['enum']!r}, got {value!r}")

    expected_type = schema.get("type")
    if expected_type is not None and not _matches_type(value, expected_type):
        errors.append(f"{path}: expected type {_type_label(expected_type)}, got {_json_type(value)}")
        return

    if isinstance(value, dict):
        required = schema.get("required") or []
        if isinstance(required, list):
            for key in required:
                if isinstance(key, str) and key not in value:
                    errors.append(f"{path}: missing required field {key!r}")

        properties = schema.get("properties") or {}
        if isinstance(properties, dict):
            for key, child_schema in properties.items():
                if key in value and isinstance(child_schema, dict):
                    _validate_value(value[key], child_schema, f"{path}.{key}", errors)

    if isinstance(value, list):
        items = schema.get("items")
        if isinstance(items, dict):
            for index, item in enumerate(value):
                _validate_value(item, items, f"{path}[{index}]", errors)


def _matches_type(value: Any, expected_type: Any) -> bool:
    expected = expected_type if isinstance(expected_type, list) else [expected_type]
    return any(_matches_single_type(value, item) for item in expected)


def _matches_single_type(value: Any, expected_type: Any) -> bool:
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "null":
        return value is None
    return True


def _json_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if isinstance(value, str):
        return "string"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    return type(value).__name__


def _type_label(expected_type: Any) -> str:
    if isinstance(expected_type, list):
        return " or ".join(str(item) for item in expected_type)
    return str(expected_type)
