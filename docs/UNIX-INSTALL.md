# macOS and Linux add-ons to Describer Workbench 0.6.1

These are additional native builds. The existing signed Windows 0.6.1 release, default stable download, installed app and launcher remain unchanged. The add-on source and downloads have their own release identity, `v0.6.1-unix.1`. Application/project compatibility remains 0.6.1; Windows artifacts are not rebuilt or replaced.

## macOS download

Choose the Apple Silicon **arm64** DMG for M-series Macs, or the **x64** DMG for Intel Macs. The initial target is macOS 15 or later. Open the DMG and drag **Describer Workbench.app** to Applications. Keep the previous copy until the new one works. macOS native voices and bundled FFmpeg/FFprobe provide offline measured narration and media processing. Additional voices can be installed using macOS settings. Ollama, subscription CLIs, model weights and your videos are separate.

There is **no Apple developer certificate or notarization**. PyInstaller applies local ad-hoc signatures needed for Mach-O integrity; those do not identify Scott as an Apple-verified publisher. macOS can require its normal Privacy & Security approval to open a downloaded unsigned application. Do not disable Gatekeeper globally. Compare the download's SHA256 with the add-on release checksums before opening.

The DMG's app includes its CLI under `Contents/MacOS/DescriberCLI`. Run `"/Applications/Describer Workbench.app/Contents/MacOS/DescriberCLI" --help` in Terminal. Its API and MCP tools use the same engine as the desktop.

## Linux download

The initial package targets Ubuntu 24.04/Debian-compatible **x86-64** desktop systems. Install the `.deb` with `sudo apt install ./DescriberWorkbench-0.6.1-linux-x64.deb`. This resolves FFmpeg, eSpeak NG, speech-dispatcher and desktop library dependencies. Launch **Describer Workbench** from the application menu, or use `describer-workbench`; `describer` provides the CLI. Other distributions can use the portable tar archive with equivalent system dependencies; compatibility outside the tested distribution is not guaranteed. No Linux publisher certificate is supplied.

The tar archive extracts to `DescriberWorkbench/`; execute its `DescriberWorkbench` GUI or `DescriberCLI`. Install `ffmpeg`, `espeak-ng`, a functioning desktop audio system and a Secret Service provider using your distribution's package manager. Linux narration uses the installed eSpeak NG voice, generates a WAV and measures it before scheduling or export. Its voice quality differs from Windows/macOS voices.

## Install from the repository

Use Python 3.11 or later. On macOS install FFmpeg first, for example using Homebrew (`brew install ffmpeg`). On Ubuntu install `python3-venv ffmpeg espeak-ng speech-dispatcher gnome-keyring libxcb-cursor0 libxkbcommon-x11-0 libegl1 libopengl0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-render-util0 libxcb-xinerama0 libxcb-xkb1 libxcb-randr0 libxcb-shape0 libxcb-xfixes0 libxcb-sync1 libx11-xcb1 libfontconfig1 libfreetype6 libglib2.0-0t64 libatspi2.0-0t64` through apt. Then, from the repository checkout, run:

Intel Mac source installs may compile cryptography because its pinned version has no Intel Mac wheel. Install Xcode command-line tools (`xcode-select --install`) and Rust/OpenSSL/pkg-config (`brew install rust openssl@3 pkgconf`) first. Downloaded DMGs already contain their compiled dependencies and do not require this toolchain.

```sh
python3 tools/install_unix.py
```

This installs into a per-user isolated environment, copies the manuals and creates a launcher: `~/Applications/Describer Workbench.app` on macOS, or a desktop entry in `~/.local/share/applications` on Linux. It prints the CLI path. No Windows installation or user project is changed. To build distributable packages instead, install `.[desktop,http,mcp,dev]`, PyInstaller 6.22.3 and the documentation requirements; on Mac first run `python3 tools/build_unix_media.py`, then run `python3 -m PyInstaller --noconfirm --distpath dist-unix --workpath build-unix/app DescriberUnix.spec` and `python3 tools/package_unix.py --output unix-packages`.

## Settings, credentials and subscriptions

macOS data is under `~/Library/Application Support/DescriberWorkbench`. Linux uses `${XDG_DATA_HOME:-~/.local/share}/DescriberWorkbench`. `DESCRIBER_HOME` still overrides the durable engine/assets workspace. Projects remain user-selected files and refer to separately stored media and narration.

Saved API credentials use **macOS Keychain** or the Linux desktop **Secret Service**. Settings contain opaque references, not plaintext secrets. Unlock your desktop keyring before saving a key. Missing/locked keyrings fail with guidance; there is no plaintext fallback. Windows DPAPI files/keys and installed Windows voices do not migrate to Unix. Re-enter credentials and select an installed native voice on the destination. Old keyring entries may remain so recovery copies retain their references; manage retained entries through your operating system's keyring manager.

All existing analysis routes remain available where their external tools are installed. Native CLI sign-in opens Terminal or a Linux desktop terminal, using the CLI's own authentication. The shared OAuth gateway remains an external connection; this add-on neither migrates its token store nor restarts it. Use its address reachable from this computer and the existing client-key reference. Exact model IDs, consent and image tests remain unchanged. Windows paths to CLIs or media must be replaced with paths on the new machine.

Timed descriptions use measured native narration or explicit OpenAI speech. Live text uses Qt system speech or the active reader where supported. Screen-reader presence is not proof of VoiceOver/Orca end-to-end accessibility acceptance. Review factual drafts and timing before final export; the earlier documented model accuracy limits remain.

## Updates, recovery and removal

Unix **Check for updates** opens the release download page. Download the matching architecture, quit the app and replace it manually; retain the old copy for rollback. The Windows signed automatic updater is not used for Unix packages. Installing a new app must not overwrite settings, projects or the durable engine workspace.

Remove the downloaded Mac app or use `sudo apt remove describer-workbench` for the Linux package; user projects/settings remain. For repository installations, remove the printed source-install environment and its launcher after closing the app. Do not delete the surrounding DescriberWorkbench data directory if you want to retain settings, engine jobs or narration. Keychain/keyring entries are managed separately.

## Verification status

The [add-on release verification receipt](https://github.com/scottconverse/Describer-Workbench/releases/download/v0.6.1-unix.1/release-verification.json) records native build and installation checks on Ubuntu 24.04 x64 and macOS 15 Apple Silicon/Intel. Checks cover frozen application/source identity, native credential storage, measured offline narration, complete MP4/MP3 exports, GUI startup and normal close, CLI/HTTP/MCP, and repository installation with a launcher. The Linux package was also removed successfully, and the portable archive's executables match the installed DEB. Mac media tools in the actual DMGs have the matching CPU architecture and only macOS system-library dependencies.

Passed evidence was retained through narrowly scoped test and verification-script repairs; the receipt identifies each build, its acceptance jobs and those repairs. The bundled manuals are snapshots of their build source and point to the maintained guides and release evidence for later results. Native CI does not establish live provider entitlement, human-listening quality or VoiceOver/Orca usability. Earlier Windows release receipts apply only to their original Windows candidate. The Mac and Linux packages do not inherit Windows certificate claims.

Mac-bundled FFmpeg/x264 and the LAME MP3 encoder have retained GPL/LGPL licenses and corresponding source; the FFmpeg build uses GPL terms. These are components used as separate executables. Their licenses, exact source archives and build script accompany the add-on distribution; see `unix-media-sources-arm64.tar.gz` or `unix-media-sources-x64.tar.gz` and the media build receipt. Linux uses package-managed media/speech executables and their distribution's licenses/source packages.
