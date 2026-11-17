"""Pure comparison logic for MCP tool catalogues."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


class CatalogueError(ValueError):
    """Raised when a catalogue cannot be validated."""


@dataclass(frozen=True)
class ToolChange:
    name: str
    description_changed: bool
    input_schema_changed: bool
    metadata_changed: bool
    before_hash: str
    after_hash: str


@dataclass(frozen=True)
class DiffReport:
    approved_file: str
    live_file: str
    approved_catalogue_hash: str
    live_catalogue_hash: str
    exact_representation_changed: bool
    order_changed: bool
    added: list[str]
    removed: list[str]
    unchanged: list[str]
    changed: list[ToolChange]

    @property
    def has_drift(self) -> bool:
        return bool(self.added or self.removed or self.changed or self.order_changed)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["has_drift"] = self.has_drift
        return data


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _extract_tools(payload: Any, source: str) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        tools = payload.get("tools")
    else:
        tools = payload

    if not isinstance(tools, list):
        raise CatalogueError(f"{source}: expected a top-level array or an object with a 'tools' array")

    validated: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, tool in enumerate(tools):
        if not isinstance(tool, dict):
            raise CatalogueError(f"{source}: tool at index {index} must be an object")
        name = tool.get("name")
        if not isinstance(name, str) or not name.strip():
            raise CatalogueError(f"{source}: tool at index {index} needs a non-empty string 'name'")
        name = name.strip()
        if name in seen:
            raise CatalogueError(f"{source}: duplicate tool name '{name}'")
        seen.add(name)
        normalized = dict(tool)
        normalized["name"] = name
        validated.append(normalized)
    return validated


def load_catalogue(path: str | Path) -> list[dict[str, Any]]:
    path = Path(path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CatalogueError(f"{path}: file not found") from exc
    except json.JSONDecodeError as exc:
        raise CatalogueError(f"{path}: invalid JSON at line {exc.lineno}, column {exc.colno}") from exc
    return _extract_tools(payload, str(path))


def _metadata_without_known_fields(tool: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in tool.items() if key not in {"name", "description", "inputSchema"}}


def compare_catalogues(
    approved: list[dict[str, Any]],
    live: list[dict[str, Any]],
    approved_file: str = "approved",
    live_file: str = "live",
) -> DiffReport:
    approved_by_name = {tool["name"]: tool for tool in approved}
    live_by_name = {tool["name"]: tool for tool in live}

    approved_names = [tool["name"] for tool in approved]
    live_names = [tool["name"] for tool in live]

    added = sorted(set(live_by_name) - set(approved_by_name))
    removed = sorted(set(approved_by_name) - set(live_by_name))
    common = sorted(set(approved_by_name) & set(live_by_name))

    changed: list[ToolChange] = []
    unchanged: list[str] = []
    for name in common:
        before = approved_by_name[name]
        after = live_by_name[name]
        if _canonical(before) == _canonical(after):
            unchanged.append(name)
            continue
        changed.append(
            ToolChange(
                name=name,
                description_changed=before.get("description") != after.get("description"),
                input_schema_changed=before.get("inputSchema") != after.get("inputSchema"),
                metadata_changed=_metadata_without_known_fields(before) != _metadata_without_known_fields(after),
                before_hash=_hash(before),
                after_hash=_hash(after),
            )
        )

    approved_common_order = [name for name in approved_names if name in common]
    live_common_order = [name for name in live_names if name in common]

    return DiffReport(
        approved_file=approved_file,
        live_file=live_file,
        approved_catalogue_hash=_hash(approved),
        live_catalogue_hash=_hash(live),
        exact_representation_changed=_canonical(approved) != _canonical(live),
        order_changed=approved_common_order != live_common_order,
        added=added,
        removed=removed,
        unchanged=unchanged,
        changed=changed,
    )


def compare_files(approved_path: str | Path, live_path: str | Path) -> DiffReport:
    approved_path = Path(approved_path)
    live_path = Path(live_path)
    approved = load_catalogue(approved_path)
    live = load_catalogue(live_path)
    return compare_catalogues(approved, live, str(approved_path), str(live_path))


def render_text(report: DiffReport) -> str:
    lines = ["MCP catalogue drift detected" if report.has_drift else "No MCP catalogue drift detected"]
    lines.append(f"Approved catalogue SHA-256: {report.approved_catalogue_hash}")
    lines.append(f"Live catalogue SHA-256:     {report.live_catalogue_hash}")
    lines.append(f"Order changed: {'yes' if report.order_changed else 'no'}")
    lines.append(f"Added tools: {', '.join(report.added) if report.added else 'none'}")
    lines.append(f"Removed tools: {', '.join(report.removed) if report.removed else 'none'}")

    if report.changed:
        lines.append("Changed tools:")
        for change in report.changed:
            fields = []
            if change.description_changed:
                fields.append("description")
            if change.input_schema_changed:
                fields.append("inputSchema")
            if change.metadata_changed:
                fields.append("metadata")
            lines.append(f"  - {change.name}: {', '.join(fields) or 'representation'}")
    else:
        lines.append("Changed tools: none")

    lines.append(f"Unchanged tools: {', '.join(report.unchanged) if report.unchanged else 'none'}")
    return "\n".join(lines)
