"""Request formats and endpoint validation without calling external providers."""
import json
from unittest.mock import patch
from app.ai_provider import chat, validate

config=dict(provider='ollama',base_url='http://host.docker.internal:11434',model='test',enabled=True,temperature=0,max_tokens=1400,context_size=8192,key='test-key')
class Response:
    def __enter__(self): return self
    def __exit__(self,*args): pass
    def read(self,size): return json.dumps(result).encode()
class Opener:
    def open(self,request,timeout):
        captured.append(request)
        return Response()
captured=[]
result={'done':True,'message':{'content':'{"ok":true}'}}
with patch('urllib.request.build_opener',return_value=Opener()):
    assert json.loads(chat([{'role':'user','content':'test'}],{'type':'object'},config))['ok']
assert captured[-1].full_url.endswith('/api/chat')
assert json.loads(captured[-1].data)['format']=={'type':'object'}
config={**config,'provider':'openai','base_url':'https://example.com/v1'}
result={'choices':[{'finish_reason':'stop','message':{'content':'{"ok":true}'}}]}
with patch('urllib.request.build_opener',return_value=Opener()):
    assert json.loads(chat([],{'type':'object'},config))['ok']
assert captured[-1].full_url=='https://example.com/v1/chat/completions'
assert captured[-1].get_header('Authorization')=='Bearer test-key'
assert json.loads(captured[-1].data)['response_format']=={'type':'json_object'}
for url in ['file:///etc/passwd','http://name:secret@host/','http://169.254.169.254','https://example.com/?key=secret']:
    try:
        validate({**config,'base_url':url})
        raise AssertionError('Unsafe URL accepted')
    except ValueError: pass
result={'choices':[{'finish_reason':'length','message':{'content':'{}'}}]}
with patch('urllib.request.build_opener',return_value=Opener()):
    try:
        chat([],None,config)
        raise AssertionError('Incomplete response accepted')
    except ValueError: pass
print('AI endpoint validation, request formats, authentication and incomplete-output checks passed')
