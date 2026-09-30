"""Operator-only, one-shot Telegram approval transport for draft publication.

No bot daemon, merge authority or automatic publication. Credentials remain in a
root-owned file outside Git. A callback only records an exact, expiring decision.
"""
import argparse
import hashlib
import hmac
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import urllib.request

ROOT=Path(__file__).resolve().parent.parent
def module(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/(name+'.py'))
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value
p=module('controller_pipeline')
d=p.d


def validate_config(value):
    if set(value)!={'bot_token','user_id','chat_id','signing_key_hex'}:
        raise ValueError('Unexpected Telegram configuration')
    if not isinstance(value['bot_token'],str) or not re.fullmatch(r'[0-9]{5,15}:[A-Za-z0-9_-]{25,120}',value['bot_token']):
        raise ValueError('Invalid bot token format')
    if type(value['user_id']) is not int or type(value['chat_id']) is not int or value['user_id']<=0 or value['chat_id']<=0:
        raise ValueError('Positive private user and chat IDs required')
    if not isinstance(value['signing_key_hex'],str) or not re.fullmatch('[a-f0-9]{64}',value['signing_key_hex']):
        raise ValueError('32-byte signing key required')
    return value


def callback(value, approval_id, decision, digest):
    if not re.fullmatch('[a-f0-9]{32}',approval_id) or not re.fullmatch('[a-f0-9]{64}',digest):
        raise ValueError('Invalid approval identity')
    if decision not in ('approve','reject'):raise ValueError('Invalid decision')
    key=bytes.fromhex(value['signing_key_hex'])
    mac=hmac.new(key,(approval_id+':'+decision+':'+digest).encode(),hashlib.sha256).hexdigest()[:16]
    result=('a' if decision=='approve' else 'r')+':'+approval_id+':'+mac
    assert len(result.encode())<=64
    return result


def decode_callback(value, data, row):
    if not isinstance(data,str) or not re.fullmatch('[ar]:[a-f0-9]{32}:[a-f0-9]{16}',data):
        raise ValueError('Malformed callback')
    label,approval_id,_=data.split(':')
    if row is None or row['approval_id']!=approval_id:raise ValueError('Unknown approval')
    decision='approve' if label=='a' else 'reject'
    if not hmac.compare_digest(data,callback(value,approval_id,decision,row['payload_sha256'])):
        raise ValueError('Callback signature mismatch')
    return decision


def bot_call(config, method, payload, transport=None):
    if method not in ('sendMessage','getUpdates','answerCallbackQuery'):
        raise ValueError('Unsupported Telegram API method')
    url='https://api.telegram.org/bot'+config['bot_token']+'/'+method
    body=json.dumps(payload,allow_nan=False).encode()
    if len(body)>8192:raise ValueError('Telegram request ceiling')
    request=urllib.request.Request(url,body,headers={'Content-Type':'application/json'},method='POST')
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),p.w.coding.NoRedirect())
    try:
        with (transport or opener.open)(request,timeout=20) as response:
            raw=response.read(262145)
        if len(raw)>262144:raise ValueError('Telegram response ceiling')
        result=json.loads(raw)
        if result.get('ok') is not True:raise ValueError('Telegram API denied request')
        return result['result']
    except Exception:
        # URLs contain bot tokens; never include transport errors in output/logs.
        raise RuntimeError('Telegram operation uncertain; inspect private state before retry') from None


def request_approval(store,root,row,config,transport=None):
    receipt=p.publication_receipt(row)
    digest=d.digest(receipt)
    if root['run_id']!=receipt['run_id'] or root['state']!='review_required':
        raise ValueError('Exact reviewed run required')
    p.eligible(root,Path(config['runtime']))
    folder=Path(config['worker_runtime'])/receipt['candidate_run']
    artifact=p.publisher.plan(folder,receipt['artifact_sha256'])
    if artifact['source_sha']!=receipt['source_sha']:
        raise ValueError('Publication source changed')
    approval_id=secrets.token_hex(16)
    t=validate_config(d.private_json(Path(config['telegram_approval_config'])))
    record=store.request_approval(approval_id,root['run_id'],digest,t['user_id'],t['chat_id'],900)
    message=('GatewayAI draft PR approval\nRun: '+root['run_id']+'\nSource: '+receipt['source_sha']+
             '\nArtifact: '+receipt['artifact_sha256']+'\nReceipt: '+digest+'\nExpires in 15 minutes.')
    markup={'inline_keyboard':[[
        {'text':'Approve draft PR','callback_data':callback(t,approval_id,'approve',digest)},
        {'text':'Reject','callback_data':callback(t,approval_id,'reject',digest)}]]}
    result=bot_call(t,'sendMessage',{'chat_id':t['chat_id'],'text':message,'reply_markup':markup},transport)
    if result.get('chat',{}).get('id')!=t['chat_id'] or type(result.get('message_id')) is not int:
        raise RuntimeError('Telegram delivery uncertain; inspect private state')
    return {'approval_id':approval_id,'run_id':root['run_id'],'state':record['state'],
            'payload_sha256':digest,'expires_at':record['expires_at']}


def apply_update(store,config,update):
    t=validate_config(config)
    if type(update.get('update_id')) is not int or update['update_id']<0:
        raise ValueError('Invalid update ID')
    query=update.get('callback_query')
    if not isinstance(query,dict):return None
    sender=query.get('from')
    message=query.get('message',{})
    if not isinstance(sender,dict) or not isinstance(message,dict):
        raise ValueError('Malformed callback identity')
    chat=message.get('chat')
    if not isinstance(chat,dict):raise ValueError('Private callback chat required')
    user=sender.get('id')
    if user!=t['user_id'] or chat.get('id')!=t['chat_id'] or chat.get('type')!='private':
        raise ValueError('Unapproved Telegram identity or chat')
    data=query.get('data','')
    if not isinstance(data,str) or not re.fullmatch('[ar]:[a-f0-9]{32}:[a-f0-9]{16}',data):
        raise ValueError('Malformed callback')
    approval_id=data.split(':')[1]
    row=store.approval(approval_id)
    decision=decode_callback(t,data,row)
    if row['state']!='pending':raise ValueError('Approval already decided')
    if not isinstance(query.get('id'),str) or not query['id']:
        raise ValueError('Callback query ID required')
    result=store.decide_approval(approval_id,row['payload_sha256'],
                                 'approved' if decision=='approve' else 'rejected',
                                 user,chat['id'],update['update_id'])
    return {'approval_id':approval_id,'state':result['state'],'callback_query_id':query['id']}


def poll_once(store,config,offset_path,transport=None):
    t=validate_config(config)
    offset=0
    if offset_path.exists():
        value=d.private_json(offset_path)
        if set(value)!={'next_update_id'} or type(value['next_update_id']) is not int or value['next_update_id']<0:
            raise ValueError('Invalid protected Telegram offset')
        offset=value['next_update_id']
    updates=bot_call(t,'getUpdates',{'offset':offset,'limit':10,'timeout':0,
                                    'allowed_updates':['callback_query']},transport)
    if not isinstance(updates,list) or len(updates)>10:raise ValueError('Invalid update batch')
    decisions=[]
    for update in updates:
        # Anyone can send a bot an update. Unauthorised or malformed callbacks
        # must not pin the offset forever; database/transport ambiguity still stops.
        try:result=apply_update(store,t,update)
        except ValueError:result=None
        if result:
            bot_call(t,'answerCallbackQuery',{'callback_query_id':result['callback_query_id'],
                                             'text':'Decision recorded'},transport)
            decisions.append({'approval_id':result['approval_id'],'state':result['state']})
        next_id=update['update_id']+1
        if next_id<=offset:raise ValueError('Out-of-order Telegram update')
        temporary=offset_path.with_suffix('.tmp')
        with temporary.open('x') as stream:
            stream.write(json.dumps({'next_update_id':next_id}));stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,offset_path)
        offset=next_id
    return decisions


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['request','poll','status'])
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--run-id')
    parser.add_argument('--approval-id')
    args=parser.parse_args()
    if os.name!='posix' or os.geteuid()!=0:raise ValueError('Linux operator only')
    os.umask(0o077)
    config=d.private_json(args.config)
    if not config.get('telegram_approval_config'):raise ValueError('Telegram disabled')
    runtime=Path(config['runtime']);p.w.private_root(runtime)
    import fcntl
    with (runtime/'dispatch.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        store=d.state.Store(config['container'],config['database'])
        if args.action=='request':
            if not re.fullmatch('[a-f0-9]{32}',args.run_id or ''):raise ValueError('Run ID required')
            root=store.get(args.run_id);row=store.pipeline(args.run_id)
            result=request_approval(store,root,row,config)
        elif args.action=='poll':
            result={'decisions':poll_once(store,d.private_json(Path(config['telegram_approval_config'])),
                                          runtime/'telegram-offset.json')}
        else:
            if not re.fullmatch('[a-f0-9]{32}',args.approval_id or ''):raise ValueError('Approval ID required')
            row=store.approval(args.approval_id)
            result={'approval_id':row['approval_id'],'run_id':row['run_id'],'state':row['state'],
                    'expires_at':row['expires_at'],'payload_sha256':row['payload_sha256']} if row else None
        print(json.dumps(result))


if __name__=='__main__':
    try:main()
    except Exception as error:
        raise SystemExit('Telegram approval stopped: '+type(error).__name__+'; inspect private state, never automatically retry')
