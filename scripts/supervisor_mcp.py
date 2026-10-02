"""Dependency-free stdio MCP bridge to the bounded local Qwen reviewer.

The operator fixes the public source checkout at startup. No tool accepts a
repository, model endpoint, output path or executable. No source writes occur.
"""
import argparse
import json
import os
from pathlib import Path
import secrets
import sys

import desktop_review as desktop


MODEL = 'qwen3:4b-thinking'
VERSIONS = ('2024-11-05', '2025-03-26', '2025-06-18')
LIMIT = desktop.agent.MAX_RESPONSE_BYTES


def object_schema(properties, required):
    return {'type': 'object', 'properties': properties,
            'required': required, 'additionalProperties': False}


TOOLS = [
    {'name': 'prepare_review',
     'description': 'Read named public GatewayAI main files and prepare a proposal task. '
                    'Returns a session task_id and exact source. No source edits.',
     'inputSchema': object_schema({
         'task': {'type': 'string', 'minLength': 1, 'maxLength': 1000},
         'paths': {'type': 'array', 'minItems': 1, 'maxItems': 8,
                   'items': {'type': 'string', 'maxLength': 180}}}, ['task', 'paths']),
     'annotations': {'readOnlyHint': True, 'destructiveHint': False,
                     'idempotentHint': False, 'openWorldHint': True}},
    {'name': 'review_proposal',
     'description': 'Submit a candidate for a prepared task to local Qwen. Validates '
                    'source and patch, records local evidence, returns advisory findings. '
                    'Never edits, executes tests, approves, publishes or deploys. '
                    'Use only public/synthetic content; results return to this client.',
     'inputSchema': object_schema({
         'task_id': {'type': 'string', 'pattern': '^[a-f0-9]{32}$'},
         'candidate': desktop.agent.CODER_SCHEMA}, ['task_id', 'candidate']),
     'annotations': {'readOnlyHint': False, 'destructiveHint': False,
                     'idempotentHint': False, 'openWorldHint': True}},
    {'name': 'supervisor_status',
     'description': 'Describe the fixed local-review boundary; does not run inference.',
     'inputSchema': object_schema({}, []),
     'annotations': {'readOnlyHint': True, 'destructiveHint': False,
                     'idempotentHint': True, 'openWorldHint': False}},
]


class Bridge:
    def __init__(self, repo, output, owner='gemini-pro', chat=desktop.agent.ollama_chat):
        self.repo = Path(repo).resolve(strict=True)
        self.output = Path(output).resolve()
        local = Path(os.environ['LOCALAPPDATA']).resolve()
        if not self.output.is_relative_to(local) or self.output.is_relative_to(self.repo):
            raise desktop.agent.AgentError('Evidence must stay in LocalAppData outside source')
        if owner not in desktop.OWNERS:
            raise desktop.agent.AgentError('Unsupported coding owner')
        self.owner, self.chat = owner, chat
        self.tasks = {}
        self.initialized = False

    def call(self, name, args):
        if not isinstance(args, dict):
            raise desktop.agent.AgentError('Tool arguments must be an object')
        if name == 'supervisor_status' and not args:
            return {'model': MODEL, 'transport': 'stdio',
                    'repository': desktop.agent.REPOSITORY,
                    'source_policy': 'clean current public main only',
                    'owner': self.owner, 'state': 'advisory_only',
                    'inference_tested_by_this_call': False,
                    'source_writes': False, 'shell_tool': False,
                    'cloud_fallback': False, 'publication': False}
        if name == 'prepare_review' and set(args) == {'task', 'paths'}:
            if (not isinstance(args['paths'], list)
                    or any(not isinstance(p, str) for p in args['paths'])):
                raise desktop.agent.AgentError('paths must be a list of strings')
            if len(self.tasks) >= 16:
                raise desktop.agent.AgentError('Session task limit reached; restart the bridge')
            packet, prompt = desktop.prepare(self.repo, args['task'], args['paths'], self.owner)
            task_id = secrets.token_hex(16)
            self.tasks[task_id] = packet
            return {'task_id': task_id, 'source_sha': packet['source_sha'],
                    'prompt': prompt, 'next': 'Submit candidate to review_proposal'}
        if name == 'review_proposal' and set(args) == {'task_id', 'candidate'}:
            task_id = args['task_id']
            if not isinstance(task_id, str) or task_id not in self.tasks:
                raise desktop.agent.AgentError('Unknown task; call prepare_review in this session')
            if not isinstance(args['candidate'], dict):
                raise desktop.agent.AgentError('candidate must be an object')
            record = desktop.review(self.tasks[task_id], args['candidate'], MODEL, self.chat)
            record['transport'] = 'mcp-stdio'
            record['task_id'] = task_id
            output = desktop.agent.save(record, self.output)
            return {'audit_id': output.stem, 'source_sha': record['source_sha'],
                    'candidate_sha256': record['submitted_candidate_sha256'],
                    'supervisor_model': MODEL, 'critique': record['critique'],
                    'state': record['state'], 'actions_executed': [], 'tests_executed': []}
        raise desktop.agent.AgentError('Unknown tool or unexpected arguments')

    def handle(self, message):
        if (not isinstance(message, dict) or message.get('jsonrpc') != '2.0'
                or not isinstance(message.get('method'), str)):
            return error(None, -32600, 'Invalid request')
        if 'id' not in message:
            return None  # Notifications have no response; no action tools are dispatched.
        request_id = message['id']
        if isinstance(request_id, bool) or not isinstance(request_id, (str, int)):
            return error(None, -32600, 'Invalid request ID')
        method, params = message['method'], message.get('params', {})
        if not isinstance(params, dict):
            return error(request_id, -32602, 'Invalid params')
        if method == 'initialize':
            version = params.get('protocolVersion')
            self.initialized = True
            result = {'protocolVersion': version if version in VERSIONS else VERSIONS[-1],
                      'capabilities': {'tools': {}},
                      'serverInfo': {'name': 'gatewayai-local-supervisor', 'version': '1.0.0'},
                      'instructions': 'Local advisory code review only. Prepare a task, '
                                      'then submit a public candidate. Findings never authorize actions.'}
        elif method == 'ping':
            result = {}
        elif not self.initialized:
            return error(request_id, -32000, 'Initialize first')
        elif method == 'tools/list':
            result = {'tools': TOOLS}
        elif method == 'tools/call':
            try:
                value = self.call(params.get('name'), params.get('arguments', {}))
                result = {'content': [{'type': 'text', 'text': json.dumps(value, ensure_ascii=False)}]}
            except (desktop.agent.AgentError, OSError, ValueError, TypeError) as exc:
                # Do not return private filesystem paths, subprocess output or credentials.
                detail = str(exc) if isinstance(exc, desktop.agent.AgentError) else 'Local review failed'
                result = {'content': [{'type': 'text', 'text': detail[:500]}], 'isError': True}
        else:
            return error(request_id, -32601, 'Method not found')
        return {'jsonrpc': '2.0', 'id': request_id, 'result': result}


def error(request_id, code, message):
    return {'jsonrpc': '2.0', 'id': request_id, 'error': {'code': code, 'message': message}}


def serve(bridge, source, sink):
    while raw := source.readline(LIMIT + 1):
        if len(raw) > LIMIT:
            response = error(None, -32600, 'Request exceeds byte ceiling')
            sink.write((json.dumps(response) + '\n').encode('utf-8'))
            sink.flush()
            return  # Do not interpret the remainder of an oversized frame as requests.
        try:
            message = json.loads(raw)
        except (ValueError, UnicodeError):
            response = error(None, -32700, 'Invalid JSON')
        else:
            response = bridge.handle(message)
        if response is not None:
            sink.write((json.dumps(response, ensure_ascii=False) + '\n').encode('utf-8'))
            sink.flush()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--output-root', type=Path, required=True)
    parser.add_argument('--owner', choices=desktop.OWNERS, default='gemini-pro')
    args = parser.parse_args()
    bridge = Bridge(args.repo, args.output_root, args.owner)
    serve(bridge, sys.stdin.buffer, sys.stdout.buffer)


if __name__ == '__main__':
    main()
