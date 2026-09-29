"""Explicit live smoke test: one small synthetic completion per requested alias."""
import json
import os
import sys
import time
import urllib.error
import urllib.request


def run():
    base = os.environ['OPENAI_API_BASE_URL']
    if base != 'http://litellm:4000/v1':
        raise ValueError('Unexpected gateway destination')
    headers = {'Authorization': 'Bearer ' + os.environ['OPENAI_API_KEY'],
               'Content-Type': 'application/json'}
    failed = False
    for alias in sys.argv[1:]:
        started = time.monotonic()
        body = {'model': alias, 'messages': [
            {'role': 'user', 'content': 'Reply with exactly OK and nothing else.'}],
            'max_completion_tokens': 64, 'stream': False}
        request = urllib.request.Request(base + '/chat/completions',
                                         json.dumps(body).encode(), headers)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                status = response.status
                result = json.load(response)
            choice = result['choices'][0]
            passed = status == 200 and choice['message']['content'].strip() == 'OK'
            usage = result.get('usage', {})
            # Never print arbitrary provider text, error bodies or credentials.
            counts = {name: value for name in ('prompt_tokens', 'completion_tokens', 'total_tokens')
                      if isinstance((value := usage.get(name)), int)}
            print(json.dumps({'alias': alias, 'http': status, 'exact_OK': passed,
                              'elapsed_seconds': round(time.monotonic() - started, 2),
                              'usage': counts}), flush=True)
            failed |= not passed
        except urllib.error.HTTPError as error:
            message = error.read().decode('utf-8', errors='replace').lower()
            category = 'provider_error'
            for marker, label in [('insufficient_quota', 'quota'), ('resource_exhausted', 'quota'),
                                  ('invalid_api_key', 'authentication'), ('api_key_invalid', 'authentication'),
                                  ('model_not_found', 'model_access'), ('unsupported_parameter', 'parameter')]:
                if marker in message:
                    category = label
                    break
            print(json.dumps({'alias': alias, 'http': error.code, 'category': category}), flush=True)
            failed = True
        except Exception:
            print(json.dumps({'alias': alias, 'category': 'transport_or_response_error'}), flush=True)
            failed = True
    return 1 if failed else 0


if __name__ == '__main__':
    try:
        sys.exit(run())
    except Exception:
        sys.exit('Provider probe failed; details omitted to protect credentials.')
