# SPDX-License-Identifier: Apache-2.0
"""One pipeline for desktop and developer clients. Original media is read-only."""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict
from pathlib import Path

from ..project import import_subtitles
from .assets import speech_model
from .planning import gaps, intervals, place
from .progress import stage


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',prefix='.dw-',suffix='.partial',dir=path.parent,delete=False) as out:
        tmp=Path(out.name)
        json.dump(value,out,indent=2,ensure_ascii=False)
    try:tmp.replace(path)
    finally:tmp.unlink(missing_ok=True)


class Checkpoints:
    def __init__(self, root, identity):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / 'identity.json'
        if path.exists() and json.loads(path.read_text('utf-8')) != identity:
            raise ValueError('Source, provider, model or settings changed; submit a new job instead of resuming.')
        atomic_json(path, identity)

    def stage(self, name, action, validate=None):
        path = self.root / (name + '.json')
        def checked(value):
            if validate:
                try:validate(value)
                except ValueError as exc:
                    # Retain rejected output for diagnosis, never as reusable success.
                    from uuid import uuid4
                    rejected=self.root/('rejected-'+uuid4().hex[:12]+'.json')
                    atomic_json(rejected, {'stage':name,'value':value,'complete':False,'error':str(exc)})
                    raise
            return value
        if path.exists():
            data = json.loads(path.read_text('utf-8'))
            if all((self.root / p).is_file() and sha(self.root / p) == h for p, h in data['files'].items()):
                try:return checked(data['value'])
                except ValueError:
                    # Keep the old cache too, without allowing it to poison retries.
                    from uuid import uuid4
                    path.rename(self.root/('invalid-'+uuid4().hex[:12]+'.json'))
        value = checked(action())
        files = {}
        if isinstance(value, dict) and value.get('audio'):
            audio = Path(value['audio'])
            files[str(audio.relative_to(self.root))] = sha(audio)
        atomic_json(path, {'value': value, 'files': files})
        return value


def check_cancel(cancel):
    if cancel is not None and cancel.is_set():
        raise InterruptedError('Cancelled; completed stages are available for resume.')


def protected_audio(project, settings, cancel, log):
    from ..services import run, tool
    from .sound import speech_spans
    info = json.loads(run([tool('ffprobe'), '-v', 'error', '-show_streams', '-of', 'json', project.video], cancel))
    spans, trace = [], []
    if any(s['codec_type'] == 'audio' for s in info['streams']):
        log('Measuring speech and vocal sounds independently of vision…')
        from .speech_cache import measured
        spans, trace = measured(Path(project.video), project.duration, speech_model(settings), cancel,log,speech_spans)
    if settings.get('captions'):
        from ..meeting import enabled, word_spans
        words = word_spans(settings['captions'], project.duration) if enabled(settings) else None
        if words is not None:
            # F2: word times show the pauses inside a caption line. They also
            # replace the detector's speech frames, which can mark a whole
            # meeting room as speech. Non-speech vocal sounds stay protected.
            from .sound import VOCAL_THRESHOLD
            spans = [[max(0.0, r['time'] - .3), min(project.duration, r['time'] + .96 + .3)]
                     for r in trace if r.get('vocal', 0) >= VOCAL_THRESHOLD] + words
        else:
            for c in import_subtitles(settings['captions'], project.duration):
                spans.append([max(0, c.start - .3), min(project.duration, c.end + .3)])
    return {'protected': intervals(spans, project.duration), 'classification': trace,
            'safe_gaps': gaps(spans, project.duration)}


def identity(project, settings, prompt, start, duration, model_required=True):
    from ..services import run, tool
    # Secrets never enter checkpoints. Their values are not generation identity.
    safe_settings = {k: v for k, v in settings.items() if not k.endswith('_key')}
    from ..providers import provider_name, model_id
    provider = provider_name(settings)
    model = model_id(settings)
    model_digest = None
    if provider == 'Ollama' and model_required:
        from ..models import model_info, json_request, is_cloud
        info = model_info(settings)
        tags = json_request(settings, '/api/tags').get('models', [])
        model_digest = next((r.get('digest') for r in tags if r.get('name') in (model, model+':latest')), None)
        if not model_digest and not is_cloud(settings, info):
            raise ValueError('The local model digest is unavailable; refresh the installed model before submitting.')
    media = json.loads(run([tool('ffprobe'), '-v', 'error', '-show_format', '-of', 'json', project.video]))
    measured = float(media['format']['duration'])
    if not math.isfinite(measured) or measured <= 0:
        raise ValueError('Invalid source duration')
    if abs(measured - project.duration) > .1:
        raise ValueError('Project duration does not match the source; reopen the media.')
    from .. import __version__
    import sys
    package = Path(__file__).resolve().parents[1]
    implementation = ({'executable':sha(sys.executable)} if getattr(sys, 'frozen', False) else
                      {str(p.relative_to(package)):sha(p) for p in package.rglob('*.py')})
    return {'engine': __version__, 'implementation':implementation, 'source': sha(project.video), 'duration': project.duration,
            'provider': provider, 'model': model, 'model_digest': model_digest,
            'settings': safe_settings, 'prompt': prompt, 'start': start, 'range': duration,
            'captions': sha(settings['captions']) if settings.get('captions') else None,
            'project': asdict(project)}


def prepare(project, settings, root, cancel, log, checkpoint):
    """Validate audio, synthesize, then place. Never trust AI speech-slot guesses."""
    from ..services import run, tool, synthesize
    stage(log,'protected-audio')
    safety = checkpoint.stage('protected-audio', lambda: protected_audio(project, settings, cancel, log))
    stage(log,'protected-audio',1,1)
    occupied, coverage = [], []
    for i, cue in enumerate(project.cues):
        stage(log,'narration',i,len(project.cues))
        check_cancel(cancel)
        cue.validate(project.duration)
        ident = cue.event_id or f'authored-{i}'
        cue.event_id = ident
        row = {'event_id': ident, 'cue_id':cue.cue_id, 'review_status':cue.review_status, 'manually_edited':cue.manually_edited, 'text': cue.text, 'kind': cue.kind,
               'event_start': cue.event_start, 'event_end': cue.event_end,
               'timing_start': cue.timing_start, 'timing_end': cue.timing_end,
               'evidence': cue.evidence, 'uncertainty': cue.uncertainty}
        if cue.uncertainty or cue.disposition == 'unresolved' or cue.review_status == 'needs-review':
            cue.disposition = 'unresolved'
            row.update(disposition='unresolved', reason=cue.uncertainty)
            coverage.append(row)
            continue

        def speak(text=cue.text,suffix=''):
            path = Path(root) / f'narration-{i:05}{suffix}.wav'
            synthesize(text, path, dict(settings, speech_volume=100), cancel)
            measured = json.loads(run([tool('ffprobe'), '-v', 'error', '-show_format', '-of', 'json', str(path)], cancel))
            return {'audio': str(path.resolve()), 'seconds': float(measured['format']['duration'])}

        audio = checkpoint.stage(f'speech-{i:05}', speak)
        window_start, window_end = cue.narration_window()
        # Authored timing is kept as written; generated cues may use a nearby pause.
        from ..meeting import narration_reach
        reach = narration_reach(settings) if cue.timing_start is None else 0.0
        placement = place(window_start, window_end, audio['seconds'], safety['safe_gaps'], occupied,
                          float(settings.get('max_speech_speed', 1.15)), reach)
        cue.narration_text=''
        if placement.disposition=='pause':
            from .shortening import concise
            shortened=concise(cue.text)
            if shortened!=cue.text:
                candidate=checkpoint.stage(f'short-speech-{i:05}',lambda:speak(shortened,'-short'))
                fitted=place(window_start,window_end,candidate['seconds'],safety['safe_gaps'],occupied,
                             float(settings.get('max_speech_speed',1.15)),reach)
                if fitted.disposition=='in-gap':
                    audio,placement=candidate,fitted;cue.narration_text=shortened
                    log('Removed a redundant visual lead-in; original description and evidence retained.')
        brief=cue.short_text.strip()
        if placement.disposition=='pause' and brief and brief!=cue.text:
            # F2: the model's own short version may fit a gap the full line does not.
            candidate=checkpoint.stage(f'brief-speech-{i:05}',lambda b=brief:speak(b,'-brief'))
            fitted=place(window_start,window_end,candidate['seconds'],safety['safe_gaps'],occupied,
                         float(settings.get('max_speech_speed',1.15)),reach)
            if fitted.disposition=='in-gap':
                audio,placement=candidate,fitted;cue.narration_text=brief
                log('Used the short version of a description to fit a gap; the full text is kept.')
        cue.audio, cue.speech_seconds, cue.audio_volume = audio['audio'], audio['seconds'], 100
        cue.disposition, cue.speed = placement.disposition, placement.speed
        if placement.disposition == 'in-gap':
            cue.start, cue.end = placement.start, placement.end
            occupied.append((cue.start, cue.end))
        else:
            # Preserve the original event interval for subtitles/editor; pause playback
            # uses event_start and the measured audio, never this subtitle end.
            cue.start, cue.end = window_start, window_end
        row.update(disposition=cue.disposition, start=cue.start, end=cue.end,
                   speech_seconds=cue.speech_seconds, speed=cue.speed, reason=placement.reason,
                   narration_text=cue.narration_text or cue.text)
        coverage.append(row)
    stage(log,'narration',len(project.cues),len(project.cues))
    from ..meeting import apply_pause_budget, pause_budget, pause_only_events
    budget=pause_budget(settings)
    if budget is not None:
        pause_only_events(project.cues,coverage,log)
        apply_pause_budget(project.cues,coverage,budget,log)
    for gap in project.analysis.get('failed_chunks', []):
        # A chunk the model never answered properly: show the hole, never hide it.
        coverage.append({'event_id': f'failed-{gap["start"]:.6f}', 'cue_id': None, 'text': '', 'kind': 'gap',
                         'event_start': gap['start'], 'event_end': gap['end'],
                         'disposition': 'failed_chunk', 'reason': gap['error']})
    for span in project.analysis.get('no_change_chunks', []):
        # Public meeting mode: a span with no visible change is recorded, not hidden.
        coverage.append({'event_id': f'nochange-{span["start"]:.6f}', 'cue_id': None, 'text': '', 'kind': 'gap',
                         'event_start': span['start'], 'event_end': span['end'],
                         'disposition': 'no_change', 'reason': span['reason']})
    project.coverage = coverage
    project.analysis.update(protected=safety['protected'], safe_gaps=safety['safe_gaps'], requires_replan=False,
                            limitations=['Coverage accounts for observed events, not a guarantee that vision found every essential event.',
                                         'Pause descriptions require the pause-aware player or extended video export.'])
    from ..export_preview import plan_stamp
    project.analysis['export_plan_stamp']=plan_stamp(project,settings)
    return project


def describe(project, settings, prompt, root, cancel, log, start=0, duration=None):
    from ..services import observe, narration_preflight
    narration_preflight(settings,cancel)
    checkpoint = Checkpoints(root, identity(project, settings, prompt, start, duration))
    check_cancel(cancel)
    from ..providers import provider_name
    if provider_name(settings) == 'Ollama':
        # Refuse a blind model before any frame is described (DW-12).
        from .. import models
        models.vision_check(settings, cancel, log, Path(root).parents[1] / 'vision-checks.json')
    # Audio preflight before expensive inference. No unsafe fallback on missing assets.
    stage(log,'protected-audio')
    checkpoint.stage('protected-audio', lambda: protected_audio(project, settings, cancel, log))
    stage(log,'protected-audio',1,1)
    project.cues = observe(project, settings, prompt, cancel, log, start, duration, checkpoint.stage)
    return prepare(project, settings, root, cancel, log, checkpoint)


def plan_export(project, settings, root, cancel, log):
    checkpoint = Checkpoints(root, identity(project, settings, '', 0, None, model_required=False))
    return prepare(project, settings, root, cancel, log, checkpoint)
