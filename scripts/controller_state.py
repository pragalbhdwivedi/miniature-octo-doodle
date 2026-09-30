"""Restricted PostgreSQL run store for the Linux operator dispatcher.

Uses existing psql through the selected local PostgreSQL container. This is an
administrator adapter, never available to the unprivileged planner or sandbox.
No production DB password, network binding, driver or new image is required.
"""
import base64
import json
import re
import subprocess


def literal(value):
    # Base64 avoids SQL quoting and psql meta-command injection from job text.
    raw = json.dumps(value, allow_nan=False).encode()
    if len(raw) > 262144:
        raise ValueError('State payload ceiling')
    return "convert_from(decode('"+base64.b64encode(raw).decode()+"','base64'),'UTF8')::jsonb"


class Store:
    def __init__(self, container, database):
        if not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', container):
            raise ValueError('Invalid database container')
        if not re.fullmatch('gatewayai_controller(?:_test_[a-f0-9]{8})?', database):
            raise ValueError('Dedicated controller database required')
        self.argv = ['docker','--host','unix:///var/run/docker.sock','exec','-i',
                     '--user','postgres',container,'psql','-X','-qAt','-v','ON_ERROR_STOP=1',
                     '-U','gatewayai_controller','-d',database]

    def query(self, sql):
        prefix = "SET statement_timeout='10s'; SET lock_timeout='3s'; SET search_path=pg_catalog;\n"
        result = subprocess.run(self.argv, input=(prefix+sql).encode(),
                                capture_output=True, timeout=20)
        if result.returncode or len(result.stdout)>1048576:
            raise RuntimeError('PostgreSQL state operation rejected; no dispatch permitted')
        return json.loads(result.stdout)

    def claim(self, request, digest):
        return self.query('SELECT controller.claim('+literal(request)+','+literal(digest)+" #>> '{}');")

    def finish(self, run_id, state, result):
        return self.query('SELECT controller.finish('+literal(run_id)+" #>> '{}',"+
                          literal(state)+" #>> '{}',"+literal(result)+');')

    def get(self, run_id):
        return self.query('SELECT coalesce((SELECT to_jsonb(r) FROM controller.runs r WHERE run_id='+
                          literal(run_id)+" #>> '{}'),'null'::jsonb);")

    def pipeline(self, run_id):
        return self.query('SELECT coalesce((SELECT to_jsonb(r) FROM controller.pipelines r WHERE run_id='+
                          literal(run_id)+" #>> '{}'),'null'::jsonb);")

    def begin_pipeline(self, run_id, spec, digest, spent):
        return self.query('SELECT controller.pipeline_begin('+literal(run_id)+" #>> '{}',"+
                          literal(spec)+','+literal(digest)+" #>> '{}',("+literal(spent)+" #>> '{}')::bigint);")

    def reserve_pipeline(self, run_id, stage, debit, body_hash):
        return self.query('SELECT controller.pipeline_reserve('+literal(run_id)+" #>> '{}',"+
                          literal(stage)+" #>> '{}',("+literal(debit)+" #>> '{}')::bigint,"+literal(body_hash)+" #>> '{}');")

    def step_pipeline(self, run_id, expected, state, evidence):
        return self.query('SELECT controller.pipeline_step('+literal(run_id)+" #>> '{}',"+
                          literal(expected)+" #>> '{}',"+literal(state)+" #>> '{}',"+literal(evidence)+');')

    def approval(self, approval_id):
        return self.query('SELECT coalesce((SELECT to_jsonb(a) FROM controller.approvals a WHERE approval_id='+
                          literal(approval_id)+" #>> '{}'),'null'::jsonb);")

    def request_approval(self, approval_id, run_id, digest, user_id, chat_id, lifetime_seconds):
        return self.query('SELECT controller.approval_request('+literal(approval_id)+" #>> '{}',"+
                          literal(run_id)+" #>> '{}',"+literal(digest)+" #>> '{}',"+
                          '('+literal(user_id)+" #>> '{}')::bigint,("+literal(chat_id)+" #>> '{}')::bigint,("+
                          literal(lifetime_seconds)+" #>> '{}')::integer);")

    def decide_approval(self, approval_id, digest, decision, user_id, chat_id, update_id):
        return self.query('SELECT controller.approval_decide('+literal(approval_id)+" #>> '{}',"+
                          literal(digest)+" #>> '{}',"+literal(decision)+" #>> '{}',"+
                          '('+literal(user_id)+" #>> '{}')::bigint,("+literal(chat_id)+" #>> '{}')::bigint,("+
                          literal(update_id)+" #>> '{}')::bigint);")

    def consume_approval(self, approval_id, run_id, digest, receipt):
        return self.query('SELECT controller.approval_consume('+literal(approval_id)+" #>> '{}',"+
                          literal(run_id)+" #>> '{}',"+literal(digest)+" #>> '{}',"+literal(receipt)+');')
