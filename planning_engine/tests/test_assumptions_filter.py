import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.plan_profile import filter_user_facing_assumptions


class TestAssumptionsFilter(unittest.TestCase):
    def test_strips_device_gallery_validator_noise(self):
        plan = {"storage_profile": "alarm", "data_tier": "local_only"}
        raw = [
            "Assumed that the validation rule requiring local_database device_gallery was a typo.",
            "Users want recurring alarms with notifications.",
        ]
        out = filter_user_facing_assumptions(raw, plan)
        self.assertEqual(len(out), 1)
        self.assertIn("alarms", out[0].lower())


if __name__ == "__main__":
    unittest.main()
