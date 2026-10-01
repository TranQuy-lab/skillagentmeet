"""Tests for client capability-detection and the server/client transcript delta.

Offline: a fake in-memory client stands in for both a next-gen server (which
advertises ``server_filtering``) and a plain agentmeet.net server (which does
not). The point is that the *same* call works against both.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agentmeet import AgentMeet  # noqa: E402
from agentmeet.protocol import encode  # noqa: E402


def msg(mid, content, sender="A"):
    return {"message_id": mid, "agent_name": sender, "content": content, "timestamp": "2026-09-20T10:00:00Z"}


class FakeClient(AgentMeet):
    def __init__(self, messages, features):
        super().__init__(room="test-room", base_url="http://fake", agent_token="at_deadbeef")
        self._messages = list(messages)
        self._features = dict(features)
        self.calls = []

    def status(self):
        return {"room_code": "test-room", "features": self._features}

    def transcript(self, limit=None, offset=None, fmt=None, mark_read=False):
        off = offset or 0
        lim = limit or 100
        batch = self._messages[off:off + lim]
        return {
            "messages": batch,
            "total_messages": len(self._messages),
            "offset": off,
            "limit": lim,
            "has_more": (off + len(batch)) < len(self._messages),
        }

    def _request(self, method, path, *, params=None, body=None, raw_body=None):
        self.calls.append((method, path, params))
        return {"messages": self._messages, "total_messages": len(self._messages)}


MSGS = [
    msg(1, "hello", "Lead"),
    msg(2, "noise about weather", "Lead"),
    msg(3, "@Dev please fix cache", "Lead"),
    msg(4, encode("status", {"task": "T1", "state": "doing", "by": "Dev"}), "Dev"),
]


class TestCapabilities(unittest.TestCase):
    def test_no_features_on_plain_server(self):
        c = FakeClient(MSGS, {})
        self.assertEqual(c.features(), {})
        self.assertFalse(c.supports("server_filtering"))

    def test_features_detected(self):
        c = FakeClient(MSGS, {"server_filtering": True, "native_tasks": True})
        self.assertTrue(c.supports("server_filtering"))
        self.assertTrue(c.supports("native_tasks"))
        self.assertFalse(c.supports("sse_stream"))

    def test_server_filtered_path_sends_params(self):
        c = FakeClient(MSGS, {"server_filtering": True})
        out = c.transcript_delta(since_id=2, mention="Dev", kind="status")
        self.assertEqual(len(c.calls), 1, "server path must be a single request")
        _, _, params = c.calls[0]
        self.assertEqual(params["since_id"], "2")
        self.assertEqual(params["mention"], "Dev")
        self.assertEqual(params["kind"], "status")
        self.assertTrue(out.get("server_filtered"))

    def test_client_fallback_filters_locally(self):
        c = FakeClient(MSGS, {})
        # since_id=2 -> messages 3 and 4; mention Dev -> only 3
        out = c.transcript_delta(since_id=2, mention="Dev")
        self.assertEqual([m["message_id"] for m in out["messages"]], [3])
        self.assertFalse(out["server_filtered"])

    def test_client_fallback_kind_filter(self):
        c = FakeClient(MSGS, {})
        out = c.transcript_delta(since_id=0, kind="status")
        self.assertEqual([m["message_id"] for m in out["messages"]], [4])

    def test_client_fallback_respects_since(self):
        c = FakeClient(MSGS, {})
        out = c.transcript_delta(since_id=3)
        self.assertEqual([m["message_id"] for m in out["messages"]], [4])


if __name__ == "__main__":
    unittest.main()
