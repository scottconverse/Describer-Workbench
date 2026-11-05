"""Build Mac-bundled FFmpeg/x264 from pinned source and retain corresponding source."""
import hashlib
import json
import os
import subprocess
import sys
import tarfile
from pathlib import Path

SOURCES=[('ffmpeg-9.0.2.tar.xz','https://ffmpeg.org/releases/ffmpeg-9.0.2.tar.xz','8c3850283eb25fa026482078a04051e0be17347b09ef81a0849bec15a96e002e'),('x264-31e19f9.tar.gz','https://codeload.github.com/mirror/x264/tar.gz/31e19f92f00c7003fa115047ce50978bc98c3a0d','d053c9d86988d6bc78237ca5205865c5ddf99c98ef4cd9927eec8f6d388f6dd9'),('lame-3.100.tar.gz','https://download.videolan.org/pub/contrib/lame/lame-3.100.tar.gz','ddfe36cab873794038ae2c1210557ad34857a4b6bdc515785d1da9e175b1da1e')]


def main():
    assert sys.platform=='darwin','Linux uses package-managed FFmpeg; Windows is unchanged.'
    root=Path.cwd();prefix=root/'unix-media';sources=prefix/'sources';sources.mkdir(parents=True,exist_ok=True)
    work=root/'build-unix/media';work.mkdir(parents=True,exist_ok=True)
    extracted={}
    for name,url,expected in SOURCES:
        archive=sources/name
        if not archive.exists():
            print('Downloading pinned source:',url,flush=True)
            subprocess.run(['curl','--fail','--location','--retry','2','--retry-all-errors','--connect-timeout','30','--max-time','180','--output',str(archive),url],check=True)
        assert hashlib.sha256(archive.read_bytes()).hexdigest()==expected,name
        with tarfile.open(archive) as source:
            target=work/name.split('.')[0];target.mkdir(exist_ok=True)
            source.extractall(target,filter='data');extracted[name]=next(p for p in target.iterdir() if p.is_dir())
    env=dict(os.environ,PKG_CONFIG_PATH=str(prefix/'lib/pkgconfig'))
    jobs=str(min(4,os.cpu_count() or 2))
    def run(args,cwd):subprocess.run(args,cwd=cwd,env=env,check=True)
    x264=extracted[SOURCES[1][0]]
    run(['./configure','--prefix='+str(prefix),'--enable-static','--disable-shared','--enable-pic','--disable-cli','--disable-asm','--disable-opencl'],x264)
    run(['make','-j'+jobs],x264);run(['make','install'],x264)
    lame=extracted[SOURCES[2][0]]
    run(['./configure','--prefix='+str(prefix),'--disable-shared','--enable-static','--disable-frontend','--disable-decoder','--disable-dependency-tracking','--with-pic','CFLAGS=-O2 -std=gnu99 -Wno-error=implicit-function-declaration'],lame)
    run(['make','-j'+jobs],lame);run(['make','install'],lame)
    ffmpeg=extracted[SOURCES[0][0]]
    arguments=['./configure','--prefix='+str(prefix),'--enable-gpl','--enable-libx264','--enable-libmp3lame','--enable-zlib','--pkg-config-flags=--static','--extra-cflags=-I'+str(prefix/'include'),'--extra-ldflags=-L'+str(prefix/'lib'),'--disable-autodetect','--disable-doc','--disable-debug','--disable-ffplay','--disable-x86asm','--disable-network','--disable-shared','--enable-static']
    run(arguments,ffmpeg);run(['make','-j'+jobs],ffmpeg);run(['make','install'],ffmpeg)
    license_dir=prefix/'licenses';license_dir.mkdir(exist_ok=True)
    for name,path in [('FFmpeg-GPLv2.txt',ffmpeg/'COPYING.GPLv2'),('x264-GPLv2.txt',x264/'COPYING'),('LAME-LGPL.txt',lame/'COPYING')]:
        (license_dir/name).write_bytes(path.read_bytes())
    (sources/'build_unix_media.py').write_bytes(Path(__file__).read_bytes())
    (prefix/'build-receipt.json').write_text(json.dumps({'sources':SOURCES,'configure':arguments,'media_binaries':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (prefix/'bin').glob('*') if p.name in ('ffmpeg','ffprobe')}},indent=2))


if __name__=='__main__':main()
