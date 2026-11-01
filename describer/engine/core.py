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


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.partial')
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')
    tmp.replace(path)


class Checkpoints:
    def __init__(self, root, identity):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / 'identity.json'
        if path.exists() and json.loads(path.read_text('utf-8')) != identity:
            raise ValueError('Source, provider, model or settings changed; submit a new job instead of resuming.')
        atomic_json(path, identity)

    def stage(self, name, action):
        path = self.root / (name + '.json')
        if path.exists():
            data = json.loads(path.read_text('utf-8'))
            if all((self.root / p).is_file() and sha(self.root / p) == h for p, h in data['files'].items()):
                return data['value']
        value = action()
        files = {}
        if isinstance(value, dict) and value.get('audio'):
            audio = Path(value['audio'])
            files[str(audio.relative_to(self.root))] = sha(audio)
        atomic_json(path, {'value': value, 'files': files})
        return value


def check_cancel(cancel):
    if cancel.is_set():
        raise InterruptedError('Cancelled; completed stages are available for resume.')


def protected_audio(project, settings, cancel, log):
    from ..services import run, tool
    from .sound import speech_spans
    info = json.loads(run([tool('ffprobe'), '-v', 'error', '-show_streams', '-of', 'json', project.video], cancel))
    spans, trace = [], []
    if any(s['codec_type'] == 'audio' for s in info['streams']):
        log('Measuring speech and vocal sounds independently of vision…')
        spans, trace = speech_spans(Path(project.video), project.duration, speech_model(settings), cancel)
    if settings.get('captions'):
        for c in import_subtitles(settings['captions'], project.duration):
            spans.append([max(0, c.start - .3), min(project.duration, c.end + .3)])
    return {'protected': intervals(spans, project.duration), 'classification': trace,
            'safe_gaps': gaps(spans, project.duration)}


def identity(project, settings, prompt, start, duration, model_required=True):
    from ..services import run, tool
    # Secrets never enter checkpoints. Their values are not generation identity.
    safe_settings = {k: v for k, v in settings.items() if not k.endswith('_key')}
    provider = settings.get('analysis_provider', 'Gemini')
    model = settings.get('ollama_model') if provider == 'Ollama' else settings.get('model')
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
    safety = checkpoint.stage('protected-audio', lambda: protected_audio(project, settings, cancel, log))
    occupied, coverage = [], []
    for i, cue in enumerate(project.cues):
        check_cancel(cancel)
        cue.validate(project.duration)
        ident = cue.event_id or f'authored-{i}'
        cue.event_id = ident
        row = {'event_id': ident, 'text': cue.text, 'kind': cue.kind,
               'event_start': cue.event_start, 'event_end': cue.event_end,
               'evidence': cue.evidence, 'uncertainty': cue.uncertainty}
        if cue.uncertainty:
            cue.disposition = 'unresolved'
            row.update(disposition='unresolved', reason=cue.uncertainty)
            coverage.append(row)
            continue

        def speak():
            path = Path(root) / f'narration-{i:05}.wav'
            synthesize(cue.text, path, settings, cancel)
            measured = json.loads(run([tool('ffprobe'), '-v', 'error', '-show_format', '-of', 'json', str(path)], cancel))
            return {'audio': str(path.resolve()), 'seconds': float(measured['format']['duration'])}

        audio = checkpoint.stage(f'speech-{i:05}', speak)
        placement = place(cue.event_start, cue.event_end, audio['seconds'], safety['safe_gaps'], occupied,
                          float(settings.get('max_speech_speed', 1.15)))
        cue.audio, cue.speech_seconds = audio['audio'], audio['seconds']
        cue.disposition, cue.speed = placement.disposition, placement.speed
        if placement.disposition == 'in-gap':
            cue.start, cue.end = placement.start, placement.end
            occupied.append((cue.start, cue.end))
        else:
            # Preserve the original event interval for subtitles/editor; pause playback
            # uses event_start and the measured audio, never this subtitle end.
            cue.start, cue.end = cue.event_start, cue.event_end
        row.update(disposition=cue.disposition, start=cue.start, end=cue.end,
                   speech_seconds=cue.speech_seconds, speed=cue.speed, reason=placement.reason)
        coverage.append(row)
    project.coverage = coverage
    project.analysis.update(protected=safety['protected'], safe_gaps=safety['safe_gaps'],
                            limitations=['Coverage accounts for observed events, not a guarantee that vision found every essential event.',
                                         'Pause descriptions require the pause-aware player or extended video export.'])
    return project


def describe(project, settings, prompt, root, cancel, log, start=0, duration=None):
    from ..services import observe
    checkpoint = Checkpoints(root, identity(project, settings, prompt, start, duration))
    check_cancel(cancel)
    # Audio preflight before expensive inference. No unsafe fallback on missing assets.
    checkpoint.stage('protected-audio', lambda: protected_audio(project, settings, cancel, log))
    project.cues = observe(project, settings, prompt, cancel, log, start, duration, checkpoint.stage)
    return prepare(project, settings, root, cancel, log, checkpoint)


def plan_export(project, settings, root, cancel, log):
    checkpoint = Checkpoints(root, identity(project, settings, '', 0, None, model_required=False))
    return prepare(project, settings, root, cancel, log, checkpoint)
