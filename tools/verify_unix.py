"""Native add-on acceptance on disposable CI machines; no inference or user data."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def command(args,**kwargs):
    value=subprocess.run([str(a) for a in args],capture_output=True,text=True,timeout=kwargs.pop('timeout',180),**kwargs)
    assert value.returncode==0,(args,value.stdout[-3000:],value.stderr[-3000:])
    return value.stdout


def gui_source(out,source):
    from PySide6.QtCore import QTimer,QUrl
    from PySide6.QtWidgets import QApplication
    from describer.app import Window
    app=QApplication.instance() or QApplication([]);window=Window(out/'gui-settings.json')
    window.settings.data.update(sounds=False,auto_update_check=False)
    window.show();window.player.setSource(QUrl.fromLocalFile(str(source)))
    observed={}
    def finish():
        observed.update(visible=window.isVisible(),title=window.windowTitle(),duration=window.player.duration(),errors=window.player.errorString())
        window.player.stop();window.dirty=False;window.close()
    QTimer.singleShot(5000,finish);app.exec()
    assert observed['visible'] and observed['duration']>0,observed
    return observed


def packaged_gui(exe,out):
    env=dict(os.environ,DESCRIBER_HOME=str(out/'packaged-data'),XDG_DATA_HOME=str(out/'packaged-data'))
    # Settings use Path.home() on macOS; keep all acceptance state disposable.
    home=out/'packaged-home';home.mkdir();env['HOME']=str(home)
    with (out/'packaged-gui.log').open('wb') as log:
        process=subprocess.Popen([str(exe)],env=env,stdout=log,stderr=log)
        quit_detail=None
        try:
            time.sleep(8);assert process.poll() is None,'Packaged GUI exited during startup'
            if sys.platform=='darwin':
                # Address the exact owned executable. A directly launched Qt
                # bundle need not be registered under its path in LaunchServices.
                script='ObjC.import("AppKit"); var a=$.NSRunningApplication.runningApplicationWithProcessIdentifier('+str(process.pid)+'); if (ObjC.unwrap(a.executableURL.path)!=='+json.dumps(str(exe))+') throw new Error("Owned application identity mismatch"); JSON.stringify({pid:a.processIdentifier,bundle:ObjC.unwrap(a.bundleIdentifier),normal_quit_requested:Boolean(a.terminate)});'
                quit_detail=json.loads(command(['osascript','-l','JavaScript','-e',script]))
                assert quit_detail['normal_quit_requested'],quit_detail
            else:
                windows=command(['wmctrl','-lp'])
                match=next((row.split()[0] for row in windows.splitlines() if len(row.split())>2 and row.split()[2]==str(process.pid)),None)
                assert match,windows
                command(['wmctrl','-ic',match])
            process.wait(timeout=30);assert process.returncode==0,process.returncode
        finally:
            if process.poll() is None:process.terminate();process.wait(timeout=10)
    return {'startup_survived':True,'normal_quit_exit':process.returncode,'native_quit':quit_detail}


def install_source(out):
    mac=sys.platform=='darwin';home=out/'source-home';home.mkdir()
    env=dict(os.environ,HOME=str(home),XDG_DATA_HOME=str(home/'.local/share'))
    # Isolate application data without hiding the preinstalled build toolchain.
    # Rustup normally locates its toolchain relative to the caller's real HOME.
    for name,folder in [('RUSTUP_HOME','.rustup'),('CARGO_HOME','.cargo')]:env.setdefault(name,str(Path.home()/folder))
    command([sys.executable,'tools/install_unix.py'],env=env,timeout=600)
    root=home/('Library/Application Support/DescriberWorkbench/source-install' if mac else '.local/share/DescriberWorkbench/source-install')
    assert command([root/'venv/bin/describer','--version'],env=env).strip()=='0.6.1'
    launcher=home/('Applications/Describer Workbench.app/Contents/MacOS/DescriberWorkbench' if mac else '.local/share/applications/describer-workbench.desktop')
    assert launcher.is_file();return {'cli_version':'0.6.1','launcher':str(launcher)}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--payload',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--source-install',action='store_true');parser.add_argument('--source-install-only',action='store_true');args=parser.parse_args()
    assert sys.platform in ('darwin','linux')
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=True);payload=args.payload.resolve()
    if args.source_install_only:
        result={'platform':sys.platform,'scope':'source-install-only','source_install':install_source(out)}
        (out/'source-install-receipt.json').write_text(json.dumps(result,indent=2));print(json.dumps(result));return
    mac=sys.platform=='darwin'
    cli=payload/'Contents/MacOS/DescriberCLI' if mac else payload/'DescriberCLI'
    gui=payload/'Contents/MacOS/DescriberWorkbench' if mac else payload/'DescriberWorkbench'
    assert cli.is_file() and gui.is_file(),list(payload.rglob('DescriberCLI'))
    # Check the exact frozen modules, not just the version string.
    from PyInstaller.archive.readers import CArchiveReader
    modules={}
    for exe in (gui,cli):
        archive=CArchiveReader(str(exe));pyz=archive.open_embedded_archive('PYZ.pyz');count=0
        for path in Path('describer').rglob('*.py'):
            name='.'.join(path.with_suffix('').parts)
            if name.endswith('.__init__'):name=name[:-9]
            if name not in pyz.toc:continue
            frozen=pyz.extract(name);source=compile(path.read_bytes(),frozen.co_filename,'exec')
            # co_filename is normalized throughout recursively by compile.
            assert source==frozen,name
            count+=1
        assert count>=31,count
        modules[exe.name]={'application_modules':count,'sha256':hashlib.sha256(exe.read_bytes()).hexdigest()}
    from describer.services import Settings,run,tool
    from describer.platforms import native_engine
    from describer.windows_speech import windows_speech
    settings=Settings(out/'keyring-settings.json');settings.data['gemini_key']='describer-ci-fixture-not-a-real-key';settings.save()
    assert Settings(settings.path).data['gemini_key']==settings.data['gemini_key']
    saved=json.loads(settings.path.read_text())['gemini_key'];reference=base64.b64decode(saved).decode()
    if mac:from keyring.backends.macOS import Keyring
    else:from keyring.backends.SecretService import Keyring
    Keyring().delete_password('DescriberWorkbench',reference)
    voices=windows_speech(native_engine(),listing=True);assert voices
    native={'voice_engine':native_engine(),'windows_voice':voices[0]['id'],'allow_cloud':False,'speech_volume':100}
    # Complete export requires the explicitly provisioned speech detector on a
    # fresh machine, just as it does in the desktop. Exercise its frozen CLI.
    detector=json.loads(command([cli,'assets','provision','--destination',out/'yamnet.onnx']))
    native['sound_model']=detector['speech_model']
    config=out/'voice-settings.json';config.write_text(json.dumps(native))
    source=out/'source.mp4'
    run([tool('ffmpeg'),'-v','error','-y','-f','lavfi','-i','color=c=blue:s=160x120:r=30:d=5','-f','lavfi','-i','sine=frequency=220:duration=5','-c:v','libx264','-c:a','aac','-shortest',str(source)])
    voice=json.loads(command([cli,'--workspace',out/'voice','--settings',config,'voice',source,'--prompt','A blue screen.']))
    assert voice['state']=='done',voice
    audio=Path(voice['artifact']['path']);assert audio.stat().st_size>1000
    duration=float(json.loads(run([tool('ffprobe'),'-v','error','-show_format','-of','json',str(audio)]))['format']['duration'])
    project={'video':str(source),'duration':5,'cues':[{'start':1,'end':2,'text':'A blue screen.','event_start':1,'event_end':2,'disposition':'pause','audio':str(audio),'speech_seconds':duration,'audio_volume':100}]}
    batch=out/'batch.json';batch.write_text(json.dumps([{'project':project,'operation':'export','export_format':'mp4'}]))
    exported=json.loads(command([cli,'--workspace',out/'export','--settings',config,'batch',batch]))
    assert exported[0]['job']['state']=='done',exported
    artifact=Path(exported[0]['job']['artifact']['path'])
    run([tool('ffmpeg'),'-v','error','-i',str(artifact),'-f','null','-'])
    export_duration=float(json.loads(run([tool('ffprobe'),'-v','error','-show_format','-of','json',str(artifact)]))['format']['duration'])
    assert abs(export_duration-(5+duration))<.25,(duration,export_duration)
    mp3_batch=out/'mp3-batch.json';mp3_batch.write_text(json.dumps([{'project':project,'operation':'export','export_format':'mp3'}]))
    mp3=json.loads(command([cli,'--workspace',out/'mp3','--settings',config,'batch',mp3_batch]))
    assert mp3[0]['job']['state']=='done',mp3
    run([tool('ffmpeg'),'-v','error','-i',mp3[0]['job']['artifact']['path'],'-f','null','-'])
    command([sys.executable,'tools/verify_portable_interfaces.py','--cli',cli,'--output',out/'interfaces','--expected-version','0.6.1'])
    source_gui=gui_source(out,source)
    frozen_gui=packaged_gui(gui,out)
    if mac:
        command(['codesign','--verify','--deep','--strict',payload])
    source_install=install_source(out) if args.source_install else None
    result={'platform':sys.platform,'frozen_modules':modules,'secure_keyring_roundtrip':True,'native_voice':voices[0],'speech_detector_sha256':hashlib.sha256(Path(detector['speech_model']).read_bytes()).hexdigest(),'speech_seconds':duration,'extended_export_seconds':export_duration,'source_gui_media':source_gui,'packaged_gui':frozen_gui,'source_install':source_install,'publisher_certificate':False,'notarized':False,'limits':['CI virtual display/audio; no human listening or VoiceOver/Orca acceptance claimed.','Existing AI transports regression-tested; no live subscription inference on CI.']}
    (out/'receipt.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))


if __name__=='__main__':main()
