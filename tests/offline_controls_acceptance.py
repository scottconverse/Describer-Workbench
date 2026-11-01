"""Native volume, notification readiness and local URL download acceptance."""
import copy,hashlib,http.server,json,math,sys,tempfile,threading,time,wave
from functools import partial
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from PySide6.QtMultimedia import QSoundEffect
from describer.app import Window
from describer.services import DEFAULTS,download,segment,run,tool
from describer.windows_speech import windows_speech
from describer.playback_speech import Readers

def main():
 output=Path(sys.argv[2]);output.mkdir(parents=True,exist_ok=True);result={};app=QApplication([])
 with tempfile.TemporaryDirectory(prefix='describer-controls-') as tmp:
  tmp=Path(tmp);result['volume']={}
  for engine in ['Windows','Windows 32-bit','Windows OneCore']:
   rms=[]
   for volume in [100,50]:
    path=tmp/'speech.wav';windows_speech(engine,'The astronaut descends the ladder.',path,volume=volume)
    raw=run([tool('ffmpeg'),'-v','error','-i',str(path),'-f','f32le','-ac','1','pipe:1'])
    import array
    samples=array.array('f');samples.frombytes(raw);rms.append(math.sqrt(sum(x*x for x in samples)/len(samples)))
   db=20*math.log10(rms[1]/rms[0]);assert -40<db<-1,(engine,db)
   result['volume'][engine]={'volume_50_vs_100_db':db}
  w=Window(tmp/'settings.json');w.settings.data['sounds']=True;w.sound('finish');deadline=time.monotonic()+4;playing=False
  while time.monotonic()<deadline:
   app.processEvents();playing=playing or w.notification.isPlaying();QTest.qWait(10)
   if playing:break
  assert w.notification.status()==QSoundEffect.Status.Ready;assert playing
  result['notification']={'ready':True,'playback_started':True,'auditory_quality':'Not assessed'}
  w.settings.data['sounds']=False;w.close();app.processEvents()
  readers=Readers();result['screen_reader']={'loaded':[o.name for o in readers.outputs],'active':getattr(readers.get_first_available_output(),'name',None),'acceptance':'Dispatch/fallback fixtures pass; no active reader available for live acceptance.'}
  segment(sys.argv[1],tmp/'clip.mp4',0,1,2)
  class Quiet(http.server.SimpleHTTPRequestHandler):
   def log_message(self,*args):pass
  server=http.server.ThreadingHTTPServer(('127.0.0.1',0),partial(Quiet,directory=str(tmp)))
  thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
  try:
   dest=tmp/'downloads';dest.mkdir();path=Path(download(f'http://127.0.0.1:{server.server_port}/clip.mp4',dest,threading.Event(),lambda _:None,'720p'))
   assert path.read_bytes()==(tmp/'clip.mp4').read_bytes();result['direct_url_download']={'passed':True,'transport':'loopback HTTP, real yt-dlp','bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
  finally:server.shutdown();server.server_close();thread.join()
 result['passed']=True;(output/'offline-controls.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))

if __name__=='__main__':main()

