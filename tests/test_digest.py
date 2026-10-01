"""Unit tests for scripts/digest.py activity summarizer."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agentmeet.protocol import encode
from scripts.digest import build_digest, format_markdown, categorize_message


class TestDigest(unittest.TestCase):
    def setUp(self):
        self.sample_messages = [
            {"message_id": 1, "agent_name": "Lead", "content": "Welcome team to the room!", "timestamp": "2026-09-20T10:00:00Z"},
            {"message_id": 2, "agent_name": "Dev", "content": encode("task", {"task": "T1", "title": "Build Cache"}), "timestamp": "2026-09-20T10:01:00Z"},
            {"message_id": 3, "agent_name": "Dev", "content": encode("status", {"task": "T1", "state": "review"}), "timestamp": "2026-09-20T10:02:00Z"},
            {"message_id": 4, "agent_name": "Verifier", "content": encode("verify", {"task": "T1", "verdict": "pass", "note": "Tested 100%"}), "timestamp": "2026-09-20T10:03:00Z"},
            {"message_id": 5, "agent_name": "Lead", "content": "@Dev @Verifier great job on T1", "timestamp": "2026-09-20T10:04:00Z"},
        ]

    def test_build_digest_counts_and_events(self):
        digest = build_digest(self.sample_messages)
        self.assertEqual(digest["total_messages"], 5)
        self.assertEqual(digest["earliest_id"], 1)
        self.assertEqual(digest["latest_id"], 5)
        
        # Check agent participation
        agents = digest["agents"]
        self.assertIn("Lead", agents)
        self.assertIn("Dev", agents)
        self.assertIn("Verifier", agents)
        self.assertEqual(agents["Dev"]["total"], 2)
        
        # Check task events
        tasks = digest["tasks"]
        self.assertEqual(len(tasks), 3) # task, status, verify
        self.assertEqual(tasks[0]["kind"], "task")
        self.assertEqual(tasks[1]["kind"], "status")
        self.assertEqual(tasks[2]["kind"], "verify")
        self.assertEqual(tasks[2]["verdict"], "pass")

    def test_format_markdown_renders_tables(self):
        digest = build_digest(self.sample_messages)
        md = format_markdown(digest)
        self.assertIn("# 📊 Team Activity Digest", md)
        self.assertIn("| **Dev** |", md)
        self.assertIn("| #4 | Verifier | `verify` | **T1** | `pass` |", md)
        self.assertIn("@Dev", md)

    def test_filter_by_agent(self):
        digest = build_digest(self.sample_messages, target_agent="Dev")
        self.assertEqual(digest["total_messages"], 2)
        self.assertEqual(list(digest["agents"].keys()), ["Dev"])


if __name__ == "__main__":
    unittest.main()
