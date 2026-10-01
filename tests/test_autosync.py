"""Tests for scripts/auto_sync.py (offline, no network)."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agentmeet import AgentMeet  # noqa: E402
from scripts.auto_sync import (  # noqa: E402
    MARKER,
    append_context,
    format_digest,
    load_state,
    save_state,
    sync_once,
)


def msg(mid, content, sender="A"):
    return {"message_id": mid, "agent_name": sender, "content": content, "timestamp": "2026-09-20T10:00:00Z"}


class FakeClient(AgentMeet):
    def __init__(self, messages):
        super().__init__(room="r", base_url="http://fake", agent_token="at_x")
        self._messages = messages
        self.seen_since = []

    def transcript_delta(self, since_id=0, **kw):
        self.seen_since.append(since_id)
        return {"messages": [m for m in self._messages if m["message_id"] > since_id], "server_filtered": True}


class TestAutoSync(unittest.TestCase):
    def test_format_digest_summarises_kinds(self):
        block = format_digest([
            msg(1, "hi", "Lead"),
            msg(2, '{"v":1,"kind":"task","data":{"task":"T1"}}', "Lead"),
        ])
        self.assertIn("2 msg", block)
        self.assertIn("task=1", block)
        self.assertIn("#1", block)

    def test_sync_once_appends_and_advances(self):
        with tempfile.TemporaryDirectory() as td:
            ctx = Path(td) / "notes.md"
            state = {"room": "r", "last_message_id": 0}
            client = FakeClient([msg(1, "a"), msg(2, "b")])
            n = sync_once(client, state, ctx)
            self.assertEqual(n, 2)
            self.assertEqual(state["last_message_id"], 2)
            text = ctx.read_text(encoding="utf-8")
            self.assertIn(MARKER, text)
            self.assertIn("#2", text)

            # second run: nothing new
            self.assertEqual(sync_once(client, state, ctx), 0)
            self.assertEqual(client.seen_since, [0, 2])

    def test_state_roundtrip_ignores_other_rooms(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "s.json"
            save_state(p, {"room": "r", "last_message_id": 42})
            self.assertEqual(load_state(p, "r")["last_message_id"], 42)
            self.assertEqual(load_state(p, "other")["last_message_id"], 0)

    def test_append_creates_header_once(self):
        with tempfile.TemporaryDirectory() as td:
            ctx = Path(td) / "n.md"
            append_context(ctx, "block1\n")
            append_context(ctx, "block2\n")
            text = ctx.read_text(encoding="utf-8")
            self.assertEqual(text.count(MARKER), 1)
            self.assertIn("block1", text)
            self.assertIn("block2", text)


if __name__ == "__main__":
    unittest.main()
