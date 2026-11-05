"""Offline playback queue and optional active screen-reader output."""
from .platforms import native_text


class PlaybackSpeech:
    def __init__(self, qt, settings, log):
        self.qt=qt;self.settings=settings;self.log=log;self.reader=None;self.reader_checked=False;self.reader_missing_reported=False

    def active_reader(self):
        if self.settings.get('playback_output')!='Screen reader':return None
        if not self.reader_checked:
            self.reader_checked=True
            try:
                self.reader=Readers()
            except Exception as exc:self.log(native_text('Screen reader unavailable; using Windows speech: ')+str(exc))
        if self.reader:
            output=self.reader.get_first_available_output()
            if output and not output.is_system_output():
                self.reader_missing_reported=False;return output
        if not self.reader_missing_reported:
            self.log(native_text('No active screen reader is available; using Windows speech for live text. Timed descriptions use measured narration audio.'))
            self.reader_missing_reported=True
        return None

    def say(self,text,interrupt=True):
        reader=self.active_reader()
        if reader:
            try:reader.speak(text,interrupt=interrupt);return
            except Exception as exc:self.log(native_text('Screen reader failed; using Windows speech: ')+str(exc))
        if interrupt:self.qt.stop();self.qt.say(text)
        else:self.qt.enqueue(text)

    def stop(self):
        self.qt.stop()
        reader=self.active_reader()
        if reader:
            try:reader.speak('',interrupt=True)
            except Exception:pass


class Readers:
    """Original output priority, with Qt as the asynchronous system fallback."""
    def __init__(self):
        import accessible_output2
        self.outputs=[]
        for cls in accessible_output2.get_output_classes():
            if cls.system_output:continue
            try:self.outputs.append(cls())
            except Exception:continue
    def get_first_available_output(self):
        for output in self.outputs:
            try:
                if output.is_active():return output
            except Exception:continue
        return None
