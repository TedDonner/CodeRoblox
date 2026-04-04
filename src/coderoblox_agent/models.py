from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class IssueSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


class BatchStatus(StrEnum):
    QUEUED = "queued"
    DISPATCHED = "dispatched"
    COMPLETED = "completed"
    FAILED = "failed"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AuditEventType(StrEnum):
    SESSION_CREATED = "session_created"
    SNAPSHOT_STORED = "snapshot_stored"
    CHECKPOINT_CREATED = "checkpoint_created"
    BATCH_QUEUED = "batch_queued"
    BATCH_DISPATCHED = "batch_dispatched"
    BATCH_COMPLETED = "batch_completed"
    BATCH_FAILED = "batch_failed"
    ROLLBACK_REQUESTED = "rollback_requested"


SUPPORTED_OPERATION_KINDS = {
    "get_project_snapshot",
    "get_selection",
    "read_scripts",
    "apply_script_patch",
    "create_instance",
    "update_properties",
    "reparent_instance",
    "delete_instance",
    "run_playtest",
    "collect_output",
    "create_checkpoint",
    "rollback_checkpoint",
}

HIGH_RISK_OPERATION_KINDS = {"delete_instance", "rollback_checkpoint"}
MEDIUM_RISK_OPERATION_KINDS = {
    "apply_script_patch",
    "create_instance",
    "update_properties",
    "reparent_instance",
    "run_playtest",
}
DESTRUCTIVE_OPERATION_KINDS = {"delete_instance", "rollback_checkpoint"}
MUTATING_OPERATION_KINDS = {
    "apply_script_patch",
    "create_instance",
    "update_properties",
    "reparent_instance",
    "delete_instance",
    "create_checkpoint",
    "rollback_checkpoint",
}


def risk_for_kind(kind: str) -> RiskLevel:
    if kind in HIGH_RISK_OPERATION_KINDS:
        return RiskLevel.HIGH
    if kind in MEDIUM_RISK_OPERATION_KINDS:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


@dataclass(slots=True)
class ValidationIssue:
    severity: IssueSeverity
    code: str
    message: str
    operation_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity.value,
            "code": self.code,
            "message": self.message,
            "operation_id": self.operation_id,
        }


@dataclass(slots=True)
class Operation:
    operation_id: str
    kind: str
    target_path: str
    payload: dict[str, Any] = field(default_factory=dict)
    preconditions: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Operation":
        return cls(
            operation_id=str(raw["operation_id"]),
            kind=str(raw["kind"]),
            target_path=str(raw.get("target_path", "")),
            payload=dict(raw.get("payload", {})),
            preconditions=dict(raw.get("preconditions", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "kind": self.kind,
            "target_path": self.target_path,
            "payload": self.payload,
            "preconditions": self.preconditions,
            "risk_level": risk_for_kind(self.kind).value,
        }


@dataclass(slots=True)
class OperationOutcome:
    operation_id: str
    success: bool
    message: str
    changed_paths: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "OperationOutcome":
        return cls(
            operation_id=str(raw["operation_id"]),
            success=bool(raw["success"]),
            message=str(raw.get("message", "")),
            changed_paths=[str(item) for item in raw.get("changed_paths", [])],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "success": self.success,
            "message": self.message,
            "changed_paths": list(self.changed_paths),
        }


@dataclass(slots=True)
class SnapshotNode:
    path: str
    name: str
    class_name: str
    script_source: str | None = None
    children: list["SnapshotNode"] = field(default_factory=list)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "SnapshotNode":
        return cls(
            path=str(raw["path"]),
            name=str(raw["name"]),
            class_name=str(raw["class_name"]),
            script_source=raw.get("script_source"),
            children=[cls.from_dict(child) for child in raw.get("children", [])],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "name": self.name,
            "class_name": self.class_name,
            "script_source": self.script_source,
            "children": [child.to_dict() for child in self.children],
        }


@dataclass(slots=True)
class ProjectSnapshot:
    captured_at: str
    selection_paths: list[str] = field(default_factory=list)
    nodes: list[SnapshotNode] = field(default_factory=list)
    diagnostics: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ProjectSnapshot":
        return cls(
            captured_at=str(raw["captured_at"]),
            selection_paths=[str(item) for item in raw.get("selection_paths", [])],
            nodes=[SnapshotNode.from_dict(node) for node in raw.get("nodes", [])],
            diagnostics=[dict(item) for item in raw.get("diagnostics", [])],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "captured_at": self.captured_at,
            "selection_paths": list(self.selection_paths),
            "nodes": [node.to_dict() for node in self.nodes],
            "diagnostics": list(self.diagnostics),
        }


@dataclass(slots=True)
class Checkpoint:
    checkpoint_id: str
    label: str
    created_at: str
    snapshot_digest: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "label": self.label,
            "created_at": self.created_at,
            "snapshot_digest": self.snapshot_digest,
        }


@dataclass(slots=True)
class AuditEvent:
    event_type: AuditEventType
    created_at: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type.value,
            "created_at": self.created_at,
            "details": self.details,
        }


@dataclass(slots=True)
class OperationBatch:
    batch_id: str
    session_id: str
    operations: list[Operation]
    status: BatchStatus
    created_at: str
    checkpoint_id: str | None = None
    outcomes: list[OperationOutcome] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "session_id": self.session_id,
            "status": self.status.value,
            "created_at": self.created_at,
            "checkpoint_id": self.checkpoint_id,
            "operations": [operation.to_dict() for operation in self.operations],
            "outcomes": [outcome.to_dict() for outcome in self.outcomes],
        }


@dataclass(slots=True)
class SessionContext:
    session_id: str
    client_name: str
    project_root: str
    created_at: str
    capabilities: dict[str, Any] = field(default_factory=dict)
    latest_snapshot: ProjectSnapshot | None = None
    checkpoints: dict[str, Checkpoint] = field(default_factory=dict)
    batches: dict[str, OperationBatch] = field(default_factory=dict)
    audit_log: list[AuditEvent] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "client_name": self.client_name,
            "project_root": self.project_root,
            "created_at": self.created_at,
            "capabilities": self.capabilities,
            "latest_snapshot": None if self.latest_snapshot is None else self.latest_snapshot.to_dict(),
            "checkpoints": [checkpoint.to_dict() for checkpoint in self.checkpoints.values()],
            "batches": [batch.to_dict() for batch in self.batches.values()],
            "audit_log": [entry.to_dict() for entry in self.audit_log],
        }
