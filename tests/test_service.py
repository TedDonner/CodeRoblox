from __future__ import annotations

import unittest

from coderoblox_agent.models import Operation, OperationOutcome, ProjectSnapshot
from coderoblox_agent.service import AgentService


def make_snapshot() -> ProjectSnapshot:
    return ProjectSnapshot(
        captured_at="2026-04-04T18:00:00+00:00",
        selection_paths=["Workspace/Baseplate"],
        nodes=[],
        diagnostics=[],
    )


def patch_operation(operation_id: str = "op-1") -> Operation:
    return Operation(
        operation_id=operation_id,
        kind="apply_script_patch",
        target_path="ReplicatedStorage/MyModule",
        payload={"script_source": "return 1"},
        preconditions={"expected_sha256": "abc123"},
    )


class AgentServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = AgentService()
        session = self.service.start_session(
            client_name="test-suite",
            project_root="/tmp/coderoblox",
        )
        self.session_id = session["session_id"]
        self.service.store_snapshot(self.session_id, make_snapshot())

    def test_duplicate_operation_ids_are_blocked(self) -> None:
        operations = [patch_operation("duplicate"), patch_operation("duplicate")]

        report = self.service.validate_operations(self.session_id, operations)

        self.assertFalse(report["allowed"])
        self.assertTrue(
            any(issue["code"] == "duplicate_operation_id" for issue in report["issues"])
        )

    def test_script_patch_requires_expected_sha(self) -> None:
        operation = patch_operation()
        operation.preconditions = {}

        report = self.service.validate_operations(self.session_id, [operation])

        self.assertFalse(report["allowed"])
        self.assertTrue(
            any(issue["code"] == "missing_expected_sha256" for issue in report["issues"])
        )

    def test_destructive_operations_require_explicit_approval(self) -> None:
        operation = Operation(
            operation_id="delete-1",
            kind="delete_instance",
            target_path="Workspace/OldPart",
        )

        report = self.service.validate_operations(self.session_id, [operation])

        self.assertFalse(report["allowed"])
        self.assertTrue(
            any(
                issue["code"] == "destructive_operation_requires_approval"
                for issue in report["issues"]
            )
        )

    def test_queue_and_complete_batch_creates_audit_entries(self) -> None:
        result = self.service.queue_operations(self.session_id, [patch_operation()])

        self.assertTrue(result["queued"])
        batch_id = result["batch"]["batch_id"]
        self.assertIsNotNone(result["batch"]["checkpoint_id"])

        next_batch = self.service.next_batch(self.session_id)
        self.assertEqual(next_batch["batch"]["batch_id"], batch_id)

        completion = self.service.complete_batch(
            self.session_id,
            batch_id,
            [
                OperationOutcome(
                    operation_id="op-1",
                    success=True,
                    message="Applied patch.",
                    changed_paths=["ReplicatedStorage/MyModule"],
                )
            ],
        )

        self.assertEqual(completion["batch"]["status"], "completed")
        session = self.service.get_session(self.session_id)
        event_types = [entry.event_type.value for entry in session.audit_log]
        self.assertIn("batch_queued", event_types)
        self.assertIn("batch_dispatched", event_types)
        self.assertIn("batch_completed", event_types)

    def test_queue_rollback_creates_destructive_batch(self) -> None:
        checkpoint = self.service.create_checkpoint(self.session_id, "before-risky-change")

        result = self.service.queue_rollback(self.session_id, checkpoint.checkpoint_id)

        self.assertTrue(result["queued"])
        self.assertEqual(result["batch"]["operations"][0]["kind"], "rollback_checkpoint")


if __name__ == "__main__":
    unittest.main()
