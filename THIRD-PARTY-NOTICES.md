# Third-party components

This project uses the components below. Original license texts are retained under third-party-licenses. Refer to each upstream license for redistribution obligations.

## macOS/Linux add-ons

The unchanged Windows release retains its original dependency/signing identity. Unix desktop packages additionally use keyring 25.7.0 (MIT, https://github.com/jaraco/keyring), with macOS Keychain or Linux Secret Service; Linux backend dependencies include SecretStorage and jeepney. Native macOS `say` is supplied by macOS. Linux FFmpeg/eSpeak NG/speech-dispatcher are package-manager dependencies, not bundled executables; consult their distribution license/source packages.

Mac packages bundle separately executed FFmpeg 9.0.2 and x264 revision31e19f92f00c7003fa115047ce50978bc98c3a0d built from pinned source with GPLv2 terms. Exact source archives, build script, configurations and retained license texts accompany each architecture's `unix-media-sources-<arch>.tar.gz`; the app also includes `unix-media/licenses` and `unix-media/build-receipt.json`. Upstream source: https://ffmpeg.org/releases/ and https://code.videolan.org/videolan/x264 . This does not change the Apache-2.0 license of the separate Workbench application.

- PySide6 6.12.0: LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only
- PySide6_Essentials 6.12.0: LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only
- PySide6_Addons 6.12.0: LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only
- shiboken6 6.12.0: LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only
- google-genai 2.34.0: Apache-2.0
- yt-dlp 2026.10.26: Unlicense
- httpx 0.28.1: BSD-3-Clause
- requests 2.34.2: Apache-2.0
- google-auth 2.62.0: Apache 2.0
- cryptography 50.0.2: Apache-2.0 OR BSD-3-Clause
- pydantic 2.14.2: MIT
- pyinstaller 6.22.3: GPLv2-or-later with a special exception which allows to use PyInstaller to build and distribute non-free programs (including commercial ones)

Qt upstream and source: https://www.qt.io/ and https://code.qt.io/ . PySide6 source browser: https://code.qt.io/cgit/pyside/pyside-setup.git/ .
FFmpeg: GPL build; see bin/FFmpeg-LICENSE.txt. Installed binary source/build provider: https://github.com/GyanD/codexffmpeg ; FFmpeg source: https://ffmpeg.org/download.html .
Original executable and bytecode are not distributed. Attributed Omni Describer translation catalogues from the supplied ZIP are included in assets/original-translations.json; original license retained in third-party-licenses/Omni-Describer.txt. Original author/contact: audioses.com, info@audioses.com. These are original contributors' translations, not newly claimed Workbench translations.
- accessible-output2 0.17: MIT; includes screen-reader controller DLLs supplied by that distribution. Upstream: https://github.com/accessibleapps/accessible_output2
- libloader 1.4.3: see retained license.
- platform-utils 1.6.3: see retained license.
- pywin32 312: see retained license.

## Shared engine additions (0.5.0)

- portalocker 3.2.0: retained distribution license/notice text in `third-party-licenses/portalocker.txt`.
- onnxruntime 1.31.1: retained distribution license/notice text in `third-party-licenses/onnxruntime.txt`.
- numpy 2.5.4: retained distribution license/notice text in `third-party-licenses/numpy.txt`.
- mcp 1.30.0: retained distribution license/notice text in `third-party-licenses/mcp.txt`.
- fastapi 0.162.0: retained distribution license/notice text in `third-party-licenses/fastapi.txt`.
- uvicorn 0.54.0: retained distribution license/notice text in `third-party-licenses/uvicorn.txt`.
- starlette 1.10.0: retained distribution license/notice text in `third-party-licenses/starlette.txt`.
- anyio 4.16.0: retained distribution license/notice text in `third-party-licenses/anyio.txt`.

The independent sound classifier adapts Apache-2.0 CivicCast code. The explicitly downloaded Google YAMNet model is hash-pinned and retains upstream Apache-2.0 terms; its weights are not embedded in the Python package. See NOTICE and `describer/engine/sound.py` for upstream attribution, model revision and SHA256. New Workbench code is Apache-2.0; this does not change the original translation restrictions or dependency terms.

Desktop interface resources: Barlow and Barlow Condensed (SIL OFL 1.1; license texts in assets/fonts). Lucide icons from v0.468.0, ISC license and Feather-derived MIT components; full upstream license in assets/icons/LICENSE. Sources: https://github.com/jpt/barlow and https://github.com/lucide-icons/lucide/tree/0.468.0 .
