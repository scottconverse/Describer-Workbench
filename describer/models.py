"""Ollama discovery and vision requests. No sign-in, downloads or fallback on selection."""
import base64
import ipaddress
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


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
              404:'Check the server address and installed model.',429:'Ollama usage limit reached; try later.'}.get(exc.code,'Check the Ollama server status.')
        raise RuntimeError(f'Ollama HTTP {exc.code}. {hint}') from None
    except (urllib.error.URLError,TimeoutError,OSError) as exc:
        raise RuntimeError('Could not reach Ollama. Start its server and check the address and timeout.') from None


def json_request(settings,path,payload=None):
    with open_request(settings,path,payload) as response:return json.load(response)


def discover(settings,cancel,log):
    tags=json_request(settings,'/api/tags');rows=[]
    loaded={row.get('name') for row in json_request(settings,'/api/ps').get('models',[])}
    for row in tags.get('models',[]):
        if cancel.is_set():raise InterruptedError('Cancelled.')
        name=row.get('name')
        if not isinstance(name,str) or not name:continue
        caps=row.get('capabilities')
        if not isinstance(caps,list):
            caps=json_request(settings,'/api/show',{'model':name}).get('capabilities',[])
        rows.append({'name':name,'vision':'vision' in caps,
            'cloud':bool(row.get('remote_host') or name.endswith('-cloud') or name.endswith(':cloud') or not is_loopback(endpoint(settings))),
            'loaded':name in loaded,'digest':row.get('digest','')})
    log(f'Ollama reports {len(rows)} models. Discovery makes no generation requests.')
    return sorted(rows,key=lambda r:(r['cloud'],not r['loaded'],r['name']))


def model_info(settings):
    name=settings.get('ollama_model','').strip()
    if not name:raise ValueError('Choose an Ollama model and refresh the model list first.')
    info=json_request(settings,'/api/show',{'model':name})
    if 'vision' not in info.get('capabilities',[]):
        raise ValueError(f'{name} does not report vision support. Choose a vision model for video analysis.')
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
    parts=[];done=None;size=0;thinking_chars=0;last_progress=time.monotonic()
    with open_request(settings,'/api/chat',payload,timeout=min(120,settings.get('ollama_timeout',600))) as response:
        for line in response:
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
    if cancel.is_set():raise InterruptedError('Cancelled.')
    if not done:raise RuntimeError('Ollama stream ended without a completed response.')
    if done.get('done_reason')=='length':raise ValueError(f'Ollama output was cut off at the {payload["options"]["num_predict"]}-token response budget. Existing descriptions are preserved.')
    text=''.join(parts).strip()
    if not text:raise ValueError('Ollama returned no description text.')
    log(f'Ollama requested {model}; reported {done.get("model","not reported")}. '
        f'Tokens: input {done.get("prompt_eval_count","unknown")}, output {done.get("eval_count","unknown")}.')
    return text


def test_connection(settings,cancel,log):
    settings=dict(settings,_ollama_info=model_info(settings))
    answer=chat(settings,[{'role':'user','content':'Reply with one short sentence confirming you can answer.'}],cancel,log,False)
    return 'Connection answered: '+answer[:300]+'. Text connection tested; visual accuracy requires a video test.'


def video_request(video,prompt,settings,cancel,log,as_json=True):
    from .services import probe,run,tool
    import tempfile
    settings=dict(settings,_ollama_info=model_info(settings))
    duration=probe(video);interval=float(settings.get('ollama_frame_interval',2))
    # Bound each request, including long scene windows, while sampling the entire clip.
    interval=max(interval,duration/8)
    messages=[]
    with tempfile.TemporaryDirectory(prefix='describer-frames-') as tmp:
        run([tool('ffmpeg'),'-v','error','-y','-i',str(video),'-vf',
             f'fps=1/{interval}:start_time=0,scale=640:-2','-frames:v','8','-q:v','3',str(Path(tmp)/'%03d.jpg')],cancel)
        frames=sorted(Path(tmp).glob('*.jpg'))
        if not frames:raise ValueError('Could not extract video frames.')
        for i,frame in enumerate(frames):
            messages.append({'role':'user','content':f'Video frame at {min(i*interval,duration):.2f} seconds in this clip.',
                'images':[base64.b64encode(frame.read_bytes()).decode('ascii')]})
        messages.append({'role':'user','content':prompt+'\nThese are sampled frames in chronological order, not continuous video. '
            'No audio is supplied. Do not claim to hear dialogue or sounds, or identify dialogue gaps. '
            'Describe only visible evidence; do not guess action between frames.'})
        log(f'Sending {len(frames)} timestamped frames to {settings["ollama_model"]}. No audio is sent.')
        return chat(settings,messages,cancel,log,as_json)
