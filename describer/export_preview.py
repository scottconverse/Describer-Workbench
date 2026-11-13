"""Measured export outcomes. No word-count duration guesses or provider calls."""
from dataclasses import asdict
import copy
import hashlib
import json
from pathlib import Path


def narration_settings(settings):
    engine=settings.get('voice_engine')
    if engine=='OpenAI':
        preset=settings.get('voice_presets',{}).get(settings.get('voice_preset',''),{})
        return {'engine':engine,'model':settings.get('tts_model'),'voice':preset.get('base_voice',settings.get('voice')),
                'speed':preset.get('speed',settings.get('voice_speed',1)),'instructions':preset.get('instructions',settings.get('voice_instructions',''))}
    return {'engine':engine,'voice':settings.get('windows_voice',''),'rate':settings.get('speech_rate',0)}


def plan_stamp(project,settings):
    from .engine.core import sha
    def stat(path):
        info=Path(path).stat();return [info.st_size,info.st_mtime_ns]
    try:
        return {'narration':narration_settings(settings),'speed_limit':settings.get('max_speech_speed',1.15),'require_review':bool(settings.get('require_review')),
                'source':[project.video,project.duration,stat(project.video)],
                'captions':sha(settings['captions']) if settings.get('captions') else None,
                'cues':hashlib.sha256(json.dumps([asdict(copy.deepcopy(c).validate(project.duration)) for c in project.cues],sort_keys=True).encode()).hexdigest(),
                'audio':{c.cue_id:stat(c.audio) for c in project.cues if c.disposition in ('pause','in-gap')}}
    except (OSError,ValueError):return None


def outcome(project,settings,suffix):
    suffix=suffix.lower().lstrip('.')
    if suffix in ('srt','vtt'):
        return {'measured':False,'blocked':False,'text':'Timed text only; no spoken narration or picture pauses. Pause cues retain original event times. Use MP4 for picture, soundtrack and pause narration together.'}
    if suffix=='txt':return {'measured':False,'blocked':False,'text':'Readable script only; no narration audio, timed playback or picture pauses.'}
    if suffix=='json':return {'measured':False,'blocked':False,'text':'Editable project data and review/provenance; narration files are referenced, not embedded. This is not a finished narrated track.'}
    unresolved=any(c.disposition=='unresolved' or c.uncertainty or c.review_status=='needs-review' for c in project.cues)
    if unresolved and settings.get('require_review'):return {'measured':False,'blocked':True,'text':'Review unresolved descriptions before measuring or exporting complete media.'}
    stamp=plan_stamp(project,settings)
    if project.analysis.get('requires_replan') or stamp is None or stamp!=project.analysis.get('export_plan_stamp'):
        return {'measured':False,'blocked':False,'text':'Finished duration has not been measured for these descriptions and this voice. Measure narration to preview actual pause time; export will also measure before writing.'}
    from .engine.exporting import included_pauses
    pauses=included_pauses(project,'complete');extra=sum(c.speech_seconds for c in pauses)
    result={'measured':True,'blocked':False,'source_seconds':project.duration,'extended_seconds':extra,'finished_seconds':project.duration+extra,'pause_descriptions':len(pauses)}
    kind='Picture freezes during pause narration, then resumes with the soundtrack.' if suffix=='mp4' else 'Audio includes the soundtrack and every planned description, including inserted pause narration; no picture.'
    result['text']=f'Measured plan: source {project.duration:.2f} s + pause narration {extra:.2f} s = approximately {project.duration+extra:.2f} s finished. {len(pauses)} pause descriptions. '+kind+' Export measures again; synthesis and codec rounding can change the final duration.'
    return result
