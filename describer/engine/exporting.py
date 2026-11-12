# SPDX-License-Identifier: Apache-2.0
"""Complete exports include pause narration by extending the source timeline."""
import tempfile
from pathlib import Path

from .core import atomic_json, check_cancel


def included_pauses(project,mode):
    return sorted((c for c in project.cues if c.disposition=='pause'),key=lambda c:c.narration_window()[0]) if mode=='complete' else []


def export(project, output, settings, cancel, log, mode='complete'):
    from ..services import LIMITER, _mix_planned_audio, narration_gain, run, tool
    target = Path(output).resolve()
    if target.suffix.lower() not in ('.mp3', '.wav', '.mp4', '.srt', '.txt', '.json', '.vtt'):
        raise ValueError('Unsupported export format')
    if mode not in ('complete', 'in-gap-only'):
        raise ValueError('Export mode must be complete or in-gap-only')
    if target == Path(project.video).resolve():
        raise ValueError('Export must not overwrite the original media')
    if target.suffix.lower() in ('.mp4', '.mp3', '.wav') and any(c.disposition == 'unresolved' for c in project.cues) and mode == 'complete':
        raise ValueError('Unresolved observations remain; inspect coverage before requesting a complete export.')
    target.parent.mkdir(parents=True, exist_ok=True)
    suffix = target.suffix.lower()
    if suffix == '.json':
        project.save(target)
        atomic_json(str(target) + '.coverage.json', {'coverage':project.coverage, 'complete':False,
                    'note':'Editable project, not a complete narrated track.'})
        return {'path': str(target), 'complete': False, 'kind': 'project'}
    if suffix in ('.srt', '.txt', '.vtt'):
        if suffix == '.vtt':
            from ..project import stamp
            # F2: each cue's ID says how it plays: "pause-N" stops the video, "in-gap-N" does not.
            cues = [c for c in project.cues if c.disposition != 'dropped_no_gap']
            body = 'WEBVTT\n\n' + '\n\n'.join(
                f'{c.disposition if c.disposition in ("pause", "in-gap") else "cue"}-{i}\n'
                f'{stamp(c.start).replace(",", ".")} --> {stamp(c.end).replace(",", ".")}\n{c.text}' for i, c in enumerate(cues, 1))
            target.write_text(body, encoding='utf-8')
        else:
            project.export(target)
        atomic_json(str(target) + '.coverage.json', {'coverage': project.coverage, 'complete': False,
                    'note': 'Text cues are not a narrated track; pause cues use original event times.'})
        return {'path': str(target), 'complete': False, 'kind': 'script'}
    included = included_pauses(project,mode)
    with tempfile.TemporaryDirectory(prefix='describer-export-') as temporary:
        tmp = Path(temporary)
        bed = tmp / 'bed.mp3'
        voice_lufs = _mix_planned_audio(project, bed, settings, cancel, log)
        parts, cursor = [], 0.0
        video = target.suffix == '.mp4'

        def part(end):
            nonlocal cursor
            if end <= cursor + 1e-5:
                return
            dest = tmp / f'part-{len(parts):05}'
            if video:
                dest = dest.with_suffix('.mp4')
                args = ['-ss', str(cursor), '-i', project.video, '-ss', str(cursor), '-i', str(bed),
                        '-t', str(end-cursor), '-map', '0:v:0', '-map', '1:a:0', '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2,fps=30',
                        '-c:v', 'libx264', '-preset', 'veryfast', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-ar', '44100', '-ac', '2']
            else:
                dest = dest.with_suffix('.wav')
                args = ['-ss', str(cursor), '-i', str(bed), '-t', str(end-cursor), '-ar', '44100', '-ac', '2', '-c:a', 'pcm_s16le']
            run([tool('ffmpeg'), '-v', 'error', '-y', *args, str(dest)], cancel)
            parts.append(dest)
            cursor = end

        for cue in included:
            check_cancel(cancel)
            at = min(project.duration, max(cursor, cue.narration_window()[0]))
            part(at)
            dest = tmp / f'part-{len(parts):05}'
            gain = f'{narration_gain(cue, settings, voice_lufs[id(cue)], cancel):.6f}'
            if video:
                frame = tmp / 'freeze.png'
                run([tool('ffmpeg'), '-v', 'error', '-y', '-ss', str(min(at, max(0, project.duration-.05))),
                     '-i', project.video, '-frames:v', '1', str(frame)], cancel)
                dest = dest.with_suffix('.mp4')
                args = ['-loop', '1', '-i', str(frame), '-i', cue.audio, '-t', str(cue.speech_seconds),
                        '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2,fps=30', '-c:v', 'libx264', '-preset', 'veryfast',
                        '-pix_fmt', 'yuv420p', '-af', 'volume='+gain+','+LIMITER, '-c:a', 'aac', '-ar', '44100', '-ac', '2']
            else:
                dest = dest.with_suffix('.wav')
                args = ['-i', cue.audio, '-af', 'volume='+gain+','+LIMITER, '-ar', '44100', '-ac', '2', '-c:a', 'pcm_s16le']
            run([tool('ffmpeg'), '-v', 'error', '-y', *args, str(dest)], cancel)
            parts.append(dest)
        part(project.duration)
        listing = tmp / 'concat.txt'
        listing.write_text('\n'.join("file '"+p.as_posix().replace("'", "'\\''")+"'" for p in parts), encoding='utf-8')
        staged = tmp / ('finished'+target.suffix)
        codec = ['-c', 'copy', '-movflags', '+faststart'] if video else ['-c:a', 'libmp3lame', '-q:a', '2'] if target.suffix == '.mp3' else ['-c:a', 'pcm_s16le']
        run([tool('ffmpeg'), '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', str(listing), *codec, str(staged)], cancel)
        check_cancel(cancel)
        # Copy to a same-directory partial before replace (output may be another drive).
        import shutil
        with tempfile.NamedTemporaryFile(prefix=target.name+'.',suffix='.partial',dir=target.parent,delete=False) as owned:
            partial = Path(owned.name)
        try:
            shutil.copyfile(staged, partial)
            partial.replace(target)
        finally:
            partial.unlink(missing_ok=True)
    receipt = {'path': str(target), 'complete': mode == 'complete', 'pause_descriptions': len(included),
               'extended_seconds': sum(c.speech_seconds for c in included), 'coverage': project.coverage,
               'note': 'Original event times are retained; complete exports extend the timeline for pause narration.'}
    atomic_json(str(target)+'.coverage.json', receipt)
    return receipt
