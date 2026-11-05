"""Refresh external documentation in an accepted native package, without rebuilding code."""
import argparse
import hashlib
import json
import struct
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path


ROOT=Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.file_digest(path.open('rb'),'sha256').hexdigest()


def documents():
    files={'README.md':(ROOT/'README.md').read_bytes().replace(b'\r\n',b'\n')}
    for p in sorted((ROOT/'docs').rglob('*')):
        if p.is_file():files[p.relative_to(ROOT).as_posix()]=p.read_bytes().replace(b'\r\n',b'\n')
    return files


def manifest():
    return {'application_version':'0.6.1','documentation_source':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            'scope':'Documentation only; original application acceptance retained. Windows signed executables unchanged. Mac ad-hoc integrity only.',
            'sha256':{name:hashlib.sha256(data).hexdigest() for name,data in documents().items()}}


def install_docs(folder):
    for name,data in documents().items():
        p=folder/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
    (folder/'documentation-manifest.json').write_text(json.dumps(manifest(),indent=2)+'\n',encoding='utf-8')


def unsigned_macho(path):
    """Compare executable instructions/data while allowing a new resource seal."""
    data=bytearray(path.read_bytes())
    assert data[:4]==b'\xcf\xfa\xed\xfe','Expected little-endian 64-bit Mach-O'
    offset=32;cut=len(data)
    for _ in range(struct.unpack_from('<I',data,16)[0]):
        command,size=struct.unpack_from('<II',data,offset)
        if command==0x1d:
            cut=struct.unpack_from('<I',data,offset+8)[0]
            data[offset+8:offset+16]=b'\0'*8
        offset+=size
    return hashlib.sha256(data[:cut]).hexdigest()


def snapshot(folder,mac=False):
    result={}
    for p in sorted(folder.rglob('*')):
        relative=p.relative_to(folder).as_posix()
        if p.is_symlink():result[relative]={'link':str(p.readlink())};continue
        if not p.is_file():continue
        if relative.startswith('_internal/docs/') or relative in ('_internal/README.md','_internal/documentation-manifest.json'):continue
        if mac and (relative.startswith('Contents/Resources/docs/') or relative in ('Contents/Resources/README.md','Contents/Resources/documentation-manifest.json','Contents/_CodeSignature/CodeResources')):continue
        value=unsigned_macho(p) if mac and relative=='Contents/MacOS/DescriberWorkbench' else digest(p)
        result[relative]={'sha256':value,'mode':p.stat().st_mode & 0o777}
    return result


def run(*args):subprocess.run(args,check=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();source=args.input.resolve();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    original=digest(source)
    with tempfile.TemporaryDirectory(prefix='describer-docs-') as tmp:
        stage=Path(tmp)
        if source.suffix=='.dmg':
            assert sys.platform=='darwin'
            mount=stage/'mount';mount.mkdir()
            run('hdiutil','attach','-readonly','-nobrowse','-mountpoint',str(mount),str(source))
            payload=stage/'payload';payload.mkdir();app=payload/'Describer Workbench.app'
            try:run('ditto',str(mount/app.name),str(app))
            finally:run('hdiutil','detach',str(mount))
            before=snapshot(app,mac=True)
            install_docs(app/'Contents/Resources')
            run('codesign','--force','--sign','-',str(app))
            run('codesign','--verify','--deep','--strict','--verbose=2',str(app))
            assert snapshot(app,mac=True)==before,'Non-documentation app content changed'
            # Validate actual executable launch after resealing, without opening an editor or provider.
            run(str(app/'Contents/MacOS/DescriberCLI'),'--help')
            (payload/'Applications').symlink_to('/Applications')
            (payload/'INSTALL.md').write_bytes(documents()['docs/UNIX-INSTALL.md'])
            run('hdiutil','create','-volname','Describer Workbench','-srcfolder',str(payload),'-format','UDZO',str(out/source.name))
            seal='Ad-hoc resource seal verified; no Apple publisher certificate or notarization'
        elif source.suffix=='.deb':
            assert sys.platform=='linux'
            package=stage/'package';run('dpkg-deb','--raw-extract',str(source),str(package))
            app=package/'opt/describer-workbench';before=snapshot(package)
            # Exclude just these external guide paths from the whole-DEB invariant.
            before={k:v for k,v in before.items() if not k.startswith('opt/describer-workbench/_internal/docs/') and k not in ('opt/describer-workbench/_internal/README.md','opt/describer-workbench/_internal/documentation-manifest.json')}
            install_docs(app/'_internal')
            after={k:v for k,v in snapshot(package).items() if not k.startswith('opt/describer-workbench/_internal/docs/') and k not in ('opt/describer-workbench/_internal/README.md','opt/describer-workbench/_internal/documentation-manifest.json')}
            assert after==before,'Non-documentation DEB content changed'
            run('dpkg-deb','--root-owner-group','--build',str(package),str(out/source.name))
            seal='Unsigned Linux; all non-documentation payload bytes and modes unchanged'
        else:
            assert sys.platform=='linux' and source.name.endswith('.tar.gz')
            with tarfile.open(source) as archive:archive.extractall(stage,filter='data')
            app=stage/'DescriberWorkbench';before=snapshot(app)
            install_docs(app/'_internal')
            assert snapshot(app)==before,'Non-documentation tar content changed'
            with tarfile.open(out/source.name,'w:gz') as archive:archive.add(app,arcname=app.name)
            seal='Unsigned Linux; all non-documentation payload bytes and modes unchanged'
        receipt={'documentation':manifest(),'original_package':{'name':source.name,'sha256':original},
                 'refreshed_package':{'name':source.name,'sha256':digest(out/source.name)},
                 'preservation':seal,'preserved_entries':len(before),'application_rebuilt':False}
        (out/(source.name+'.docs.json')).write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':main()
