import copy,json,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from describer.services import Settings,DEFAULTS,generate
from describer.project import normalize_generated,scene_data
from describer.playback_speech import PlaybackSpeech
from describer.compatibility import read_original_settings,read_prompt_presets

class AuditFixTests(unittest.TestCase):
 def test_queue_does_not_drop_second_cue(self):
  qt=Mock();speech=PlaybackSpeech(qt,{},lambda _:None)
  speech.say('First',False);speech.say('Second',False)
  self.assertEqual([c.args[0] for c in qt.enqueue.call_args_list],['First','Second']);qt.say.assert_not_called()
  speech.say('Interrupt',True);qt.stop.assert_called_once();qt.say.assert_called_once_with('Interrupt')
 def test_screen_reader_dispatch_and_fallback(self):
  qt=Mock();reader=Mock();reader.is_system_output.return_value=False
  speech=PlaybackSpeech(qt,{'playback_output':'Screen reader'},lambda _:None);speech.reader_checked=True;speech.reader=Mock();speech.reader.get_first_available_output.return_value=reader
  speech.say('A person enters.',False);reader.speak.assert_called_once_with('A person enters.',interrupt=False);qt.enqueue.assert_not_called()
  reader.speak.side_effect=RuntimeError('reader gone');speech.say('Fallback',False);qt.enqueue.assert_called_once_with('Fallback')
 def test_generated_cleanup_keeps_valid_rows(self):
  logs=[];cues=normalize_generated([{'start':1,'end':3,'text':'Door.'},{'start':'bad','end':5,'text':'Bad'},{'start':2,'end':4,'text':'Person.'},{'start':5,'end':6,'text':'Person.'},{'start':7,'end':6,'text':'Leaves.'}],10,logs.append)
  self.assertEqual([c.text for c in cues],['Door.','Person.','Leaves.']);self.assertGreater(cues[1].start,cues[0].end);self.assertGreater(cues[2].end,cues[2].start);self.assertEqual(len(logs),2)
 def test_scene_validation_and_unique_grid(self):
  data=scene_data({'layout':'A room.','objects':[{'name':'Door','description':'Red','x':5,'y':5},{'name':'Chair','description':'Blue','x':5,'y':5},{'name':'Invalid','description':'','x':float('nan'),'y':1}]})
  self.assertEqual(len(data['objects']),2);self.assertEqual(len({(o['x'],o['y']) for o in data['objects']}),2)
  with self.assertRaises(ValueError):scene_data({'objects':None})
 def test_disabled_chunking_and_verbosity(self):
  from describer.project import Project
  settings=copy.deepcopy(DEFAULTS);settings.update(chunking=False,chunk=15,verbosity='Detailed')
  with patch('describer.services.segment') as segment,patch('describer.services.google_request',return_value='{"descriptions":[{"start":1,"end":2,"text":"Door."}]}') as request:
   generate(Project('fixture',46),settings,'',threading.Event(),lambda _:None)
  self.assertEqual(segment.call_count,1);self.assertIn('6-12 words',request.call_args.args[1])
 def test_damaged_settings_preserved_and_recovered(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'settings.json';path.write_bytes(b'{broken');settings=Settings(path)
   self.assertTrue(settings.load_warning);self.assertEqual(path.read_bytes(),b'{broken');settings.save()
   backup=list(path.parent.glob('settings.json.recovery-*'));self.assertEqual(len(backup),1);self.assertEqual(backup[0].read_bytes(),b'{broken')
 def test_old_fernet_and_prompt_import_readonly(self):
  from cryptography.fernet import Fernet
  from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
  from cryptography.hazmat.primitives import hashes
  import base64
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);salt=b'fixture-salt';(root/'key.salt').write_bytes(salt)
   kdf=PBKDF2HMAC(algorithm=hashes.SHA256(),length=32,salt=salt,iterations=480000)
   raw=Fernet(base64.urlsafe_b64encode(kdf.derive(b'fixture-machine'))).encrypt(json.dumps({'enable_video_chunking':False,'gemini_description_verbosity':'Detailed','user_gemini_api_key':'never-import'}).encode())
   path=root/'settings.dat';path.write_bytes(raw)
   with patch('describer.compatibility.hardware_password',return_value=b'fixture-machine'):
    self.assertEqual(read_original_settings(path),{'chunking':False,'verbosity':'Detailed'})
   self.assertEqual(path.read_bytes(),raw)
   path=root/'prompts.json';path.write_text(json.dumps({'English':[{'name':'Custom','prompt':'Describe gestures.'}]}))
   self.assertEqual(read_prompt_presets(path),{'English':{'Custom':'Describe gestures.'}})

if __name__=='__main__':unittest.main()
