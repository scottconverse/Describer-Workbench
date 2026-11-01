"""Real desktop library matrix. No cloud requests or API keys used."""
import copy,hashlib,json,sys,tempfile,threading,time
from pathlib import Path
from PySide6.QtCore import QUrl
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from PySide6.QtMultimedia import QMediaPlayer,QVideoSink,QAudioOutput
from describer.project import Project,Cue,import_subtitles
from describer.services import DEFAULTS,probe,segment,export_audio,run,tool
from describer.windows_speech import windows_speech
from describer.app import Window
from describer.i18n import LANGUAGES,apply_language,translate


def main():
 library=Path(sys.argv[1]);output=Path(sys.argv[2]);output.mkdir(parents=True,exist_ok=True);app=QApplication([])
 def digest(path):
  with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
 identity={str(p):digest(p) for p in sorted(Path('describer').glob('*.py'))}
 inputs={str(p.relative_to(library)):digest(p) for p in sorted(library.rglob('*')) if p.suffix.lower() in ['.mp4','.mov','.mkv','.avi','.webm','.srt','.vtt','.flac']}
 result={'source_sha256':identity,'input_sha256':inputs,'videos':[],'subtitles':[],'audio_layouts':[],'native_voices':[],'cloud':'Not called. No API keys used.'}
 def save(): (output/'library-matrix.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf8')
 with tempfile.TemporaryDirectory(prefix='describer-library-') as tmp:
  tmp=Path(tmp);settings=copy.deepcopy(DEFAULTS);settings['sounds']=False
  for source in sorted(library.rglob('*')):
   if source.suffix.lower() not in ['.mp4','.mov','.mkv','.avi','.webm']:continue
   duration=probe(source);clip=tmp/'clip.mp4';segment(source,clip,min(10,duration/2),3,2)
   info=json.loads(run([tool('ffprobe'),'-v','error','-show_streams','-of','json',str(source)]))
   player=QMediaPlayer();sink=QVideoSink();audio=QAudioOutput();audio.setMuted(True);player.setAudioOutput(audio);player.setVideoSink(sink)
   frames=[];sink.videoFrameChanged.connect(lambda f:frames.append(f.isValid()) if f.isValid() else None)
   player.setSource(QUrl.fromLocalFile(str(source)));player.play()
   for _ in range(60):
    app.processEvents();QTest.qWait(100)
    if len(frames)>=2:break
   item={'file':str(source.relative_to(library)),'duration':duration,'source_audio_channels':[s.get('channels') for s in info['streams'] if s['codec_type']=='audio'],'transcode_duration':probe(clip),'qt_frames':len(frames),'playback_error':player.errorString()}
   player.stop();player.setSource(QUrl());app.processEvents();QTest.qWait(100)
   assert item['qt_frames']>0,item
   # Original multichannel audio is retained by trimming without stereo downmix.
   original=tmp/'original.mkv';run([tool('ffmpeg'),'-v','error','-y','-ss','10','-i',str(source),'-t','3','-c','copy',str(original)])
   settings=copy.deepcopy(DEFAULTS);settings['sounds']=False
   mixed=tmp/'mixed.mp3';export_audio(Project(str(original),3,[Cue(.5,2.5,'A person moves across the scene.')]),mixed,settings,threading.Event(),lambda _:None)
   j=json.loads(run([tool('ffprobe'),'-v','error','-show_format','-show_streams','-of','json',str(mixed)]))
   item['export_duration']=float(j['format']['duration']);item['export_channels']=j['streams'][0]['channels'];assert 2.9<item['export_duration']<3.3
   result['videos'].append(item);save();print(item,flush=True)
  for source in sorted(library.rglob('*')):
   if source.suffix.lower() not in ['.srt','.vtt']:continue
   warnings=[];cues=import_subtitles(source,warnings=warnings);target=tmp/'roundtrip.srt';Project(cues=cues).export(target);restored=import_subtitles(target)
   assert [(round(c.start*1000),round(c.end*1000),c.text) for c in cues]==[(round(c.start*1000),round(c.end*1000),c.text) for c in restored]
   result['subtitles'].append({'file':str(source.relative_to(library)),'cues':len(cues),'roundtrip':True,'warnings':warnings})
  save()
  for engine in ['Windows','Windows 32-bit','Windows OneCore']:
   voices=windows_speech(engine,listing=True);assert voices
   wav=tmp/(engine+'.wav');windows_speech(engine,'The astronaut steps onto the moon.',wav,voices[0]['id'])
   result['native_voices'].append({'engine':engine,'host_bits':voices[0]['bits'],'available':[v['name'] for v in voices],'tested':voices[0]['name'],'audio_bytes':wav.stat().st_size})
  # M&E and separate stereo / 5.1 mixes from library, with a video stream.
  visual=tmp/'visual.mp4';segment(next(library.rglob('Apollo_11_moonwalk_montage_720p~orig.mov')),visual,0,3,2,silent=True)
  silent_info=json.loads(run([tool('ffprobe'),'-v','error','-show_streams','-of','json',str(visual)]));assert not any(s['codec_type']=='audio' for s in silent_info['streams'])
  for source in sorted(library.rglob('*.flac')):
   fixture=tmp/'layout.mkv';run([tool('ffmpeg'),'-v','error','-y','-i',str(visual),'-i',str(source),'-map','0:v','-map','1:a','-t','3','-c','copy',str(fixture)])
   j=json.loads(run([tool('ffprobe'),'-v','error','-show_streams','-of','json',str(fixture)]));channels=next(s['channels'] for s in j['streams'] if s['codec_type']=='audio')
   export_audio(Project(str(fixture),3,[Cue(.5,2.5,'The scene changes.')]),tmp/'layout.mp3',settings,threading.Event(),lambda _:None)
   mixed=json.loads(run([tool('ffprobe'),'-v','error','-show_streams','-show_format','-of','json',str(tmp/'layout.mp3')]))
   assert mixed['streams'][0]['channels']==2;assert 2.9<float(mixed['format']['duration'])<3.3
   result['audio_layouts'].append({'file':str(source.relative_to(library)),'input_channels':channels,'export_channels':2,'export_duration':float(mixed['format']['duration']),'export_passed':True})
  export_audio(Project(str(visual),3,[Cue(.5,2.5,'An astronaut stands on the moon.')]),output/'silent-source-described.mp3',settings,threading.Event(),lambda _:None)
  result['silent_source_export']=True;save()
  w=Window(tmp/'ui-settings.json');w.settings.data['sounds']=False;w.set_video(visual);w.generated(([Cue(.5,2.5,'An astronaut stands on the moon.')],'Astronaut: White spacesuit.'))
  assert 'spacesuit' in w.project.glossary
  for language in LANGUAGES:
   apply_language(w,language);assert w.table.horizontalHeaderItem(0).text()==translate('Start',language)
  apply_language(w,'English');w.show();app.processEvents();w.grab().save(str(output/'workbench-0.3.png'));w.dirty=False;w.close();app.processEvents();QTest.qWait(500);app.processEvents()
 result['passed']=True;save();print('PASSED',len(result['videos']),'videos',len(result['subtitles']),'subtitles',len(result['audio_layouts']),'audio mixes',flush=True)

if __name__=='__main__':main()
