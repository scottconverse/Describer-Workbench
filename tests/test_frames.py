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
        # Compare against the exact source frame through the same JPEG path.
        # FFmpeg versions differ in RGB/YUV range conversion (Ubuntu's black
        # fixture decodes as 4), so a fixed RGB tolerance measures the codec,
        # not frame identity. The old sampler's frame29 still differs from 0.
        reference=tmp_path/f'reference-{round(time*30)}.jpg'
        run([tool('ffmpeg'),'-v','error','-y','-i',str(source),
             '-vf',f'select=eq(n\\,{round(time*30)}),scale=640:-2',
             '-frames:v','1','-q:v','3',str(reference)])
        expected_raw=run([tool('ffmpeg'),'-v','error','-i',str(reference),'-vf','scale=2:2','-pix_fmt','rgb24','-f','rawvideo','-'])
        assert raw==expected_raw
