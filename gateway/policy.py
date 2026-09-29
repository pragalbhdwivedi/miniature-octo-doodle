"""Deterministic admission and conservative, durable USD budget accounting.

Charges are upper-bound admission debits, not provider invoices. Never refund an
ambiguous attempt. SQLite transactions serialize workers and survive restarts.
"""
import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path


class Denied(Exception):
    def __init__(self, reason, status=403):
        self.reason, self.status = reason, status
        super().__init__(reason)


def budget_micro(value):
    amount = Decimal(str(value))
    if not amount.is_finite() or amount < 0 or amount > 1000000:
        raise ValueError("Invalid monthly USD budget")
    return int(amount * 1000000)


class Ledger:
    def __init__(self, path, limit, concurrency=4, lease_seconds=300):
        self.path, self.limit = str(path), budget_micro(limit)
        self.concurrency, self.lease = concurrency, lease_seconds
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS months(period TEXT PRIMARY KEY, debit INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS requests(id TEXT PRIMARY KEY, period TEXT,
                route TEXT, candidates TEXT, expires REAL, active INTEGER, attempts INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS attempts(request_id TEXT, ordinal INTEGER,
                provider TEXT, model TEXT, reason TEXT, PRIMARY KEY(request_id, ordinal));
            """)
            db.execute('BEGIN IMMEDIATE')
            columns = {row[1] for row in db.execute('PRAGMA table_info(attempts)')}
            if 'outcome' not in columns:
                db.execute("ALTER TABLE attempts ADD COLUMN outcome TEXT NOT NULL DEFAULT 'pending'")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            with db:
                yield db
        finally:
            db.close()

    def reserve(self, route, candidates, debit, now=None):
        now = time.time() if now is None else now
        period = datetime.fromtimestamp(now, timezone.utc).strftime("%Y-%m")
        request_id = uuid.uuid4().hex
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("UPDATE requests SET active=0 WHERE expires < ?", (now,))
            active = db.execute("SELECT count(*) FROM requests WHERE active=1").fetchone()[0]
            if active >= self.concurrency:
                raise Denied("concurrency_limit", 429)
            db.execute("INSERT OR IGNORE INTO months VALUES (?,0)", (period,))
            spent = db.execute("SELECT debit FROM months WHERE period=?", (period,)).fetchone()[0]
            if debit <= 0 or spent + debit > self.limit:
                raise Denied("monthly_budget_exhausted", 429)
            db.execute("UPDATE months SET debit=debit+? WHERE period=?", (debit, period))
            db.execute("INSERT INTO requests VALUES (?,?,?,?,?,1,0)",
                       (request_id, period, route, json.dumps(candidates), now + self.lease))
        return request_id

    def attempt(self, request_id, model, now=None):
        now = time.time() if now is None else now
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT candidates,attempts,active,expires FROM requests WHERE id=?", (request_id,)).fetchone()
            if not row or not row[2] or row[3] < now:
                raise Denied("missing_or_expired_admission")
            candidates, ordinal = json.loads(row[0]), row[1]
            if ordinal >= len(candidates) or candidates[ordinal]["model"] != model:
                raise Denied("unapproved_attempt")
            db.execute("UPDATE requests SET attempts=attempts+1 WHERE id=?", (request_id,))
            db.execute("INSERT INTO attempts(request_id,ordinal,provider,model,reason) VALUES (?,?,?,?,?)", (request_id, ordinal,
                       model.split('/')[0], model, "primary" if ordinal == 0 else "provider_failure"))

    def outcome(self, request_id, model, status):
        with self.connect() as db:
            db.execute('UPDATE attempts SET outcome=? WHERE request_id=? AND model=?', (status, request_id, model))

    def release(self, request_id):
        if request_id:
            with self.connect() as db:
                db.execute("UPDATE requests SET active=0 WHERE id=?", (request_id,))

    def renew(self, request_ids, now=None):
        now = time.time() if now is None else now
        with self.connect() as db:
            db.executemany('UPDATE requests SET expires=? WHERE id=? AND active=1',
                           [(now + self.lease, token) for token in request_ids])


class Policy:
    BODY_FIELDS = {"model", "messages", "stream", "stream_options", "temperature",
                   "top_p", "max_tokens", "max_completion_tokens", "stop", "seed",
                   "metadata", "user", "frequency_penalty", "presence_penalty", "tools"}

    def __init__(self, config, ledger):
        self.config, self.ledger = config, ledger

    def admit(self, body, key_metadata=None):
        if not isinstance(body, dict) or set(body) - self.BODY_FIELDS:
            raise Denied("unsupported_request_fields")
        if body.get("tools") is not None and body["tools"] != []:
            raise Denied("tools_not_approved")
        meta = body.get("metadata") or {}
        if not isinstance(meta, dict) or set(meta) - {"data_class", "allowed_providers", "require_approval"}:
            raise Denied("unsupported_metadata")
        key_metadata = key_metadata or {}
        # Key policy is set by the administrator; request labels can only narrow.
        labels = [meta.get("data_class", "public"), key_metadata.get("data_class", "public")]
        if any(not isinstance(label, str) for label in labels):
            raise Denied("unknown_data_class")
        classes = set(labels)
        if not classes <= {"public", "synthetic", "private", "local-private"}:
            raise Denied("unknown_data_class")
        if meta.get("require_approval") or key_metadata.get("require_approval"):
            raise Denied("human_approval_required")
        route = body.get("model")
        if not isinstance(route, str):
            raise Denied("invalid_route", 400)
        if route == "local-private" or "local-private" in classes:
            raise Denied("local_provider_unavailable", 503)
        if "private" in classes:
            raise Denied("private_provider_approval_missing")
        candidates = self.config["resolved_routes"].get(route)
        if not candidates:
            raise Denied("unknown_or_unavailable_route")
        allowed = {"openai", "gemini"}
        for restrictions in (meta, key_metadata):
            if "allowed_providers" in restrictions:
                values = restrictions["allowed_providers"]
                if not isinstance(values, list) or any(not isinstance(v, str) or v not in allowed for v in values):
                    raise Denied("invalid_provider_allowlist")
                allowed &= set(values)
        candidates = [c for c in candidates if c["model"].split('/')[0] in allowed]
        if not candidates:
            raise Denied("no_allowed_provider")
        messages = body.get("messages")
        if not isinstance(messages, list) or not 1 <= len(messages) <= 32:
            raise Denied("invalid_messages", 400)
        for message in messages:
            if (not isinstance(message, dict) or set(message) != {"role", "content"}
                or message["role"] not in {"system", "user", "assistant"}
                or not isinstance(message["content"], str)):
                raise Denied("text_only_messages_required", 400)
        input_bytes = len(json.dumps(messages, ensure_ascii=False).encode("utf-8"))
        if input_bytes > self.config["max_input_bytes"]:
            raise Denied("input_limit", 413)
        if "max_tokens" in body and "max_completion_tokens" in body:
            raise Denied("ambiguous_output_limit", 400)
        output = body.get("max_completion_tokens", body.get("max_tokens", self.config["max_output_tokens"]))
        if type(output) is not int or not 1 <= output <= self.config["max_output_tokens"]:
            raise Denied("output_limit", 400)
        # Bytes upper-bound text tokenization; reserve additional template overhead.
        debit = 0
        for candidate in candidates:
            price = self.config["prices"].get(candidate["model"])
            if not price:
                raise Denied("unreviewed_model_price")
            debit += (input_bytes + 4096) * price["input_micro_usd"] + output * price["output_micro_usd"]
        request_id = self.ledger.reserve(route, candidates, debit)
        return request_id, candidates, output
