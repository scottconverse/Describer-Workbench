"""Package an already-built platform add-on; never builds or replaces Windows."""
import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    assert sys.platform in ('darwin','linux')
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    root=Path.cwd();arch='arm64' if platform.machine() in ('arm64','aarch64') else 'x64'
    label='DescriberWorkbench-0.6.1-'+('macos' if sys.platform=='darwin' else 'linux')+'-'+arch
    if sys.platform=='darwin':
        stage=out/'dmg-content';stage.mkdir();shutil.copytree(root/'dist-unix/Describer Workbench.app',stage/'Describer Workbench.app',symlinks=True)
        (stage/'Applications').symlink_to('/Applications');shutil.copy2(root/'docs/UNIX-INSTALL.md',stage/'INSTALL.md')
        archive=out/(label+'.dmg')
        subprocess.run(['hdiutil','create','-volname','Describer Workbench','-srcfolder',str(stage),'-format','UDZO',str(archive)],check=True)
        with tarfile.open(out/('unix-media-sources-'+arch+'.tar.gz'),'w:gz') as target:
            target.add(root/'unix-media/sources',arcname='sources')
            target.add(root/'unix-media/build-receipt.json',arcname='build-receipt.json')
            target.add(root/'unix-media/licenses',arcname='licenses')
    else:
        archive=out/(label+'.tar.gz')
        with tarfile.open(archive,'w:gz') as target:target.add(root/'dist-unix/DescriberWorkbench',arcname='DescriberWorkbench')
        package=out/'deb-root';application=package/'opt/describer-workbench';application.parent.mkdir(parents=True)
        shutil.copytree(root/'dist-unix/DescriberWorkbench',application,symlinks=True)
        binaries=package/'usr/bin';binaries.mkdir(parents=True)
        for name,entry in [('describer-workbench','DescriberWorkbench'),('describer','DescriberCLI')]:
            launcher=binaries/name;launcher.write_text('#!/bin/sh\nexec /opt/describer-workbench/'+entry+' "$@"\n');launcher.chmod(0o755)
        desktop=package/'usr/share/applications';desktop.mkdir(parents=True)
        (desktop/'describer-workbench.desktop').write_text('[Desktop Entry]\nType=Application\nName=Describer Workbench\nExec=/usr/bin/describer-workbench\nTerminal=false\nCategories=AudioVideo;Accessibility;\n')
        control=package/'DEBIAN';control.mkdir()
        (control/'control').write_text('Package: describer-workbench\nVersion: 0.6.1-1\nArchitecture: amd64\nMaintainer: Scott Converse\nSection: video\nPriority: optional\nDepends: ffmpeg, espeak-ng, libxcb-cursor0, libxcb-icccm4, libxcb-image0, libxcb-keysyms1, libxcb-render-util0, libxcb-xinerama0, libxcb-xkb1, libxcb-randr0, libxcb-shape0, libxcb-xfixes0, libxcb-sync1, libx11-xcb1, libfontconfig1, libfreetype6, libglib2.0-0t64, libatspi2.0-0t64, libxkbcommon-x11-0, libegl1, libopengl0, libdbus-1-3, speech-dispatcher\nRecommends: gnome-keyring\nDescription: Audio description creation and review workbench\n')
        subprocess.run(['dpkg-deb','--root-owner-group','--build',str(package),str(out/(label+'.deb'))],check=True)
    artifacts=[p for p in out.iterdir() if p.suffix in ('.dmg','.deb','.gz') and p.is_file()]
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in artifacts}
    (out/'SHA256SUMS.txt').write_text(''.join(value+'  '+name+'\n' for name,value in hashes.items()))
    (out/'package-receipt.json').write_text(json.dumps({'platform':sys.platform,'architecture':arch,'sha256':hashes,'publisher_certificate':False,'notarized':False,'windows_modified':False},indent=2))


if __name__=='__main__':main()
