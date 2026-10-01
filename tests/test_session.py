"""Unit test cho workspace theo phiên và CLI hợp nhất (T8_SESSION_CLI).

Chạy: ``python -m pytest tests/test_session.py -q`` hoặc
``python -m unittest tests.test_session -v`` (stdlib, không cần mạng).
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from agentmeet import session as S
from agentmeet.__main__ import split_globals


class TestNormalizeRoom(unittest.TestCase):
    def test_raw_code(self):
        self.assertEqual(S.normalize_room("714-df3f-4e38"), "714-df3f-4e38")

    def test_http_url(self):
        self.assertEqual(S.normalize_room("https://www.agentmeet.net/714-df3f-4e38"), "714-df3f-4e38")

    def test_bare_host_path(self):
        self.assertEqual(S.normalize_room("agentmeet.net/714-df3f-4e38"), "714-df3f-4e38")

    def test_trailing_query_hash(self):
        self.assertEqual(S.normalize_room("https://www.agentmeet.net/714-df3f-4e38?x=1#y"), "714-df3f-4e38")

    def test_invalid(self):
        with self.assertRaises(ValueError):
            S.normalize_room("")


class TestSessionWorkspace(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "sessions"
        os.environ["AGENTMEET_SESSIONS"] = str(self.root)
        self.active = Path(self.tmp.name) / "active.json"
        os.environ["AGENTMEET_ACTIVE"] = str(self.active)

    def tearDown(self):
        for k in ("AGENTMEET_SESSIONS", "AGENTMEET_ACTIVE", "AGENTMEET_CREDS"):
            os.environ.pop(k, None)
        self.tmp.cleanup()

    def test_creds_roundtrip_and_paths(self):
        s = S.Session("714-df3f-4e38")
        s.save({"agent_id": "ag_x", "agent_token": "at_secret", "agent_name": "opencode",
                "base_url": "https://www.agentmeet.net"})
        self.assertTrue(s.creds_path.exists())
        self.assertTrue((s.agent_dir("ag_x") / "tasks").is_dir())
        # mọi file nằm trong <room>/<slug>, KHÔNG để rác ở root room
        self.assertEqual(s.dir.name, "714-df3f-4e38")
        self.assertFalse((s.dir / "creds.json").exists())
        loaded = s.load()
        self.assertEqual(loaded["agent_token"], "at_secret")
        self.assertEqual(loaded["room"], "714-df3f-4e38")

    def test_agent_registry_multi_agent(self):
        s = S.Session("aaa-1111-2222")
        s.save({"agent_id": "ag_1", "agent_token": "t1", "agent_name": "A"})
        s.save({"agent_id": "ag_2", "agent_token": "t2", "agent_name": "B"})
        names = {a["agent_id"] for a in s.agents()}
        self.assertEqual(names, {"ag_1", "ag_2"})
        # chọn danh tính theo tên hoặc id
        s.set_active_agent("A")
        self.assertEqual(s.load()["agent_name"], "A")
        self.assertEqual(s.find_agent("ag_2"), "ag_2")
        self.assertEqual(s.find_agent("B"), "ag_2")

    def test_per_agent_files_isolated(self):
        s = S.Session("aaa-2222-3333")
        s.save({"agent_id": "ag_1", "agent_token": "t1", "agent_name": "A"})
        s.save({"agent_id": "ag_2", "agent_token": "t2", "agent_name": "B"})
        self.assertTrue(s.agent_creds_path("ag_1").exists())
        self.assertEqual(s.load("ag_2")["agent_token"], "t2")
        self.assertNotEqual(s.load("ag_1")["agent_token"], s.load("ag_2")["agent_token"])
        # cursor tách theo agent
        s.save_cursor(11, agent_id="ag_1")
        s.save_cursor(22, agent_id="ag_2")
        self.assertEqual(s.load_cursor("ag_1"), 11)
        self.assertEqual(s.load_cursor("ag_2"), 22)

    def test_agent_folder_admin_convention(self):
        # Admin #293: file agent nằm ở <room>/<agent-slug>
        s = S.Session("aaa-3333-4444")
        s.save({"agent_id": "ag_x", "agent_token": "t", "agent_name": "opencode (deepseek-v4.1-flash)"})
        folder = s.agent_dir("ag_x").name
        self.assertEqual(folder, "opencode-deepseek-v4-1-flash")
        self.assertTrue((s.dir / folder / "creds.json").exists())
        self.assertTrue(str(s.agent_creds_path("ag_x")).startswith(str(s.dir)))

    def test_slug_collision_gets_suffix(self):
        # Hai danh tính trùng slug không được ghi đè nhau
        s = S.Session("aaa-4444-5555")
        s.save({"agent_id": "ag_1111", "agent_token": "t1", "agent_name": "opencode"})
        s.save({"agent_id": "ag_2222", "agent_token": "t2", "agent_name": "opencode"})
        dirs = {a["agent_id"]: a["folder"] for a in s.agents()}
        self.assertNotEqual(dirs["ag_1111"], dirs["ag_2222"])
        self.assertEqual(s.load("ag_1111")["agent_token"], "t1")
        self.assertEqual(s.load("ag_2222")["agent_token"], "t2")

    def test_cursor_roundtrip(self):
        s = S.Session("bbb-1111-2222")
        s.save({"agent_id": "ag_c", "agent_token": "t", "agent_name": "C"})
        self.assertEqual(s.load_cursor(), 0)
        s.save_cursor(42, agent_id="ag_c", agent_name="C")
        self.assertEqual(s.load_cursor(), 42)

    def test_cursor_isolated_per_room(self):
        a = S.Session("ccc-1111-2222"); a.save({"agent_id": "ag_a", "agent_token": "ta", "agent_name": "A"}); a.save_cursor(10, agent_id="ag_a")
        b = S.Session("ddd-1111-2222"); b.save({"agent_id": "ag_b", "agent_token": "tb", "agent_name": "B"}); b.save_cursor(99, agent_id="ag_b")
        self.assertEqual(a.load_cursor(), 10)
        self.assertEqual(b.load_cursor(), 99)

    def test_no_room_cross_talk(self):
        s = S.Session("eee-1111-2222")
        s.save({"agent_id": "ag", "agent_token": "t", "agent_name": "X"})
        other = S.Session("fff-1111-2222")
        self.assertEqual(other.load().get("agent_token"), None)  # phòng khác => trống

    def test_latest_and_active(self):
        north = S.Session("north-room")
        north.save({"agent_id": "ag_n", "agent_token": "tn", "agent_name": "N"})
        south = S.Session("south-room")
        south.save({"agent_id": "ag_s", "agent_token": "ts", "agent_name": "S"})
        south.mark_active()
        self.assertEqual(S.active_room(), "south-room")
        self.assertEqual(S.latest_session().room, "south-room")
        rooms = {r["room"] for r in S.list_sessions()}
        self.assertEqual(rooms, {"north-room", "south-room"})

    def test_legacy_creds_migration(self):
        legacy = Path(self.tmp.name) / "legacy_creds.json"
        legacy.write_text(json.dumps({
            "room": "oldroom-1", "agent_id": "ag_old", "agent_token": "at_old",
            "agent_name": "legacy", "base_url": "https://www.agentmeet.net"
        }, ensure_ascii=False), encoding="utf-8")
        os.environ["AGENTMEET_CREDS"] = str(legacy)
        s = S.Session("oldroom-1")
        loaded = s.load()  # chưa có creds.json -> fallback legacy
        self.assertEqual(loaded["agent_token"], "at_old")
        # phòng khác thì KHÔNG nhận legacy
        self.assertEqual(S.Session("other-room").load().get("agent_token"), None)


class TestGlobalArgsOrder(unittest.TestCase):
    """Lỗi cũ: option trước/sau subcommand cho kết quả khác nhau."""

    def test_options_before_command(self):
        ns, rest = split_globals(["--room", "abc-1111-2222", "--token-file", "c.json", "board", "list"])
        self.assertEqual(ns.room, "abc-1111-2222")
        self.assertEqual(ns.token_file, "c.json")
        self.assertEqual(rest, ["board", "list"])

    def test_options_after_command(self):
        ns, rest = split_globals(["board", "--room", "abc-1111-2222", "list"])
        self.assertEqual(ns.room, "abc-1111-2222")
        self.assertEqual(rest, ["board", "list"])

    def test_equals_form(self):
        ns, rest = split_globals(["poll", "--room=abc-1111-2222", "--json"])
        self.assertEqual(ns.room, "abc-1111-2222")
        self.assertTrue(ns.json)
        self.assertEqual(rest, ["poll"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
