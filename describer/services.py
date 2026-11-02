"""Media, speech and cloud adapters. Cloud work runs only on explicit UI actions."""
import base64
import ctypes
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path
from .project import Cue, parse_cues, response_json, normalize_generated
from .catalogue import PROMPTS,VOICE_PRESETS

CREATE_NO_WINDOW = 0x08000000 if os.name == 'nt' else 0


def asset_path(name):
    root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1])) / 'assets'
    return (root if root.is_dir() else Path(__file__).resolve().parent / 'resources') / name


def tool(name):
    bundled = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1])) / 'bin' / (name + '.exe')
    found = str(bundled) if bundled.exists() else shutil.which(name)
    if not found:
        raise RuntimeError(f'{name} was not found. Install FFmpeg or put it on PATH.')
    return found


def run(args, cancel=None):
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        p = subprocess.Popen(args, stdout=out, stderr=err, creationflags=CREATE_NO_WINDOW)
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
        return output


def probe(path):
    j = json.loads(run([tool('ffprobe'), '-v', 'error', '-show_format', '-show_streams', '-of', 'json', str(path)]))
    if not any(s['codec_type'] == 'video' for s in j['streams']):
        raise ValueError('The selected file has no video stream.')
    return float(j['format']['duration'])


def segment(source, output, start, duration, fps=2, cancel=None, silent=False):
    run([tool('ffmpeg'), '-v', 'error', '-y', '-ss', str(start), '-i', str(source), '-t', str(duration),
         '-vf', f'scale=640:-2,fps={fps}', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '28',
         *(['-an'] if silent else ['-c:a', 'aac', '-b:a', '64k']), str(output)], cancel)


def dpapi(data, decrypt=False):
    if os.name != 'nt':
        raise RuntimeError('Persistent secret storage requires Windows DPAPI.')
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
            'ollama_key':'','ollama_timeout':600,'ollama_frame_interval':2,
            'voice_engine': 'Windows', 'voice': 'alloy', 'tts_model': 'gpt-4o-mini-tts',
            'voice_presets': VOICE_PRESETS, 'settings_version': 3,
            'voice_preset': '', 'voice_speed': 1.0, 'voice_instructions': '', 'windows_voice': '', 'speech_rate': 0,
            'playback_voice': '', 'sounds': True, 'ui_language': 'English', 'auto_glossary': True,
            'silent_upload': False, 'safety_block_none': False, 'temperature': 0.3, 'update_feed': '', 'auto_update_check': False,
            'logging_level':'INFO','chunking': True, 'verbosity': 'Standard', 'download_quality': 'Best', 'player_volume': 80, 'speech_volume': 100,
            'playback_output': 'Windows speech', 'duck_db': -15, 'interrupt': True, 'presets': {'English': {'Standard': '', **PROMPTS}}, 'gemini_key': '', 'openai_key': ''}


class Settings:
    def __init__(self, path=None):
        self.path = Path(path) if path else Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'DescriberWorkbench' / 'settings.json'
        self.data = json.loads(json.dumps(DEFAULTS))
        self.load_warning='';self.needs_recovery=False
        if self.path.exists():
            try:
                j=json.loads(self.path.read_text(encoding='utf-8-sig'))
                if not isinstance(j,dict):raise ValueError('Expected a settings object.')
                for k in ['gemini_key','openai_key','ollama_key']:
                    if j.get(k):
                        try:j[k]=dpapi(base64.b64decode(j[k]),True).decode()
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
                if self.data['analysis_provider'] not in ('Gemini','Ollama'):raise ValueError('Unknown analysis provider.')
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
        for k in ['gemini_key', 'openai_key', 'ollama_key']:
            if j[k]: j[k] = base64.b64encode(dpapi(j[k].encode())).decode()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix('.tmp');temp.write_text(json.dumps(j, indent=2), encoding='utf-8');temp.replace(self.path)


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
                if not response.text: raise ValueError('The model returned no text. Review provider feedback or try a shorter segment.')
                return response.text
            except Exception as e:
                if getattr(e, 'code', None) not in [429, 500, 502, 503] or attempt == 3: raise
                if cancel.wait(2 ** (attempt + 1)): raise InterruptedError('Cancelled.')
    finally:
        if uploaded:
            try: client.files.delete(name=uploaded.name)
            except Exception: log('Could not delete uploaded file; Google file retention policy applies.')
        client.close()


def video_request(video,prompt,settings,cancel,log,as_json=True):
    if settings.get('analysis_provider','Gemini')=='Ollama':
        from .models import video_request as ollama_request
        return ollama_request(video,prompt,settings,cancel,log,as_json)
    return google_request(video,prompt,settings,cancel,log,as_json)


def observe(project, settings, prompt, cancel, log, start_at=0, duration=None, checkpoint=None):
    cues=[];glossary=project.glossary
    chunk=max(15,int(settings['chunk'])) if settings.get('chunking',True) else max(1,__import__('math').ceil(project.duration))
    if settings.get('analysis_provider','Gemini')=='Ollama':
        chunk=min(chunk,8*int(settings.get('ollama_frame_interval',2)))
        log('Vision receives sampled images; the engine independently measures protected audio.')
    stop=min(project.duration,start_at+duration) if duration is not None else project.duration
    with tempfile.TemporaryDirectory(prefix='describer-') as tmp:
        start=start_at
        while start<stop:
            if cancel.is_set():raise InterruptedError('Cancelled.')
            length=min(chunk, stop-start)
            if length < .1: break
            log(f'Preparing {start:.0f}–{start+length:.0f} seconds…')
            clip=Path(tmp)/'segment.mp4';segment(project.video, clip, start, length, settings['fps'], cancel, settings.get('silent_upload',False))
            ollama=settings.get('analysis_provider','Gemini')=='Ollama'
            instruction=(f'Create concise audio descriptions in {settings["language"]}. Describe visible action, people and settings. '
                +('Use visible evidence only. No audio is supplied; do not infer speech, sounds or dialogue gaps. Do not invent facts. ' if ollama else 'Use visible evidence and supplied audio; do not repeat dialogue or invent facts. ')+
                'Return JSON {"descriptions":[{"start":0.0,"end":2.0,"text":"description","kind":"action","evidence":"visible evidence","uncertainty":""}]}. '
                'Times describe the VISUAL EVENT, not a proposed speech slot. Cover meaningful unspoken printed text, actions, identities and scene changes. '
                'Use objective visible facts. Quote printed text exactly; state uncertainty instead of inventing unreadable words or actions. '
                f'Times are numeric seconds relative to this {length:.2f}-second clip and must fit within it. '
                f'Prior character glossary: {glossary}\nEditorial guidance: {prompt}')
            if settings.get("auto_glossary",False):
                instruction += ' Also return "character_glossary": [{"id":"stable_visual_label","name":null,"description":"visual identity"}]. '+('Keep name=null because no audio is supplied. ' if ollama else 'Use a personal name only if clearly spoken and unambiguously linked; otherwise name=null. ')+'Reuse prior identities; include only visible characters.'
            verbosity={'Short':'Use 1-3 words for each description.','Standard':'Aim for 3-6 words per description.','Detailed':'Aim for 6-12 words per description.'}.get(settings.get('verbosity','Standard'),'')
            instruction += '\n'+verbosity+' Do not omit essential information to meet a timing or verbosity target. The engine schedules narration separately.'+(' Describe visual changes concisely.' if ollama else ' Avoid describing sounds already audible.')
            def request():return response_json(video_request(clip,instruction,settings,cancel,log))
            data=checkpoint(f'observe-{start:.6f}',request) if checkpoint else request()
            if settings.get("auto_glossary",False) and isinstance(data,dict) and "character_glossary" in data:
                from .compatibility import merge_glossary
                glossary=merge_glossary(glossary,data["character_glossary"])
            for cue in normalize_generated(data,length,log):
                cue.start+=start;cue.end+=start;cue.event_start+=start;cue.event_end+=start
                cue.event_id=f'{start:.6f}:{cue.event_start:.6f}:{cue.event_end:.6f}:{len(cues)}'
                cues.append(cue)
            start+=length
    from dataclasses import asdict
    cues=normalize_generated([asdict(c) for c in cues],project.duration,log)
    if not cues: raise ValueError('No descriptions were returned.')
    project.glossary=glossary
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
        info=y.extract_info(url,download=True)
        return y.prepare_filename(info)


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
            factors.append(f'atempo={rate:.6f}')
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
