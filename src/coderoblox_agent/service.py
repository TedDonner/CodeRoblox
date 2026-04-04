from __future__ import annotations

import hashlib
import json
import uuid
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from .models import (
    AuditEvent,
    AuditEventType,
    BatchStatus,
    Checkpoint,
    DESTRUCTIVE_OPERATION_KINDS,
    IssueSeverity,
    MUTATING_OPERATION_KINDS,
    Operation,
    OperationBatch,
    OperationOutcome,
    ProjectSnapshot,
    SUPPORTED_OPERATION_KINDS,
    SessionContext,
    ValidationIssue,
    risk_for_kind,
)


class AgentError(Exception):
    """Base error for the local agent."""


class SessionNotFoundError(AgentError):
    """Raised when a session does not exist."""


class BatchNotFoundError(AgentError):
    """Raised when a batch does not exist."""


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def snapshot_digest(snapshot: ProjectSnapshot | None) -> str | None:
    if snapshot is None:
        return None

    payload = json.dumps(snapshot.to_dict(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class AgentService:
    """Coordinates Studio sessions, queued operations, checkpoints, and audit logs."""

    def __init__(self) -> None:
        self._sessions: dict[str, SessionContext] = {}

    def health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "supported_operations": sorted(SUPPORTED_OPERATION_KINDS),
            "session_count": len(self._sessions),
        }

    def start_session(
        self,
        client_name: str,
        project_root: str,
        capabilities: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        session_id = f"session-{uuid.uuid4().hex[:12]}"
        session = SessionContext(
            session_id=session_id,
            client_name=client_name,
            project_root=project_root,
            created_at=utc_now(),
            capabilities=capabilities or {},
        )
        session.audit_log.append(
            AuditEvent(
                event_type=AuditEventType.SESSION_CREATED,
                created_at=utc_now(),
                details={"client_name": client_name, "project_root": project_root},
            )
        )
        self._sessions[session_id] = session
        return {
            "session_id": session.session_id,
            "created_at": session.created_at,
            "supported_operations": sorted(SUPPORTED_OPERATION_KINDS),
        }

    def get_session(self, session_id: str) -> SessionContext:
        try:
            return self._sessions[session_id]
        except KeyError as exc:
            raise SessionNotFoundError(f"Unknown session: {session_id}") from exc

    def store_snapshot(self, session_id: str, snapshot: ProjectSnapshot) -> dict[str, Any]:
        session = self.get_session(session_id)
        session.latest_snapshot = snapshot
        digest = snapshot_digest(snapshot)
        session.audit_log.append(
            AuditEvent(
                event_type=AuditEventType.SNAPSHOT_STORED,
                created_at=utc_now(),
                details={
                    "captured_at": snapshot.captured_at,
                    "selection_paths": snapshot.selection_paths,
                    "snapshot_digest": digest,
                },
            )
        )
        return {"session_id": session_id, "snapshot_digest": digest}

    def validate_operations(
        self,
        session_id: str,
        operations: list[Operation],
        allow_destructive: bool = False,
    ) -> dict[str, Any]:
        self.get_session(session_id)
        issues: list[ValidationIssue] = []
        operation_ids = Counter(operation.operation_id for operation in operations)
        risk_summary = Counter(risk_for_kind(operation.kind).value for operation in operations)
        kind_summary = Counter(operation.kind for operation in operations)

        for operation in operations:
            if operation_ids[operation.operation_id] > 1:
                issues.append(
                    ValidationIssue(
                        severity=IssueSeverity.ERROR,
                        code="duplicate_operation_id",
                        message="Operation ids must be unique within a batch.",
                        operation_id=operation.operation_id,
                    )
                )

            if operation.kind not in SUPPORTED_OPERATION_KINDS:
                issues.append(
                    ValidationIssue(
                        severity=IssueSeverity.ERROR,
                        code="unsupported_operation",
                        message=f"Unsupported operation kind: {operation.kind}",
                        operation_id=operation.operation_id,
                    )
                )
                continue

            if operation.kind in DESTRUCTIVE_OPERATION_KINDS and not allow_destructive:
                issues.append(
                    ValidationIssue(
                        severity=IssueSeverity.ERROR,
                        code="destructive_operation_requires_approval",
                        message="Destructive operations require explicit approval.",
                        operation_id=operation.operation_id,
                    )
                )

            if operation.kind == "apply_script_patch":
                if not isinstance(operation.payload.get("script_source"), str):
                    issues.append(
                        ValidationIssue(
                            severity=IssueSeverity.ERROR,
                            code="missing_script_source",
                            message="apply_script_patch requires payload.script_source.",
                            operation_id=operation.operation_id,
                        )
                    )
                if not isinstance(operation.preconditions.get("expected_sha256"), str):
                    issues.append(
                        ValidationIssue(
                            severity=IssueSeverity.ERROR,
                            code="missing_expected_sha256",
                            message="apply_script_patch requires preconditions.expected_sha256.",
                            operation_id=operation.operation_id,
                        )
                    )

            if operation.kind == "create_instance":
                if not isinstance(operation.payload.get("class_name"), str):
                    issues.append(
                        ValidationIssue(
                            severity=IssueSeverity.ERROR,
                            code="missing_class_name",
                            message="create_instance requires payload.class_name.",
                            operation_id=operation.operation_id,
                        )
                    )
                if not isinstance(operation.payload.get("parent_path"), str):
                    issues.append(
                        ValidationIssue(
                            severity=IssueSeverity.ERROR,
                            code="missing_parent_path",
                            message="create_instance requires payload.parent_path.",
                            operation_id=operation.operation_id,
                        )
                    )
                if not isinstance(operation.payload.get("name"), str):
                    issues.append(
                        ValidationIssue(
                            severity=IssueSeverity.ERROR,
                            code="missing_name",
                            message="create_instance requires payload.name.",
                            operation_id=operation.operation_id,
                        )
                    )

            if operation.kind == "update_properties" and not isinstance(
                operation.payload.get("properties"), dict
            ):
                issues.append(
                    ValidationIssue(
                        severity=IssueSeverity.ERROR,
                        code="missing_properties",
                        message="update_properties requires payload.properties.",
                        operation_id=operation.operation_id,
                    )
                )

            if operation.kind == "reparent_instance" and not isinstance(
                operation.payload.get("new_parent_path"), str
            ):
                issues.append(
                    ValidationIssue(
                        severity=IssueSeverity.ERROR,
                        code="missing_new_parent_path",
                        message="reparent_instance requires payload.new_parent_path.",
                        operation_id=operation.operation_id,
                    )
                )

            if operation.kind == "rollback_checkpoint" and not isinstance(
                operation.payload.get("checkpoint_id"), str
            ):
                issues.append(
                    ValidationIssue(
                        severity=IssueSeverity.ERROR,
                        code="missing_checkpoint_id",
                        message="rollback_checkpoint requires payload.checkpoint_id.",
                        operation_id=operation.operation_id,
                    )
                )

        return {
            "allowed": not any(issue.severity == IssueSeverity.ERROR for issue in issues),
            "issues": [issue.to_dict() for issue in issues],
            "summary": {
                "total": len(operations),
                "destructive": sum(
                    1 for operation in operations if operation.kind in DESTRUCTIVE_OPERATION_KINDS
                ),
                "risk_levels": dict(risk_summary),
                "by_kind": dict(kind_summary),
            },
        }

    def create_checkpoint(self, session_id: str, label: str) -> Checkpoint:
        session = self.get_session(session_id)
        checkpoint = Checkpoint(
            checkpoint_id=f"chk-{uuid.uuid4().hex[:12]}",
            label=label,
            created_at=utc_now(),
            snapshot_digest=snapshot_digest(session.latest_snapshot),
        )
        session.checkpoints[checkpoint.checkpoint_id] = checkpoint
        session.audit_log.append(
            AuditEvent(
                event_type=AuditEventType.CHECKPOINT_CREATED,
                created_at=utc_now(),
                details=checkpoint.to_dict(),
            )
        )
        return checkpoint

    def queue_operations(
        self,
        session_id: str,
        operations: list[Operation],
        allow_destructive: bool = False,
    ) -> dict[str, Any]:
        session = self.get_session(session_id)
        validation = self.validate_operations(
            session_id=session_id,
            operations=operations,
            allow_destructive=allow_destructive,
        )
        if not validation["allowed"]:
            return {"queued": False, "validation": validation}

        checkpoint_id = None
        if any(operation.kind in MUTATING_OPERATION_KINDS for operation in operations):
            checkpoint = self.create_checkpoint(session_id, label=f"auto-before-{len(session.batches) + 1}")
            checkpoint_id = checkpoint.checkpoint_id

        batch = OperationBatch(
            batch_id=f"batch-{uuid.uuid4().hex[:12]}",
            session_id=session_id,
            operations=operations,
            status=BatchStatus.QUEUED,
            created_at=utc_now(),
            checkpoint_id=checkpoint_id,
        )
        session.batches[batch.batch_id] = batch
        session.audit_log.append(
            AuditEvent(
                event_type=AuditEventType.BATCH_QUEUED,
                created_at=utc_now(),
                details={"batch_id": batch.batch_id, "checkpoint_id": checkpoint_id},
            )
        )
        return {"queued": True, "validation": validation, "batch": batch.to_dict()}

    def next_batch(self, session_id: str) -> dict[str, Any]:
        session = self.get_session(session_id)
        queued_batches = [
            batch for batch in session.batches.values() if batch.status == BatchStatus.QUEUED
        ]
        queued_batches.sort(key=lambda batch: batch.created_at)
        if not queued_batches:
            return {"batch": None}

        batch = queued_batches[0]
        batch.status = BatchStatus.DISPATCHED
        session.audit_log.append(
            AuditEvent(
                event_type=AuditEventType.BATCH_DISPATCHED,
                created_at=utc_now(),
                details={"batch_id": batch.batch_id},
            )
        )
        return {"batch": batch.to_dict()}

    def complete_batch(
        self,
        session_id: str,
        batch_id: str,
        outcomes: list[OperationOutcome],
    ) -> dict[str, Any]:
        session = self.get_session(session_id)
        try:
            batch = session.batches[batch_id]
        except KeyError as exc:
            raise BatchNotFoundError(f"Unknown batch: {batch_id}") from exc

        batch.outcomes = outcomes
        all_success = all(outcome.success for outcome in outcomes)
        batch.status = BatchStatus.COMPLETED if all_success else BatchStatus.FAILED
        event_type = (
            AuditEventType.BATCH_COMPLETED if all_success else AuditEventType.BATCH_FAILED
        )
        session.audit_log.append(
            AuditEvent(
                event_type=event_type,
                created_at=utc_now(),
                details={
                    "batch_id": batch_id,
                    "outcome_count": len(outcomes),
                    "status": batch.status.value,
                },
            )
        )
        return {"batch": batch.to_dict()}

    def queue_rollback(self, session_id: str, checkpoint_id: str) -> dict[str, Any]:
        session = self.get_session(session_id)
        if checkpoint_id not in session.checkpoints:
            raise AgentError(f"Unknown checkpoint: {checkpoint_id}")

        operation = Operation(
            operation_id=f"rollback-{uuid.uuid4().hex[:8]}",
            kind="rollback_checkpoint",
            target_path="",
            payload={"checkpoint_id": checkpoint_id},
            preconditions={},
        )
        result = self.queue_operations(
            session_id=session_id,
            operations=[operation],
            allow_destructive=True,
        )
        session.audit_log.append(
            AuditEvent(
                event_type=AuditEventType.ROLLBACK_REQUESTED,
                created_at=utc_now(),
                details={"checkpoint_id": checkpoint_id},
            )
        )
        return result
