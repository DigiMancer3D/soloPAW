import json
import os
import tempfile
import unittest
from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("switcher", ROOT / "solopaw_profile_switcher.py")
switcher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(switcher)


class CoreTests(unittest.TestCase):
    def test_default_slots(self):
        self.assertEqual(len(switcher.DEFAULT_CONFIG["slots"]), 3)
        self.assertEqual(
            switcher.DEFAULT_CONFIG["slots"][0]["profile"],
            switcher.CYBERPUNK_PROFILE,
        )
        self.assertEqual(
            switcher.DEFAULT_CONFIG["slots"][1]["profile"],
            switcher.MEGABONK_PROFILE,
        )
        self.assertEqual(switcher.DEFAULT_CONFIG["slots"][2]["profile"], "")

    def test_profile_validation(self):
        good = [{"input_combination": [{"type": 1, "code": 17}], "target_uinput": "keyboard", "output_symbol": "w"}]
        ok, _ = switcher.validate_profile_data(good)
        self.assertTrue(ok)
        ok, _ = switcher.validate_profile_data({"not": "a preset"})
        self.assertFalse(ok)

    def test_sanitizer_strips_origin_hash(self):
        data = [{"input_combination": [{"type": 1, "code": 17, "origin_hash": "deadbeef"}], "target_uinput": "keyboard", "output_symbol": "w"}]
        sanitized, stripped, issues = switcher.sanitize_profile_data(data)
        self.assertEqual(stripped, 1)
        self.assertNotIn("origin_hash", sanitized[0]["input_combination"][0])
        self.assertEqual(issues, [])

    def test_privacy_audit_catches_generic_home_path(self):
        data = [{"input_combination": [{"type": 1, "code": 17}], "target_uinput": "keyboard", "output_symbol": "exec /home/example/private.sh"}]
        issues = switcher.privacy_audit_profile_data(data)
        self.assertTrue(any("filesystem" in item or "home-directory" in item for item in issues))

    def test_atomic_json(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "x.json"
            switcher.save_json_atomic(path, {"a": 1})
            self.assertEqual(json.loads(path.read_text()), {"a": 1})


if __name__ == "__main__":
    unittest.main()
