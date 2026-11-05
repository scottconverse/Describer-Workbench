"""Native Windows voices through isolated PowerShell processes of the selected bitness."""
import json
import os
import tempfile
from pathlib import Path

SCRIPT = r'''
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
$d=Get-Content -Raw -Encoding UTF8 -LiteralPath $args[0] | ConvertFrom-Json
if ($d.engine -eq 'Windows OneCore') {
 Add-Type -AssemblyName System.Runtime.WindowsRuntime
 $null=[Windows.Media.SpeechSynthesis.SpeechSynthesizer,Windows.Media.SpeechSynthesis,ContentType=WindowsRuntime]
 $voices=[Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices
 if ($d.list) { @($voices | ForEach-Object { @{id=$_.Id;name=$_.DisplayName;bits=[IntPtr]::Size*8} }) | ConvertTo-Json -Compress; exit }
 $s=[Windows.Media.SpeechSynthesis.SpeechSynthesizer]::new()
 try {
  if ($d.voice) { $v=$voices | Where-Object Id -eq $d.voice; if (!$v) {throw 'Selected voice is not installed'}; $s.Voice=$v }
  $s.Options.AudioVolume=[double]$d.volume/100
  $s.Options.SpeakingRate=[Math]::Pow(2,[double]$d.rate/10)
  $op=$s.SynthesizeTextToStreamAsync($d.text)
  $m=[System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {$_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'} | Select-Object -First 1
  $task=$m.MakeGenericMethod([Windows.Media.SpeechSynthesis.SpeechSynthesisStream]).Invoke($null,@($op)); $task.Wait(); $stream=$task.Result
  $reader=[Windows.Storage.Streams.DataReader,Windows.Storage.Streams,ContentType=WindowsRuntime]::new($stream)
  $op=$reader.LoadAsync([uint32]$stream.Size);$t=$m.MakeGenericMethod([uint32]).Invoke($null,@($op));$t.Wait()
  $bytes=New-Object byte[] $stream.Size;$reader.ReadBytes($bytes);[IO.File]::WriteAllBytes($d.output,$bytes)
  $reader.Dispose();$stream.Dispose()
 } finally {$s.Dispose()}
} else {
 $s=New-Object -ComObject SAPI.SpVoice
 $voices=$s.GetVoices()
 if ($d.list) { $a=@();for($i=0;$i -lt $voices.Count;$i++) {$v=$voices.Item($i);$a+=@{id=$v.Id;name=$v.GetDescription();bits=[IntPtr]::Size*8}};ConvertTo-Json -InputObject $a -Compress;exit }
 if ($d.voice) { $found=$false;for($i=0;$i -lt $voices.Count;$i++) {if($voices.Item($i).Id -eq $d.voice){$s.Voice=$voices.Item($i);$found=$true;break}};if(!$found){throw 'Selected voice is not installed'} }
 $s.Volume=[int]$d.volume
 $s.Rate=[int]$d.rate
 $stream=New-Object -ComObject SAPI.SpFileStream
 try {$stream.Open($d.output,3,$false);$s.AudioOutputStream=$stream;$null=$s.Speak($d.text)} finally {$stream.Close()}
}
'''

def windows_speech(engine='Windows', text='', output='', voice='', rate=0, cancel=None, listing=False, volume=100):
    if engine in ('macOS','eSpeak NG'):
        from .unix_speech import unix_speech
        return unix_speech(engine,text,output,voice,rate,cancel,listing,volume)
    from .services import run
    root=Path(os.environ.get('WINDIR',r'C:\Windows'))
    shell=root/('SysWOW64' if engine=='Windows 32-bit' else 'System32')/'WindowsPowerShell/v1.0/powershell.exe'
    if not shell.is_file():raise RuntimeError(f'Windows speech host unavailable: {shell}')
    with tempfile.TemporaryDirectory(prefix='describer-native-') as tmp:
        tmp=Path(tmp);script=tmp/'speech.ps1';payload=tmp/'payload.json'
        script.write_text(SCRIPT,encoding='utf-8-sig')
        payload.write_text(json.dumps(dict(engine=engine,text=text,output=str(output),voice=voice,rate=max(-10,min(10,int(rate))),volume=max(0,min(100,int(volume))),list=listing)),encoding='utf8')
        result=run([str(shell),'-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',str(script),str(payload)],cancel)
        if listing:
            voices=json.loads(result.decode('utf-8-sig') or '[]')
            return voices if isinstance(voices,list) else [voices]
    if not Path(output).is_file() or Path(output).stat().st_size<44:raise RuntimeError('Windows voice returned no audio.')
