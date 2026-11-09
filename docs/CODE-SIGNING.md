# Windows release signing

Documentation updated November 9, 2026. [Platform installation](UNIX-INSTALL.md) · [Architecture and trust boundaries](ARCHITECTURE.md).

Scott’s instruction to “push, merge, tag and publish” includes signing release executables/installers in his name using the established Azure Trusted Signing process. Unsigned Windows builds are not publication-ready. Scott explicitly authorized the macOS/Linux add-ons without publisher certificates; that exception does not weaken the Windows gate.

Use the existing `townlight/townlight` workflow `.github/workflows/sign-private-native-payload.yml` for exact prebuilt executables. Submit an unpublished draft intake with a hash-pinned schema-version-1 manifest, dispatch the workflow, and retrieve its private artifact. The Azure account is `scottconverse-signing`, profile `ScottConversePublic`, endpoint `https://wcus.codesigning.azure.net`. Credentials remain in the existing GitHub secrets and private keys remain in Azure HSMs. No local PFX or new credentials are needed.

The returned private receipt is signing evidence, not publication approval. Independently verify each returned file with `signtool verify /pa /v` and `Get-AuthenticodeSignature`; require Valid, CN=Scott Converse and a timestamp certificate. Preserve intake-to-signed hash mappings, confirm unchanged application contents, package only verified files, and generate checksums after signing. Verify the published download and installed signatures. Preserve rollback artifacts and user data.

## macOS and Linux

Mac packages have no Apple developer publisher certificate and no notarization. Their ad-hoc signatures verify local Mach-O/resource integrity only; never describe them as Scott Converse publisher-signed. Linux packages are unsigned. Both have their own release checksums and provenance. Use the normal macOS approval flow without disabling Gatekeeper globally.

A documentation-only package refresh must preserve application code. Windows signed EXE bytes and timestamp signatures stay unchanged and are independently reverified; recompute archive checksums after changing external manuals. On Mac, changes within the bundle require a native ad-hoc resource reseal and strict codesign verification. Record documentation revision and resulting package hashes separately from original application acceptance. No Azure signing run is needed for unchanged Windows executables.

For 0.5.2, the original unsigned package was replaced under the existing release at the owner’s instruction. Tag/source identity was preserved, and the release receipt records both original and signed identities.
