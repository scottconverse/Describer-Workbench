"""Public meeting mode: describe what changes, not every sampled frame (F1).

Other genres keep the default behavior. Only `drafting_mode = "Public meeting"`
turns on the change gate, the prior-cue prompt and the repeat merge.
"""
import re

MODE = 'Public meeting'
MODES = ('', MODE)

# A frame is "changed" when the whole picture moves a little or one area of it
# (for example a slide on a wall screen) moves a lot. Values are 0..255 grey.
THUMB_W, THUMB_H = 64, 36
GRID_X, GRID_Y = 8, 4
WHOLE_DIFF = 6.0
CELL_DIFF = 24.0

PRIOR_CUES = 3
MERGE_SIMILARITY = .8
RESTATE_SIMILARITY = .5
RESTATE_WORDS = re.compile(r'\b(remains?|remaining|continues?|continuing|still)\b', re.I)
_ARTICLES = {'a', 'an', 'the'}
_TOKEN = re.compile(r"[a-z0-9']+")


def enabled(settings):
    return (settings or {}).get('drafting_mode', '') == MODE


# Slides on a wall screen need more pixels than 640 to be read (F4).
FRAME_SIDE = 1280


def frame_side(settings):
    return FRAME_SIDE if enabled(settings) else 640


def thumbnails(paths, cancel=None):
    """Small grey thumbnails of image files, one bytes object per file."""
    from .services import run, tool
    if not paths:
        return []
    args = [tool('ffmpeg'), '-v', 'error']
    for path in paths:
        args += ['-i', str(path)]
    graph = ';'.join(f'[{i}:v]scale={THUMB_W}:{THUMB_H},format=gray[g{i}]' for i in range(len(paths)))
    graph += ';' + ''.join(f'[g{i}]' for i in range(len(paths))) + f'concat=n={len(paths)}:v=1:a=0[out]'
    raw = run(args + ['-filter_complex', graph, '-map', '[out]', '-fps_mode', 'passthrough', '-f', 'rawvideo', '-pix_fmt', 'gray', '-'], cancel)
    size = THUMB_W * THUMB_H
    if len(raw) != size * len(paths):
        raise ValueError('Could not measure frame changes.')
    return [raw[i * size:(i + 1) * size] for i in range(len(paths))]


def changed(a, b):
    """True when thumbnail b shows a visible change from thumbnail a."""
    if a is None:
        return True
    total = sum(abs(x - y) for x, y in zip(a, b))
    if total / len(a) > WHOLE_DIFF:
        return True
    cw, ch = THUMB_W // GRID_X, THUMB_H // GRID_Y
    for gy in range(GRID_Y):
        for gx in range(GRID_X):
            diff = 0
            for y in range(gy * ch, (gy + 1) * ch):
                row = y * THUMB_W
                for x in range(gx * cw, (gx + 1) * cw):
                    diff += abs(a[row + x] - b[row + x])
            if diff / (cw * ch) > CELL_DIFF:
                return True
    return False


class ChangeGate:
    """Keeps only frames that differ from the last frame the model saw."""

    def __init__(self, measure=None):
        self.measure = measure
        self.last = None
        self.sent = 0
        self.skipped = 0

    def __call__(self, frames, cancel=None):
        thumbs = (self.measure or thumbnails)([path for path, _ in frames], cancel)
        kept = []
        for frame, thumb in zip(frames, thumbs):
            if changed(self.last, thumb):
                kept.append(frame)
                self.last = thumb
        self.sent += len(kept)
        self.skipped += len(frames) - len(kept)
        return kept


def prior_instruction(texts):
    texts = [t for t in texts if t][-PRIOR_CUES:]
    rule = ('This is a public meeting. Describe only what is new since the previous descriptions. '
            'If nothing new is visible, return an empty descriptions list: {"descriptions":[]}. '
            'When a new slide or screen with text appears, give its exact title word for word in quotes, '
            'then its main point in a few words. ')
    if texts:
        rule += 'Previous descriptions, oldest first: ' + ' | '.join(texts) + '. '
    return rule


def tokens(text, labels=()):
    words = _TOKEN.findall(str(text).lower())
    drop = _ARTICLES | {str(label).lower() for label in labels}
    return {w for w in words if w not in drop and not re.fullmatch(r'[a-z]+(_[a-z0-9]+)+', w)}


def similarity(a, b, labels=()):
    ta, tb = tokens(a, labels), tokens(b, labels)
    if not ta and not tb:
        return 1.0
    return len(ta & tb) / len(ta | tb)


def merge_repeats(cues, log=lambda _: None, labels=()):
    """Join consecutive cues that say the same thing; drop "still" restatements.

    `cues` are dicts sorted by event start. A merged cue keeps the first text
    and spans both events.
    """
    out = []
    merged = dropped = 0
    for cue in cues:
        prev = out[-1] if out else None
        if prev is not None and not prev.get('manually_edited') and not cue.get('manually_edited'):
            score = similarity(prev['text'], cue['text'], labels)
            if score >= MERGE_SIMILARITY or (RESTATE_WORDS.search(cue['text']) and score >= RESTATE_SIMILARITY):
                prev['end'] = max(prev['end'], cue['end'])
                prev['event_end'] = max(prev.get('event_end', prev['end']), cue.get('event_end', cue['end']))
                if score >= MERGE_SIMILARITY:
                    merged += 1
                else:
                    dropped += 1
                continue
        out.append(cue)
    if merged or dropped:
        log(f'Public meeting mode: merged {merged} repeated and dropped {dropped} restating descriptions.')
    return out
