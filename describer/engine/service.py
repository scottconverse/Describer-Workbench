# SPDX-License-Identifier: Apache-2.0
"""Persistent single-owner jobs shared by every adapter; no Qt dependency."""
from __future__ import annotations

import copy
import json
import math
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

import portalocker

from ..project import Project, parse_cues
from .assets import default_root
from .core import atomic_json, check_cancel

TERMINAL = {'done', 'error', 'cancelled', 'interrupted'}


class DescriptionService:
    def __init__(self, root=None, settings=None):
        from ..services import DEFAULTS
        self.root = Path(root or default_root() / 'engine').resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.settings = dict(copy.deepcopy(DEFAULTS), **(settings or {}))
        self._lock = portalocker.Lock(str(self.root / '.owner.lock'), timeout=0)
        try:
            self._lock.acquire()
        except portalocker.exceptions.LockException as exc:
            raise RuntimeError('This workspace already has an owning engine. Connect to its HTTP service, or choose another workspace.') from exc
        self._mutex = threading.RLock()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='describer')
        self._cancels, self._secrets, self._futures = {}, {}, {}
        self._closed = False
        self.damaged_jobs = {}
        for path in self.root.glob('*/job.json'):
            data = self._read_record(path)
            if data is None:continue
            if data['state'] in ('queued', 'running', 'cancelling'):
                data.update(state='interrupted', error='Previous owner exited; resume explicitly.')
                atomic_json(path, data)

    def _read_record(self, path):
        """Report unusable records without rewriting or deleting their evidence."""
        try:
            data = json.loads(path.read_text('utf-8'))
            if not isinstance(data, dict):raise ValueError('Expected a job object')
            if data.get('id') != path.parent.name or len(data['id']) != 32 or any(c not in '0123456789abcdef' for c in data['id']):
                raise ValueError('Invalid job identity')
            if data.get('state') not in TERMINAL | {'queued','running','cancelling'}:raise ValueError('Invalid job state')
            if not isinstance(data.get('created'), (int,float)) or not math.isfinite(data['created']):raise ValueError('Invalid creation time')
            if not isinstance(data.get('revision'), int) or data['revision'] < 0:raise ValueError('Invalid revision')
            if not isinstance(data.get('settings'), dict):raise ValueError('Invalid settings')
            if data.get('operation') not in ('describe','export','ask','explore','voice-preview'):raise ValueError('Invalid operation')
            if not isinstance(data.get('progress'), str):raise ValueError('Invalid progress')
        except (OSError,ValueError,TypeError,KeyError) as exc:
            self.damaged_jobs[path.parent.name] = {'path':str(path), 'error':type(exc).__name__+': unreadable or invalid job record; original preserved'}
            return None
        self.damaged_jobs.pop(path.parent.name,None)
        return data

    def _path(self, job_id):
        if not isinstance(job_id, str) or len(job_id) != 32 or any(c not in '0123456789abcdef' for c in job_id):
            raise ValueError('Invalid job ID')
        root = self.root / job_id
        if not (root / 'job.json').is_file():
            raise KeyError('Job not found')
        return root

    def get_job(self, job_id):
        with self._mutex:
            data = self._read_record(self._path(job_id) / 'job.json')
            if data is None:raise ValueError('Damaged job record; original preserved. Inspect damaged_jobs for its location.')
            return data

    def list_jobs(self, limit=50, state=None):
        if not 1 <= limit <= 200:
            raise ValueError('limit must be 1..200')
        with self._mutex:
            rows = [data for p in self.root.glob('*/job.json') if (data := self._read_record(p)) is not None]
        return sorted((j for j in rows if state is None or j['state'] == state), key=lambda j:j['created'], reverse=True)[:limit]

    def _update(self, job_id, **values):
        with self._mutex:
            data = self.get_job(job_id)
            data.update(values, updated=time.time())
            atomic_json(self._path(job_id) / 'job.json', data)
            return data

    def submit(self, source=None, project=None, settings=None, prompt='', start=0, duration=None, operation='describe', export_format=None, mode='complete'):
        from ..services import probe
        if operation not in ('describe', 'export', 'ask', 'explore', 'voice-preview'):
            raise ValueError('Unknown job operation')
        if project is None:
            if not source:
                raise ValueError('source or project is required')
            source = str(Path(source).resolve())
            if not Path(source).is_file():
                raise ValueError('Source media is missing')
            project = Project(source, probe(source))
        elif isinstance(project, (str, Path)):
            project = Project.load(project)
        elif isinstance(project, dict):
            project = Project(project['video'], float(project['duration']), parse_cues(project.get('cues', []), float(project['duration'])), project.get('glossary', ''), project.get('coverage', []), project.get('analysis', {}))
        project = copy.deepcopy(project)
        if not Path(project.video).is_file():
            raise ValueError('Source media is missing')
        if not math.isfinite(project.duration) or project.duration <= 0 or not math.isfinite(start) or start < 0 or start >= project.duration or (duration is not None and (not math.isfinite(duration) or duration <= 0)):
            raise ValueError('Invalid analysis range')
        selected = dict(copy.deepcopy(self.settings), **(settings or {}))
        # API callers must explicitly permit remote inference, not inherit a GUI dialog.
        if selected.get('analysis_provider') == 'Gemini' and operation in ('describe','ask','explore') and not selected.get('allow_cloud', False):
            raise ValueError('Gemini requires allow_cloud=true')
        uses_speech = operation in ('describe','voice-preview') or (operation == 'export' and export_format in ('mp3','wav','mp4'))
        if uses_speech and selected.get('voice_engine') == 'OpenAI' and not selected.get('allow_cloud', False):
            raise ValueError('OpenAI speech requires allow_cloud=true')
        if selected.get('analysis_provider') == 'Ollama' and operation in ('describe','ask','explore'):
            from ..models import endpoint, is_cloud, model_info
            endpoint(selected)
            if is_cloud(selected, model_info(selected)) and not selected.get('allow_cloud', False):
                raise ValueError('Remote/cloud Ollama requires allow_cloud=true')
        if operation == 'export' and export_format not in ('mp3', 'wav', 'mp4', 'srt', 'vtt', 'txt', 'json'):
            raise ValueError('Choose a supported export format')
        if mode not in ('complete', 'in-gap-only'):
            raise ValueError('Export mode must be complete or in-gap-only')
        with self._mutex:
            if self._closed:
                raise RuntimeError('Engine is closed')
            if sum(not f.done() for f in self._futures.values()) >= 20:
                raise ValueError('Job queue is full')
            job_id = uuid4().hex
            root = self.root / job_id
            root.mkdir()
            project.save(root / 'input.adproject')
            data = {'id':job_id, 'state':'queued', 'operation':operation, 'created':time.time(),
                    'revision':0, 'prompt':prompt, 'start':start, 'duration':duration,
                    'settings':{k:v for k,v in selected.items() if not k.endswith('_key')},
                    'export_format':export_format, 'mode':mode, 'progress':'queued', 'error':None}
            atomic_json(root / 'job.json', data)
            self._secrets[job_id] = selected
            self._schedule(job_id)
            return self.get_job(job_id)

    def submit_batch(self, items):
        if not 1 <= len(items) <= 20:
            raise ValueError('Batch must contain 1..20 jobs')
        results = []
        for item in items:
            try:
                results.append({'job':self.submit(**item)})
            except (ValueError, OSError, KeyError, RuntimeError, TypeError) as exc:
                results.append({'error':str(exc)})
        return results

    def _schedule(self, job_id):
        self._cancels[job_id] = threading.Event()
        self._futures[job_id] = self._executor.submit(self._run, job_id)

    def _run(self, job_id):
        from . import core, exporting
        cancel = self._cancels[job_id]
        try:
            with self._mutex:
                check_cancel(cancel)
                data = self._update(job_id, state='running', error=None)
            root = self._path(job_id)
            project = Project.load(root / 'input.adproject')
            settings = dict(data['settings'], **self._secrets.get(job_id, {}))
            def log(message):
                # Avoid storing provider output/keys in public status responses.
                if cancel.is_set():
                    return
                self._update(job_id, progress=message)
            stages = root / 'stages'
            if data['operation'] == 'describe':
                result = core.describe(project, settings, data['prompt'], stages, cancel, log, data['start'], data['duration'])
            elif data['operation'] == 'export':
                result = (project if data['export_format'] in ('srt','vtt','txt','json')
                          else core.plan_export(project, settings, stages, cancel, log))
                artifact = exporting.export(result, root / ('export.'+data['export_format']), settings, cancel, log, data['mode'])
                self._update(job_id, artifact=artifact)
            elif data['operation'] == 'voice-preview':
                from ..services import synthesize
                path = root / 'preview.wav'
                synthesize(data['prompt'], path, settings, cancel)
                result = project
                self._update(job_id, artifact={'path':str(path), 'kind':'voice-preview'})
            else:
                from ..services import segment, video_request
                from ..project import response_json, scene_data
                length = min(data['duration'] or 10, project.duration-data['start'])
                clip = root / 'scene.mp4'
                segment(project.video, clip, data['start'], length, settings['fps'], cancel, settings.get('silent_upload', False))
                instruction = (f'Return JSON {{"answer":"answer"}}. Answer in {settings["language"]}. Question: {data["prompt"]}'
                               if data['operation'] == 'ask' else
                               f'In {settings["language"]}, describe spatial layout. Return JSON {{"layout":"summary","objects":[{{"name":"object","description":"visible facts","x":5,"y":5}}]}}. Grid is 0..10. Do not invent hidden objects.')
                answer = response_json(video_request(clip, instruction, settings, cancel, log))
                if data['operation'] == 'explore':
                    answer = scene_data(answer)
                elif not isinstance(answer, dict) or not isinstance(answer.get('answer'), str):
                    raise ValueError('Invalid scene answer')
                result = project
                result.analysis['scene_result'] = answer
            with self._mutex:
                check_cancel(cancel)
                result.save(root / 'result.adproject')
                self._update(job_id, state='done', progress='done', revision=data['revision']+1)
        except InterruptedError as exc:
            self._update(job_id, state='cancelled', progress='cancelled', error=str(exc))
        except Exception as exc:
            message = str(exc)
            for key, value in self._secrets.get(job_id, {}).items():
                if key.endswith('_key') and value:
                    message = message.replace(str(value), '[redacted]')
            self._update(job_id, state='error', progress='error', error=message)

    def cancel(self, job_id):
        with self._mutex:
            job = self.get_job(job_id)
            if job['state'] in TERMINAL:
                return job
            self._cancels[job_id].set()
            if self._futures[job_id].cancel():
                return self._update(job_id, state='cancelled', progress='cancelled')
            return self._update(job_id, state='cancelling', progress='cancelling')

    def resume(self, job_id, settings=None):
        with self._mutex:
            job = self.get_job(job_id)
            if job['state'] not in ('error', 'cancelled', 'interrupted') or (job_id in self._futures and not self._futures[job_id].done()):
                raise ValueError('Only a terminal interrupted, failed or cancelled job may resume')
            # Non-secret changed settings are validated against checkpoint identity.
            self._secrets[job_id] = {**self.settings, **job['settings'], **self._secrets.get(job_id, {}), **(settings or {})}
            self._update(job_id, state='queued', progress='queued', error=None)
            self._schedule(job_id)
            return self.get_job(job_id)

    def result(self, job_id):
        job = self.get_job(job_id)
        if job['state'] != 'done':
            raise ValueError('Job is not done; inspect status before reading results')
        return Project.load(self._path(job_id) / 'result.adproject')

    def read(self, job_id, offset=0, limit=100, start=None, end=None):
        if offset < 0 or not 1 <= limit <= 500:
            raise ValueError('Invalid page')
        project = self.result(job_id)
        rows = [asdict(c) for c in project.cues if (start is None or c.event_end > start) and (end is None or c.event_start < end)]
        return {'id':job_id, 'revision':self.get_job(job_id)['revision'], 'total':len(rows),
                'cues':rows[offset:offset+limit], 'glossary':project.glossary,
                'next_offset':offset+limit if offset+limit < len(rows) else None}

    def coverage(self, job_id):
        project = self.result(job_id)
        return {'events':project.coverage, 'analysis':project.analysis,
                'counts':{kind:sum(c.disposition == kind for c in project.cues) for kind in ('in-gap','pause','unresolved')}}

    def scene_result(self, job_id):
        return self.result(job_id).analysis.get('scene_result', {})

    def export_job(self, job_id, export_format='mp4', settings=None, mode='complete'):
        with self._mutex:
            original = self.get_job(job_id)
            selected = {**original['settings'], **self._secrets.get(job_id, {}), **(settings or {})}
            return self.submit(project=self.result(job_id), settings=selected, operation='export', export_format=export_format, mode=mode)

    def models(self, settings=None):
        from ..models import discover
        return discover(dict(self.settings, **(settings or {})), threading.Event(), lambda _:None)

    def capabilities(self):
        from .. import __version__
        return {'version':__version__, 'operations':['describe','export','ask','explore','voice-preview'],
                'exports':['mp4','mp3','wav','srt','vtt','txt','json'],
                'providers':['Ollama','Gemini'], 'transports':['python','cli','http','mcp-stdio','mcp-streamable-http'],
                'single_owner':True, 'max_concurrent_jobs':1, 'telemetry':False}

    def edit(self, job_id, revision, cues=None, glossary=None):
        with self._mutex:
            job = self.get_job(job_id)
            if revision != job['revision']:
                raise ValueError('Project revision changed; read it again before editing')
            project = self.result(job_id)
            if cues is not None:
                previous = project.cues
                edited = parse_cues(cues, project.duration)
                for cue in edited:
                    matches = [old for old in previous if
                               (cue.event_id and old.event_id == cue.event_id) or
                               (not cue.event_id and (old.start, old.end) == (cue.start, cue.end))]
                    if len(matches) == 1:
                        old = matches[0]
                        preserved = old.edited(cue.start, cue.end, cue.text, project.duration)
                        cue.event_id, cue.event_start, cue.event_end = preserved.event_id, preserved.event_start, preserved.event_end
                        cue.evidence, cue.uncertainty, cue.kind = preserved.evidence, preserved.uncertainty, preserved.kind
                        cue.disposition = preserved.disposition
                    cue.disposition = 'unresolved' if cue.disposition == 'unresolved' or cue.uncertainty else 'unplanned'
                    cue.audio, cue.speech_seconds, cue.speed = '', 0, 1
                project.cues = edited
                project.coverage = []
                project.analysis = {'note':'Edited; re-plan before exporting narration.'}
            if glossary is not None:
                project.glossary = str(glossary)
            project.save(self._path(job_id) / 'result.adproject')
            return self._update(job_id, revision=revision+1)

    def wait(self, job_id, cancel=None, log=lambda _:None):
        previous = None
        while True:
            job = self.get_job(job_id)
            if job['progress'] != previous:
                previous = job['progress']
                log(previous)
            if job['state'] in TERMINAL:
                if job['state'] != 'done':
                    if job['state'] == 'cancelled':
                        raise InterruptedError(job.get('error') or 'Cancelled')
                    raise RuntimeError(job.get('error') or job['state'])
                return self.result(job_id)
            if cancel and cancel.is_set():
                self.cancel(job_id)
            time.sleep(.05)

    def describe(self, project, settings, prompt, cancel, log, start=0, duration=None):
        job = self.submit(project=project, settings=settings, prompt=prompt, start=start, duration=duration)
        result = self.wait(job['id'], cancel, log)
        project.glossary, project.coverage, project.analysis = result.glossary, result.coverage, result.analysis
        return result.cues

    def export(self, project, output, settings, cancel, log):
        import shutil
        target = Path(output).resolve()
        if target == Path(project.video).resolve():
            raise ValueError('Cannot overwrite original media')
        job = self.submit(project=project, settings=settings, operation='export', export_format=target.suffix.lower().lstrip('.'))
        self.wait(job['id'], cancel, log)
        artifact = self.get_job(job['id'])['artifact']
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_name(target.name+'.partial')
        try:
            shutil.copyfile(artifact['path'], partial)
            partial.replace(target)
        finally:
            partial.unlink(missing_ok=True)
        receipt = Path(artifact['path']+'.coverage.json')
        if receipt.is_file():
            shutil.copyfile(receipt, str(target)+'.coverage.json')
        return dict(artifact, path=str(target))

    def close(self):
        with self._mutex:
            self._closed = True
            for job_id in self._cancels:
                self.cancel(job_id)
        self._executor.shutdown(wait=True, cancel_futures=False)
        self._lock.release()


_services = {}
_registry_lock = threading.Lock()


def get_service(root=None):
    key = str(Path(root or default_root() / 'engine').resolve())
    with _registry_lock:
        if key not in _services or _services[key]._closed:
            _services[key] = DescriptionService(key)
        return _services[key]
