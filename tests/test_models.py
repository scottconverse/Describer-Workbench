import copy,io,json,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch
from describer.services import DEFAULTS,Settings,observe as generate,video_request
from describer import models


class OllamaTests(unittest.TestCase):
    def setUp(self):
        self.settings=copy.deepcopy(DEFAULTS);self.settings.update(analysis_provider='Ollama',ollama_model='gemma4:12b')
        self.cancel=threading.Event()

    def test_exact_model_capabilities_and_cloud_labels(self):
        rows=[{'name':'vision:local','capabilities':['vision'],'digest':'a'},
              {'name':'text:local','capabilities':['completion']},
              {'name':'alias','remote_host':'https://ollama.com','capabilities':['vision']}]
        with patch.object(models,'json_request',side_effect=[{'models':rows},{'models':[{'name':'vision:local'}]}]):
            result=models.discover(self.settings,self.cancel,lambda _:None)
        self.assertTrue(next(r for r in result if r['name']=='vision:local')['loaded'])
        self.assertFalse(next(r for r in result if r['name']=='text:local')['vision'])
        self.assertTrue(next(r for r in result if r['name']=='alias')['cloud'])
        with patch.object(models,'json_request',return_value={'capabilities':['completion']}),self.assertRaisesRegex(ValueError,'vision'):
            models.model_info(self.settings)

    def test_stream_completion_truncation_cancellation_and_1017_effort(self):
        event={'model':'gemma4:12b','message':{'content':'{"answer":"A rabbit."}'},'done':True,'done_reason':'stop'}
        def stream(e):return io.BytesIO((json.dumps(e)+'\n').encode())
        with patch.object(models,'open_request',return_value=stream(event)) as request:
            self.assertIn('rabbit',models.chat(self.settings,[],self.cancel,lambda _:None))
            self.assertIs(request.call_args.args[2]['think'],False)
            self.assertEqual(request.call_args.args[2]['options']['num_predict'],32768)
            self.assertEqual(request.call_args.args[2]['options']['num_ctx'],65536)
            self.assertNotIn('temperature',request.call_args.args[2]['options'])
            self.assertEqual(request.call_args.args[2]['format'],'json')
        with patch.object(models,'open_request',return_value=stream(event)) as request:
            models.chat(dict(self.settings,_ollama_info={'remote_host':'https://ollama.com'}),[],self.cancel,lambda _:None)
            self.assertNotIn('format',request.call_args.args[2])
        self.settings['ollama_model']='deepseek-v4.1-flash:1017-cloud'
        with patch.object(models,'open_request',return_value=stream(event)) as request:
            models.chat(self.settings,[],self.cancel,lambda _:None)
            self.assertEqual(request.call_args.args[2]['think'],'low')
            self.assertEqual(request.call_args.args[2]['options']['num_predict'],8192)
            self.assertNotIn('num_ctx',request.call_args.args[2]['options'])
            self.assertEqual(request.call_args.args[2]['options']['temperature'],.3)
            self.assertNotIn('format',request.call_args.args[2])
        with patch.object(models,'open_request',return_value=stream(dict(event,done_reason='length'))),self.assertRaisesRegex(ValueError,'cut off'):
            models.chat(self.settings,[],self.cancel,lambda _:None)
        self.cancel.set()
        with patch.object(models,'open_request') as request,self.assertRaises(InterruptedError):
            models.chat(self.settings,[],self.cancel,lambda _:None)
        request.assert_not_called()

    def test_range_offsets_and_no_silent_gemini_fallback(self):
        from describer.project import Project
        replies=['{"descriptions":[{"start":1,"end":3,"text":"A rabbit."}]}',
                 '{"descriptions":[{"start":1,"end":3,"text":"A butterfly."}]}',
                 '{"descriptions":[{"start":1,"end":3,"text":"A tree."}]}',
                 '{"descriptions":[{"start":1,"end":3,"text":"A flower."}]}']
        with patch('describer.services.segment') as segment,patch('describer.models.video_request',side_effect=replies) as request,patch('describer.services.google_request') as google:
            cues=generate(Project('fixture',140),self.settings,'',self.cancel,lambda _:None,60,60)
        self.assertEqual([c.start for c in cues],[61,77,93,109]);self.assertEqual([c.args[3] for c in segment.call_args_list],[16,16,16,12]);google.assert_not_called()
        instruction=request.call_args.args[1]
        self.assertNotIn('Place descriptions in dialogue gaps',instruction)
        self.assertNotIn('clearly spoken',instruction)
        self.assertIn('Keep name=null',instruction)
        with patch('describer.models.video_request',side_effect=ValueError('no vision')),patch('describer.services.google_request') as google,self.assertRaisesRegex(ValueError,'no vision'):
            video_request('fixture','',self.settings,self.cancel,lambda _:None)
        google.assert_not_called()

    def test_url_safeguards_and_settings_migration_secret_storage(self):
        for url in ['file:///c:/test','http://user:password@localhost:11434','http://example.org','https://example.org/v1']:
            with self.assertRaises(ValueError):models.endpoint(dict(ollama_url=url))
        self.assertEqual(models.endpoint({'ollama_url':'https://ollama.com/'}),'https://ollama.com')
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'settings.json';p.write_text('{"model":"original-gemini","gemini_key":"","player_volume":45}')
            settings=Settings(p);self.assertEqual(settings.data['model'],'original-gemini');self.assertEqual(settings.data['analysis_provider'],'Gemini')
            settings.data['ollama_key']='test-secret';settings.save()
            self.assertNotIn('test-secret',p.read_text());self.assertEqual(Settings(p).data['ollama_key'],'test-secret')
            self.assertEqual(Settings(p).data['player_volume'],45)


class PickerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app=QApplication.instance() or QApplication([])

    def test_provider_switch_preserves_gemini_and_exact_ollama_id(self):
        from describer.app import Window
        with tempfile.TemporaryDirectory() as tmp:
            w=Window(Path(tmp)/'settings.json');w.settings.data['sounds']=False
            picker=w.model_picker;original=w.settings.data['model']
            picker.provider.setCurrentText('Ollama')
            picker.discovered([{'name':'gemma4:12b','cloud':False,'vision':True,'loaded':False},
                               {'name':'deepseek-v4.1-flash:1017-cloud','cloud':True,'vision':True,'loaded':False}])
            picker.model.setCurrentIndex(picker.model.findData('gemma4:12b'))
            self.assertEqual(w.settings.data['ollama_model'],'gemma4:12b');self.assertIn('Local',picker.help.text())
            picker.model.setCurrentIndex(picker.model.findData('deepseek-v4.1-flash:1017-cloud'))
            self.assertIn('allowance',picker.help.text());self.assertEqual(w.settings.data['model'],original)
            picker.provider.setCurrentText('Gemini');self.assertEqual(picker.model.currentText(),original)
            w.dirty=False;w.close();self.app.processEvents()

    def test_regeneration_save_keeps_new_text_instead_of_stale_editor(self):
        from describer.app import Window
        from describer.project import Project,Cue
        with tempfile.TemporaryDirectory() as tmp:
            w=Window(Path(tmp)/'settings.json');w.settings.data['sounds']=False
            try:
                w.project=Project('fixture',100,[Cue(60,62,'Old description.')]);w.project_path=Path(tmp)/'result.adproject'
                w.refresh();w.table.selectRow(0);w.select_cue()
                w.generated(([Cue(60,62,'New generated description.')],''))
                self.assertTrue(w.save_project())
                self.assertEqual(Project.load(w.project_path).cues[0].text,'New generated description.')
            finally:w.dirty=False;w.close();self.app.processEvents()

    def test_selected_bunny_models_use_matched_profile_without_affecting_other_tags(self):
        from describer.app import Window
        tags=['gemma4:26b','qwen3.8:27b-q6_K-vision','qwen3.8:27b-q5_K_M-vision']
        with tempfile.TemporaryDirectory() as tmp:
            w=Window(Path(tmp)/'settings.json');w.settings.data['sounds']=False
            try:
                picker=w.model_picker;picker.provider.setCurrentText('Ollama')
                picker.discovered([dict(name=tag,cloud=False,vision=True,loaded=False) for tag in tags])
                for tag in tags:
                    with self.subTest(model=tag):
                        picker.model.setCurrentIndex(picker.model.findData(tag))
                        event={'model':tag,'message':{'content':'A rabbit.'},'done':True,'done_reason':'stop'}
                        logs=[]
                        with patch.object(models,'open_request',return_value=io.BytesIO((json.dumps(event)+'\n').encode())) as request:
                            models.chat(w.settings.data,[],threading.Event(),logs.append)
                        payload=request.call_args.args[2];self.assertEqual(payload['model'],tag)
                        if tag in tags[:2]:
                            self.assertIs(payload['think'],False)
                            self.assertEqual(payload['options'],{'num_predict':32768,'num_ctx':65536})
                            self.assertIn('context: 65536 tokens; thinking off',logs[0])
                        else:
                            self.assertNotIn('think',payload)
                            self.assertEqual(payload['options'],{'num_predict':8192,'temperature':.3})
            finally:w.dirty=False;w.close();self.app.processEvents()
