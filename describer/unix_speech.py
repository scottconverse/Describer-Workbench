"""Measured offline narration using installed macOS or eSpeak NG voices."""
import re
import shutil
import sys
import tempfile
from pathlib import Path


def unix_speech(engine,text='',output='',voice='',rate=0,cancel=None,listing=False,volume=100):
    from .services import run,tool
    expected='macOS' if sys.platform=='darwin' else 'eSpeak NG'
    if engine!=expected:raise ValueError('Select '+expected+' or OpenAI in Settings > Export voice.')
    program='/usr/bin/say' if engine=='macOS' else shutil.which('espeak-ng')
    if not program or not Path(program).is_file():raise RuntimeError('Install espeak-ng using your Linux package manager, then retry voice discovery.')
    if listing:
        raw=run([program,'-v','?'] if engine=='macOS' else [program,'--voices'],cancel).decode('utf-8',errors='replace')
        rows=[]
        for line in raw.splitlines():
            if engine=='macOS':
                match=re.match(r'(.+?)\s+([a-z]{2,3}[_-]\S+)\s+#',line)
                if match:rows.append({'id':match[1].strip(),'name':match[1].strip()+' ('+match[2]+')'})
            else:
                parts=line.split()
                if len(parts)>=5 and parts[0].isdigit():rows.append({'id':parts[4],'name':parts[3].replace('_',' ')+' ('+parts[1]+')'})
        return rows
    with tempfile.TemporaryDirectory(prefix='describer-native-') as directory:
        root=Path(directory);source=root/'speech.txt';source.write_text(text,encoding='utf-8')
        raw=root/('speech.aiff' if engine=='macOS' else 'speech.wav')
        speed=str(round(175*2**(max(-10,min(10,int(rate)))/10)))
        args=[program,'-f',str(source),'-r',speed,'-o',str(raw)] if engine=='macOS' else [program,'-f',str(source),'-s',speed,'-w',str(raw),'-a','100']
        if voice:args+=['-v',voice]
        run(args,cancel)
        run([tool('ffmpeg'),'-v','error','-y','-i',str(raw),'-af','volume='+str(max(0,min(100,float(volume)))/100),'-acodec','pcm_s16le',str(output)],cancel)
    if not Path(output).is_file() or Path(output).stat().st_size<44:raise RuntimeError('Native voice returned no audio.')
