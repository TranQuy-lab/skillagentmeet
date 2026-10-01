"""Filter/render tests for scripts/inbox.py (pure, offline).

These lock in the context-saving behaviour: the filters must drop messages *in
the client* so an agent never pulls a whole room into context to find a few.
"""

import argparse
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.inbox import _matches, _render, _summary, extract_mentions  # noqa: E402


def m(content, sender="AgentA", mid=1):
    return {"message_id": mid, "agent_name": sender, "content": content, "timestamp": "2026-09-20T09:00:00Z"}


def args(**kw):
    base = dict(
        exclude_mine=False, from_agents=[], keywords=[], mention=None, mention_me=False,
        kind=None, task=None, grep=None,
    )
    base.update(kw)
    return argparse.Namespace(**base)


class TestInboxFilters(unittest.TestCase):
    def test_from_and_exclude_mine(self):
        msg = m("hello", sender="Admin")
        self.assertTrue(_matches(msg, args(), "me"))
        self.assertFalse(_matches(msg, args(from_agents=["opencode"]), "me"))
        self.assertTrue(_matches(msg, args(from_agents=["ad"]), "me"))  # substring, ci
        self.assertFalse(_matches(msg, args(exclude_mine=True), "Admin"))

    def test_contains_and_mention(self):
        msg = m("please @DevAgent fix the cache", sender="Lead")
        self.assertTrue(_matches(msg, args(keywords=["cache"]), "me"))
        self.assertFalse(_matches(msg, args(keywords=["zzz"]), "me"))
        self.assertTrue(_matches(msg, args(mention="DevAgent"), "me"))
        self.assertFalse(_matches(msg, args(mention="Other"), "me"))
        self.assertTrue(_matches(msg, args(mention_me=True), "DevAgent"))
        self.assertFalse(_matches(msg, args(mention_me=True), "Nobody"))

    def test_kind_and_task_envelopes(self):
        env = '{"v":1,"kind":"status","data":{"task":"T1","state":"doing","by":"A"}}'
        msg = m(env, sender="A")
        self.assertTrue(_matches(msg, args(kind="status"), "me"))
        self.assertFalse(_matches(msg, args(kind="verify"), "me"))
        self.assertTrue(_matches(msg, args(task="T1"), "me"))
        self.assertFalse(_matches(msg, args(task="T2"), "me"))
        # a plain chat message is not a protocol envelope
        self.assertFalse(_matches(m("just chatting"), args(kind="status"), "me"))

    def test_grep(self):
        msg = m("the flag is number{abc}")
        self.assertTrue(_matches(msg, args(grep=r"flag|number"), "me"))
        self.assertFalse(_matches(msg, args(grep=r"^zzz"), "me"))

    def test_mentions_are_deduped(self):
        self.assertEqual(extract_mentions("@A hi @B and @A"), ["A", "B"])

    def test_render_compact_truncates(self):
        long = "x" * 500
        line = _render(m(long), width=400, compact=True)
        self.assertLessEqual(len(line), 160)
        full = _render(m("hi"), width=400, compact=False)
        self.assertIn("#1", full)

    def test_summary_counts(self):
        shown = [m("a", sender="A"), m("b", sender="A"), m('{"v":1,"kind":"task","data":{}}', sender="B")]
        s = _summary(shown)
        self.assertIn("3 message", s)
        self.assertIn("A=2", s)
        self.assertIn("task=1", s)


if __name__ == "__main__":
    unittest.main()
