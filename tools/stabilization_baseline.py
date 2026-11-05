"""Repeatable real-media/Qt baseline; never reads the user's settings or calls AI.

Cue populations are controlled editor load, not generated descriptions or accuracy
evidence. Speech timing measures the real independent detector, not full AI work.
Run from the repository with its desktop/local dependencies installed.
"""
import argparse
import copy
import json
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def memory():
    if sys.platform == 'win32':
        import ctypes
        from ctypes import wintypes
        class Counters(ctypes.Structure):
            _fields_ = [('cb', wintypes.DWORD), ('faults', wintypes.DWORD)] + [
                (name, ctypes.c_size_t) for name in ('peak', 'working', 'peak_pool', 'pool', 'peak_nonpaged', 'nonpaged', 'pagefile', 'peak_pagefile')]
        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        ctypes.windll.kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        query = ctypes.windll.psapi.GetProcessMemoryInfo
        query.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
        if not query(ctypes.windll.kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
            raise ctypes.WinError()
        return {'working_bytes': counters.working, 'process_peak_bytes': counters.peak}
    import resource
    return {'process_peak_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == 'darwin' else 1024)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', action='append', required=True, help='label=video path')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--speech', action='store_true')
    args = parser.parse_args()
    from PySide6.QtCore import QUrl
    from PySide6.QtWidgets import QApplication
    from PySide6.QtTest import QTest
    from describer.app import Window
    from describer.project import Cue
    from describer.services import DEFAULTS, probe, segment
    from describer.engine.core import protected_audio, sha
    app = QApplication.instance() or QApplication([])
    args.output.mkdir(parents=True, exist_ok=True)
    results = {'source': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
               'platform': sys.platform, 'qt_platform': app.platformName(), 'cases': [],
               'limits': ['Controlled cues test editor load, not AI quality.', 'Detector/segment timings exclude AI inference and synthesis.',
                          'Memory is this process; child FFmpeg memory is not included.']}
    def save():
        (args.output/'baseline.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    with tempfile.TemporaryDirectory(prefix='describer-baseline-') as temporary:
        root = Path(temporary)
        for case in args.case:
            label, path = case.split('=', 1)
            source = Path(path).resolve()
            row = {'label': label, 'path': str(source), 'sha256': sha(source), 'duration': probe(source), 'failures': []}
            results['cases'].append(row)
            save()
            window = Window(root/(label+'-settings.json'))
            window.settings.data['sounds'] = False
            try:
                window.show()
                started = time.perf_counter()
                window.set_video(source)
                window.audio.setMuted(True)
                window.player.play()
                deadline = time.monotonic()+10
                while window.player.position() < 100 and time.monotonic() < deadline:
                    app.processEvents()
                    QTest.qWait(20)
                row['open_to_play_seconds'] = time.perf_counter()-started
                row['playback_position_ms'] = window.player.position()
                if not row['playback_position_ms']:row['failures'].append('No playback progress within 10 seconds: '+window.player.errorString())
                window.player.pause()
                count = max(1, int(row['duration']//10))
                window.project.cues = [Cue(i*10+1, min(i*10+4, row['duration']), f'Controlled editor load description {i+1}.').validate(row['duration']) for i in range(count)]
                window.refresh()
                window.choose(count//2)
                app.processEvents()
                timings = []
                window.text.setFocus()
                for letter in 'abcdefghijklmnopqrst':
                    started = time.perf_counter()
                    QTest.keyClicks(window.text, letter)
                    app.processEvents()
                    timings.append((time.perf_counter()-started)*1000)
                row['editing'] = {'cue_count': count, 'samples_ms': timings,
                                  'median_ms': statistics.median(timings), 'max_ms': max(timings),
                                  'undo_commands': window.undo_stack.count(), 'memory': memory()}
                window.grab().save(str(args.output/(label+'.png')))
                window.player.setSource(QUrl())
                started = time.perf_counter()
                segment(source, root/(label+'-segment.mp4'), min(10, row['duration']/2), min(20, row['duration']/2), 2)
                row['visual_20s_segment_seconds'] = time.perf_counter()-started
                if args.speech:
                    started = time.perf_counter()
                    safety = protected_audio(window.project, copy.deepcopy(DEFAULTS), threading.Event(), lambda _:None)
                    row['whole_media_speech_seconds'] = time.perf_counter()-started
                    row['protected_intervals'] = len(safety['protected'])
                    row['classification_samples'] = len(safety['classification'])
                    row['speech_memory'] = memory()
            except Exception as exc:
                row['failures'].append(type(exc).__name__+': '+str(exc))
            finally:
                window.dirty = False
                window.close()
                app.processEvents()
                save()
            print(json.dumps(row), flush=True)


if __name__ == '__main__':
    main()
