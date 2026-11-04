import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from describer.project import Project
from describer.services import google_request, observe as generate


class CloudAdapterTests(unittest.TestCase):
    def test_file_lifecycle_and_usage(self):
        from unittest.mock import MagicMock
        client=MagicMock();file=SimpleNamespace(name='files/test',state=SimpleNamespace(name='ACTIVE'))
        client.files.upload.return_value=file
        client.models.generate_content.return_value=SimpleNamespace(text='{"descriptions":[]}',usage_metadata='12 tokens', candidates=[SimpleNamespace(finish_reason='STOP')])
        logs=[]
        with patch('google.genai.Client',return_value=client):
            text=google_request('not-uploaded.mp4','test',{'gemini_key':'dummy','model':'test'},threading.Event(),logs.append)
        self.assertIn('descriptions',text);client.files.delete.assert_called_once_with(name='files/test');client.close.assert_called_once()
        self.assertTrue(any('12 tokens' in line for line in logs))

    def test_chunks_offset_and_cancel(self):
        project=Project('not-uploaded.mp4',35)
        settings={'chunk':20,'fps':2,'language':'English'}
        with patch('describer.services.segment') as clip,patch('describer.services.google_request',side_effect=['{"descriptions":[{"start":1,"end":3,"text":"A door."}]}','{"descriptions":[{"start":1,"end":3,"text":"A person."}]}']):
            cues=generate(project,settings,'',threading.Event(),lambda _:None)
        self.assertEqual([c.start for c in cues],[1,21]);self.assertEqual(clip.call_count,2)
        with patch('describer.services.segment'),patch('describer.services.google_request',return_value='{"descriptions":[{"start":1,"end":3,"text":"A door."}]}'):
            cues=generate(project,settings,'',threading.Event(),lambda _:None)
        self.assertEqual(len(cues),2) # Separate events in distinct chunks must survive.


if __name__=='__main__':unittest.main()
