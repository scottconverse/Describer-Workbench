"""F5 (DW-4): narration never speaks a model's internal identity label."""
import copy
import json
import re
import threading
from unittest.mock import patch

from describer.engine.exporting import export
from describer.project import Project
from describer.services import DEFAULTS, observe

ID_PATTERN = re.compile(r'\b[a-z]+(_[a-z0-9]+)+\b')


def reply(*rows, glossary=()):
    return json.dumps({'timestamp_reference': 'clip', 'descriptions': list(rows),
                       'character_glossary': list(glossary)})


def cue(text, start=1, end=3):
    return {'start': start, 'end': end, 'text': text}


def draft(replies, duration=10):
    settings = copy.deepcopy(DEFAULTS)
    settings.update(chunk=20, auto_glossary=True)
    project = Project('fixture.mp4', duration)
    with patch('describer.services.segment'), patch('describer.services.google_request', side_effect=replies):
        project.cues = observe(project, settings, '', threading.Event(), lambda _: None)
    return project


def test_glossary_ids_become_names_descriptions_or_a_person():
    project = draft([reply(
        cue('man_1 gestures with hands.', 1, 2),
        cue('person_center nods to woman_blue.', 3, 4),
        cue('speaker_2 points at the screen.', 5, 6),
        glossary=[{'id': 'man_1', 'name': None, 'description': 'man in a grey suit'},
                  {'id': 'woman_blue', 'name': 'Mayor Ruiz', 'description': 'woman in a blue jacket'},
                  {'id': 'person_center', 'name': None, 'description': ''}])])
    texts = [c.text for c in project.cues]
    assert texts == ['A man in a grey suit gestures with hands.',
                     'A person nods to Mayor Ruiz.',
                     'A person points at the screen.']


def test_no_exported_text_matches_the_id_pattern(tmp_path):
    project = draft([reply(cue('man_1 sits.', 1, 2), cue('board_member_3 raises a hand.', 4, 6),
                           glossary=[{'id': 'man_1', 'name': None, 'description': 'a man in glasses'}])])
    for name in ('track.srt', 'track.vtt', 'track.txt'):
        export(project, tmp_path / name, {}, threading.Event(), lambda _: None, 'in-gap-only')
        body = (tmp_path / name).read_text('utf-8')
        assert not ID_PATTERN.search(body), body
    assert not any(ID_PATTERN.search(c.text) for c in project.cues)


def test_cue_left_without_meaning_is_held_for_review():
    project = draft([reply(cue('man_1.', 1, 2), cue('A slide titled History of the Program.', 4, 6),
                           glossary=[{'id': 'man_1', 'name': None, 'description': ''}])])
    held, kept = project.cues
    assert not ID_PATTERN.search(held.text)
    assert held.disposition == 'unresolved' and held.uncertainty
    assert kept.disposition == 'unplanned' and not kept.uncertainty


def test_capitalized_ids_are_never_spoken():
    """gemma4 also writes IDs with a capital letter ("Man_plaid", "Woman_3")."""
    project = draft([reply(
        cue('Man_plaid sits at the table.', 1, 2),
        cue('Woman_3 raises a hand.', 3, 4),
        cue('Woman_maroon sits down next to man_1.', 5, 6),
        glossary=[{'id': 'man_plaid', 'name': None, 'description': 'man in a plaid shirt'},
                  {'id': 'Woman_maroon', 'name': None, 'description': 'woman in a maroon jacket'},
                  {'id': 'man_1', 'name': 'Mayor Ruiz', 'description': ''}])])
    texts = [c.text for c in project.cues]
    assert texts == ['A man in a plaid shirt sits at the table.',
                     'A person raises a hand.',
                     'A woman in a maroon jacket sits down next to Mayor Ruiz.']
    assert not any(re.search(ID_PATTERN.pattern, t, re.I) for t in texts)


def test_spaced_labels_are_never_spoken():
    """gemma4 also writes labels with a space: "Speaker 1", "Board member 3" (seen in M4, L3, L4a)."""
    project = draft([reply(
        cue('Speaker 1 stands and gestures to the slide.', 1, 2),
        cue('Board member 3 looks forward.', 3, 4),
        cue('Attendee 7 leans back.', 5, 6),
        cue('Person 4 looks at a laptop.', 7, 8),
        glossary=[{'id': 'person_4', 'name': None, 'description': 'woman in a red jacket'}])])
    texts = [c.text for c in project.cues]
    assert texts == ['A speaker stands and gestures to the slide.',
                     'A board member looks forward.',
                     'An attendee leans back.',
                     'A woman in a red jacket looks at a laptop.']


def test_counts_and_ordinary_numbers_are_kept():
    project = draft([reply(cue('3 members raise their hands.', 1, 2),
                           cue('Slide: "Item 4 of 10".', 3, 4))])
    assert [c.text for c in project.cues] == ['3 members raise their hands.', 'Slide: "Item 4 of 10".']


def test_short_version_never_speaks_an_id():
    """The short version is spoken when it fits a gap, so it is cleaned the same way."""
    row = cue('man_plaid looks down at papers.', 1, 2)
    row['short_text'] = 'man_plaid looks down'
    row2 = cue('Speaker 1 points at the screen.', 3, 4)
    row2['short_text'] = 'Speaker 1 points'
    project = draft([reply(row, row2, glossary=[{'id': 'man_plaid', 'name': None, 'description': 'man in a plaid shirt'}])])
    assert [c.short_text for c in project.cues] == ['A man in a plaid shirt looks down', 'A speaker points']


def test_a_long_description_is_never_cut_mid_phrase():
    from describer.project import speakable
    labels = {'man_check': {'id': 'man_check', 'name': None, 'description': 'man in a checkered shirt standing at the front'},
              'man_stripe': {'id': 'man_stripe', 'name': None, 'description': 'man in a light blue striped shirt on the left side of the table'},
              'man_pink': {'id': 'man_pink', 'name': None, 'description': 'A man with short hair and glasses wearing a pink shirt'}}
    assert speakable('man_check points at the screen.', labels)[0] == 'A man in a checkered shirt standing at the front points at the screen.'
    assert speakable('man_stripe looks down.', labels)[0] == 'A man in a light blue striped shirt looks down.'
    assert speakable('man_pink nods.', labels)[0] == 'A man with short hair and glasses nods.'
