"""Run inside restored WebUI; use existing scoped credentials without printing them."""
import json
import os
import sys
import urllib.error
import urllib.request


def request(url, key=None, body=None, expected=200):
    headers = {'Content-Type':'application/json'}
    if key:
        headers['Authorization'] = 'Bearer ' + key
    data = json.dumps(body).encode() if body is not None else None
    try:
        with urllib.request.urlopen(urllib.request.Request(url,data,headers),timeout=30) as response:
            status,payload=response.status,response.read()
    except urllib.error.HTTPError as error:
        status,payload=error.code,error.read()
    assert status == expected, 'Unexpected HTTP status: ' + str(status)
    return json.loads(payload)


def main():
    gateway=os.environ['OPENAI_API_BASE_URL'].removesuffix('/v1')
    key=os.environ['OPENAI_API_KEY']
    ui='http://127.0.0.1:8080'
    request(gateway+'/health/liveliness')
    request(gateway+'/v1/models',expected=401)
    models=request(gateway+'/v1/models',key)['data']
    request(gateway+'/key/list',key,expected=403)
    request(ui+'/health')
    login=request(ui+'/api/v1/auths/signin',body={'email':os.environ['WEBUI_ADMIN_EMAIL'],'password':os.environ['WEBUI_ADMIN_PASSWORD']})
    assert login['role']=='admin'
    discovered=request(ui+'/api/models',login['token'])['data']
    expected=json.loads(sys.argv[1])
    assert sorted(m['id'] for m in models)==sorted(m['id'] for m in discovered)==sorted(expected)
    if models:
        denial=request(gateway+'/v1/chat/completions',key,
                       {'model':models[0]['id'],'messages':[{'role':'user','content':'Synthetic recovery deny probe'}]},429)
        assert 'monthly_budget_exhausted' in json.dumps(denial)
    print(json.dumps({'restored_admin_login':True,'restricted_key':True,'model_count':len(models),'zero_budget_denial':bool(models)}))


if __name__=='__main__':
    try:
        main()
    except Exception as error:
        sys.exit('Recovery HTTP test failed ('+type(error).__name__+'); response omitted.')
