$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (!(Test-Path '.venv\Scripts\python.exe')) { py -3 -m venv .venv }
& .venv\Scripts\python.exe -m pip install -e '.[desktop,http,mcp]' pyinstaller==6.22.3
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
New-Item -ItemType Directory -Force bin | Out-Null
foreach ($mediaTool in @('ffmpeg','ffprobe')) {
    if (!(Test-Path "bin\$mediaTool.exe")) {
        $mediaPath = (Get-Command "$mediaTool.exe" -ErrorAction Stop).Source
        $shimPath = [IO.Path]::ChangeExtension($mediaPath,'.shim')
        if (Test-Path $shimPath) {
            $shimText = Get-Content -LiteralPath $shimPath -Raw
            if ($shimText -match 'path = "([^"]+)"') { $mediaPath = $Matches[1] }
        }
        Copy-Item -LiteralPath $mediaPath -Destination "bin\$mediaTool.exe"
    }
}
& .venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --distpath dist --workpath build DescriberWorkbench.spec
if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
