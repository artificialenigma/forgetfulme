"""Session/CSRF-protected provider configuration."""
import html
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from app.browser_history import admin, csrf, form
from app.ai_provider import settings, validate, secret_key
from app.db import connect
from app.layout import render_page

router=APIRouter()


def render_settings(request, error='', values=None):
    config=values or settings()
    escape=lambda value: html.escape(str(value),quote=True)
    token=csrf(request)
    body='<section class="panel content-panel"><h2>AI provider</h2><p>These settings control wiki summaries and Q&amp;A. Changes apply to the next job without restarting Docker. Your sources and questions are sent to the selected provider when processing is enabled.</p>'
    if error: body+='<p role="alert">'+escape(error)+'</p>'
    if request.query_params.get('saved'): body+='<p role="status">Settings saved.</p>'
    body+=f'<form method="post" action="/settings/ai"><input type="hidden" name="csrf" value="{token}"><label for="provider">Provider API</label><select id="provider" name="provider">'
    for value,label in [('ollama','Ollama'),('openai','OpenAI-compatible')]:
        body+=f'<option value="{value}"'+(' selected' if config['provider']==value else '')+'>'+label+'</option>'
    body+='</select><label for="base_url">Base URL</label>'
    body+=f'<input id="base_url" name="base_url" type="url" value="{escape(config["base_url"])}" required maxlength="2000"><p>Ollama: http://host.docker.internal:11434. OpenAI-compatible: include the API prefix, for example https://api.openai.com/v1. The app adds /api/chat or /chat/completions. Inside Docker, localhost points to the container; use host.docker.internal for your computer.</p>'
    body+=f'<label for="model">Model</label><input id="model" name="model" value="{escape(config["model"])}" required maxlength="200">'
    body+='<label for="api_key">API key (optional for local providers)</label><input id="api_key" name="api_key" type="password" autocomplete="new-password" maxlength="2000" placeholder="Leave blank to keep the saved key">'
    body+='<p>'+('A key is stored.' if config.get('has_key') else 'No key is stored.')+' Keys are encrypted in the database.</p><label><input type="checkbox" name="clear_key" value="1"> Remove saved key</label>'
    for name,label,minimum,maximum,step in [('temperature','Temperature',0,2,'0.1'),('max_tokens','Maximum output tokens',256,4096,'1'),('context_size','Context size (Ollama only)',2048,32768,'1')]:
        body+=f'<label for="{name}">{label}</label><input type="number" id="{name}" name="{name}" min="{minimum}" max="{maximum}" step="{step}" value="{escape(config[name])}" required>'
    body+='<label><input type="checkbox" name="enabled" value="1"'+(' checked' if config['enabled'] else '')+'> Enable AI processing</label><p>Pause keeps queued work pending. Switching providers applies only to future work; completed notes are preserved. For cloud providers, use HTTPS. Models must support JSON output.</p><button name="action" value="save">Save settings</button> <button name="action" value="test">Save and test connection</button></form></section>'
    body+='<section class="panel content-panel"><h2>Connection test</h2><p>'+escape(config.get('test_state','untested'))+'</p><p>'+escape(config.get('test_message') or 'Use Save and test connection, then refresh to see the result. The worker sends only a short test prompt.')+'</p><a class="button" href="/settings/ai">Refresh status</a></section>'
    body+=f'<section class="panel content-panel"><h2>Retry failed summaries</h2><p>After fixing your provider settings, requeue failed source summaries. Reviewed and completed notes stay protected.</p><form method="post" action="/settings/ai/retry"><input type="hidden" name="csrf" value="{token}"><button>Retry failed summaries</button></form></section>'
    return HTMLResponse(render_page(body,'AI settings','/settings/ai'),status_code=400 if error else 200)


@router.get('/settings/ai',dependencies=[Depends(admin)])
def provider_settings(request: Request):
    return render_settings(request)


@router.post('/settings/ai',dependencies=[Depends(admin)])
async def save(request: Request):
    data=await form(request)
    current=settings()
    try:
        config=validate(dict(provider=data.get('provider',[''])[0],base_url=data.get('base_url',[''])[0],model=data.get('model',[''])[0],temperature=float(data.get('temperature',['0'])[0]),max_tokens=int(data.get('max_tokens',['1400'])[0]),context_size=int(data.get('context_size',['8192'])[0]),enabled=data.get('enabled')==['1']))
        key=data.get('api_key',[''])[0]
        if len(key)>2000 or any(ord(c)<32 for c in key): raise ValueError('API key contains invalid characters or is too long')
        changed_destination=config['provider']!=current['provider'] or config['base_url']!=current['base_url']
        clear=data.get('clear_key')==['1'] or changed_destination
        # Changing endpoint never forwards an old provider's credential to the new one.
        with connect() as db:
            db.execute("""INSERT INTO ai_settings(id,provider,base_url,model,enabled,temperature,max_tokens,context_size,api_key,test_state)
                VALUES(1,%s,%s,%s,%s,%s,%s,%s,CASE WHEN %s='' THEN NULL ELSE pgp_sym_encrypt(%s,%s) END,%s)
                ON CONFLICT(id) DO UPDATE SET provider=excluded.provider,base_url=excluded.base_url,model=excluded.model,
                enabled=excluded.enabled,temperature=excluded.temperature,max_tokens=excluded.max_tokens,context_size=excluded.context_size,
                api_key=CASE WHEN %s<>'' THEN excluded.api_key WHEN %s THEN NULL ELSE ai_settings.api_key END,
                test_state=excluded.test_state,test_message=NULL,updated_at=now()""",
                (config['provider'],config['base_url'],config['model'],config['enabled'],config['temperature'],config['max_tokens'],config['context_size'],key,key,secret_key(),'pending' if data.get('action')==['test'] else 'untested',key,clear))
    except (ValueError,OverflowError):
        return render_settings(request,'Check the provider, URL, model and numeric limits. URLs cannot contain credentials, query strings or fragments; keys cannot contain control characters.')
    return RedirectResponse('/settings/ai?saved=1',status_code=303)


@router.post('/settings/ai/retry',dependencies=[Depends(admin)])
async def retry(request: Request):
    await form(request)
    with connect() as db:
        db.execute("UPDATE page_captures SET ai_state='pending',ai_attempts=0,ai_error=NULL,ai_next_attempt=now() WHERE ai_state IN ('failed','retry')")
    return RedirectResponse('/settings/ai?saved=1',status_code=303)
