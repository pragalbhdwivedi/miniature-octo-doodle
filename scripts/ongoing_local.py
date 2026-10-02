"""Installed loopback-only local coder. Structured proposals, no tools/downloads."""
import json
import ast
import textwrap
from pathlib import Path
import urllib.request
import local_agent
from pilot_worker import write_json

MODEL='devstral-small-2:24b'
CODER_MODELS=frozenset({MODEL,'qwen3:4b-instruct'})
MAX_PROMPT_BYTES=10000
METHOD_SCHEMA={'type':'object','properties':{k:{'type':'string'} for k in ('summary','proposal','method_source')},
               'required':['summary','proposal','method_source'],'additionalProperties':False}
DEVELOPMENT_SCHEMA={'type':'object','properties':{
    'summary':{'type':'string'},'proposal':{'type':'string'},
    'changes':{'type':'array','minItems':1,'maxItems':4,'items':{'type':'object',
        'properties':{'path':{'type':'string'},'content':{'type':'string'}},
        'required':['path','content'],'additionalProperties':False}}},
    'required':['summary','proposal','changes'],'additionalProperties':False}


def apply_method(before,method):
    """Place one returned method in the existing test class; never evaluate code."""
    tree=ast.parse(method)
    if (len(tree.body)!=1 or not isinstance(tree.body[0],ast.FunctionDef) or
            not tree.body[0].name.startswith('test_') or tree.body[0].decorator_list):
        raise ValueError('Local output must contain exactly one undecorated test method')
    classes=[n for n in ast.parse(before).body if isinstance(n,ast.ClassDef)]
    if len(classes)!=1:raise ValueError('Local compact lane requires one existing test class')
    cls=classes[0]
    if any(isinstance(n,ast.FunctionDef) and n.name==tree.body[0].name for n in cls.body):
        raise ValueError('Local method must not replace an existing test')
    lines=before.splitlines(keepends=True)
    return ''.join(lines[:cls.end_lineno]).rstrip('\n')+'\n\n'+textwrap.indent(method.rstrip(),'    ')+'\n'+''.join(lines[cls.end_lineno:])


def proposal(before,value,path):
    # Some local structured decoders put the method in the proposal field.
    # Accept only one unambiguous single-method AST, never evaluate either field.
    candidates=set()
    for key in ('method_source','proposal'):
        try:candidates.add(apply_method(before,value[key]))
        except (KeyError,ValueError,SyntaxError,TypeError):continue
    if len(candidates)!=1:raise ValueError('Local method output missing or ambiguous')
    return {'summary':value['summary'],'proposal':'Local single-method proposal; tests not run by coder.',
            'changes':[{'path':path,'content':candidates.pop()}]}


def run(prompt,directory,model=MODEL,opener=None,development=False):
    maximum=24000 if development else MAX_PROMPT_BYTES
    if model not in CODER_MODELS or not isinstance(prompt,str) or not prompt.strip() or len(prompt.encode())>maximum:
        raise ValueError('Local lane supports explicitly configured installed coding models and compact tasks only')
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    if (directory/'local-intent.json').exists():raise ValueError('Local inference already reserved; replay denied')
    route={'model':model,'provider':'ollama_local','cloud_quota_used':False,'api_fallback':False}
    write_json(directory/'local-intent.json',route)
    body={'model':model,'messages':[{'role':'user','content':prompt}],
          'format':DEVELOPMENT_SCHEMA if development else METHOD_SCHEMA,'stream':False,'think':False,'keep_alive':'2m',
          'options':{'num_ctx':8192 if development else 4096,'num_predict':3072 if development else 512,'temperature':0}}
    request=urllib.request.Request(local_agent.OLLAMA_URL,json.dumps(body).encode(),
                                   {'Content-Type':'application/json'},method='POST')
    opener=opener or urllib.request.build_opener(urllib.request.ProxyHandler({}),local_agent.NoRedirect())
    with opener.open(request,timeout=600) as response:
        raw=response.read(local_agent.MAX_RESPONSE_BYTES+1)
    if len(raw)>local_agent.MAX_RESPONSE_BYTES:raise ValueError('Local output exceeds bound')
    (directory/'local-response.json').write_bytes(raw)
    value=json.loads(raw)
    if (value.get('model')!=model or value.get('done') is not True or value.get('done_reason')!='stop'
            or value.get('message',{}).get('tool_calls')):
        raise ValueError('Local result incomplete, wrong model or attempted tools; claim retained')
    candidate=json.loads(value['message']['content'])
    if not isinstance(candidate,dict):raise ValueError('Local structured result missing')
    result={'candidate':candidate,'route':route,'usage':{
        'input_tokens':value.get('prompt_eval_count'),'output_tokens':value.get('eval_count'),
        'duration_ns':value.get('total_duration'),'cloud_tokens':0}}
    write_json(directory/'local-result.json',result)
    return result
