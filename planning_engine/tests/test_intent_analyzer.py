# Tests for intent analyzer (run: python -m unittest tests.test_intent_analyzer)

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.intent_analyzer import (
    _rule_based_intent,
    _unwrap_intent_result,
    analyze_intent,
    normalize_intent,
)


class TestIntentAnalyzer(unittest.TestCase):
    def test_unwrap_nested_intent_json(self):
        raw = {"intent_json": {"domain": "media", "complexity": "simple", "confidence": 0.8}}
        self.assertEqual(_unwrap_intent_result(raw)["domain"], "media")

    def test_rule_based_gallery_prompt(self):
        intent = _rule_based_intent("build an app for simple pics gallery")
        self.assertEqual(intent["domain"], "media")
        self.assertEqual(intent["complexity"], "simple")
        self.assertGreaterEqual(intent["confidence"], 0.65)
        self.assertIn("gallery_grid", intent["detected_modules"])

    def test_normalize_fixes_unknown_llm_output(self):
        weak = {"domain": "unknown", "complexity": "unknown", "confidence": 0}
        fixed = normalize_intent(weak, "build an app for simple pics gallery")
        self.assertEqual(fixed["domain"], "media")
        self.assertEqual(fixed["complexity"], "simple")
        self.assertGreater(fixed["confidence"], 0.5)

    def test_normalize_domain_alias(self):
        raw = {"domain": "photo_gallery", "complexity": "low", "confidence": 0.7}
        out = normalize_intent(raw, "photo gallery")
        self.assertEqual(out["domain"], "media")
        self.assertEqual(out["complexity"], "simple")


if __name__ == "__main__":
    unittest.main()
