import unittest

from gateway.jev import select_route


class DevelopmentChoiceTests(unittest.TestCase):
    def setUp(self):
        self.allowed = ["coding-fast", "coding-standard"]
        self.deterministic = "coding-standard"
        self.valid_decision = {
            "route": "coding-fast",
            "confidence": 0.95,
            "in_domain": True,
        }

    def test_calibrated_rejects_invalid_thresholds(self):
        invalid_thresholds = [
            True,
            False,
            "0.9",
            "invalid",
            float("nan"),
            float("inf"),
            float("-inf"),
            -0.001,
            -1.0,
            1.001,
            2.0,
            None,
            [],
            {},
        ]
        for threshold in invalid_thresholds:
            with self.subTest(threshold=threshold):
                route, reason = select_route(
                    self.valid_decision,
                    self.allowed,
                    self.deterministic,
                    calibrated=True,
                    threshold=threshold,
                )
                self.assertEqual(route, self.deterministic)
                self.assertEqual(reason, "invalid_threshold")

    def test_uncalibrated_preserves_disabled_live_jev_default(self):
        route, reason = select_route(
            self.valid_decision,
            self.allowed,
            self.deterministic,
            calibrated=False,
            threshold="invalid",
        )
        self.assertEqual(route, self.deterministic)
        self.assertEqual(reason, "live_calibration_pending")

    def test_calibrated_valid_threshold_boundaries_and_route_selection(self):
        route, reason = select_route(
            self.valid_decision,
            self.allowed,
            self.deterministic,
            calibrated=True,
            threshold=0.0,
        )
        self.assertEqual(route, "coding-fast")
        self.assertEqual(reason, "evaluated_decision")

        route, reason = select_route(
            self.valid_decision,
            self.allowed,
            self.deterministic,
            calibrated=True,
            threshold=1.0,
        )
        self.assertEqual(route, self.deterministic)
        self.assertEqual(reason, "review_or_deterministic")

        route, reason = select_route(
            self.valid_decision,
            self.allowed,
            self.deterministic,
            calibrated=True,
            threshold=0.9,
        )
        self.assertEqual(route, "coding-fast")
        self.assertEqual(reason, "evaluated_decision")


if __name__ == "__main__":
    unittest.main()
