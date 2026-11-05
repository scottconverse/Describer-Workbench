"""Install from this repository into an isolated per-user environment and launcher."""
import os
import plistlib
import shlex
import shutil
import subprocess
import sys
from pathlib import Path


def main():
    if sys.platform not in ('darwin','linux'):raise SystemExit('This installer is only for macOS and Linux. The Windows release is unchanged.')
    repo=Path(__file__).resolve().parents[1]
    root=(Path.home()/'Library/Application Support' if sys.platform=='darwin' else Path(os.environ.get('XDG_DATA_HOME',str(Path.home()/'.local/share'))))/'DescriberWorkbench/source-install'
    environment=root/'venv'
    subprocess.run([sys.executable,'-m','venv',str(environment)],check=True)
    python=environment/'bin/python'
    subprocess.run([str(python),'-m','pip','install',str(repo)+'[desktop,http,mcp]'],check=True)
    root.mkdir(parents=True,exist_ok=True);shutil.copytree(repo/'docs',root/'docs',dirs_exist_ok=True);shutil.copy2(repo/'README.md',root/'README.md')
    command=environment/'bin/describer-workbench'
    if sys.platform=='darwin':
        app=Path.home()/'Applications/Describer Workbench.app';contents=app/'Contents';(contents/'MacOS').mkdir(parents=True,exist_ok=True)
        launcher=contents/'MacOS/DescriberWorkbench';launcher.write_text('#!/bin/sh\nexec '+shlex.quote(str(command))+' "$@"\n');launcher.chmod(0o755)
        with (contents/'Info.plist').open('wb') as stream:plistlib.dump({'CFBundleExecutable':'DescriberWorkbench','CFBundleIdentifier':'org.describer.workbench.source','CFBundleName':'Describer Workbench','CFBundlePackageType':'APPL','CFBundleShortVersionString':'0.7.0'},stream)
        print('Installed:',app)
    else:
        applications=Path(os.environ.get('XDG_DATA_HOME',str(Path.home()/'.local/share')))/'applications';applications.mkdir(parents=True,exist_ok=True)
        # Desktop Entry Exec has its own quoting grammar, independent of the shell.
        escaped=str(command).replace('\\','\\\\').replace('"','\\"').replace('`','\\`').replace('$','\\$').replace('%','%%')
        (applications/'describer-workbench.desktop').write_text('[Desktop Entry]\nType=Application\nName=Describer Workbench\nExec="'+escaped+'"\nTerminal=false\nCategories=AudioVideo;Accessibility;\n',encoding='utf-8')
        print('Installed:',applications/'describer-workbench.desktop')
    print('CLI:',environment/'bin/describer')
    print('User settings/projects were not replaced. See docs/UNIX-INSTALL.md for system speech/media dependencies and uninstall instructions.')


if __name__=='__main__':main()
