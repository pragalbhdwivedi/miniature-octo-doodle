"""Signed, question-bound fixed answers and explicit custom reply capture."""
import hashlib
import hmac
import re

import pilot_state as state


def choices(q):
    values=q.get('options')
    if values is None:
        values=['Sent','Still blocked'] if q['id'].startswith('delivery') else ['Keep stopped','Request a repair']
    if not isinstance(values,list) or not 1<=len(values)<=6 or any(not isinstance(v,str) or not 1<=len(v)<=60 for v in values):
        raise ValueError('Invalid fixed answers')
    return values


def signature(s,q,option,key):
    identity={'batch':s['batch']['id'],'id':q['id'],'question':q['question'],
              'options':choices(q),'option':option,'context':q.get('context_digest')}
    return hmac.new(bytes.fromhex(key),state.digest(identity).encode(),hashlib.sha256).hexdigest()[:16]


def callback(s,q,option,key):
    if not re.fullmatch(r'[a-zA-Z0-9-]{1,24}',q['id']):raise ValueError('Invalid question identity')
    return 'q:'+q['id']+':'+str(option)+':'+signature(s,q,str(option),key)


def keyboard(s,q,key):
    buttons=[{'text':text,'callback_data':callback(s,q,str(i),key)} for i,text in enumerate(choices(q))]
    rows=[buttons[i:i+2] for i in range(0,len(buttons),2)]
    rows.append([{'text':'Custom','callback_data':callback(s,q,'custom',key)}])
    return {'inline_keyboard':rows}


def pending(s,qid):
    q=next((q for q in s['questions'] if q['id']==qid and q.get('kind')=='decision'),None)
    if not q or q.get('state')!='pending':raise ValueError('That question is already answered or no longer pending')
    return q


def record(s,q,text,mode):
    if not isinstance(text,str) or not text.strip() or len(text)>3000:raise ValueError('Please enter an answer of 1 to 3000 characters')
    q.update(state='answered',answer=text.strip(),answer_mode=mode,answered_at=state.stamp())
    if s.get('pending_reply',{}).get('question_id')==q['id']:s.pop('pending_reply',None)
    state.event(s,'Owner answered question '+q['id']+' ('+mode+').')
    if q.get('purpose')=='detail_preference' and text in ('Brief','Detailed','Comprehensive'):
        s['detail_level']={'Brief':'brief','Detailed':'detailed','Comprehensive':'full'}[text]
        outcome='Your preferred menu detail level is saved.'
    elif q.get('purpose')=='detail_preference':outcome='Your custom preference is saved for review.'
    else:outcome='Saved with the original question. This records your instruction; it does not publish code or restart blocked work.'
    state.message(s,'Answer received: '+text[:1000]+'\n'+outcome)


def handle_callback(s,data,key):
    bits=data.split(':')
    if len(bits)!=4 or bits[0]!='q':raise ValueError('Invalid answer button')
    _,qid,option,mac=bits;q=pending(s,qid)
    if not hmac.compare_digest(mac,signature(s,q,option,key)):raise ValueError('This answer button is outdated')
    if option=='custom':
        s['pending_reply']={'question_id':qid,'context':state.digest(q),'requested_at':state.stamp()}
        state.message(s,'Custom answer for: '+q['question'][:1600]+'\nType your answer as your next message. No /answer command is needed.',
                      {'inline_keyboard':[[{'text':'Cancel custom answer','callback_data':callback(s,q,'cancel',key)}]]})
    elif option=='cancel':
        if s.get('pending_reply',{}).get('question_id')==qid:s.pop('pending_reply',None)
        state.message(s,'Custom entry cancelled. Choose an answer below.',keyboard(s,q,key))
    elif option.isdigit() and int(option)<len(choices(q)):
        record(s,q,choices(q)[int(option)],'fixed')
    else:raise ValueError('Unknown fixed answer')


def custom_text(s,text):
    target=s.get('pending_reply')
    if not target:return False
    try:
        q=pending(s,target['question_id'])
        if state.digest(q)!=target['context']:raise ValueError('The question changed; choose Custom again from Decisions')
        record(s,q,text,'custom')
    except ValueError as error:
        s.pop('pending_reply',None)
        state.message(s,str(error)+'. Your text was not used as a new task or sent to Qwen.')
    return True


def show_pending(s,key):
    questions=[q for q in s['questions'] if q.get('kind')=='decision' and q.get('state')=='pending']
    for q in questions[:6]:state.message(s,q['question']+'\nChoose a fixed answer or Custom.',keyboard(s,q,key))
    return bool(questions)
