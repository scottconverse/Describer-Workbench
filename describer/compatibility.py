"""Explicit, read-only imports of original JSON/obfuscated settings and output."""
import base64
import json
import math
from pathlib import Path
from .project import Project, parse_cues


def merge_glossary(previous, entries):
    if not isinstance(entries,list):raise ValueError('Character glossary must be a list.')
    lines={line.split(':',1)[0].strip().casefold():line for line in previous.splitlines() if line.strip()}
    for entry in entries:
        if not isinstance(entry,dict):raise ValueError('Invalid character glossary entry.')
        name=str(entry.get('name') or entry.get('character_name') or entry.get('id') or '').strip()
        detail=str(entry.get('description',entry.get('visual_description',''))).strip()
        if name and detail:lines[name.casefold()]=f'{name}: {detail}'
    return '\n'.join(lines.values())


def import_original_output(path, video='', duration=0):
    data=json.loads(Path(path).read_text(encoding='utf-8-sig'))
    return Project(video,duration,parse_cues(data,duration),merge_glossary('',data.get('character_glossary',[])) if isinstance(data,dict) else '')


def read_original_settings(path):
    raw=Path(path).read_bytes()
    try:data=json.loads(raw.decode('utf-8-sig'))
    except (UnicodeDecodeError,json.JSONDecodeError):
        key=b'OmniDescriberSettingsKey2026!@#xK9'
        try:
            decoded=base64.b64decode(raw.strip(),validate=True)
            data=json.loads(bytes(b^key[i%len(key)] for i,b in enumerate(decoded)).decode('utf8'))
        except Exception:
            try:
                from cryptography.fernet import Fernet
                from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
                from cryptography.hazmat.primitives import hashes
                salt=Path(path).with_name('key.salt').read_bytes()
                kdf=PBKDF2HMAC(algorithm=hashes.SHA256(),length=32,salt=salt,iterations=480000)
                data=json.loads(Fernet(base64.urlsafe_b64encode(kdf.derive(hardware_password()))).decrypt(raw))
            except Exception as e:raise ValueError('Cannot read this settings file. Hardware-bound settings.dat requires its key.salt and the original Windows machine.') from e
    if not isinstance(data,dict):raise ValueError('Settings must be a JSON object.')
    mapping={'gemini_model_override':'model','openai_tts_model':'tts_model','openai_tts_voice':'voice',
      'player_allow_speech_interruption':'interrupt','enable_character_glossary':'auto_glossary',
      'send_silenced_video_to_ai':'silent_upload','frame_rate_for_ai':'fps','video_chunk_duration_seconds':'chunk',
      'mp3_audio_ducking_level_db':'duck_db','gemini_disable_safety_block_none':'safety_block_none','gemini_temperature':'temperature',
      'enable_video_chunking':'chunking','gemini_description_verbosity':'verbosity','youtube_download_quality':'download_quality','player_volume_percent':'player_volume','logging_level':'logging_level'}
    # Deliberately do not import secrets or alter providers/defaults implicitly.
    result={new:data[old] for old,new in mapping.items() if old in data and data[old] is not None and data[old]!=''}
    if 'fps' in result:result['fps']=max(1,min(30,int(result['fps'])))
    if 'chunk' in result:result['chunk']=max(15,min(1800,int(result['chunk'])))
    if 'duck_db' in result:result['duck_db']=max(-40,min(0,int(result['duck_db'])))
    languages=dict(zip(('en','es','fr','it','pt','ru','tr','uk','vi','ar'),('English','Español','Français','Italiano','Português','Русский','Türkçe','Українська','Tiếng Việt','العربية')))
    language=data.get('application_language')
    if language:
        language=languages.get(language,language)
        if language not in languages.values():raise ValueError('The original interface language is unsupported; source settings are unchanged.')
        result['ui_language']=language
    original_engine=data.get('tts_engine')
    if original_engine:
        engines={'sapi5':('Windows','sapi5'),'sapi5_32':('Windows 32-bit','sapi5'),
                 'sapi5_32bit':('Windows 32-bit','sapi5'),'onecore':('Windows OneCore','onecore'),'openai':('OpenAI','openai')}
        entry=engines.get(str(original_engine).lower())
        if entry is None:raise ValueError('The original speech engine is unsupported; select its replacement explicitly.')
        engine,prefix=entry;result['voice_engine']=engine
        if engine!='OpenAI':
            voice=data.get(prefix+'_voice_id')
            if voice:result['windows_voice']=str(voice)
            rate=data.get(prefix+'_voice_rate_percent')
            if rate is not None:
                # REA defaults are100 percent (normal speed), not zero.
                ratio=float(rate)/100
                if not math.isfinite(ratio) or ratio<=0:raise ValueError('Invalid original speech rate; source settings are unchanged.')
                result['speech_rate']=max(-10,min(10,round(10*math.log2(ratio))))
            volume=data.get(prefix+'_voice_volume',data.get('sapi5_voice_volume'))
            if volume is not None:
                value=float(volume)
                if not math.isfinite(value):raise ValueError('Invalid original speech volume; source settings are unchanged.')
                result['speech_volume']=max(0,min(100,round(value*100 if 0<=value<=1 else value)))
    return result


def hardware_password():
    import platform,uuid,subprocess
    parts=[platform.node(),platform.processor(),str(uuid.getnode())]
    try:
        output=subprocess.check_output(['vol','C:'],shell=True,text=True,creationflags=0x08000000)
        parts.append(output.split('is ')[-1].strip())
    except Exception:pass
    return ''.join(parts).encode('utf8')


def read_prompt_presets(path):
    data=json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if not isinstance(data,dict):raise ValueError('Expected a language-to-presets object.')
    result={}
    for language,presets in data.items():
        if not isinstance(presets,list):raise ValueError('Each language must contain a preset list.')
        result[language]={}
        for preset in presets:
            if not isinstance(preset,dict) or not isinstance(preset.get('name'),str) or not isinstance(preset.get('prompt'),str):raise ValueError('Invalid prompt preset.')
            result[language][preset['name']]=preset['prompt']
    return result


def read_voice_presets(path):
    data=json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if not isinstance(data,list):raise ValueError('Expected the original voices.json list.')
    result={}
    for p in data:
        name=str(p['name']).strip();speed=float(p.get('speed',1))
        if not name or not .25<=speed<=4:raise ValueError('Voice name/speed is invalid.')
        result[name]={'base_voice':str(p['base_voice']),'speed':speed,'instructions':str(p.get('instructions',''))}
    return result
