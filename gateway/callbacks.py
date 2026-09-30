"""Pinned LiteLLM proxy callbacks. Policy errors contain no request text."""
import asyncio
import json
import os
import threading
import time
from fastapi import HTTPException
from litellm.integrations.custom_logger import CustomLogger
from gateway.policy import Denied, Ledger, Policy


class GatewayPolicy(CustomLogger):
    def __init__(self):
        super().__init__()
        with open(os.environ.get("GATEWAY_POLICY_CONFIG", "/app/policy.json")) as f:
            config = json.load(f)
        self.ledger = Ledger(os.environ.get("GATEWAY_LEDGER", "/app/policy-data/budget.sqlite3"),
                             os.environ.get("GATEWAY_MONTHLY_BUDGET_USD", "0"),
                             config["max_concurrency"], config["lease_seconds"])
        self.policy = Policy(config, self.ledger)
        self.owners = {}
        self.ownership_lock = threading.Lock()
        threading.Thread(target=self.keep_alive, daemon=True).start()

    def keep_alive(self):
        while True:
            time.sleep(30)
            with self.ownership_lock:
                tokens = list(self.owners)
            # A failed renewal must stop this worker, not silently free live slots.
            try:
                self.ledger.renew(tokens)
            except Exception:
                os._exit(1)

    @staticmethod
    def request_id(data):
        return (data.get("metadata") or {}).get("gateway_admission")

    def release(self, data):
        request_id = self.request_id(data)
        if not isinstance(request_id, str):
            return None
        with self.ownership_lock:
            owner = self.owners.get(request_id)
            if owner == id(data):
                self.ledger.release(request_id)
                self.owners.pop(request_id, None)
                return request_id
        return None

    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type):
        # Remove a caller's forged token before any failure hook can release it.
        # The separate requester snapshot still makes that input a hard deny.
        if isinstance(data.get("metadata"), dict):
            data["metadata"].pop("gateway_admission", None)
        if call_type not in ("completion", "acompletion"):
            raise HTTPException(403, "policy: chat_completions_only")
        body = (data.get("proxy_server_request") or {}).get("body")
        if isinstance(body, str):
            try:
                body = json.loads(body)
            except ValueError:
                body = None
        if isinstance(body, dict):
            body = dict(body)
            # LiteLLM enriches the shallow body snapshot with admin metadata.
            # Its requester_metadata copy is taken before those enrichments.
            metadata = (data.get("metadata") or {}).get("requester_metadata", {})
            if isinstance(metadata, dict):
                metadata = {k: v for k, v in metadata.items() if k != "headers"}
            body["metadata"] = metadata
        try:
            request_id, candidates, output = self.policy.admit(body, getattr(user_api_key_dict, "metadata", None))
        except Denied as exc:
            raise HTTPException(exc.status, "policy: " + exc.reason) from None
        data["metadata"] = dict(data.get("metadata") or {}, gateway_admission=request_id)
        with self.ownership_lock:
            self.owners[request_id] = id(data)
        data["model"] = candidates[0]["alias"]
        data.pop("max_tokens", None)
        data.pop("tools", None)
        data["max_completion_tokens"] = output
        data["num_retries"] = 0
        data["timeout"] = 300 if all(c["model"].startswith("ollama/") for c in candidates) else 60
        data["fallbacks"] = [{candidates[0]["alias"]: [c["alias"] for c in candidates[1:]]}]
        return data

    @staticmethod
    def deployment(kwargs):
        params = kwargs.get("litellm_params") or {}
        metadata = kwargs.get("metadata") or params.get("metadata") or {}
        provider = kwargs.get("custom_llm_provider") or params.get("custom_llm_provider")
        model = kwargs.get("model", "")
        if provider and not model.startswith(provider + "/"):
            model = provider + "/" + model
        return metadata.get("gateway_admission"), model

    async def async_pre_call_deployment_hook(self, kwargs, call_type):
        request_id, model = self.deployment(kwargs)
        try:
            self.ledger.attempt(request_id, model)
        except Denied as exc:
            raise HTTPException(exc.status, "policy: " + exc.reason) from None
        return kwargs

    async def async_post_call_failure_deployment_hook(self, request_data, exception, call_type, fallback_depth=None):
        request_id, model = self.deployment(request_data)
        status = getattr(exception, "status_code", None)
        self.ledger.outcome(request_id, model, "http_" + str(status) if type(status) is int else "provider_error")

    async def async_post_call_success_deployment_hook(self, request_data, response, call_type):
        request_id, model = self.deployment(request_data)
        self.ledger.outcome(request_id, model, "accepted")

    async def async_post_call_success_hook(self, data, user_api_key_dict, response):
        if not data.get("stream"):
            self.release(data)
        return response

    async def async_post_call_failure_hook(self, request_data, original_exception, user_api_key_dict, **kwargs):
        request_id = self.release(request_data)
        if isinstance(original_exception, HTTPException):
            return original_exception
        if not request_id:
            return None
        status = getattr(original_exception, "status_code", 502)
        if status not in (400, 401, 403, 404, 413, 429, 503, 504):
            status = 502
        return HTTPException(status, "policy: provider_execution_failed")

    async def async_post_call_response_headers_hook(self, data, user_api_key_dict, response, request_headers=None):
        request_id = self.request_id(data)
        return {"x-gateway-request-id": request_id, "x-gateway-decision": "deterministic"} if request_id else {}

    async def async_post_call_streaming_iterator_hook(self, user_api_key_dict, response, request_data):
        completed = False
        try:
            async with asyncio.timeout(120):
                async for item in response:
                    yield item
            completed = True
        except Exception:
            raise HTTPException(502, "policy: stream_execution_failed") from None
        finally:
            request_id = self.release(request_data)
            if request_id:
                self.ledger.finish_stream(request_id, completed)


proxy_handler_instance = GatewayPolicy()
