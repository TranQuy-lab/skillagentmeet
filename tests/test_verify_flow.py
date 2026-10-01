"""Tests for the verification gate and the new protocol kinds.

Pure/offline: these fold hand-built envelopes, no network. They exist so the
"no task is done without independent verification" rule is enforced by code that
a verifier can run, not by prose (see docs/OPERATIONS.md, docs/VERIFIER_GUIDE.md).
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agentmeet.protocol import (  # noqa: E402
    build_board,
    board_summary,
    decode,
    encode,
    KIND_VERIFY,
    KIND_HEARTBEAT,
    KIND_CONTROL,
)


def msg(content, sender="AgentA", mid=0):
    return {"message_id": mid, "agent_name": sender, "content": content, "timestamp": ""}


class TestVerifyGate(unittest.TestCase):
    def _board(self):
        msgs = [
            msg(encode("task", {"task": "T1", "title": "x", "by": "Lead"}), "Lead", 1),
            msg(encode("claim", {"task": "T1", "by": "AgentA"}), "AgentA", 2),
            msg(encode("status", {"task": "T1", "state": "review", "by": "AgentA"}), "AgentA", 3),
        ]
        return build_board(msgs), msgs

    def test_done_without_verify_is_flagged(self):
        board, msgs = self._board()
        msgs.append(msg(encode("status", {"task": "T1", "state": "done", "by": "AgentA"}), "AgentA", 4))
        board = build_board(msgs)
        self.assertTrue(board["T1"].status == "done")
        self.assertFalse(board["T1"].verified)
        self.assertIn("| NO |", board_summary(board))

    def test_verify_pass_sets_verified(self):
        board, msgs = self._board()
        msgs.append(msg(encode("verify", {"task": "T1", "verdict": "pass", "by": "Verifier"}), "Verifier", 4))
        board = build_board(msgs)
        self.assertTrue(board["T1"].verified)
        self.assertIn("| yes |", board_summary(board))

    def test_verify_fail_clears_and_notes(self):
        board, msgs = self._board()
        msgs.append(msg(encode("verify", {"task": "T1", "verdict": "pass", "by": "V"}), "V", 4))
        msgs.append(msg(encode("verify", {"task": "T1", "verdict": "fail", "note": "crc mismatch", "by": "V2"}), "V2", 5))
        board = build_board(msgs)
        self.assertFalse(board["T1"].verified)
        self.assertTrue(any("VERIFY FAIL" in n for n in board["T1"].notes))

    def test_heartbeat_and_control_roundtrip(self):
        hb = decode(encode("heartbeat", {"by": "A", "state": "doing", "note": "alive"}))
        self.assertEqual(hb.kind, KIND_HEARTBEAT)
        self.assertEqual(hb.data["note"], "alive")
        ctl = decode(encode("control", {"action": "scope-freeze", "by": "Lead"}))
        self.assertEqual(ctl.kind, KIND_CONTROL)
        self.assertEqual(ctl.data["action"], "scope-freeze")

    def test_heartbeat_does_not_change_state(self):
        board, msgs = self._board()
        msgs.append(msg(encode("heartbeat", {"by": "AgentA", "note": "still here"}), "AgentA", 4))
        board = build_board(msgs)
    def test_self_verify_rejected_by_protocol(self):
        board, msgs = self._board()
        # Owner of T1 is AgentA. AgentA tries to verify pass on T1.
        msgs.append(msg(encode("verify", {"task": "T1", "verdict": "pass", "by": "AgentA"}), "AgentA", 4))
        board = build_board(msgs)
        self.assertFalse(board["T1"].verified, "Author self-verification must not set verified=True")
        self.assertTrue(any("cannot self-verify" in n for n in board["T1"].notes))

    def test_clear_dissent_clears_active_flag_and_records_note(self):
        board, msgs = self._board()
        msgs.append(msg(encode("dissent", {"task": "T1", "reason": "touches auth logic", "by": "Auditor"}), "Auditor", 4))
        board = build_board(msgs)
        self.assertEqual(len(board["T1"].dissent), 1)
        self.assertIn("Auditor: touches auth logic", board["T1"].dissent[0])

        # Now issue clear_dissent
        msgs.append(msg(encode("clear_dissent", {"task": "T1", "reason": "auth logic fixed and verified", "by": "Auditor"}), "Auditor", 5))
        board = build_board(msgs)
        self.assertEqual(len(board["T1"].dissent), 0, "Dissent list must be cleared")
        self.assertTrue(any("DISSENT CLEARED by Auditor: auth logic fixed and verified" in n for n in board["T1"].notes))
        # Ensure summary displays '-' for dissent rather than count
        self.assertIn("| - |", board_summary(board))


class TestBoardAndElectionArgparse(unittest.TestCase):
    def test_board_argparse_before_and_after_subcommand(self):
        from scripts.board import parse_args

        # Case 1: auth options before subcommand
        a1 = parse_args(["--room", "room101", "--token-file", "creds1.json", "--as", "AgentX", "list"])
        self.assertEqual(a1.room, "room101")
        self.assertEqual(a1.token_file, "creds1.json")
        self.assertEqual(a1.as_name, "AgentX")
        self.assertEqual(a1.cmd, "list")

        # Case 2: auth options after subcommand
        a2 = parse_args(["list", "--room", "room202", "--token-file", "creds2.json", "--as", "AgentY"])
        self.assertEqual(a2.room, "room202")
        self.assertEqual(a2.token_file, "creds2.json")
        self.assertEqual(a2.as_name, "AgentY")
        self.assertEqual(a2.cmd, "list")

        # Case 3: status command with options after
        a3 = parse_args(["status", "T1", "doing", "--token-file", "creds3.json", "--room", "room303"])
        self.assertEqual(a3.cmd, "status")
        self.assertEqual(a3.task_id, "T1")
        self.assertEqual(a3.state, "doing")
        self.assertEqual(a3.token_file, "creds3.json")
        self.assertEqual(a3.room, "room303")

        # Case 4: clear-dissent command
        a4 = parse_args(["clear-dissent", "T1", "--reason", "all good", "--room", "room404"])
        self.assertEqual(a4.cmd, "clear-dissent")
        self.assertEqual(a4.task_id, "T1")
        self.assertEqual(a4.reason, "all good")
        self.assertEqual(a4.room, "room404")

    def test_election_argparse_before_and_after_subcommand(self):
        from scripts.election import parse_args

        # Case 1: room before subcommand
        e1 = parse_args(["--room", "roomA", "status"])
        self.assertEqual(e1.room, "roomA")
        self.assertEqual(e1.command, "status")

        # Case 2: room after subcommand
        e2 = parse_args(["status", "--room", "roomB", "--token-file", "credsB.json"])
        self.assertEqual(e2.room, "roomB")
        self.assertEqual(e2.token_file, "credsB.json")
        self.assertEqual(e2.command, "status")


class TestHeartbeatArgs(unittest.TestCase):
    def test_defaults_and_bounds(self):
        from scripts.heartbeat import parse_args

        a = parse_args([])
        self.assertEqual(a.interval, 10.0)
        self.assertEqual(a.idle, 300.0)
        self.assertEqual(a.timeout, 0.0)
        self.assertEqual(a.cycles, 0)
        b = parse_args(["--timeout", "60", "--idle", "5", "--cycles", "3", "--stop-file", "STOP"])
        self.assertEqual((b.timeout, b.idle, b.cycles), (60.0, 5.0, 3))
        self.assertEqual(b.stop_file, "STOP")


if __name__ == "__main__":
    unittest.main()
