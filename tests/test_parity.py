import base64,copy,hashlib,json,tempfile,threading,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
from describer.project import Project,import_subtitles
from describer.services import DEFAULTS,observe as generate,synthesize
from describer.compatibility import read_original_settings,import_original_output,read_voice_presets
from describer.updates import read_feed,stage_update
from describer.i18n import LANGUAGES,TRANSLATIONS,KEYS

class ParityTests(unittest.TestCase):
 def test_single_and_chunked_glossary(self):
  settings=copy.deepcopy(DEFAULTS);settings.update(chunk=20)
  replies=[json.dumps({'descriptions':[{'start':1,'end':3,'text':'A person enters.'}],'character_glossary':[{'name':'Red coat','description':'A person wearing red.'}]}),json.dumps({'descriptions':[{'start':2,'end':4,'text':'The person leaves.'}],'character_glossary':[{'name':'Red coat','description':'A person wearing a red coat.'}]})]
  for duration,count in [(10,1),(35,2)]:
   project=Project('fixture.mp4',duration)
   with patch('describer.services.segment'),patch('describer.services.google_request',side_effect=replies[:count]) as request:
    cues=generate(project,settings,'',threading.Event(),lambda _:None)
   self.assertEqual(len(cues),count);self.assertIn('Red coat:',project.glossary)
   if count==2:self.assertIn('Red coat:',request.call_args_list[1].args[1]);self.assertEqual(cues[1].start,22)
 def test_original_formats_readonly(self):
  with tempfile.TemporaryDirectory() as tmp:
   tmp=Path(tmp);p=tmp/'settings.dat2';raw=json.dumps({'frame_rate_for_ai':4,'user_gemini_api_key':'never-import','openai_tts_model':'tts-1'}).encode();key=b'OmniDescriberSettingsKey2026!@#xK9'
   encoded=base64.b64encode(bytes(b^key[i%len(key)] for i,b in enumerate(raw)));p.write_bytes(encoded)
   imported=read_original_settings(p);self.assertEqual(imported,{'fps':4,'tts_model':'tts-1'});self.assertEqual(p.read_bytes(),encoded)
   p=tmp/'output.json';p.write_text(json.dumps({'audio_descriptions':[{'start_time_mmss':'00:01','end_time_mmss':'00:03','description_text':'A door opens.'}],'character_glossary':[{'name':'Ada','description':'A woman in blue.'}]}))
   project=import_original_output(p,'video.mp4',10);self.assertEqual(project.cues[0].start,1);self.assertIn('Ada:',project.glossary)
   p=tmp/'voices.json';p.write_text(json.dumps([{'name':'Warm','base_voice':'nova','speed':1.2,'instructions':'Speak warmly.'}]))
   self.assertEqual(read_voice_presets(p)['Warm']['speed'],1.2)
 def test_openai_preset_payload(self):
  settings=copy.deepcopy(DEFAULTS);settings.update(voice_engine='OpenAI',openai_key='fixture',voice_preset='Warm',voice_presets={'Warm':{'base_voice':'nova','speed':1.2,'instructions':'Speak warmly.'}})
  with tempfile.TemporaryDirectory() as tmp,patch('urllib.request.urlopen') as call:
   call.return_value.__enter__.return_value.read.return_value=b'fixture-wave'
   synthesize('A door opens.',Path(tmp)/'voice.wav',settings)
   payload=json.loads(call.call_args.args[0].data)
   self.assertEqual(payload['voice'],'nova');self.assertEqual(payload['speed'],1.2);self.assertEqual(payload['instructions'],'Speak warmly.')
 def test_update_staging_and_rejections(self):
  with tempfile.TemporaryDirectory() as tmp:
   tmp=Path(tmp);archive=tmp/'portable.zip'
   with zipfile.ZipFile(archive,'w') as z:z.writestr('DescriberWorkbench/DescriberWorkbench.exe',b'new fixture');z.writestr('DescriberWorkbench/DescriberCLI.exe',b'cli fixture');z.writestr('DescriberWorkbench/_internal/marker',b'runtime')
   data={'application':'DescriberWorkbench','version':'9.0.0','url':str(archive),'sha256':hashlib.sha256(archive.read_bytes()).hexdigest()}
   feed=tmp/'feed.json';feed.write_text(json.dumps(data));self.assertTrue(read_feed(str(feed))['newer'])
   with patch('describer.updates.verify_signatures') as verify:
    stage=Path(stage_update(data,tmp/'staging',threading.Event(),lambda _:None));self.assertTrue((stage/'update-receipt.json').exists());verify.assert_called_once()
   with self.assertRaises(ValueError):stage_update(dict(data,sha256='0'*64),tmp/'bad',threading.Event(),lambda _:None)
   with zipfile.ZipFile(archive,'w') as z:z.writestr('../escape.txt',b'bad')
   data['sha256']=hashlib.sha256(archive.read_bytes()).hexdigest()
   with self.assertRaises(ValueError):stage_update(data,tmp/'unsafe',threading.Event(),lambda _:None)
   self.assertFalse((tmp/'escape.txt').exists())
 def test_legacy_and_malformed_subtitles(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'legacy.srt';p.write_bytes('1\n00:00:01,000 --> 00:00:02,000\nUma lâmina.\n\n2\n00:00:03,000 --> 00:00:03,000\nZero duration.\n\n3\n00:00:04,000 --> 00:00:05,000\n<i></i>\n'.encode('cp1252'))
   warnings=[];cues=import_subtitles(p,warnings=warnings)
   self.assertEqual(cues[0].text,'Uma lâmina.');self.assertEqual(len(cues),1);self.assertEqual(len(warnings),2)
 def test_adjustable_filters_and_cleanup_on_failure(self):
  from types import SimpleNamespace
  from unittest.mock import MagicMock
  from describer.services import google_request
  client=MagicMock();client.files.upload.return_value=SimpleNamespace(name='files/fixture',state=SimpleNamespace(name='ACTIVE'))
  client.models.generate_content.side_effect=ValueError('provider fixture failure')
  settings=copy.deepcopy(DEFAULTS);settings.update(gemini_key='fixture',safety_block_none=True,temperature=.7)
  with patch('google.genai.Client',return_value=client),self.assertRaises(ValueError):google_request('fixture.mp4','test',settings,threading.Event(),lambda _:None)
  config=client.models.generate_content.call_args.kwargs['config'];self.assertEqual(len(config.safety_settings),4);self.assertEqual(config.temperature,.7)
  client.files.delete.assert_called_once_with(name='files/fixture');client.close.assert_called_once()
 def test_control_languages(self):
  self.assertEqual(len(TRANSLATIONS),len(LANGUAGES)-1)
  for language,entries in TRANSLATIONS.items():self.assertEqual(set(entries),set(KEYS),language)

if __name__=='__main__':unittest.main()
