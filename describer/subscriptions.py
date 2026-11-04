"""Existing subscription transports and compatible APIs; no fallback or token store.

Native CLIs retain ownership of their authentication. Gateway credentials are
read by reference only. Every request uses the exact selected model.
"""
import base64
import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .engine.progress import usage
from .models import NoRedirect,is_loopback
from .providers import model_id,provider_name


def connection(settings):
    provider=provider_name(settings)
    key=''
    if provider=='Subscription gateway':
        url=settings.get('gateway_url','http://127.0.0.1:8317/v1')
        path=settings.get('gateway_key_file','')
        if path:
            try:key=Path(path).read_text(encoding='utf-8-sig').strip()
            except OSError:raise ValueError('The gateway client-key file could not be read. Select the existing gateway client key; do not copy its auth store.') from None
    else:
        entry=settings.get('connections',{}).get(settings.get('connection_id',''),{})
        if not entry or not entry.get('enabled',True):raise ValueError('Select an enabled compatible connection in Settings.')
        url=entry.get('url','')
        key=settings.get(entry.get('credential',''),'')
    url=url.strip().rstrip('/')
    parsed=urllib.parse.urlsplit(url)
    if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('Connection URL must use HTTP(S), without embedded credentials, query or fragment.')
    if parsed.scheme=='http' and not is_loopback(url):raise ValueError('Remote compatible connections require HTTPS.')
    return {'url':url,'key':key}


def api_request(url, key, payload=None, timeout=30, headers=None):
    headers=dict(headers or {},Accept='application/json',**{'Content-Type':'application/json'})
    if key:headers['Authorization']='Bearer '+key
    request=urllib.request.Request(url,data=json.dumps(payload).encode() if payload is not None else None,headers=headers)
    try:
        with urllib.request.build_opener(NoRedirect()).open(request,timeout=timeout) as response:
            body=response.read(8*1024*1024+1)
            if len(body)>8*1024*1024:raise ValueError('Provider response exceeded the size limit.')
            return json.loads(body)
    except urllib.error.HTTPError as exc:
        hint={401:'Sign in or check the selected connection credential.',403:'Check this account/model entitlement.',404:'Check the exact model ID and endpoint.',429:'Account usage limit reached; retry later.',503:'Upstream unavailable. Check the gateway/provider sign-in, account status and service availability.'}.get(exc.code,'Check the selected provider status.')
        raise RuntimeError(f'Analysis provider HTTP {exc.code}. {hint} No fallback model was used.') from None
    except (urllib.error.URLError,TimeoutError,OSError):
        raise RuntimeError('Could not reach the selected analysis endpoint. Check its URL/server and retry; no fallback was used.') from None


def cli_command(settings):
    provider=provider_name(settings)
    name={'Codex CLI':'codex','Claude CLI':'claude','Gemini CLI':'agy'}[provider]
    configured=settings.get({'Codex CLI':'codex_cli','Claude CLI':'claude_cli','Gemini CLI':'gemini_cli'}[provider]) or settings.get('cli_paths',{}).get(provider,'')
    path=configured or shutil.which(name+'.exe') or shutil.which(name) or shutil.which(name+'.ps1')
    if not path and name=='agy':
        candidate=Path.home()/'Tools'/'agy'/'bin'/'agy.exe'
        if candidate.is_file():path=str(candidate)
    if not path or not Path(path).is_file():raise ValueError(provider+' is not installed or its configured executable is missing. Install/sign in with the existing CLI, then retry.')
    path=Path(path).resolve()
    if path.suffix.lower() in ('.cmd','.bat'):
        script=path.parent/'node_modules'/'@anthropic-ai'/'claude-code'/'cli.js'
        node=shutil.which('node.exe') or shutil.which('node')
        if name=='claude' and script.is_file() and node:return [node,str(script)]
        alternate=path.with_suffix('.ps1')
        if alternate.is_file():path=alternate
        else:raise ValueError('Select a native executable or PowerShell CLI shim; batch command strings are not executed.')
    if path.suffix.lower()=='.ps1':
        shell=shutil.which('pwsh.exe') or shutil.which('powershell.exe')
        if not shell:raise ValueError('PowerShell is required to run the selected CLI shim.')
        return [shell,'-NoProfile','-File',str(path)]
    return [str(path)]


def subscription_environment():
    # Keep the user's native sign-in home, process essentials and network trust.
    # Do not hand unrelated application secrets, API billing overrides, ADC or
    # executable Node preloads to an agent interpreting media-derived input.
    allowed=set(('PATH PATHEXT COMSPEC SYSTEMROOT SYSTEMDRIVE WINDIR OS '
                 'USERPROFILE HOME HOMEDRIVE HOMEPATH APPDATA LOCALAPPDATA USERNAME USERDOMAIN LOGNAME '
                 'TEMP TMP TMPDIR LANG TZ TERM COLORTERM NO_COLOR '
                 'NODE_EXTRA_CA_CERTS NODE_NO_WARNINGS HTTP_PROXY HTTPS_PROXY ALL_PROXY NO_PROXY '
                 'SSL_CERT_FILE SSL_CERT_DIR CODEX_HOME CLAUDE_CONFIG_DIR').split())
    return {key:value for key,value in os.environ.items() if key.upper() in allowed or key.upper().startswith('LC_')}


def open_native_login(settings,cwd):
    """Hand the existing native sign-in tool to the user in a visible console.

    No token, login URL or CLI output is read by Describer. A launched process
    is not proof of authentication; the normal image test confirms the route.
    """
    provider=provider_name(settings)
    args={'Codex CLI':['login','--device-auth'],'Claude CLI':['auth','login','--claudeai'],
          'Gemini CLI':['--sandbox','--settings',json.dumps({'modelProvider':'','useG1Credits':False})]}
    if provider not in args:raise ValueError('Choose a native subscription CLI. The shared gateway retains its own sign-in tools.')
    return subprocess.Popen(cli_command(settings)+args[provider],cwd=str(cwd),env=subscription_environment(),
                            creationflags=subprocess.CREATE_NEW_CONSOLE)


def run_cli(command, args, text, cwd, cancel, timeout):
    """Bound one owned invocation; never kill an unrelated CLI by name."""
    from .services import CREATE_NO_WINDOW
    with tempfile.TemporaryFile() as output,tempfile.TemporaryFile() as error,tempfile.TemporaryFile() as stdin:
        stdin.write(text.encode());stdin.seek(0)
        env=subscription_environment()
        process=subprocess.Popen(command+args,stdin=stdin,stdout=output,stderr=error,cwd=cwd,env=env,creationflags=CREATE_NO_WINDOW)
        deadline=time.monotonic()+timeout
        try:
            while process.poll() is None:
                if cancel.wait(.1):raise InterruptedError('Analysis cancelled; no further request will be started.')
                if time.monotonic()>deadline:raise TimeoutError('Selected CLI exceeded the configured timeout.')
                if output.tell()>8*1024*1024:raise ValueError('CLI response exceeded the size limit.')
            output.seek(0);body=output.read(8*1024*1024+1)
            if len(body)>8*1024*1024:raise ValueError('CLI response exceeded the size limit.')
            if process.returncode:
                raise RuntimeError('Selected CLI did not complete. Check its sign-in, exact model entitlement and timeout. No fallback was used.')
            return body.decode('utf8')
        finally:
            if process.poll() is None:
                if os.name=='nt':
                    subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=10)
                else:process.terminate()
                try:process.wait(timeout=5)
                except subprocess.TimeoutExpired:process.kill();process.wait()


def discover(settings,cancel,log):
    provider=provider_name(settings)
    if provider in ('Subscription gateway','OpenAI-compatible'):
        info=connection(settings)
        data=api_request(info['url']+'/models',info['key'])
        rows=[]
        for row in data.get('data',[]):
            if cancel.is_set():raise InterruptedError('Cancelled')
            name=row.get('id')
            if not isinstance(name,str) or not name:continue
            caps=row.get('capabilities')
            rows.append({'name':name,'cloud':provider=='Subscription gateway' or not is_loopback(info['url']),
                         'vision':('vision' in caps if isinstance(caps,list) else None),'loaded':False})
        return sorted(rows,key=lambda row:row['name'])
    if provider in ('Codex CLI','Claude CLI','Gemini CLI'):
        cli_command(settings)
        if provider=='Codex CLI':
            cache=Path(os.environ.get('CODEX_HOME',str(Path.home()/'.codex')))/'models_cache.json'
            if cache.is_file():
                try:
                    data=json.loads(cache.read_text(encoding='utf8'))
                    return [{'name':row['slug'],'vision':'image' in row.get('input_modalities',[]),'cloud':True,'loaded':False,'catalog_source':'CLI cache; request availability unverified'}
                            for row in data.get('models',[]) if isinstance(row.get('slug'),str)]
                except (OSError,ValueError,TypeError):log('Codex model cache unavailable; enter an exact ID.')
        if provider=='Gemini CLI':
            with tempfile.TemporaryDirectory(prefix='describer-models-') as tmp:
                raw=run_cli(cli_command(settings),['models'],'',tmp,cancel,30)
            return [{'name':line.split()[0],'vision':None,'cloud':True,'loaded':False} for line in raw.splitlines() if line.strip() and line.split()[0].startswith(('gemini-','claude-','gpt-'))]
        # These CLIs do not share a model-discovery protocol. Never fabricate
        # a remote catalog from a static marketing model list.
        return [{'name':model_id(settings),'cloud':True,'vision':None,'loaded':False}] if model_id(settings) else []
    return []


def model_info(settings):
    provider=provider_name(settings)
    if not model_id(settings):raise ValueError('Enter the exact model ID for '+provider+'. No default or fallback model is selected.')
    if provider in ('Codex CLI','Claude CLI','Gemini CLI'):cli_command(settings)
    elif provider in ('Subscription gateway','OpenAI-compatible'):connection(settings)
    elif provider=='Anthropic API' and not settings.get('anthropic_key'):raise ValueError('Enter an Anthropic API key or select the Claude subscription transport.')
    return {'vision':None,'provider':provider,'model':model_id(settings)}


def cli_reply(settings, frames, prompt, cancel, log, cwd):
    provider=provider_name(settings);model=model_id(settings);command=cli_command(settings)
    effort=settings.get('analysis_effort','')
    if effort and effort not in ('low','medium','high','xhigh','max'):raise ValueError('Choose a supported reasoning effort or provider default.')
    if provider=='Codex CLI':
        args=['exec','--skip-git-repo-check','--sandbox','read-only','--ephemeral','--ignore-user-config','--json','--color','never','--model',model,
              '--disable','shell_tool','--disable','multi_agent','--disable','hooks','--disable','skill_search',
              '--disable','skill_mcp_dependency_install','--enable','skip_host_skill_discovery',
              '-c','project_doc_max_bytes=0','-c','web_search="disabled"']
        for path in frames:args.extend(('--image',str(path)))
        if effort:args.extend(('-c','model_reasoning_effort='+effort))
        args+=['-'];text=prompt
    else:
        content=[{'type':'image','source':{'type':'base64','media_type':'image/jpeg','data':base64.b64encode(path.read_bytes()).decode()}} for path in frames]
        content.append({'type':'text','text':prompt})
        if provider=='Claude CLI':
            args=['--print','--input-format','stream-json','--output-format','stream-json','--verbose','--model',model,'--no-session-persistence',
                  '--safe-mode','--restricted','--tools','','--strict-mcp-config','--mcp-config','{"mcpServers":{}}','--disable-slash-commands',
                  '--settings','{"disableAllHooks":true,"autoMemoryEnabled":false,"claudeMdExcludes":["**"]}']
            if effort:args+=['--effort',effort]
            text=json.dumps({'type':'user','message':{'role':'user','content':content}})+'\n'
        else:
            # CLI settings differ from the IDE's protobuf setting names.
            # Explicit denials also cover writes inside the temporary workspace.
            restrictions={'allowNonWorkspaceAccess':False,'toolPermission':'request-review',
                          'artifactReviewPolicy':'asks-for-review','useG1Credits':False,
                          'modelProvider':'','statusLine':{'enabled':False},'title':{'enabled':False},
                          'permissions':{'allow':['read_file('+str(cwd).replace('\\','/')+')'],
                                         'deny':['command(*)','write_file(*)','read_url(*)','execute_url(*)','mcp(*)']}}
            args=['--model',model,'--mode','default','--sandbox','--settings',json.dumps(restrictions),
                  '--disable-slash-commands','--input-format','stream-json','--output-format','stream-json','--print=']
            if effort:args+=['--effort',effort]
            # agy accepts only text input blocks. Its read-only image-viewer
            # tool must open the owned frame files within this invocation's
            # workspace; it receives no original-media or outside-file path.
            instruction=prompt+'\nInspect only these workspace image files with the image-viewer/read tool: '+', '.join(path.name for path in frames)+'. Do not run commands, browse, edit files, access other directories or delegate. Return the requested final JSON.'
            text=json.dumps({'event':'user','message':{'role':'user','content':instruction}})+'\n'
    raw=run_cli(command,args,text,cwd,cancel,float(settings.get('analysis_timeout',600)))
    events=[]
    for line in raw.splitlines():
        try:event=json.loads(line)
        except ValueError:continue
        if isinstance(event,dict):events.append(event)
    answer=None;reported=None;counts={};completed=False
    for event in events:
        reported=event.get('model',reported)
        if provider=='Codex CLI':
            if event.get('type')=='item.completed' and event.get('item',{}).get('type')=='agent_message':answer=event['item'].get('text')
            if event.get('type')=='turn.completed':counts=event.get('usage',{});completed=True
        elif provider=='Gemini CLI' and event.get('event')=='result':
            payload=event.get('result',{})
            if not isinstance(payload,dict) or payload.get('status')!='SUCCESS':raise ValueError('Gemini CLI reported an incomplete/error result.')
            answer=payload.get('response');counts=payload.get('usage',{});reported=payload.get('model',reported);completed=True
        elif event.get('type')=='result':
            if event.get('is_error') or event.get('status')=='ERROR':raise ValueError('CLI reported an incomplete/error result.')
            answer=event.get('result',event.get('text'));counts=event.get('usage',{});completed=True
            model_usage=event.get('modelUsage',{})
            if not reported and len(model_usage)==1:reported=next(iter(model_usage))
    if not completed or not isinstance(answer,str) or not answer.strip():raise ValueError('CLI did not return a completed text result; no partial response was accepted.')
    usage(log,provider,model,reported,counts.get('input_tokens'),counts.get('output_tokens'),counts.get('total_tokens'))
    return answer


def test_connection(settings,cancel,log):
    """An image-backed smoke test, using synthetic media rather than user video."""
    from .services import run,tool
    with tempfile.TemporaryDirectory(prefix='describer-vision-test-') as tmp:
        video=Path(tmp)/'blue.mp4'
        run([tool('ffmpeg'),'-v','error','-y','-f','lavfi','-i','color=c=blue:s=128x128:d=1',
             '-c:v','libx264','-pix_fmt','yuv420p',str(video)],cancel)
        answer=video_request(video,'Identify the dominant color. Return only JSON {"answer":"color name"}.',settings,cancel,log)
    try:color=json.loads(answer)['answer']
    except (ValueError,TypeError,KeyError):raise ValueError('Image test returned an invalid answer; visual capability remains unverified.') from None
    if not isinstance(color,str) or color.strip().lower()!='blue':
        raise ValueError('Image test did not identify the synthetic blue frame; visual capability remains unverified.')
    return 'Image test passed for '+provider_name(settings)+', requested model '+model_id(settings)+'. Synthetic blue frame recognized; this does not establish narration quality or unreported model identity.'


def video_request(video,prompt,settings,cancel,log,as_json=True):
    from .services import probe
    from .frames import sample
    model_info(settings)
    if cancel.is_set():raise InterruptedError('Cancelled')
    provider=provider_name(settings);model=model_id(settings)
    length=probe(video);interval=max(float(settings.get('ollama_frame_interval',2)),length/8)
    with tempfile.TemporaryDirectory(prefix='describer-subscription-') as tmp:
        root=Path(tmp)
        sampled=sample(video,root,interval,cancel);frames=[path for path,_ in sampled]
        prompt+='\nOnly these sampled frames are supplied, in chronological order at '+', '.join(f'{timestamp:.3f}s' for _,timestamp in sampled)+'. No audio. Do not infer dialogue, sounds or unseen motion.'
        log(f'Sending {len(frames)} sampled images to {provider}, exact model {model}.')
        if provider.endswith(' CLI'):return cli_reply(settings,frames,prompt,cancel,log,root)
        timeout=min(120,max(1,float(settings.get('analysis_timeout',600))))
        if provider=='Anthropic API':
            content=[{'type':'image','source':{'type':'base64','media_type':'image/jpeg','data':base64.b64encode(path.read_bytes()).decode()}} for path in frames]+[{'type':'text','text':prompt}]
            data=api_request('https://api.anthropic.com/v1/messages','',{'model':model,'max_tokens':8192,'messages':[{'role':'user','content':content}]},timeout,{'x-api-key':settings['anthropic_key'],'anthropic-version':'2023-06-01'})
            if data.get('stop_reason')!='end_turn':raise ValueError('Anthropic did not complete the response; try a shorter segment.')
            text=''.join(block.get('text','') for block in data.get('content',[]) if block.get('type')=='text');counts=data.get('usage',{})
            usage(log,provider,model,data.get('model'),counts.get('input_tokens'),counts.get('output_tokens'))
        else:
            info=connection(settings)
            content=[{'type':'image_url','image_url':{'url':'data:image/jpeg;base64,'+base64.b64encode(path.read_bytes()).decode()}} for path in frames]+[{'type':'text','text':prompt}]
            payload={'model':model,'messages':[{'role':'user','content':content}],'stream':False}
            if settings.get('analysis_effort'):payload['reasoning_effort']=settings['analysis_effort']
            data=api_request(info['url']+'/chat/completions',info['key'],payload,timeout)
            choices=data.get('choices',[])
            if not choices or choices[0].get('finish_reason')!='stop':raise ValueError('Selected provider did not complete the response; no partial result was accepted.')
            text=choices[0].get('message',{}).get('content');counts=data.get('usage',{})
            usage(log,provider,model,data.get('model'),counts.get('prompt_tokens'),counts.get('completion_tokens'),counts.get('total_tokens'))
        if cancel.is_set():raise InterruptedError('Cancelled')
        if not isinstance(text,str) or not text.strip():raise ValueError('Selected provider returned no text.')
        return text
