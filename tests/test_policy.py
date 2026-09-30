import concurrent.futures
import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from gateway.jev import normalize_choice, select_route
from gateway.policy import Denied, Ledger, Policy


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "ledger.sqlite3"
        self.config = json.loads(Path("config/policy/policy.json").read_text())
        self.candidates = [{"alias": "openai-chat", "model": "openai/gpt-5.4-mini"},
                           {"alias": "gemini-chat", "model": "gemini/gemini-3.1-flash-lite"}]
        self.config["resolved_routes"] = {"coding-standard": self.candidates}
        self.ledger = Ledger(self.path, 100)
        self.policy = Policy(self.config, self.ledger)
        self.body = {"model": "coding-standard", "messages": [{"role": "user", "content": "synthetic hello"}], "max_completion_tokens": 64}

    def tearDown(self):
        self.temp.cleanup()

    def test_labelled_policy_cases(self):
        cases = [({}, None), ({"data_class": "public"}, None), ({"data_class": "synthetic"}, None),
                 ({"data_class": "private"}, "private_provider_approval_missing"),
                 ({"data_class": "local-private"}, "local_provider_unavailable"),
                 ({"data_class": "secret"}, "unknown_data_class"),
                 ({"require_approval": True}, "human_approval_required"),
                 ({"allowed_providers": []}, "no_allowed_provider"),
                 ({"allowed_providers": ["omniroute"]}, "invalid_provider_allowlist")]
        for metadata, reason in cases:
            with self.subTest(metadata=metadata):
                body = dict(self.body, metadata=metadata)
                if reason:
                    with self.assertRaises(Denied) as error:
                        self.policy.admit(body)
                    self.assertEqual(error.exception.reason, reason)
                else:
                    request_id, _, _ = self.policy.admit(body)
                    self.ledger.release(request_id)

    def test_key_floor_and_allowlist_intersection(self):
        with self.assertRaises(Denied):
            self.policy.admit(dict(self.body, metadata={"data_class": "public"}), {"data_class": "private"})
        request_id, candidates, _ = self.policy.admit(self.body, {"allowed_providers": ["gemini"]})
        self.assertEqual(candidates, self.candidates[1:])
        self.ledger.attempt(request_id, self.candidates[1]["model"])
        with self.assertRaises(Denied):
            self.ledger.attempt(request_id, self.candidates[0]["model"])

    def test_request_overrides_and_tools_rejected(self):
        for field in ("tools", "api_base", "api_key", "fallbacks", "num_retries", "extra_body", "service_tier", "n", "headers"):
            with self.subTest(field=field), self.assertRaises(Denied):
                self.policy.admit(dict(self.body, **{field: "attacker"}))
        with self.assertRaises(Denied):
            self.policy.admit(dict(self.body, metadata={"gateway_admission": "forged"}))

    def test_empty_webui_tools_are_not_tool_authority(self):
        for value in (None, []):
            request_id, _, _ = self.policy.admit(dict(self.body, tools=value))
            self.ledger.release(request_id)
        with self.assertRaises(Denied):
            self.policy.admit(dict(self.body, tools=[{"type": "function"}]))

    def test_request_limits_and_model_price_review(self):
        for patch in ({"model": "local-private"}, {"model": "unknown"}, {"max_completion_tokens": 1025},
                      {"max_completion_tokens": True}, {"messages": []},
                      {"messages": [{"role": "user", "content": "x" * 33000}]},
                      {"messages": [{"role": "user", "content": [{"image_url": "secret"}]}]}):
            with self.subTest(patch=list(patch)), self.assertRaises(Denied):
                self.policy.admit(dict(self.body, **patch))
        self.config["prices"] = {}
        with self.assertRaises(Denied):
            self.policy.admit(self.body)

    def test_attempt_order_and_retry_bound(self):
        request_id, _, _ = self.policy.admit(self.body)
        with self.assertRaises(Denied):
            self.ledger.attempt(request_id, self.candidates[1]["model"])
        for candidate in self.candidates:
            self.ledger.attempt(request_id, candidate["model"])
        with self.assertRaises(Denied):
            self.ledger.attempt(request_id, self.candidates[1]["model"])
        self.ledger.release(request_id)
        with self.assertRaises(Denied):
            self.ledger.attempt(request_id, self.candidates[0]["model"])

    def test_atomic_budget_restart_and_month_rollover(self):
        ledger = Ledger(self.path, 0.1, concurrency=100)
        def reserve(_):
            try:
                token = ledger.reserve("route", self.candidates, 10000, now=1790812800)
                ledger.release(token)
                return True
            except Denied:
                return False
        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
            self.assertEqual(sum(pool.map(reserve, range(40))), 10)
        restarted = Ledger(self.path, 0.1)
        with self.assertRaises(Denied):
            restarted.reserve("route", self.candidates, 1, now=1790812800)
        self.assertTrue(restarted.reserve("route", self.candidates, 100000, now=1793491200))

    def test_concurrency_expiration_no_refund(self):
        ledger = Ledger(self.path, 1, concurrency=1, lease_seconds=300)
        first = ledger.reserve("route", self.candidates, 500000, now=1790812800)
        with self.assertRaises(Denied):
            ledger.reserve("route", self.candidates, 1, now=1790812801)
        second = ledger.reserve("route", self.candidates, 500000, now=1790813101)
        with self.assertRaises(Denied):
            ledger.attempt(first, self.candidates[0]["model"], now=1790813101)
        ledger.release(second)
        with self.assertRaises(Denied):
            ledger.reserve("route", self.candidates, 1, now=1790813102)

    def test_live_lease_renewal_and_stopped_owner_expiry(self):
        ledger = Ledger(self.path, 1, concurrency=1, lease_seconds=300)
        token = ledger.reserve('route', self.candidates, 1, now=1790812800)
        ledger.renew([token], now=1790813090)
        with self.assertRaises(Denied):
            ledger.reserve('route', self.candidates, 1, now=1790813101)
        # When the owning process stops renewing, the crash lease expires.
        self.assertTrue(ledger.reserve('route', self.candidates, 1, now=1790813391))

    def test_zero_budget_and_secret_free_ledger(self):
        with self.assertRaises(Denied):
            Ledger(self.path, 0).reserve("route", self.candidates, 1)
        token, _, _ = self.policy.admit(self.body)
        self.ledger.attempt(token, self.candidates[0]["model"])
        with self.ledger.connect() as db:
            dump = "\n".join(db.iterdump())
        self.assertNotIn("synthetic hello", dump)
        self.assertNotIn("messages", dump)
        self.assertIn("gpt-5.4-mini", dump)

    def test_optional_local_routes_are_zero_spend_and_never_cloud_fallback(self):
        local = [{"alias": "local-coding", "model": "ollama/devstral-small-2:24b"}]
        self.config["resolved_routes"]["local-coding"] = local
        self.config["prices"][local[0]["model"]] = {"input_micro_usd": 0,
                                                    "output_micro_usd": 0}
        body = dict(self.body, model="local-coding")
        with self.assertRaisesRegex(Denied, 'no_allowed_provider'):
            self.policy.admit(body)
        self.config["local_models_enabled"] = True
        with self.assertRaisesRegex(Denied, 'no_allowed_provider'):
            self.policy.admit(dict(body, metadata={"allowed_providers": ["openai"]}))
        token, candidates, _ = self.policy.admit(body)
        self.assertEqual(candidates, local)
        self.ledger.attempt(token, local[0]["model"])
        with self.assertRaises(Denied):
            self.ledger.attempt(token, self.candidates[0]["model"])
        with self.ledger.connect() as db:
            self.assertEqual(db.execute('SELECT debit FROM months').fetchone()[0], 0)
        self.ledger.release(token)
        for label in ('private', 'local-private'):
            with self.assertRaises(Denied):
                self.policy.admit(dict(body, metadata={"data_class": label}))
        self.config["resolved_routes"]["mixed"] = local + self.candidates[:1]
        with self.assertRaisesRegex(Denied, 'mixed_local_cloud_route_denied'):
            self.policy.admit(dict(body, model="mixed"))

    def test_jev_boundaries(self):
        allowed = ["coding-fast", "coding-standard"]
        valid = {"route": "coding-fast", "confidence": 0.95, "in_domain": True}
        self.assertEqual(select_route(valid, allowed, "coding-standard")[1], "live_calibration_pending")
        for decision in (None, {}, dict(valid, confidence=0.1), dict(valid, confidence=float('nan')),
                         dict(valid, confidence=True), dict(valid, in_domain=False), dict(valid, route="local-private")):
            with self.subTest(decision=decision):
                self.assertEqual(select_route(decision, allowed, "coding-standard", calibrated=True)[0], "coding-standard")
        self.assertEqual(select_route(valid, allowed, "coding-standard", calibrated=True)[0], "coding-fast")

    def test_jev_documented_wire_contract(self):
        allowed = ["coding-fast", "coding-standard"]
        answer = {"type": "choice", "choice": "coding-fast", "probabilities": {"coding-fast": 0.95, "coding-standard": 0.05}, "confidence": 0.9}
        decision = normalize_choice({"answers": {"route": answer}}, allowed, in_domain=True)
        self.assertEqual(decision["route"], "coding-fast")
        for patch in ({"probabilities": {}}, {"confidence": float('nan')}, {"choice": "unapproved"}, {"type": "score"},
                      {"probabilities": {"coding-fast": 0.4, "coding-standard": 0.1}}):
            self.assertIsNone(normalize_choice({"answers": {"route": dict(answer, **patch)}}, allowed))
        self.assertIsNone(normalize_choice(None, allowed))

    def test_jev_disabled_even_with_key_and_invalid_activation_rejected(self):
        with patch.dict('os.environ', {'TYPESAFE_API_KEY': 'synthetic-unused-key'}), patch('urllib.request.urlopen') as network:
            token, candidates, _ = self.policy.admit(self.body)
            self.assertEqual(candidates, self.candidates)
            network.assert_not_called()
            self.ledger.release(token)
        for settings in (None, {}, {'mode': 'jev', 'jev_enabled': True},
                         {'mode': 'deterministic', 'jev_enabled': 'false'},
                         {'mode': 'deterministic', 'jev_enabled': 0}):
            with self.subTest(settings=settings), self.assertRaises(ValueError):
                Policy(dict(self.config, decision_plane=settings), self.ledger)

    def test_stream_outcome_updates_only_last_attempt(self):
        token, _, _ = self.policy.admit(self.body)
        for candidate in self.candidates:
            self.ledger.attempt(token, candidate['model'])
        self.ledger.outcome(token, self.candidates[0]['model'], 'http_503')
        self.ledger.finish_stream(token, True)
        with self.ledger.connect() as db:
            self.assertEqual(db.execute('SELECT outcome FROM attempts ORDER BY ordinal').fetchall(), [('http_503',), ('stream_completed',)])
        self.ledger.finish_stream(token, False)
        with self.ledger.connect() as db:
            self.assertEqual(db.execute('SELECT outcome FROM attempts WHERE ordinal=1').fetchone()[0], 'stream_incomplete')


if __name__ == "__main__":
    unittest.main()
