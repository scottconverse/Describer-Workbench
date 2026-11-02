# v0.5.1 release acceptance

This release packages the redesigned native PySide6 editor. The shared engine and developer contracts remain compatible with v0.5.0. CivicCast release-candidate and live data are untouched.

## Changes

Start, the inline description editor, Scene and Glossary tabs, Draft/Export/Settings dialogs, button hierarchy, light/dark themes and local fonts/icons follow the Industry handoff. The timeline includes zoom, scroll, follow, selection seeking, eight visible-range thumbnails, legible ruler labels and striped sped-up blocks. Only unresolved descriptions show Mark as checked. Export discovers installed voices for the selected engine; editorial prompts accept multiple lines.

## Verification and provenance

The redesigned implementation passed 51 tests plus 3 subtests locally and on Windows CI. Final affected UI/documentation checks passed 12 tests. Native captures verified eight distinct thumbnail frames and two installed Windows voices with isolated fixture settings. Screenshots use manually entered descriptions, not accuracy evidence. Qt window captures exclude the native video surface; decoded frames were checked separately.

The release asset `release-verification.json` records final candidate identity, rebuilt executable hashes, frozen module/source comparison and packaged desktop/CLI/HTTP/MCP acceptance. `SHA256SUMS.txt` covers downloadable packages and contained executables. GitHub CI checks the release source, tests, documentation and Python packages. Both landing pages and guides carry this version.

## Recovery and limits

The Windows ZIP is a complete unsigned portable folder. Extract it separately, keep `_internal` beside the executables, and retain the previous folder until the new app works. Packaging does not overwrite saved projects, settings or media.

Three 120-second native Blender vision/classifier/narration checks belong to [v0.5.0 engine acceptance](V050-ACCEPTANCE.md) and are reused for unchanged engine behavior. No full-film accuracy percentage, WCAG certification, new cloud-provider acceptance or screen-reader end-to-end validation is claimed.
