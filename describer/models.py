"""Ollama discovery and vision requests. No sign-in, downloads or fallback on selection."""
import base64
import http.client
import ipaddress
import json
import time
import urllib.error
import urllib.parse
import urllib.request


def endpoint(settings):
    value=settings.get('ollama_url','http://127.0.0.1:11434').strip().rstrip('/')
    url=urllib.parse.urlsplit(value)
    if url.scheme not in ('http','https') or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ValueError('Ollama address must be an HTTP or HTTPS server URL without credentials, query or fragment.')
    if url.path not in ('','/'):
        raise ValueError('Use the Ollama server root address, without /api or /v1.')
    if url.scheme=='http' and not is_loopback(value):
        raise ValueError('Use HTTPS for a remote Ollama server.')
    return value


def is_loopback(value):
    host=urllib.parse.urlsplit(value).hostname
    if host=='localhost':return True
    try:return ipaddress.ip_address(host).is_loopback
    except ValueError:return False


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


def open_request(settings,path,payload=None,timeout=10):
    headers={'Content-Type':'application/json','Accept':'application/json'}
    key=settings.get('ollama_key','')
    if key:headers['Authorization']='Bearer '+key
    request=urllib.request.Request(endpoint(settings)+path,
        data=json.dumps(payload).encode() if payload is not None else None,headers=headers)
    try:
        return urllib.request.build_opener(NoRedirect()).open(request,timeout=timeout)
    except urllib.error.HTTPError as exc:
        # Never include a provider's raw body, which can echo credentials or media.
        hint={401:'Check Ollama sign-in or the server API key.',403:'Check Ollama sign-in or account access.',
              404:'The selected model or endpoint was not found. Open Settings > Keys & privacy to check the server address, then Draft > Refresh models. Install your chosen vision model in Ollama if it is absent.',429:'Ollama usage limit reached; try later.'}.get(exc.code,'Check the Ollama server status.')
        raise RuntimeError(f'Ollama HTTP {exc.code}. {hint}') from None
    except urllib.error.URLError:
        # urllib wraps only failures before the request was sent: refused,
        # no route, name lookup or connect timeout.
        raise RuntimeError(unreachable(settings)) from None
    except (OSError,http.client.HTTPException):
        # The server took the request, then dropped, reset or timed out.
        raise Unfinished(unfinished(settings)) from None


class Unfinished(RuntimeError):
    """Ollama accepted a request but did not finish it."""


HEADLESS_HINT=('In the app, use Settings > Keys & privacy and Draft > Refresh models. '
               'Headless: pass ollama_url in the settings file, then run "describer models" (CLI) or POST /models (REST).')


def unreachable(settings):
    return (f'Could not reach Ollama at {endpoint(settings)}. Start the Ollama application/server. '
            'If it is not installed, use https://ollama.com/download. '+HEADLESS_HINT+' No model is downloaded automatically.')


def unfinished(settings):
    return (f'Ollama at {endpoint(settings)} accepted the request but did not finish it (the model may still be loading). '
            'Check the Ollama server log and retry. '+HEADLESS_HINT)


def json_request(settings,path,payload=None):
    with open_request(settings,path,payload) as response:return json.load(response)


def discover(settings,cancel,log):
    tags=json_request(settings,'/api/tags');rows=[]
    loaded={row.get('name') for row in json_request(settings,'/api/ps').get('models',[])}
    for row in tags.get('models',[]):
        if cancel.is_set():raise InterruptedError('Cancelled.')
        if not isinstance(row,dict):continue
        name=row.get('name')
        if not isinstance(name,str) or not name:continue
        caps=row.get('capabilities')
        error=None
        info={}
        try:
            info=json_request(settings,'/api/show',{'model':name})
            if not isinstance(info,dict):raise ValueError('Invalid model metadata')
            if not isinstance(caps,list):caps=info.get('capabilities')
        except (OSError,RuntimeError,ValueError):
            info={};error='Model details unavailable; supplied catalog fields retained. Retry before analysis.'
        details=dict(row.get('details') or {}) if isinstance(row.get('details'),dict) else {}
        if isinstance(info.get('details'),dict):details.update(info['details'])
        metadata=info.get('model_info',{})
        metadata=metadata if isinstance(metadata,dict) else {}
        architecture=metadata.get('general.architecture')
        context=metadata.get(str(architecture)+'.context_length')
        if context is None:
            contexts=[value for key,value in metadata.items() if key.endswith('.context_length')]
            if len(contexts)==1:context=contexts[0]
        def number(value):return value if isinstance(value,int) and not isinstance(value,bool) and value>0 else None
        def text(value):return value if isinstance(value,str) and value.strip() else None
        rows.append({'name':name,'vision':('vision' in caps if isinstance(caps,list) else None), 'error':error,
            'cloud':bool(row.get('remote_host') or info.get('remote_host') or name.endswith('-cloud') or name.endswith(':cloud') or not is_loopback(endpoint(settings))),
            'loaded':name in loaded,'digest':row.get('digest',''), 'family':text(details.get('family')),
            'parameter_size':text(details.get('parameter_size')), 'quantization':text(details.get('quantization_level')),
            'size':number(row.get('size')), 'context_length':number(context)})
    log(f'Ollama reports {len(rows)} models. Discovery makes no generation requests.')
    return sorted(rows,key=lambda r:(r['cloud'],not r['loaded'],r['name']))


def model_info(settings):
    name=settings.get('ollama_model','').strip()
    if not name:raise ValueError('Open Draft > Refresh models, then select or type the exact installed vision model ID. If none is installed, install your chosen vision model using Ollama first.')
    info=json_request(settings,'/api/show',{'model':name})
    if 'vision' not in info.get('capabilities',[]):
        raise ValueError(f'{name} does not report vision support. Open Draft > Refresh models and select an installed vision model for video analysis. Your current selection has not been changed.')
    return info


def is_cloud(settings,info):
    name=settings.get('ollama_model','')
    return bool(info.get('remote_host') or info.get('remote_model') or name.endswith('-cloud') or name.endswith(':cloud') or not is_loopback(endpoint(settings)))


def chat(settings,messages,cancel,log,as_json=True):
    if cancel.is_set():raise InterruptedError('Cancelled.')
    model=settings['ollama_model'];deadline=time.monotonic()+settings.get('ollama_timeout',600)
    payload={'model':model,'messages':messages,'stream':True,
             'options':{'temperature':settings.get('temperature',.3),'num_predict':8192}}
    matched_profile=model in ('gemma4:12b','gemma4:26b','qwen3.8:27b-q6_K-vision')
    if matched_profile:
        # Reserve context for images, the prompt, thinking and the final JSON.
        payload['options'].update(num_predict=32768,num_ctx=65536)
        # The UI temperature belongs to Gemini; preserve this tag's sampling defaults.
        payload['options'].pop('temperature')
        payload['think']=False
    log(f'Ollama response budget: {payload["options"]["num_predict"]} tokens'
        +(f'; context: {payload["options"]["num_ctx"]} tokens; thinking off.' if matched_profile else '.'))
    # Hosted Ollama models do not support the structured-output parameter.
    # The prompt still requests JSON and the caller validates the reply.
    if as_json and not is_cloud(settings,settings.get('_ollama_info',{})):payload['format']='json'
    # Scott's exact 1017 policy; leave every other model's thinking default alone.
    if model.startswith('deepseek-v4.1-flash:1017'):payload['think']='low'
    def stream():
        parts=[];done=None;size=0;thinking_chars=0;last_progress=time.monotonic()
        with open_request(settings,'/api/chat',payload,timeout=min(120,settings.get('ollama_timeout',600))) as response:
            lines=iter(response)
            while True:
                try:line=next(lines)
                except StopIteration:break
                except (OSError,http.client.HTTPException):raise Unfinished(unfinished(settings)) from None
                if cancel.is_set():raise InterruptedError('Cancelled; no more requests will be sent.')
                if time.monotonic()>deadline:raise TimeoutError('Ollama exceeded the configured request timeout.')
                size+=len(line)
                if size>4*1024*1024:raise ValueError('Ollama response exceeded the size limit.')
                if not line.strip():continue
                event=json.loads(line)
                if event.get('error'):raise RuntimeError('Ollama rejected the request. Check model access and the server log.')
                parts.append(event.get('message',{}).get('content',''))
                thinking_chars+=len(event.get('message',{}).get('thinking',''))
                if time.monotonic()-last_progress>=15:
                    log(f'Ollama is generating: {thinking_chars} thinking characters; {sum(map(len,parts))} answer characters received.')
                    last_progress=time.monotonic()
                if event.get('done'):done=event;break
        return parts,done
    try:parts,done=stream()
    except Unfinished:
        # A cold start can outlast the read timeout (DW-1). Wait for the model
        # to load with an empty-prompt warm-up, then retry once.
        if cancel.is_set():raise InterruptedError('Cancelled.')
        log('Ollama accepted the request but did not finish it. Waiting for the model to load, then retrying once.')
        with open_request(settings,'/api/generate',{'model':model,'prompt':'','keep_alive':'10m','stream':False},
                          timeout=settings.get('ollama_timeout',600)) as response:response.read()
        parts,done=stream()
    if cancel.is_set():raise InterruptedError('Cancelled.')
    if not done:raise RuntimeError('Ollama stream ended without a completed response.')
    if done.get('done_reason')=='length':raise ValueError(f'Ollama output was cut off at the {payload["options"]["num_predict"]}-token response budget. Existing descriptions are preserved.')
    text=''.join(parts).strip()
    if not text:raise ValueError('Ollama returned no description text.')
    log(f'Ollama requested {model}; reported {done.get("model","not reported")}. '
        f'Tokens: input {done.get("prompt_eval_count","unknown")}, output {done.get("eval_count","unknown")}.')
    from .engine.progress import usage
    usage(log,'Ollama',model,done.get('model'),done.get('prompt_eval_count'),done.get('eval_count'))
    return text


def test_connection(settings,cancel,log):
    settings=dict(settings,_ollama_info=model_info(settings))
    answer=chat(settings,[{'role':'user','content':'Reply with one short sentence confirming you can answer.'}],cancel,log,False)
    return 'Connection answered: '+answer[:300]+'. Text connection tested; visual accuracy requires a video test.'


VISION_QUESTION='Read all text in this image exactly, and name the colour of the shape. Reply in one short sentence.'


def vision_check(settings,cancel,log,cache=None):
    """Refuse a model that cannot read a known image (DW-12).

    The built-in image shows the text "CIVIC 42" and a red circle. The result
    is cached per model digest, so each installed model is tested once.
    """
    from pathlib import Path
    from .services import asset_path
    name=settings['ollama_model']
    info=model_info(settings)
    tags=json_request(settings,'/api/tags').get('models',[])
    digest=next((r.get('digest') for r in tags if r.get('name') in (name,name+':latest')),None) or 'unknown'
    key=f'{name}@{digest}'
    store={}
    if cache and Path(cache).is_file():
        try:store=json.loads(Path(cache).read_text('utf-8'))
        except (OSError,ValueError):store={}
    result=store.get(key) if digest!='unknown' else None
    if result is None:
        log(f'Checking that {name} can read a test image before the job starts…')
        image=base64.b64encode(asset_path('vision-check.png').read_bytes()).decode('ascii')
        answer=chat(dict(settings,_ollama_info=info),[{'role':'user','content':VISION_QUESTION,'images':[image]}],cancel,log,False)
        text=answer.casefold()
        result={'passed':'civic' in text and '42' in text and 'red' in text,'answer':answer[:300]}
        if cache and digest!='unknown':
            store[key]=result
            Path(cache).parent.mkdir(parents=True,exist_ok=True)
            Path(cache).write_text(json.dumps(store,indent=2),'utf-8')
    if not result.get('passed'):
        raise ValueError(f'Model {name} failed the vision check (could not read a test image). Choose a vision-capable model.')
    log(f'{name} passed the vision check.')


def video_request(video,prompt,settings,cancel,log,as_json=True,gate=None):
    from .services import probe
    from .frames import sample
    import tempfile
    settings=dict(settings,_ollama_info=model_info(settings))
    duration=probe(video);interval=float(settings.get('ollama_frame_interval',2))
    # Bound each request, including long scene windows, while sampling the entire clip.
    interval=max(interval,duration/8)
    messages=[]
    with tempfile.TemporaryDirectory(prefix='describer-frames-') as tmp:
        frames=sample(video,tmp,interval,cancel)
        if gate:
            sampled=len(frames);frames=gate(frames,cancel)
            if not frames:
                # Public meeting mode: nothing changed, so the model is not asked.
                log(f'No visible change in {sampled} frames; the model was not asked.')
                return {'descriptions':[],'timestamp_reference':'clip','no_change':True}
            if len(frames)<sampled:log(f'Sending {len(frames)} of {sampled} frames; the others show no visible change.')
        for frame,timestamp in frames:
            messages.append({'role':'user','content':f'Video frame at {timestamp:.3f} seconds in this clip.',
                'images':[base64.b64encode(frame.read_bytes()).decode('ascii')]})
        messages.append({'role':'user','content':prompt+'\nThese are sampled frames in chronological order, not continuous video. '
            'No audio is supplied. Do not claim to hear dialogue or sounds, or identify dialogue gaps. '
            'Describe only visible evidence; do not guess action between frames.'})
        log(f'Sending {len(frames)} timestamped frames to {settings["ollama_model"]}. No audio is sent.')
        return chat(settings,messages,cancel,log,as_json)
