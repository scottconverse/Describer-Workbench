"""Media, speech and cloud adapters. Cloud work runs only on explicit UI actions."""
import base64
import ctypes
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from .project import response_json, normalize_generated
from .catalogue import PROMPTS,VOICE_PRESETS
from .platforms import data_directory,native_engine,speech_label

CREATE_NO_WINDOW = 0x08000000 if os.name == 'nt' else 0


def asset_path(name):
    root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1])) / 'assets'
    return (root if root.is_dir() else Path(__file__).resolve().parent / 'resources') / name


def tool(name):
    bundled = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1])) / 'bin' / (name + ('.exe' if os.name=='nt' else ''))
    found = str(bundled) if bundled.exists() else shutil.which(name)
    if not found and sys.platform=='darwin':
        found=next((str(p) for p in (Path('/opt/homebrew/bin')/name,Path('/usr/local/bin')/name) if p.is_file()),None)
    if not found:
        raise RuntimeError(f'{name} was not found. Install FFmpeg or put it on PATH.')
    return found


def run(args, cancel=None, *, return_stderr=False):
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        options={}
        if os.name!='nt':
            from .platforms import external_environment
            options['env']=external_environment()
        p = subprocess.Popen(args, stdout=out, stderr=err, creationflags=CREATE_NO_WINDOW,**options)
        while p.poll() is None:
            if cancel and cancel.wait(.1):
                p.terminate()
                try: p.wait(timeout=5)
                except subprocess.TimeoutExpired: p.kill(); p.wait()
                raise InterruptedError('Operation cancelled.')
            if not cancel: time.sleep(.1)
        out.seek(0); err.seek(0)
        output, error = out.read(), err.read()
        if p.returncode:
            raise RuntimeError(error.decode(errors='replace')[-3000:])
        return error if return_stderr else output


def probe(path):
    j = json.loads(run([tool('ffprobe'), '-v', 'error', '-show_format', '-show_streams', '-of', 'json', str(path)]))
    if not any(s['codec_type'] == 'video' for s in j['streams']):
        raise ValueError('The selected file has no video stream.')
    return float(j['format']['duration'])


def scale_filter(max_side=640):
    if max_side==640:return 'scale=640:-2'
    # Keep the source size, but cap the long side; never upscale (F4).
    return (f"scale='min({max_side},iw)':'min({max_side},ih)'"
            ':force_original_aspect_ratio=decrease:force_divisible_by=2')


def segment(source, output, start, duration, fps=2, cancel=None, silent=False, max_side=640):
    run([tool('ffmpeg'), '-v', 'error', '-y', '-ss', str(start), '-i', str(source), '-t', str(duration),
         '-vf', f'{scale_filter(max_side)},fps={fps}', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '28' if max_side==640 else '20',
         *(['-an'] if silent else ['-c:a', 'aac', '-b:a', '64k']), str(output)], cancel)


def dpapi(data, decrypt=False):
    if os.name != 'nt':
        from .platforms import keyring_secret
        return keyring_secret(data,decrypt)
    from ctypes import wintypes
    class Blob(ctypes.Structure):
        _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]
    buf = ctypes.create_string_buffer(data)
    src = Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_ubyte))); dst = Blob()
    fn = ctypes.windll.crypt32.CryptUnprotectData if decrypt else ctypes.windll.crypt32.CryptProtectData
    if not fn(ctypes.byref(src), None, None, None, None, 1, ctypes.byref(dst)):
        raise ctypes.WinError()
    try: return ctypes.string_at(dst.data, dst.size)
    finally: ctypes.windll.kernel32.LocalFree(dst.data)


DEFAULTS = {'ui_theme':'light','recent_projects':[], 'model': 'gemini-2.5-flash', 'language': 'English', 'chunk': 300, 'fps': 2,
            'sound_model':'', 'max_speech_speed':1.15, 'allow_cloud':False, 'captions':'',
            'analysis_provider':'Gemini','ollama_url':'http://127.0.0.1:11434','ollama_model':'',
            'provider_models':{},'connections':{},'connection_id':'','gateway_url':'http://127.0.0.1:8317/v1','gateway_key_file':'',
            'cli_paths':{},'analysis_timeout':600,'analysis_effort':'','anthropic_key':'',
            'codex_cli':'','claude_cli':'','gemini_cli':'',
            'ollama_key':'','ollama_timeout':600,'ollama_frame_interval':2,'drafting_mode':'','max_pause_seconds_per_minute':8,
            'voice_engine': native_engine(), 'voice': 'alloy', 'tts_model': 'gpt-4o-mini-tts',
            'voice_presets': VOICE_PRESETS, 'settings_version': 3,
            'voice_preset': '', 'voice_speed': 1.0, 'voice_instructions': '', 'windows_voice': '', 'speech_rate': 0,
            'playback_voice': '', 'sounds': True, 'ui_language': 'English', 'auto_glossary': True,
            'silent_upload': False, 'safety_block_none': False, 'temperature': 0.3, 'update_feed': '', 'auto_update_check': False,
            'logging_level':'INFO','chunking': True, 'verbosity': 'Standard', 'download_quality': 'Best', 'player_volume': 80, 'speech_volume': 100,
            'playback_output': speech_label(), 'duck_db': -15, 'interrupt': True, 'presets': {'English': {'Standard': '', **PROMPTS}}, 'gemini_key': '', 'openai_key': ''}


class Settings:
    def __init__(self, path=None):
        self.path = Path(path) if path else data_directory() / 'settings.json'
        self.data = json.loads(json.dumps(DEFAULTS))
        self._protected_cache={}
        self.load_warning='';self.needs_recovery=False
        if self.path.exists():
            try:
                j=json.loads(self.path.read_text(encoding='utf-8-sig'))
                if not isinstance(j,dict):raise ValueError('Expected a settings object.')
                for k in [key for key in j if key.endswith('_key')]:
                    if j.get(k):
                        try:
                            protected=j[k];j[k]=dpapi(base64.b64decode(protected),True).decode()
                            self._protected_cache[k]=(j[k],protected)
                        except Exception:
                            j[k]='';self.load_warning='A saved API key could not be unlocked. Re-enter it in Settings.';self.needs_recovery=True
                for key,default in DEFAULTS.items():
                    if key not in j:continue
                    value=j[key]
                    if isinstance(default,bool) and not isinstance(value,bool):raise ValueError('Invalid switch.')
                    if isinstance(default,(int,float)) and not isinstance(default,bool):
                        if isinstance(value,bool) or not isinstance(value,(int,float)) or not __import__('math').isfinite(value):raise ValueError('Invalid number.')
                    elif isinstance(default,str) and not isinstance(value,str):raise ValueError('Invalid text.')
                    elif isinstance(default,list) and (not isinstance(value,list) or not all(isinstance(x,str) for x in value)):raise ValueError('Invalid recent projects.')
                    elif isinstance(default,dict) and not isinstance(value,dict):raise ValueError('Invalid presets.')
                    self.data[key]=value
                if not all(isinstance(v,dict) and all(isinstance(k,str) and isinstance(t,str) for k,t in v.items()) for v in self.data['presets'].values()):raise ValueError('Invalid prompt presets.')
                for preset in self.data['voice_presets'].values():
                    if not isinstance(preset,dict) or not isinstance(preset.get('base_voice'),str) or not .25<=float(preset.get('speed',1))<=4:raise ValueError('Invalid voice preset.')
                ranges={'chunk':(15,1800),'fps':(1,30),'duck_db':(-40,0),'speech_rate':(-10,10),'player_volume':(0,100),'speech_volume':(0,100),'temperature':(0,2),'ollama_timeout':(30,1800),'ollama_frame_interval':(1,10)}
                for key,(low,high) in ranges.items():self.data[key]=max(low,min(high,self.data[key]))
                from .providers import provider_name
                provider_name(self.data)
                validate_connection_settings(self.data)
                self.data.update({key:value for key,value in j.items() if key.endswith('_key') and isinstance(value,str)})
                if j.get('settings_version',0)<3:
                    for name,prompt in PROMPTS.items():self.data['presets'].setdefault('English',{}).setdefault(name,prompt)
                    for name,preset in VOICE_PRESETS.items():self.data['voice_presets'].setdefault(name,dict(preset))
                self.data['settings_version']=3
            except Exception:
                self.data=json.loads(json.dumps(DEFAULTS));self.load_warning='Settings are damaged or incompatible. Defaults loaded; the existing file is preserved and will be backed up before saving.';self.needs_recovery=True

    def save(self):
        if self.needs_recovery and self.path.exists():
            shutil.copy2(self.path,self.path.with_name(self.path.name+'.recovery-'+str(time.time_ns())))
            self.needs_recovery=False
        j = dict(self.data)
        for k in [key for key in j if key.endswith('_key')]:
            if j[k]:
                cached=self._protected_cache.get(k)
                if os.name!='nt' and cached and cached[0]==j[k]:j[k]=cached[1]
                else:
                    plain=j[k];j[k]=base64.b64encode(dpapi(plain.encode())).decode()
                    self._protected_cache[k]=(plain,j[k])
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix('.tmp');temp.write_text(json.dumps(j, indent=2), encoding='utf-8');temp.replace(self.path)


def validate_connection_settings(settings):
    """Validate persisted nested choices without contacting providers or reading keys."""
    from .providers import PROVIDERS
    for provider,model in settings['provider_models'].items():
        if provider not in PROVIDERS or not isinstance(model,str):raise ValueError('Invalid provider model.')
    for provider,path in settings['cli_paths'].items():
        if provider not in ('Codex CLI','Claude CLI','Gemini CLI') or not isinstance(path,str):raise ValueError('Invalid CLI path.')
    for ident,entry in settings['connections'].items():
        if not ident or not isinstance(entry,dict):raise ValueError('Invalid connection entry.')
        for field in ('url','credential'):
            if not isinstance(entry.get(field),str) or not entry[field].strip():raise ValueError('Invalid connection '+field+'.')
        if not isinstance(entry.get('name',''),str):raise ValueError('Invalid connection name.')
        if not entry['credential'].endswith('_key'):raise ValueError('Invalid connection credential reference.')
        if not isinstance(entry.get('enabled',True),bool) or not isinstance(entry.get('model',''),str):raise ValueError('Invalid connection choices.')
    if settings['connection_id'] and settings['connection_id'] not in settings['connections']:raise ValueError('Selected connection is missing.')
    choices={'voice_engine':('Windows','Windows 32-bit','Windows OneCore','macOS','eSpeak NG','OpenAI'),
             'playback_output':('Windows speech','System speech','Screen reader'), 'analysis_effort':('','low','medium','high','xhigh','max'),
             'drafting_mode':('','Public meeting')}
    for field,values in choices.items():
        if settings[field] not in values:raise ValueError('Invalid '+field+'.')


class IncompleteResponse(ValueError):
    """Recoverable text for inspection only; never a completed model result."""
    def __init__(self, message, partial_text):
        super().__init__(message)
        self.partial_text=partial_text[:8*1024*1024] if isinstance(partial_text,str) else ''
        self.context={}


def completed_google_text(response):
    """Never treat parseable partial output as a completed observation."""
    def reason(value):
        return str(getattr(value, 'name', value) or '').rsplit('.', 1)[-1]
    feedback = getattr(response, 'prompt_feedback', None)
    block = reason(getattr(feedback, 'block_reason', None))
    if block not in ('', '0', 'BLOCK_REASON_UNSPECIFIED'):
        raise ValueError('Gemini blocked the request (' + block + '). Review the provider feedback and selected media; no complete result was accepted.')
    candidates = getattr(response, 'candidates', None)
    if not candidates:
        raise ValueError('Gemini returned no candidates. Review provider feedback or try a shorter segment.')
    finish = reason(getattr(candidates[0], 'finish_reason', None))
    if finish == 'MAX_TOKENS':
        raise IncompleteResponse('Gemini output was cut off (MAX_TOKENS). Use shorter chunks; partial output was not accepted as complete.',response.text)
    if finish != 'STOP':
        raise ValueError('Gemini did not complete the response (' + (finish or 'unknown finish reason') + '). Review provider feedback or try a shorter segment.')
    text = response.text
    if not isinstance(text, str) or not text.strip():
        raise ValueError('Gemini returned no text. Review provider feedback or try a shorter segment.')
    return text


def google_request(video, prompt, settings, cancel, log, as_json=True):
    from google import genai
    from google.genai import types
    if not settings['gemini_key']: raise ValueError('Enter a Gemini API key in Settings first.')
    client = genai.Client(api_key=settings['gemini_key'], http_options=types.HttpOptions(timeout=120000))
    uploaded = None
    try:
        log('Uploading the selected video segment to Google Gemini…')
        uploaded = client.files.upload(file=str(video))
        deadline = time.monotonic() + 300
        while uploaded.state.name == 'PROCESSING':
            if cancel.wait(2): raise InterruptedError('Cancelled.')
            if time.monotonic() > deadline: raise TimeoutError('Video preparation timed out.')
            uploaded = client.files.get(name=uploaded.name)
        if uploaded.state.name != 'ACTIVE': raise RuntimeError('Google could not prepare the video.')
        for attempt in range(4):
            if cancel.is_set(): raise InterruptedError('Cancelled.')
            try:
                response = client.models.generate_content(model=settings['model'], contents=[uploaded, prompt],
                    config=types.GenerateContentConfig(response_mime_type='application/json' if as_json else 'text/plain',
                        temperature=float(settings.get('temperature', .3)),
                        safety_settings=([types.SafetySetting(category=c, threshold='BLOCK_NONE') for c in
                          ['HARM_CATEGORY_HARASSMENT','HARM_CATEGORY_HATE_SPEECH','HARM_CATEGORY_SEXUALLY_EXPLICIT','HARM_CATEGORY_DANGEROUS_CONTENT']]
                          if settings.get('safety_block_none') else None)))
                log('Token usage: ' + str(response.usage_metadata))
                from .engine.progress import usage
                meta=response.usage_metadata
                usage(log,'Gemini',settings['model'],getattr(response,'model_version',None),
                      getattr(meta,'prompt_token_count',None),getattr(meta,'candidates_token_count',None),getattr(meta,'total_token_count',None))
                return completed_google_text(response)
            except Exception as e:
                if getattr(e, 'code', None) not in [429, 500, 502, 503] or attempt == 3: raise
                if cancel.wait(2 ** (attempt + 1)): raise InterruptedError('Cancelled.')
    finally:
        if uploaded:
            try: client.files.delete(name=uploaded.name)
            except Exception: log('Could not delete uploaded file; Google file retention policy applies.')
        client.close()


def video_request(video,prompt,settings,cancel,log,as_json=True,gate=None):
    from .providers import provider_name
    provider=provider_name(settings)
    if provider=='Ollama':
        from .models import video_request as ollama_request
        return ollama_request(video,prompt,settings,cancel,log,as_json,gate=gate)
    if provider=='Gemini':return google_request(video,prompt,settings,cancel,log,as_json)
    from .subscriptions import video_request as subscription_request
    return subscription_request(video,prompt,settings,cancel,log,as_json)


class RejectedChunk(ValueError):
    """The model replied, but the reply is not a usable chunk; worth a retry."""


def vote_pass(project,settings,w0,wl,lines,labels,count,cancel,log,clip,checkpoint=None):
    """F3: ask who raises a hand around a vote line, one frame per second.

    A failed pass is logged and skipped; it never fails the job.
    """
    from . import meeting
    from .project import normalize_chunk, speakable
    log(f'Public meeting mode: vote words at {w0:.0f} s; checking for raised hands.')
    segment(project.video,clip,w0,wl,settings['fps'],cancel,settings.get('silent_upload',False),max_side=meeting.frame_side(settings))
    ask=lambda:response_json(video_request(clip,meeting.vote_instruction(lines,wl),dict(settings,ollama_frame_interval=1),cancel,log))
    def validate(data):
        try:normalize_chunk(data,0,wl)
        except ValueError as exc:raise RejectedChunk(str(exc)) from exc
    try:
        data=checkpoint(f'vote-{w0:.6f}',ask,validate) if checkpoint else ask()
        validate(data)
        rows=normalize_chunk(data,0,wl,log)
    except (ValueError,TypeError,IncompleteResponse) as exc:
        log(f'Vote check at {w0:.0f} s failed; no vote cue added. {exc}')
        return []
    out=[]
    for cue in rows:
        cue.kind='vote'
        cue.text,_=speakable(cue.text,labels)
        cue.short_text,_=speakable(cue.short_text,labels)
        cue.start+=w0;cue.end+=w0;cue.event_start+=w0;cue.event_end+=w0
        cue.event_id=f'vote-{w0:.6f}:{cue.event_start:.6f}:{cue.event_end:.6f}:{count+len(out)}'
        out.append(cue)
    return out


def check_pass(project,settings,rows,cancel,log,checkpoint=None,dropped=None):
    """Option 1c: show the model one second at the middle of each event and ask if the cue is true.

    A cue the model calls false is dropped and flagged. A failed or unclear check keeps the cue.
    """
    import hashlib, tempfile
    from . import meeting
    from .project import response_json
    out=[];false=0
    with tempfile.TemporaryDirectory(prefix='describer-check-') as tmp:
        clip=Path(tmp)/'check.mp4'
        for n,row in enumerate(rows):
            if cancel.is_set():raise InterruptedError('Cancelled.')
            # A vote is a motion (hands go up, then down). One second of video can miss it,
            # and the vote check already looked at the clip. So a vote cue is not checked again.
            if row.get('kind')=='vote':
                out.append(row);continue
            mid=(row.get('event_start',row['start'])+row.get('event_end',row['end']))/2
            at=max(0.0,mid-0.5)
            try:
                segment(project.video,clip,at,1.0,settings['fps'],cancel,settings.get('silent_upload',False),max_side=meeting.frame_side(settings))
                ask=lambda:response_json(video_request(clip,meeting.check_instruction(row['text']),dict(settings,ollama_frame_interval=1),cancel,log))
                data=checkpoint(f'check-{n:05}-{at:.3f}-{hashlib.sha1(row["text"].encode()).hexdigest()[:8]}',ask) if checkpoint else ask()
                verdict=meeting.check_verdict(data)
            except InterruptedError:
                raise
            except Exception as exc:
                log(f'Check at {mid:.0f} s failed; the cue is kept. {exc}')
                verdict=None
            if verdict is False and not row.get('manually_edited'):
                false+=1
                if dropped is not None:
                    dropped.append({'start':row.get('event_start',row['start']),'end':row.get('event_end',row['end']),
                        'reason':'Not true: on a second look, the model said the description did not match the frame.'})
                continue
            out.append(row)
    if rows and not out:
        log('The check pass called every description not true; all are kept for review.')
        if dropped is not None:del dropped[len(dropped)-false:]
        return rows
    if false:log(f'Public meeting mode: the check pass dropped {false} descriptions that were not true.')
    return out


def observe(project, settings, prompt, cancel, log, start_at=0, duration=None, checkpoint=None):
    cues=[];glossary=project.glossary;failed=[];unchanged=[]
    from .project import glossary_labels, speakable
    from . import meeting
    labels=glossary_labels(glossary)
    meeting_mode=meeting.enabled(settings)
    gate=meeting.ChangeGate() if meeting_mode else None
    if meeting_mode:log('Public meeting mode: only frames with a visible change are described.')
    said=[]
    if meeting_mode and settings.get('captions'):
        from .project import import_subtitles
        said=meeting.transcript(import_subtitles(settings['captions'],project.duration))
        log(f'Public meeting mode: the transcript ({len(said)} lines) is given to the model.')
    chunk=max(15,int(settings['chunk'])) if settings.get('chunking',True) else max(1,__import__('math').ceil(project.duration))
    if settings.get('analysis_provider','Gemini')!='Gemini':
        chunk=min(chunk,8*int(settings.get('ollama_frame_interval',2)))
        log('Vision receives sampled images; the engine independently measures protected audio.')
    stop=min(project.duration,start_at+duration) if duration is not None else project.duration
    from .engine.progress import stage
    total=__import__('math').ceil((stop-start_at)/chunk)
    if total>1 and (stop-start_at)-(total-1)*chunk<4:total-=1
    with tempfile.TemporaryDirectory(prefix='describer-') as tmp:
        start=start_at
        while start<stop:
            stage(log,'observation',round((start-start_at)/chunk),total)
            if cancel.is_set():raise InterruptedError('Cancelled.')
            length=min(chunk, stop-start)
            # Fold a short remainder into this chunk rather than sending a clip
            # too short to describe (DW-13).
            if 0 < stop-start-length < 4: length=stop-start
            if length < .1: break
            log(f'Preparing {start:.0f}–{start+length:.0f} seconds…')
            clip=Path(tmp)/'segment.mp4';segment(project.video, clip, start, length, settings['fps'], cancel, settings.get('silent_upload',False),max_side=meeting.frame_side(settings))
            ollama=settings.get('analysis_provider','Gemini')!='Gemini'
            instruction=(f'Create concise audio descriptions in {settings["language"]}. Describe visible action, people and settings. '
                +('Use visible evidence only. No audio is supplied; do not infer speech, sounds or dialogue gaps. Do not invent facts. ' if ollama else 'Use visible evidence and supplied audio; do not repeat dialogue or invent facts. ')+
                ('Return JSON {"descriptions":[{"start":0.0,"end":2.0,"text":"description","short_text":"main fact in 4 words","kind":"other","evidence":"visible evidence","uncertainty":""}]}. '
                 if meeting_mode else  # the model copies this example, so it shows the meeting fields (F2, F3)
                 'Return JSON {"descriptions":[{"start":0.0,"end":2.0,"text":"description","kind":"action","evidence":"visible evidence","uncertainty":""}]}. ')+
                'Times describe the VISUAL EVENT, not a proposed speech slot. Cover meaningful unspoken printed text, actions, identities and scene changes. '
                'Use objective visible facts. Quote printed text exactly; state uncertainty instead of inventing unreadable words or actions. '
                f'Times are numeric seconds relative to this {length:.2f}-second clip and must fit within it. Set the top-level timestamp_reference field to "clip". '
                f'Prior character glossary: {glossary}\nEditorial guidance: {prompt}')
            if meeting_mode:
                instruction += '\n'+meeting.prior_instruction([c.text for c in cues if c.disposition!='unresolved'])
                instruction += meeting.transcript_instruction(said,start,length)
                instruction += meeting.event_instruction(prompt)
            if settings.get("auto_glossary",False):
                instruction += ' Also return "character_glossary": [{"id":"stable_visual_label","name":null,"description":"visual identity"}]. '+('Keep name=null because no audio is supplied. ' if ollama else 'Use a personal name only if clearly spoken and unambiguously linked; otherwise name=null. ')+'Reuse prior identities; include only visible characters.'
            verbosity={'Short':'Use 1-3 words for each description.','Standard':'Aim for 3-6 words per description.','Detailed':'Aim for 6-12 words per description.'}.get(settings.get('verbosity','Standard'),'')
            instruction += '\n'+verbosity+' Do not omit essential information to meet a timing or verbosity target. The engine schedules narration separately.'+(' Describe visual changes concisely.' if ollama else ' Avoid describing sounds already audible.')
            def request():
                try:return response_json(video_request(clip,instruction,settings,cancel,log,gate=gate))
                except IncompleteResponse as exc:
                    exc.context={'clip_start':start,'clip_duration':length,'timestamp_reference':'clip'}
                    raise
            from .project import normalize_chunk
            def validate(data):
                try:normalize_chunk(data,start,length)
                except ValueError as exc:raise RejectedChunk(str(exc)) from exc
                if settings.get('auto_glossary',False) and isinstance(data,dict) and 'character_glossary' in data:
                    from .compatibility import merge_glossary
                    merge_glossary(glossary,data['character_glossary'])
            if gate:gate.first_kept=None  # a resumed chunk does not call the gate
            attempts=1+max(0,int(settings.get('chunk_retries',2)))
            for attempt in range(attempts):
                try:
                    data=checkpoint(f'observe-{start:.6f}',request,validate) if checkpoint else request()
                    validate(data);break
                except RejectedChunk as exc:
                    if attempt+1<attempts:
                        log(f'Chunk {start:.0f}–{start+length:.0f} s was malformed; retrying ({attempt+1} of {attempts-1}).')
                        continue
                    log(f'Chunk {start:.0f}–{start+length:.0f} s failed after {attempts} tries; recorded as a gap.')
                    failed.append({'start':start,'end':start+length,'error':str(exc)})
                    data=None
            if data is None:
                start+=length;continue
            if settings.get("auto_glossary",False) and isinstance(data,dict) and "character_glossary" in data:
                from .compatibility import merge_glossary
                glossary=merge_glossary(glossary,data["character_glossary"])
            if isinstance(data,dict):labels.update(glossary_labels('',data.get('character_glossary',[])))
            rows=normalize_chunk(data,start,length,log)
            if meeting_mode and not rows:
                unchanged.append({'start':start,'end':start+length,
                    'reason':'No visible change; the model was not asked.' if isinstance(data,dict) and data.get('no_change') else 'The model saw nothing new.'})
            for cue in rows:
                # Models reuse glossary IDs ("man_1") in text; never speak them.
                cue.text,meaningful=speakable(cue.text,labels)
                cue.short_text,_=speakable(cue.short_text,labels)  # the short version is spoken too (F2)
                if not meaningful:
                    cue.disposition='unresolved'
                    cue.uncertainty=cue.uncertainty or 'Only an internal identity label was returned; review this description.'
                first=gate.first_kept if gate else None
                if first is not None and cue.event_start<first:
                    # The model copies the example time 0.0; the event is first seen at this frame.
                    # Keep each length, so a short event is not left with zero length and dropped.
                    shift=first-cue.event_start
                    cue.event_start=first;cue.event_end=min(length,max(cue.event_end,cue.event_end+shift))
                    if cue.event_end<=first:cue.event_end=min(length,first+0.5)
                    if cue.start<first:
                        size=cue.end-cue.start;cue.start=first;cue.end=min(length,max(cue.end,first+size))
                    if cue.end<=cue.start:cue.end=min(length,cue.start+0.5)
                cue.start+=start;cue.end+=start;cue.event_start+=start;cue.event_end+=start
                cue.event_id=f'{start:.6f}:{cue.event_start:.6f}:{cue.event_end:.6f}:{len(cues)}'
                cues.append(cue)
            start+=length
        if meeting_mode:
            for w0,wl,lines in meeting.vote_windows(said,start_at,stop):
                cues+=vote_pass(project,settings,w0,wl,lines,labels,len(cues),cancel,log,Path(tmp)/'vote.mp4',checkpoint)
    stage(log,'observation',total,total)
    from dataclasses import asdict
    rows=[asdict(c) for c in cues]
    if meeting_mode:
        rows=meeting.slide_first(sorted(rows,key=lambda r:r['start']),log,dropped=unchanged)
        rows=meeting.merge_repeats(sorted(rows,key=lambda r:r['start']),log,labels,dropped=unchanged)
        rows=meeting.drop_trivial(rows,log,dropped=unchanged)
        rows=check_pass(project,settings,rows,cancel,log,checkpoint,dropped=unchanged)
        log(f'Public meeting mode: {gate.sent} frames described, {gate.skipped} unchanged frames skipped.')
    cues=normalize_generated(rows,project.duration,log)
    if not cues: raise ValueError('No descriptions were returned.'+(f' {len(failed)} chunks failed: {failed[-1]["error"]}' if failed else ''))
    project.glossary=glossary
    project.analysis['failed_chunks']=failed
    if meeting_mode:project.analysis['no_change_chunks']=unchanged
    return cues


def generate(project, settings, prompt, cancel, log, start_at=0, duration=None):
    """Desktop compatibility entry point; uses the same durable service as adapters."""
    from .engine import get_service
    return get_service().describe(project, settings, prompt, cancel, log, start_at, duration)


def download(url, destination, cancel, log, quality="Best"):
    from urllib.parse import urlparse
    from yt_dlp import YoutubeDL
    u=urlparse(url)
    if u.scheme not in ['http','https'] or not u.netloc: raise ValueError('Enter an HTTP or HTTPS URL.')
    def progress(d):
        if cancel.is_set(): raise InterruptedError('Download cancelled.')
    limit={'360p':360,'480p':480,'720p':720,'1080p':1080}.get(quality)
    selected=f'best[height<={limit}][ext=mp4]/best[height<={limit}]/best' if limit else 'best[ext=mp4]/best'
    with YoutubeDL({'outtmpl':str(Path(destination)/'%(title).100s-%(id)s.%(ext)s'),
                    'format':selected,'noplaylist':True,'quiet':True,'progress_hooks':[progress],
                    'socket_timeout':30, 'ffmpeg_location':str(Path(tool('ffmpeg')).parent)}) as y:
        try:
            info=y.extract_info(url,download=True)
            return y.prepare_filename(info)
        except Exception as exc:
            if cancel.is_set():raise InterruptedError('Download cancelled.') from None
            message=str(exc).lower()
            if any(word in message for word in ('sign in','login','private','authentication','cookies','bot')):
                reason='The provider requires account access or a browser/bot check. This app does not import browser cookies or bypass access checks.'
            elif any(word in message for word in ('javascript','runtime','extractor','unsupported url')):
                reason='The extractor or its runtime could not handle this URL. Check the project release notes for a supported app update.'
            elif any(word in message for word in ('timed out','network','resolve','connection')):
                reason='The provider could not be reached. Check the connection and retry.'
            else:reason='The provider or extractor rejected the download.'
            raise RuntimeError(reason+' Retry Open URL, check Settings > Interface download quality, or use Open video with a local file you can access. Diagnostic category: '+type(exc).__name__) from None


def narration_preflight(settings, cancel=None):
    """Check selected speech prerequisites without paid preview synthesis."""
    if cancel and cancel.is_set():raise InterruptedError('Cancelled')
    engine=settings.get('voice_engine','Windows')
    if engine=='OpenAI':
        if not settings.get('openai_key'):raise ValueError('OpenAI speech needs an API key. Open Settings > Keys & privacy, or select a Windows narration engine.')
        return
    if engine not in ('Windows','Windows 32-bit','Windows OneCore','macOS','eSpeak NG'):raise ValueError('Select a supported narration engine in Settings > Export voice.')
    from .windows_speech import windows_speech
    rows=windows_speech(engine,cancel=cancel,listing=True)
    if not rows:raise ValueError('No voices are installed for '+engine+'. Choose another engine or install a voice in Windows Settings.')
    selected=settings.get('windows_voice','')
    if selected and not any(row.get('id')==selected for row in rows):raise ValueError('The selected narration voice is missing. Select an installed voice in Settings > Export voice.')


def synthesize(text, output, settings, cancel=None):
    if settings['voice_engine']=='OpenAI':
        if not settings['openai_key']: raise ValueError('Enter an OpenAI key in Settings.')
        preset=settings.get('voice_presets',{}).get(settings.get('voice_preset',''),{})
        body={'model':settings['tts_model'],'voice':preset.get('base_voice',settings['voice']),'input':text,'response_format':'wav',
              'speed':float(preset.get('speed',settings.get('voice_speed',1)))}
        instructions=preset.get('instructions',settings.get('voice_instructions',''))
        if instructions and settings['tts_model'].startswith('gpt-4o-mini-tts'): body['instructions']=instructions
        body=json.dumps(body).encode()
        req=urllib.request.Request('https://api.openai.com/v1/audio/speech',data=body,headers={
            'Authorization':'Bearer '+settings['openai_key'],'Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=90) as r: Path(output).write_bytes(r.read())
    else:
        from .windows_speech import windows_speech
        windows_speech(settings['voice_engine'],text,output,settings.get('windows_voice',''),settings.get('speech_rate',0),cancel,volume=settings.get('speech_volume',100))


def _mix_planned_audio(project, output, settings, cancel, log):
    if not project.cues: raise ValueError('Add descriptions first.')
    with tempfile.TemporaryDirectory(prefix='describer-mix-') as tmp:
        tmp=Path(tmp);sources=[];windows=[]
        for i,c in enumerate(project.cues):
            if c.disposition != 'in-gap':continue
            log(f'Synthesizing description {i+1}/{len(project.cues)}…')
            if cancel.is_set(): raise InterruptedError('Cancelled.')
            wav=Path(c.audio)
            if not wav.is_file():raise ValueError('Narration file is missing; re-plan this export.')
            # Bound speech to its allotted window. Faster speech is used when needed.
            j=json.loads(run([tool('ffprobe'),'-v','error','-show_format','-of','json',str(wav)],cancel))
            rate=c.speed;factors=[]
            if float(j['format']['duration']) / rate > c.end-c.start+.025:
                raise ValueError('Narration no longer fits its verified slot; re-plan export.')
            if c.audio_volume is None:raise ValueError('Narration has no recorded synthesis volume; repair narration before export.')
            gain=float(settings.get('speech_volume',100))/c.audio_volume
            factors.extend((f'atempo={rate:.6f}', f'volume={gain:.6f}'))
            timed=tmp/f'timed{i}.wav';run([tool('ffmpeg'),'-v','error','-y','-i',str(wav),'-af',','.join(factors),'-t',str(c.end-c.start),str(timed)],cancel)
            sources.append(timed);windows.append((c.start,c.end))
        audio=tmp/'bed.wav'
        info=json.loads(run([tool('ffprobe'),'-v','error','-show_streams','-of','json',project.video],cancel))
        if any(s['codec_type']=='audio' for s in info['streams']):
            run([tool('ffmpeg'),'-v','error','-y','-i',project.video,'-vn','-ar','44100','-ac','2',str(audio)],cancel)
        else:
            run([tool('ffmpeg'),'-v','error','-y','-f','lavfi','-i','anullsrc=r=44100:cl=stereo','-t',str(project.duration),str(audio)],cancel)
        # Build a gain envelope as an audio stream, avoiding command-line limits and
        # avoiding repeated ducking of narration across batches.
        import wave, struct, math
        envelope=tmp/'gain.wav'; block=1024; sample_rate=1000
        merged=[]
        for start,end in sorted(windows):
            if merged and start<=merged[-1][1]+.1:merged[-1]=(merged[-1][0],max(end,merged[-1][1]))
            else:merged.append((start,end))
        interval=0
        with wave.open(str(envelope),'wb') as w:
            w.setparams((1,2,sample_rate,0,'NONE','not compressed'))
            for frame in range(0,math.ceil(project.duration*sample_rate),block):
                if cancel.is_set():raise InterruptedError('Cancelled.')
                values=[]
                for n in range(frame,min(frame+block,math.ceil(project.duration*sample_rate))):
                    t=n/sample_rate; amount=0.0
                    while interval<len(merged) and t>merged[interval][1]+.05:interval+=1
                    for start,end in merged[interval:interval+1]:
                        # 50 ms smooth fade at each description boundary.
                        amount=max(amount,min(1,max(0,(t-start+.05)/.05),max(0,(end+.05-t)/.05)))
                    values.append(round(32767*(1-amount*(1-10**(float(settings['duck_db'])/20)))))
                w.writeframes(struct.pack('<'+'h'*len(values),*values))
        bed=tmp/'ducked.wav'
        run([tool('ffmpeg'),'-v','error','-y','-i',str(audio),'-i',str(envelope),
             '-filter_complex','[1:a]aresample=44100,pan=stereo|c0=c0|c1=c0[g];[0:a][g]amultiply[m]',
             '-map','[m]',str(bed)],cancel)
        for offset in range(0,len(sources),20):
            args=[tool('ffmpeg'),'-v','error','-y','-i',str(bed)];filters=[];labels=[]
            for k,wav in enumerate(sources[offset:offset+20],1):
                args+=['-i',str(wav)];start,end=windows[offset+k-1]
                filters.append(f'[{k}:a]adelay={round(start*1000)}:all=1[s{k}]');labels.append(f'[s{k}]')
            filters.append('[0:a]'+''.join(labels)+f'amix=inputs={len(labels)+1}:normalize=0:duration=first[m]')
            nextbed=tmp/f'mix{offset}.wav'
            run(args+['-filter_complex',';'.join(filters),'-map','[m]','-t',str(project.duration),str(nextbed)],cancel);bed=nextbed
        target=Path(output);partial=target.with_name(target.stem+'.partial.mp3')
        try:
            run([tool('ffmpeg'),'-v','error','-y','-i',str(bed),'-c:a','libmp3lame','-q:a','2',str(partial)],cancel);partial.replace(target)
        finally:
            if partial.exists(): partial.unlink()


def export_audio(project, output, settings, cancel, log):
    from .engine import get_service
    return get_service().export(project, output, settings, cancel, log)
