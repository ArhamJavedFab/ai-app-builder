# Tests for stable plan IDs (run: python -m unittest tests.test_plan_ids)

import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.plan_editor import apply_patch
from core.plan_ids import (
    build_id_index,
    find_by_id,
    normalize_plan_ids,
    resolve_patch_path,
)


SAMPLE = {
    "app_name": "TestApp",
    "screens": [
        {"name": "HomeScreen", "route": "/home", "widgets": ["A"]},
        {"name": "CartScreen", "route": "/cart", "widgets": []},
    ],
    "navigation": {
        "routes": [
            {"path": "/home", "screen": "HomeScreen"},
            {"path": "/cart", "screen": "CartScreen"},
        ],
        "bottom_tabs": [{"label": "Home", "route": "/home"}],
    },
    "features": [
        {
            "module": "cart",
            "items": [
                {"name": "add_to_cart", "depends_on": []},
            ],
        }
    ],
    "mvp_features": ["add_to_cart"],
}


class TestPlanIds(unittest.TestCase):
    def test_normalize_assigns_stable_ids(self):
        plan = normalize_plan_ids(copy.deepcopy(SAMPLE))
        self.assertTrue(plan.get("project_id", "").startswith("prj_"))
        self.assertEqual(plan.get("plan_version"), "1.1")
        home = plan["screens"][0]
        self.assertTrue(home["id"].startswith("scr_"))
        self.assertEqual(plan["navigation"]["routes"][0]["screen_id"], home["id"])
        feat_id = plan["features"][0]["items"][0]["id"]
        self.assertEqual(plan.get("mvp_feature_ids"), [feat_id])

    def test_normalize_idempotent(self):
        once = normalize_plan_ids(copy.deepcopy(SAMPLE))
        twice = normalize_plan_ids(copy.deepcopy(once))
        self.assertEqual(
            [s["id"] for s in once["screens"]],
            [s["id"] for s in twice["screens"]],
        )

    def test_patch_by_target_id(self):
        plan = normalize_plan_ids(copy.deepcopy(SAMPLE))
        home = find_by_id(plan["screens"], plan["screens"][0]["id"])
        patch = {
            "op": "set",
            "target": {"collection": "screens", "id": home["id"]},
            "field": "widgets",
            "value": ["SearchBar"],
        }
        path = resolve_patch_path(plan, patch)
        updated = apply_patch(plan, {**patch, "path": path})
        patched = find_by_id(updated["screens"], home["id"])
        self.assertEqual(patched["widgets"], ["SearchBar"])

    def test_id_index_built(self):
        plan = normalize_plan_ids(copy.deepcopy(SAMPLE))
        index = build_id_index(plan)
        self.assertTrue(len(index.get("screens", [])) >= 2)

    def test_screen_id_is_first_key(self):
        plan = normalize_plan_ids(copy.deepcopy(SAMPLE))
        for screen in plan["screens"]:
            self.assertEqual(list(screen.keys())[0], "id")


if __name__ == "__main__":
    unittest.main()
