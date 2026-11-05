"""GUI-thread regression for worker completion, without cloud or modal prompts."""
import tempfile,time,unittest
from pathlib import Path
from PySide6.QtCore import QThread
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QDialog,QFormLayout,QLabel
from describer.app import Window

class WorkerGuiTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
 def test_completion_runs_on_gui_thread(self):
  with tempfile.TemporaryDirectory() as tmp:
   w=Window(Path(tmp)/'settings.json');w.settings.data['sounds']=False;calls=[];errors=[];w.error=errors.append
   stages=[];w.stage_update_job=lambda data,folder:stages.append((data,folder,w.thread is None))
   def complete(result):
    calls.append((result,QThread.currentThread()==self.app.thread()));w.pending_update=({'version':'fixture'},'fixture-folder')
   w.job(lambda c,l:42,complete)
   deadline=time.monotonic()+5
   while (w.thread is not None or not calls) and time.monotonic()<deadline:self.app.processEvents();QTest.qWait(10)
   self.assertEqual(calls,[(42,True)]);self.assertEqual(errors,[]);self.assertIsNone(w.thread)
   self.assertEqual(stages,[({'version':'fixture'},'fixture-folder',True)])
   w.dirty=False;w.close();self.app.processEvents()
 def test_offline_controls_and_answer_insertion(self):
  from describer.services import Settings
  from describer.i18n import translate,LANGUAGES
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'settings.json';w=Window(path);w.settings.data['sounds']=False
   w.project.duration=20;w.project.video='fixture'
   w.add_scene_answer('A person opens the door.',5)
   self.assertEqual((w.project.cues[0].start,w.project.cues[0].end),(5,9))
   w.project_path=Path(tmp)/'project.adproject';w.choose(0);w.text.setPlainText('A person closes the door.');self.assertTrue(w.save_project())
   from describer.project import Project
   self.assertEqual(Project.load(w.project_path).cues[0].text,'A person closes the door.')
   import logging
   w.settings.data.update(gemini_key='fixture-key',logging_level='WARNING');w.log('Hidden diagnostic fixture-key',logging.INFO)
   self.assertNotIn('Hidden diagnostic',(path.parent/'workbench.log').read_text())
   w.settings.data['logging_level']='DEBUG';w.log('Visible diagnostic fixture-key',logging.DEBUG)
   self.assertIn('Visible diagnostic [redacted]',(path.parent/'workbench.log').read_text());w.settings.data['gemini_key']=''
   w.volume.setValue(45);self.assertAlmostEqual(w.audio.volume(),.45,places=5);self.assertEqual(Settings(path).data['player_volume'],45)
   positions=[];w.player.setPosition=positions.append;w.slider.setRange(0,20000);w.slider.setValue(5000);self.assertEqual(positions,[5000])
   for language in LANGUAGES[1:]:
    w.settings.data['ui_language']=language;dialog=QDialog(w);form=QFormLayout(dialog);label=QLabel('Gemini API key');form.addRow(label);dialog.show();self.app.processEvents()
    self.assertEqual(label.text(),translate('Gemini API key',language));self.assertNotEqual(label.text(),'Gemini API key');dialog.close()
   w.dirty=False;w.close();self.app.processEvents()

if __name__=='__main__':unittest.main()

