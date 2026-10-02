"""Official native CLI, explicit model, tools disabled, live shared-quota routing."""
import json
import os
from pathlib import Path
import re
from datetime import datetime, timezone, timedelta
import local_agent
from pilot_worker import bounded_run, write_json

DENY=[name+'(*)' for name in ('read_file','write_file','read_url','execute_url','command','unsandboxed','mcp')]
AGENT='''---
name: aadi-proposal
description: Produce structured code proposals from supplied immutable text only
tools: [finish]
mainAgent: true
subagent: false
model: inherit
commandExecutionPolicy: "off"
mcpServers: []
skills: []
plugins: []
---
Return only the requested JSON from the supplied source. No tools, shell, file access,
network, skills, delegation, source writes or execution. Do not claim tests ran.
Use finish to return the requested structured result exactly once.
'''


class QuotaWait(RuntimeError):
    def __init__(self,reset_at):
        super().__init__('Suitable subscription groups are exhausted; waiting for observed reset')
        self.reset_at=reset_at


def parse_quotas(text):
    groups={}
    for line in text.splitlines():
        fields=line.split('\t')
        if len(fields)!=4:continue
        group,window,percent,reset=fields
        if group not in ('Gemini Models','Claude and GPT models') or not re.fullmatch(r'\d+(?:\.\d+)?%',percent):continue
        value=float(percent[:-1]);instant=datetime.fromisoformat(reset.replace('Z','+00:00'))
        if not 0<=value<=100 or instant.tzinfo is None:raise ValueError('Invalid quota metadata')
        groups.setdefault(group,{})[window]={'remaining':value,'reset_at':reset}
    for group in ('Gemini Models','Claude and GPT models'):
        if set(groups.get(group,{}))!={'Weekly Limit Remaining','Five Hour Limit Remaining'}:
            raise ValueError('Incomplete live quota metadata')
    return groups


def select_model(available,quotas,complexity='routine',attempt=0,prefer_group=None):
    if complexity not in ('routine','complex','hard','high_risk') or attempt not in (0,1):raise ValueError('Invalid route')
    gemini=(['gemini-3.8-flash-low','gemini-3.8-flash-medium','gemini-3.7-flash-medium','gemini-3.6-flash-medium','gemini-3.1-pro-low']
            if complexity=='routine' and attempt==0 else ['gemini-3.1-pro-low','gemini-3.1-pro-high','gemini-3.8-flash-high'])
    other=['claude-sonnet-4-6','gpt-oss-120b-medium','claude-opus-4-6-thinking']
    if complexity in ('hard','high_risk'):other=['claude-opus-4-6-thinking','claude-sonnet-4-6']
    groups=[('Gemini Models',gemini),('Claude and GPT models',other)]
    if prefer_group=='Claude and GPT models':groups.reverse()
    for group,models in groups:
        if any(v['remaining']<=0 for v in quotas[group].values()):continue
        for model in models:
            if model in available:return {'model':model,'group':group,'selection':'live native quota and model inventory','api_fallback':False}
    resets=[]
    for group,models in groups:
        if not set(models)&available:continue
        exhausted=[datetime.fromisoformat(v['reset_at'].replace('Z','+00:00')) for v in quotas[group].values() if v['remaining']<=0]
        if exhausted:resets.append(max(exhausted))
    if not resets:raise ValueError('No suitable installed native model')
    raise QuotaWait(max(datetime.now(timezone.utc)+timedelta(seconds=60),min(resets)).isoformat())


def verify_settings(path=None):
    path=Path(path) if path else Path.home()/'.gemini/antigravity-cli/settings.json'
    settings=json.loads(path.read_text(encoding='utf-8'))
    if (settings.get('toolPermission')!='strict' or settings.get('useG1Credits')!='off' or
            not set(DENY)<=set(settings.get('permissions',{}).get('deny',[]))):
        raise ValueError('Proposal-only CLI permission profile required')
    agent=Path.home()/'.gemini/config/agents/aadi-proposal.md'
    if agent.read_text(encoding='utf-8').strip()!=AGENT.strip():raise ValueError('Restricted native agent definition changed')


def parse_result(stdout,route):
    events=[json.loads(line) for line in stdout.decode('utf-8').splitlines() if line.strip()]
    init=[x['init'] for x in events if x.get('event')=='init']
    if len(init)!=1 or init[0].get('model')!=route['model'] or init[0].get('agent')!='aadi-proposal':
        raise ValueError('CLI model or agent was not enforced')
    # CLI init advertises its global inventory even for a tools:[finish] agent.
    # Require the effective strict permission mode and inspect actual calls.
    if init[0].get('permission_mode')!='strict':raise ValueError('Native permission profile not enforced')
    if any((x.get('step_update',{}).get('step_type')=='tool' and x['step_update'].get('tool_name')!='finish') or x.get('step_update',{}).get('subagent_info') for x in events):
        raise ValueError('Unexpected tool/delegation attempt')
    results=[x['result'] for x in events if x.get('event')=='result']
    if (len(results)!=1 or results[0].get('status')!='SUCCESS'
            or type(results[0].get('num_turns')) is not int
            or results[0]['num_turns'] not in (1,2)):
        raise ValueError('CLI did not complete a bounded structured response; preserve claim, no automatic generation retry')
    result=results[0]
    value=result.get('structured_output')
    if value is None:raise ValueError('Native structured result missing; no response concatenation or replay')
    if not isinstance(value,dict):raise ValueError('Structured output missing')
    return {'candidate':value,'route':{**route,'native_turns':result['num_turns']},'usage':result.get('usage',{'status':'unavailable'})}


def prepare(executable,directory,complexity='routine',attempt=0,prefer_group=None,runner=bounded_run):
    verify_settings();directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    if (directory/'antigravity-intent.json').exists():raise ValueError('Existing inference intent; no replay')
    executable=str(Path(executable).resolve(strict=True))
    names={'SYSTEMROOT','WINDIR','SYSTEMDRIVE','COMSPEC','PATH','PATHEXT','TEMP','TMP','USERPROFILE','HOMEDRIVE','HOMEPATH','APPDATA','LOCALAPPDATA'}
    env={k:v for k,v in os.environ.items() if k.upper() in names}
    code,out,err=runner([executable,'models'],timeout=30,limit=65536,env=env)
    (directory/'models-stderr.txt').write_bytes(err)
    if code:raise ValueError('Native model inventory unavailable')
    available={line.split('\t')[0] for line in out.decode().splitlines() if '\t' in line}
    code,out,err=runner([executable,'--print','/usage','--print-timeout','20s'],timeout=30,limit=65536,env=env)
    (directory/'usage-stderr.txt').write_bytes(err)
    if code:raise ValueError('Live quota check failed; no generation started')
    quotas=parse_quotas(out.decode());write_json(directory/'quotas.json',{'observed_at':datetime.now(timezone.utc).isoformat(),'groups':quotas})
    return select_model(available,quotas,complexity,attempt,prefer_group)


def run(executable,prompt,directory,complexity='routine',attempt=0,schema=None,prefer_group=None,runner=bounded_run,prepared=None):
    if not isinstance(prompt,str) or not prompt.strip() or len(prompt.encode())>65536:raise ValueError('Bounded prompt required')
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    if (directory/'antigravity-intent.json').exists():raise ValueError('Existing inference intent; no replay')
    route=prepared or prepare(executable,directory,complexity,attempt,prefer_group,runner)
    verify_settings()
    executable=str(Path(executable).resolve(strict=True))
    names={'SYSTEMROOT','WINDIR','SYSTEMDRIVE','COMSPEC','PATH','PATHEXT','TEMP','TMP','USERPROFILE','HOMEDRIVE','HOMEPATH','APPDATA','LOCALAPPDATA'}
    env={k:v for k,v in os.environ.items() if k.upper() in names}
    agent=directory/'.agents/agents/aadi-proposal.md';agent.parent.mkdir(parents=True,exist_ok=True);agent.write_text(AGENT,encoding='utf-8')
    schema_path=directory/'antigravity-schema.json';write_json(schema_path,schema or local_agent.CODER_SCHEMA)
    write_json(directory/'antigravity-intent.json',route)
    # Stdin avoids Windows command-line limits; fresh native conversation, never --continue.
    command=[executable,'--input-format','stream-json','--output-format','stream-json',
        '--model',route['model'],'--agent','aadi-proposal','--json-schema',str(schema_path),
        '--disable-slash-commands','--print-timeout','180s']
    data=(json.dumps({'event':'user','message':{'content':prompt}})+'\n').encode()
    code,out,err=runner(command,data=data,timeout=200,limit=1024*1024,cwd=directory,env=env)
    (directory/'antigravity-events.jsonl').write_bytes(out);(directory/'antigravity-stderr.txt').write_bytes(err)
    write_json(directory/'antigravity-exit.json',{'exit_code':code})
    if code:raise ValueError('Native CLI failed; inspect saved evidence, no automatic replay')
    result=parse_result(out,route);write_json(directory/'antigravity-result.json',result)
    return result
