import unittest
import json
import tempfile
import sys
from pathlib import Path

# Add parent path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.inbox import extract_mentions, load_state, save_state, get_state_file, parse_args


class TestInbox(unittest.TestCase):
    def test_extract_mentions(self):
        text = "Hello @Admin and @opencode, please review @Antigravity!"
        mentions = extract_mentions(text)
        self.assertIn("Admin", mentions)
        self.assertIn("opencode", mentions)
        self.assertIn("Antigravity", mentions)

    def test_state_load_and_save(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "cursor.json"
            state = load_state(state_file, "test-room")
            self.assertEqual(state["room"], "test-room")
            self.assertIsNone(state["last_offset"])

            state["last_offset"] = 150
            state["last_message_id"] = 155
            save_state(state_file, state)

            loaded = load_state(state_file, "test-room")
            self.assertEqual(loaded["last_offset"], 150)
            self.assertEqual(loaded["last_message_id"], 155)
            self.assertGreater(loaded["updated_at"], 0)

    def test_get_state_file(self):
        path = get_state_file("room-123/456")
        self.assertTrue(path.name.endswith(".json"))
        self.assertNotIn("/", path.name)

    def test_parse_args_aliases(self):
        args = parse_args(["--cursor-file", "my_cursor.json", "--no-save", "--from", "Admin", "--contains", "urgent", "--cap", "25"])
        self.assertEqual(args.state_file, "my_cursor.json")
        self.assertTrue(args.peek)
        self.assertIn("Admin", args.from_agents)
        self.assertIn("urgent", args.keywords)
        self.assertEqual(args.limit, 25)


if __name__ == "__main__":
    unittest.main()
