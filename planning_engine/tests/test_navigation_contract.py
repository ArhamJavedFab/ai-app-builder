# Tests for navigation contract (run: python -m unittest tests.test_navigation_contract)

import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.navigation_contract import (
    HOME_ROUTE,
    ROOT_ROUTE,
    apply_navigation_contract,
    finalize_navigation,
    rewrite_root_route_to_home,
)
from core.plan_ids import normalize_plan_ids
from validation.validator import _rule_based_checks


STATUS_SAVER_SCREENS = [
    {"name": "SplashScreen", "route": "/splash"},
    {"name": "OnboardingScreen", "route": "/onboarding"},
    {"name": "PermissionsScreen", "route": "/permissions"},
    {"name": "WhatsAppStatusListScreen", "route": "/"},
    {"name": "ImageDetailScreen", "route": "/image/:id"},
]


class TestNavigationContract(unittest.TestCase):
    def test_rewrite_root_to_home(self):
        screens = copy.deepcopy(STATUS_SAVER_SCREENS)
        self.assertTrue(rewrite_root_route_to_home(screens))
        home = next(s for s in screens if s["name"] == "WhatsAppStatusListScreen")
        self.assertEqual(home["route"], HOME_ROUTE)

    def test_finalize_adds_initial_route_and_redirects(self):
        screens = copy.deepcopy(STATUS_SAVER_SCREENS)
        rewrite_root_route_to_home(screens)
        nav = finalize_navigation(screens, {"nav_type": "none", "routes": []})
        self.assertEqual(nav["initial_route"], "/splash")
        self.assertTrue(len(nav.get("redirects", [])) >= 2)
        paths = {r["path"] for r in nav["routes"] if isinstance(r, dict)}
        self.assertIn(HOME_ROUTE, paths)

    def test_apply_on_full_plan(self):
        plan = apply_navigation_contract({
            "screens": copy.deepcopy(STATUS_SAVER_SCREENS),
            "navigation": {},
            "user_flows": [
                {"name": "Launch", "steps": ["/splash", "/"]},
            ],
        })
        routes = {s["route"] for s in plan["screens"]}
        self.assertNotIn(ROOT_ROUTE, routes)
        self.assertIn(HOME_ROUTE, routes)
        self.assertEqual(plan["navigation"]["initial_route"], "/splash")
        self.assertEqual(plan["user_flows"][0]["steps"][-1], HOME_ROUTE)

    def test_normalize_plan_ids_applies_contract(self):
        plan = normalize_plan_ids({
            "screens": copy.deepcopy(STATUS_SAVER_SCREENS),
            "navigation": {"routes": [{"path": "/", "screen": "WhatsAppStatusListScreen"}]},
        })
        self.assertEqual(
            next(s for s in plan["screens"] if "List" in s["name"])["route"],
            HOME_ROUTE,
        )
        self.assertEqual(plan["navigation"]["initial_route"], "/splash")

    def test_validator_flags_bare_root(self):
        issues = _rule_based_checks({
            "screens": [{"name": "HomeScreen", "route": "/"}],
            "navigation": {"routes": [], "redirects": []},
            "backend": {},
            "database_tables": [],
            "flutter_architecture": {},
            "design_system": {},
        })
        categories = [i["issue"] for i in issues]
        self.assertTrue(any("forbidden route '/'" in msg for msg in categories))


if __name__ == "__main__":
    unittest.main()
