import tempfile
import unittest
from pathlib import Path
from describer.project import Cue, Project, seconds, stamp, parse_cues, import_subtitles


class ProjectTests(unittest.TestCase):
    def test_time_bounds(self):
        self.assertEqual(seconds('01:02:03,45'),3723.45)
        self.assertEqual(stamp(59.9996),'00:01:00,000')
        for x in ['nan','inf',-1]:
            with self.assertRaises(ValueError):seconds(x)
        with self.assertRaises(ValueError):Cue(3,2,'bad').validate()
        with self.assertRaises(ValueError):Cue(1,6,'past end').validate(5)

    def test_response_and_roundtrip(self):
        cues=parse_cues('```json\n{"descriptions":[{"start":"00:01","end":3,"text":"A door opens."}]}\n```',5)
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'test.adproject';Project('video.mp4',5,cues).save(p)
            project=Project.load(p);self.assertEqual(project.cues,cues)
            for ext in ['srt','txt']:
                out=p.with_suffix('.'+ext);project.export(out)
                self.assertIn('A door opens.',out.read_text())
            self.assertEqual(import_subtitles(p.with_suffix('.srt'),5),cues)

    def test_source_subtitle_variants(self):
        with tempfile.TemporaryDirectory() as tmp:
            for encoding,arrow,frac in [('utf-8','-->','45'),('utf-8','->','450'),('utf-16','-->','450')]:
                p=Path(tmp)/'source.srt';p.write_text(f'1\n00:00:01,{frac} {arrow} 00:00:03,000\nA sign.\n',encoding=encoding)
                cues=import_subtitles(p,4);self.assertEqual(cues[0].start,1.45)


if __name__=='__main__':unittest.main()
