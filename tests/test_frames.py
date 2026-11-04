"""Real FFmpeg regression: sampled image identity must match its reported time."""
import threading
import pytest
from describer.frames import sample
from describer.services import run,tool


@pytest.mark.parametrize('interval,expected',[(2,[0,2]),(1.17,[0,1.2,2.4,3.6])])
def test_exact_source_frames_and_nonintegral_timestamps(tmp_path,interval,expected):
    for i in range(120):
        (tmp_path/f'{i:03}.ppm').write_bytes(b'P6\n2 2\n255\n'+bytes([i,i,i])*4)
    source=tmp_path/'counter.mkv'
    run([tool('ffmpeg'),'-v','error','-y','-framerate','30','-i',str(tmp_path/'%03d.ppm'),'-c:v','ffv1',str(source)])
    output=tmp_path/'samples';output.mkdir()
    frames=sample(source,output,interval,threading.Event())
    assert [time for _,time in frames]==pytest.approx(expected,abs=.0001)
    for (path,time) in frames:
        raw=run([tool('ffmpeg'),'-v','error','-i',str(path),'-vf','scale=2:2','-pix_fmt','rgb24','-f','rawvideo','-'])
        # Lossy JPEG may move a channel by a few levels. The old sampler picked
        # frame29 for its purported0s image, rather than frame0.
        assert abs(raw[0]-round(time*30))<=3
