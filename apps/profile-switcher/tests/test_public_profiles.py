import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILE_DIR = ROOT / "profiles" / "public"


class PublicProfileTests(unittest.TestCase):
    def test_profiles_exist(self):
        names = {p.name for p in PROFILE_DIR.glob("*.json")}
        self.assertIn("soloPAW-Cyberpunk2077-v2.8-JDirect-ScanH-QuickW.json", names)
        self.assertIn("soloPAW-Megabonk-v1.1-DirectKeys-Esc.json", names)

    def test_profiles_are_valid_mapping_lists(self):
        for path in PROFILE_DIR.glob("*.json"):
            data = json.loads(path.read_text())
            self.assertIsInstance(data, list, path.name)
            self.assertGreater(len(data), 0, path.name)
            for mapping in data:
                self.assertIsInstance(mapping.get("input_combination"), list)
                self.assertTrue(mapping["input_combination"])

    def test_no_origin_hash_or_personal_paths(self):
        forbidden = [
            re.compile(r"/home/[^/\s]+/"),
            re.compile(r"/Users/[^/\s]+/"),
            re.compile(r"/run/user/\d+/"),
        ]
        for path in PROFILE_DIR.glob("*.json"):
            text = path.read_text()
            self.assertNotIn("origin_hash", text, path.name)
            for pattern in forbidden:
                self.assertIsNone(pattern.search(text), path.name)

    def test_megabonk_is_direct_key_profile(self):
        path = PROFILE_DIR / "soloPAW-Megabonk-v1.1-DirectKeys-Esc.json"
        data = json.loads(path.read_text())
        forbidden = ("key(", "hold_keys(", "if_", "set(", "wait(")
        for mapping in data:
            output = mapping.get("output_symbol", "")
            self.assertFalse(any(token in output for token in forbidden), output)


if __name__ == "__main__":
    unittest.main()
