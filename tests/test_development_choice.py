import unittest

from gateway.jev import normalize_choice, select_route, validate_catalogue


class DevelopmentChoiceTests(unittest.TestCase):
    def setUp(self):
        self.allowed = ["coding-fast", "coding-standard"]
        self.deterministic = "coding-standard"
        self.valid_decision = {
            "route": "coding-fast",
            "confidence": 0.95,
            "in_domain": True,
        }
        self.valid_wire_response = {
            "answers": {
                "route": {
                    "type": "choice",
                    "choice": "coding-fast",
                    "probabilities": {"coding-fast": 0.95, "coding-standard": 0.05},
                    "confidence": 0.9,
                }
            }
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
            10**1000,
            -(10**1000),
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

    def test_catalogue_valid_types_accepted(self):
        catalogues = [
            ["coding-fast", "coding-standard"],
            ("coding-fast", "coding-standard"),
            {"coding-fast", "coding-standard"},
            frozenset(["coding-fast", "coding-standard"]),
        ]
        for catalogue in catalogues:
            with self.subTest(catalogue_type=type(catalogue)):
                self.assertTrue(validate_catalogue(catalogue))
                decision = normalize_choice(self.valid_wire_response, catalogue, in_domain=True)
                self.assertIsNotNone(decision)
                self.assertEqual(decision["route"], "coding-fast")

                route, reason = select_route(
                    self.valid_decision,
                    catalogue,
                    self.deterministic,
                    calibrated=True,
                    threshold=0.9,
                )
                self.assertEqual(route, "coding-fast")
                self.assertEqual(reason, "evaluated_decision")

    def test_catalogue_invalid_types_and_formats_rejected(self):
        class UnhashableObject:
            __hash__ = None

        invalid_catalogues = [
            "coding-fast",
            (x for x in ["coding-fast", "coding-standard"]),
            {"coding-fast": 1, "coding-standard": 2},
            UnhashableObject(),
            [{"nested": "unhashable"}],
            ["coding-fast", None],
            ["coding-fast", 123],
            ["coding-fast", True],
            None,
            123,
            ["coding-fast", "coding-fast"],
            ("coding-standard", "coding-standard"),
        ]
        for catalogue in invalid_catalogues:
            with self.subTest(catalogue=repr(catalogue)):
                self.assertFalse(validate_catalogue(catalogue))
                self.assertIsNone(normalize_choice(self.valid_wire_response, catalogue))
                with self.assertRaises(ValueError):
                    select_route(self.valid_decision, catalogue, self.deterministic, calibrated=False)
                with self.assertRaises(ValueError):
                    select_route(self.valid_decision, catalogue, self.deterministic, calibrated=True)

    def test_catalogue_size_and_string_length_boundaries(self):
        # Empty catalogues
        for empty in ([], (), set(), frozenset()):
            with self.subTest(empty=repr(empty)):
                self.assertFalse(validate_catalogue(empty))
                self.assertIsNone(normalize_choice(self.valid_wire_response, empty))
                with self.assertRaises(ValueError):
                    select_route(self.valid_decision, empty, self.deterministic)

        # Min catalogue size (1 ID)
        single_allowed = ["coding-fast"]
        self.assertTrue(validate_catalogue(single_allowed))

        # Max catalogue size (64 IDs)
        catalogue_64 = [f"r-{i:03d}" for i in range(64)]
        self.assertTrue(validate_catalogue(catalogue_64))

        # Exceeding catalogue size (65 IDs)
        catalogue_65 = [f"r-{i:03d}" for i in range(65)]
        self.assertFalse(validate_catalogue(catalogue_65))
        self.assertIsNone(normalize_choice(self.valid_wire_response, catalogue_65))
        with self.assertRaises(ValueError):
            select_route(self.valid_decision, catalogue_65, catalogue_65[0])

        # ID length boundaries: 0 chars, 1 char, 128 chars, 129 chars
        self.assertFalse(validate_catalogue([""]))
        self.assertTrue(validate_catalogue(["a"]))
        self.assertTrue(validate_catalogue(["a" * 128]))
        self.assertFalse(validate_catalogue(["a" * 129]))
        self.assertFalse(validate_catalogue(["coding-fast", "a" * 129]))

    def test_catalogue_boundaries_through_both_public_entrypoints(self):
        for factory in (list, tuple, set, frozenset):
            for routes in (['x'], ['x' * 128], ['r' + str(i) for i in range(64)]):
                allowed = factory(routes)
                wire = {'answers': {'route': {'type': 'choice', 'choice': routes[0],
                    'probabilities': {r: 1 if r == routes[0] else 0 for r in routes},
                    'confidence': 1}}}
                with self.subTest(factory=factory, size=len(routes), length=len(routes[0])):
                    normalized = normalize_choice(wire, allowed, in_domain=True)
                    self.assertEqual(normalized['route'], routes[0])
                    self.assertEqual(select_route(normalized, allowed, routes[0]),
                                     (routes[0], 'live_calibration_pending'))
                    self.assertEqual(select_route(normalized, allowed, routes[0], calibrated=True),
                                     (routes[0], 'evaluated_decision'))
            for routes in ([''], ['x' * 129], ['r' + str(i) for i in range(65)]):
                with self.subTest(factory=factory, invalid=routes):
                    self.assertIsNone(normalize_choice(self.valid_wire_response, factory(routes)))
                    with self.assertRaises(ValueError):
                        select_route(None, factory(routes), routes[0])

    def test_generator_is_rejected_without_consumption_and_unhashables_fail_closed(self):
        def forbidden():
            raise AssertionError('Invalid catalogue must not be iterated')
            yield 'route'
        for catalogue in (forbidden(), [['nested']], ({'nested': 1},)):
            self.assertIsNone(normalize_choice(self.valid_wire_response, catalogue))
            for calibrated in (False, True):
                with self.assertRaises(ValueError):
                    select_route(None, catalogue, self.deterministic, calibrated=calibrated)

    def test_authority_denial_and_unallowed_deterministic_route(self):
        # Deterministic route not in allowed catalogue
        with self.assertRaises(ValueError):
            select_route(self.valid_decision, ["coding-fast"], "coding-standard")

        # Authority violation when decision route is not in catalogue
        unauthorized_decision = dict(self.valid_decision, route="unauthorized-route")
        route, reason = select_route(
            unauthorized_decision,
            self.allowed,
            self.deterministic,
            calibrated=True,
            threshold=0.9,
        )
        self.assertEqual(route, self.deterministic)
        self.assertEqual(reason, "authority_violation")


if __name__ == "__main__":
    unittest.main()
