from __future__ import annotations

import json
import threading
import unittest
from urllib import request

from coderoblox_agent.server import JsonHttpServer
from coderoblox_agent.service import AgentService


def json_request(url: str, method: str = "GET", payload: dict | None = None) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with request.urlopen(req, timeout=5) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


class AgentServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.server = JsonHttpServer(("127.0.0.1", 0), AgentService())
        host, port = self.server.server_address
        self.base_url = f"http://{host}:{port}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def test_health_endpoint(self) -> None:
        payload = json_request(f"{self.base_url}/health")

        self.assertEqual(payload["status"], "ok")
        self.assertGreater(len(payload["supported_operations"]), 0)

    def test_session_snapshot_and_batch_roundtrip(self) -> None:
        session = json_request(
            f"{self.base_url}/api/sessions",
            method="POST",
            payload={
                "client_name": "studio-plugin",
                "project_root": "C:/Projects/CodeRoblox",
            },
        )
        session_id = session["session_id"]

        snapshot_ack = json_request(
            f"{self.base_url}/api/snapshots",
            method="POST",
            payload={
                "session_id": session_id,
                "snapshot": {
                    "captured_at": "2026-04-04T18:00:00+00:00",
                    "selection_paths": ["Workspace/Baseplate"],
                    "nodes": [],
                    "diagnostics": [],
                },
            },
        )
        self.assertEqual(snapshot_ack["session_id"], session_id)

        queue_result = json_request(
            f"{self.base_url}/api/operations/queue",
            method="POST",
            payload={
                "session_id": session_id,
                "operations": [
                    {
                        "operation_id": "op-1",
                        "kind": "apply_script_patch",
                        "target_path": "ReplicatedStorage/MyModule",
                        "payload": {"script_source": "return 1"},
                        "preconditions": {"expected_sha256": "abc123"},
                    }
                ],
            },
        )
        self.assertTrue(queue_result["queued"])

        next_batch = json_request(
            f"{self.base_url}/api/operations/next?session_id={session_id}",
            method="GET",
        )
        batch = next_batch["batch"]
        self.assertEqual(batch["status"], "dispatched")

        completion = json_request(
            f"{self.base_url}/api/operations/result",
            method="POST",
            payload={
                "session_id": session_id,
                "batch_id": batch["batch_id"],
                "outcomes": [
                    {
                        "operation_id": "op-1",
                        "success": True,
                        "message": "Applied patch.",
                        "changed_paths": ["ReplicatedStorage/MyModule"],
                    }
                ],
            },
        )
        self.assertEqual(completion["batch"]["status"], "completed")


if __name__ == "__main__":
    unittest.main()
