# Tests for plan profile (run: python -m unittest tests.test_plan_profile)

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.plan_profile import (
    apply_local_first_to_plan_dict,
    enrich_intent_for_planners,
    is_local_first_plan,
    resolve_data_tier,
    resolve_storage_profile,
)
from core.plan_editor import apply_patch


class TestPlanProfile(unittest.TestCase):
    def test_application_does_not_match_pics_hint(self):
        """Regression: 'pics' must not match inside 'application'."""
        profile = resolve_storage_profile(
            {"domain": "other", "app_type": "mobile app"},
            "can you build application of time alarm",
        )
        self.assertEqual(profile, "alarm")

    def test_gallery_resolves_local_only(self):
        intent = {
            "domain": "media",
            "complexity": "simple",
            "needs_backend": False,
            "needs_auth": False,
        }
        clarifications = {
            "image_source": {
                "question": "Where will the app get images from?",
                "answer": "Only from the device's local storage",
            },
        }
        self.assertEqual(
            resolve_data_tier(intent, clarifications, "build an app for simple pics gallery"),
            "local_only",
        )
        self.assertEqual(
            resolve_storage_profile(intent, "pics gallery app", clarifications),
            "media",
        )

    def test_notes_app_uses_notes_profile(self):
        intent = {
            "domain": "productivity",
            "app_type": "notes taking app",
            "needs_backend": False,
            "needs_auth": False,
        }
        self.assertEqual(
            resolve_storage_profile(intent, "create notes taking application"),
            "notes",
        )

    def test_enrich_intent_sets_storage_profile(self):
        intent = {"domain": "productivity", "app_type": "alarm clock app", "needs_backend": False, "needs_auth": False}
        out = enrich_intent_for_planners(intent, {}, "time alarm app")
        self.assertEqual(out["data_tier"], "local_only")
        self.assertEqual(out["storage_profile"], "alarm")

    def test_alarm_plan_sanitized(self):
        intent = {
            "domain": "productivity",
            "app_type": "alarm clock app",
            "storage_profile": "alarm",
            "data_tier": "local_only",
        }
        plan = {
            "flutter_architecture": {"local_database": "device_gallery"},
            "flutter_dependencies": [{"package": "photo_manager"}],
            "backend": {
                "security_rules": [
                    "Request gallery/storage permissions before reading media.",
                ],
            },
            "security_rules": ["Enable Firestore persistence"],
        }
        apply_local_first_to_plan_dict(plan, intent, "time alarm app")
        self.assertEqual(plan["flutter_architecture"]["local_database"], "isar")
        self.assertNotIn("photo_manager", {d["package"] for d in plan["flutter_dependencies"]})
        self.assertTrue(all("gallery" not in r.lower() for r in plan["backend"]["security_rules"]))

    def test_patch_can_add_id_field(self):
        plan = {"screens": [{"name": "HomeScreen", "route": "/home"}]}
        updated = apply_patch(plan, {
            "op": "set",
            "path": "/screens/0/id",
            "value": "scr_test",
        })
        self.assertEqual(updated["screens"][0]["id"], "scr_test")

    def test_local_plan_detection(self):
        plan = {"data_tier": "local_only", "backend": {"needs_backend": False, "backend_type": "local"}}
        self.assertTrue(is_local_first_plan(plan))


if __name__ == "__main__":
    unittest.main()
