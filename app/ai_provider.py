"""Administrator-selected AI endpoint; secrets stay out of page rendering."""
import hashlib
import ipaddress
import json
import os
import urllib.request
from urllib.parse import urlsplit
from app.db import connect


def secret_key():
    return hashlib.sha256(('forgetfulme:ai-key:'+os.environ['ADMIN_PASSWORD']).encode()).hexdigest()


def settings(include_key=False):
    with connect() as db:
        fields = ',pgp_sym_decrypt(api_key,%s) AS key' if include_key else ',(api_key IS NOT NULL) AS has_key'
        row = db.execute('SELECT provider,base_url,model,enabled,temperature,max_tokens,context_size,test_state,test_message,models,models_state,models_message,models_fetched_at'+fields+' FROM ai_settings WHERE id=1', (secret_key(),) if include_key else ()).fetchone()
    return row or dict(provider='ollama',base_url=os.environ.get('OLLAMA_URL','http://host.docker.internal:11434'),model=os.environ.get('OLLAMA_MODEL','qwen2.5:3b'),enabled=True,temperature=0.0,max_tokens=1400,context_size=8192,has_key=False,key=None,test_state='untested',test_message=None)


def validate(values):
    if values['provider'] not in {'ollama','openai'}: raise ValueError('Choose Ollama or an OpenAI-compatible provider')
    url=values['base_url'].strip().rstrip('/')
    parsed=urlsplit(url)
    if parsed.scheme not in {'http','https'} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or any(c.isspace() or ord(c)<32 for c in url):
        raise ValueError('Use an HTTP(S) base URL without credentials, query or fragment')
    _=parsed.port
    try:
        address=ipaddress.ip_address(parsed.hostname)
    except ValueError: address=None
    if address and (address.is_link_local or address.is_unspecified or address.is_multicast): raise ValueError('This address cannot be used as an AI endpoint')
    if not values['model'].strip() or len(values['model'])>200: raise ValueError('Provide a model name up to 200 characters')
    if len(url)>2000: raise ValueError('Base URL is too long')
    if not 0<=float(values['temperature'])<=2 or not 256<=int(values['max_tokens'])<=4096 or not 2048<=int(values['context_size'])<=32768: raise ValueError('Check temperature, output tokens and context size limits')
    values['base_url']=url;values['model']=values['model'].strip()
    return values


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('AI endpoint redirects are not supported; enter its final base URL')


def chat(messages, schema=None, config=None):
    config=config or settings(include_key=True)
    if not config['enabled']: raise ValueError('AI processing is paused')
    headers={'Content-Type':'application/json'}
    if config.get('key'): headers['Authorization']='Bearer '+config['key']
    if config['provider']=='ollama':
        path='/api/chat'
        payload={'model':config['model'],'messages':messages,'stream':False,'options':{'temperature':float(config['temperature']),'num_ctx':config['context_size'],'num_predict':config['max_tokens']},'keep_alive':'5m'}
        if schema: payload['format']=schema
    else:
        path='/chat/completions'
        messages=list(messages)
        if schema: messages=[{'role':'system','content':'Return JSON matching this schema: '+json.dumps(schema)}]+messages
        payload={'model':config['model'],'messages':messages,'stream':False,'temperature':float(config['temperature']),'max_tokens':config['max_tokens']}
        if schema: payload['response_format']={'type':'json_object'}
    request=urllib.request.Request(config['base_url'].rstrip('/')+path,data=json.dumps(payload).encode(),headers=headers)
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    with opener.open(request,timeout=60) as response: data=response.read(1024*1024+1)
    if len(data)>1024*1024: raise ValueError('Model response too large')
    result=json.loads(data)
    if config['provider']=='ollama':
        if not result.get('done') or result.get('done_reason')=='length': raise ValueError('Model output incomplete')
        return result['message']['content']
    choice=result['choices'][0]
    if choice.get('finish_reason')!='stop': raise ValueError('Model output incomplete')
    return choice['message']['content']


def test_pending():
    with connect() as db:
        row=db.execute("SELECT id FROM ai_settings WHERE id=1 AND test_state='pending' FOR UPDATE SKIP LOCKED").fetchone()
        if not row: return False
        try:
            config=settings(include_key=True);config['enabled']=True
            result=json.loads(chat([{'role':'user','content':'Return JSON with ok set to true.'}],{'type':'object','properties':{'ok':{'type':'boolean'}},'required':['ok']},config))
            if result.get('ok') is not True: raise ValueError('Invalid test output')
            state,message='success','Connected: model returned valid JSON. No browsing content was sent for this test.'
        except Exception:
            state,message='failed','Connection test failed. Check the base URL, API key, model and JSON support; inspect provider availability.'
        db.execute('UPDATE ai_settings SET test_state=%s,test_message=%s WHERE id=1',(state,message))
    return True


def fetch_models(config):
    path='/api/tags' if config['provider']=='ollama' else '/models'
    headers={'Accept':'application/json'}
    if config.get('key'): headers['Authorization']='Bearer '+config['key']
    request=urllib.request.Request(config['base_url'].rstrip('/')+path,headers=headers)
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    with opener.open(request,timeout=15) as response: content=response.read(1024*1024+1)
    if len(content)>1024*1024: raise ValueError('Model list too large')
    response=json.loads(content)
    items=response.get('models') if config['provider']=='ollama' else response.get('data')
    if not isinstance(items,list): raise ValueError('Invalid model catalog')
    names=set()
    for item in items:
        if not isinstance(item,dict): continue
        name=(item.get('name') or item.get('model')) if config['provider']=='ollama' else item.get('id')
        if isinstance(name,str) and name.strip() and len(name)<=200 and not any(ord(c)<32 for c in name): names.add(name)
    return sorted(names)[:1000]


def discover_pending():
    with connect() as db:
        row=db.execute("SELECT id FROM ai_settings WHERE id=1 AND models_state='pending' FOR UPDATE SKIP LOCKED").fetchone()
        if not row: return False
        try:
            models=fetch_models(settings(include_key=True))
            state='success'
            message=f'Found {len(models)} models. Choose one and save settings.' if models else 'The provider returned no available models. Install a model or enter its name manually.'
        except Exception:
            models=[];state='failed';message='Could not fetch models. Check the base URL, provider type, credentials and /models or /api/tags support. Manual model entry is still available.'
        db.execute('UPDATE ai_settings SET models=%s::jsonb,models_state=%s,models_message=%s,models_fetched_at=now() WHERE id=1',(json.dumps(models),state,message))
    return True
