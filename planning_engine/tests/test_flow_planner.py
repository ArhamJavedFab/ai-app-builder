# Tests for user flow planner (run: python -m unittest tests.test_flow_planner)

import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.flow_planner import _fallback_user_flows, _filter_flow_steps, plan_user_flows
from core.plan_ids import normalize_plan_ids


SCREENS_FIXTURE = {
    "screens": [
        {"name": "SplashScreen", "route": "/splash"},
        {"name": "OnboardingScreen", "route": "/onboarding"},
        {"name": "PermissionsScreen", "route": "/permissions"},
        {"name": "WhatsAppStatusListScreen", "route": "/"},
        {"name": "ImageDetailScreen", "route": "/image/:id"},
        {"name": "VideoPlayerScreen", "route": "/video/:id"},
    ]
}

NAV_FIXTURE = {
    "guest_routes": ["/", "/image/:id"],
    "routes": [],
}


class TestFlowPlanner(unittest.TestCase):
    def test_filter_flow_steps_drops_invalid_routes(self):
        valid = {"/", "/splash"}
        steps = _filter_flow_steps(["/splash", "/missing", "/"], valid)
        self.assertEqual(steps, ["/splash", "/"])

    def test_fallback_builds_onboarding_and_detail_flows(self):
        flows = _fallback_user_flows(SCREENS_FIXTURE["screens"], NAV_FIXTURE)
        self.assertGreaterEqual(len(flows), 2)
        names = {f["name"] for f in flows}
        self.assertTrue(any("launch" in n.lower() or "first" in n.lower() for n in names))
        first = flows[0]
        self.assertGreaterEqual(len(first["steps"]), 2)
        self.assertEqual(first["steps"][0], "/splash")

    def test_normalize_links_flow_screen_ids(self):
        plan = normalize_plan_ids({
            "screens": copy.deepcopy(SCREENS_FIXTURE["screens"]),
            "user_flows": [
                {
                    "name": "First launch",
                    "trigger": "open app",
                    "priority": "mvp",
                    "steps": ["/splash", "/onboarding", "/"],
                }
            ],
        })
        flow = plan["user_flows"][0]
        self.assertTrue(flow["id"].startswith("flow_"))
        self.assertEqual(list(flow.keys())[0], "id")
        self.assertEqual(len(flow["step_screen_ids"]), 3)
        self.assertTrue(flow["step_screen_ids"][0].startswith("scr_"))

    def test_normalize_id_first_on_dependencies(self):
        plan = normalize_plan_ids({
            "flutter_dependencies": [
                {"package": "path_provider", "version": "^2.1.3", "purpose": "paths"},
            ],
        })
        dep = plan["flutter_dependencies"][0]
        self.assertEqual(list(dep.keys())[0], "id")
        self.assertTrue(dep["id"].startswith("dep_"))


class TestFlowPlannerIntegration(unittest.TestCase):
    def test_plan_user_flows_uses_fallback_without_api(self):
        """Fallback path must work when LLM is not called (monkeypatch)."""
        import agents.flow_planner as fp

        original = fp.call_gemini_json

        def boom(*_a, **_k):
            raise RuntimeError("no api in test")

        fp.call_gemini_json = boom
        try:
            result = plan_user_flows(
                {"core_goal": "save statuses", "data_tier": "local_only"},
                SCREENS_FIXTURE,
                NAV_FIXTURE,
            )
        finally:
            fp.call_gemini_json = original

        flows = result.get("user_flows", [])
        self.assertGreaterEqual(len(flows), 1)
        for flow in flows:
            self.assertGreaterEqual(len(flow["steps"]), 1)


if __name__ == "__main__":
    unittest.main()
