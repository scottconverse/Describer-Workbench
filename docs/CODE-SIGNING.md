# Windows release signing

Scott’s instruction to “push, merge, tag and publish” includes signing release executables/installers in his name using the established Azure Trusted Signing process. Unsigned builds are not publication-ready.

Use the existing `townlight/townlight` workflow `.github/workflows/sign-private-native-payload.yml` for exact prebuilt executables. Submit an unpublished draft intake with a hash-pinned schema-version-1 manifest, dispatch the workflow, and retrieve its private artifact. The Azure account is `scottconverse-signing`, profile `ScottConversePublic`, endpoint `https://wcus.codesigning.azure.net`. Credentials remain in the existing GitHub secrets and private keys remain in Azure HSMs. No local PFX or new credentials are needed.

The returned private receipt is signing evidence, not publication approval. Independently verify each returned file with `signtool verify /pa /v` and `Get-AuthenticodeSignature`; require Valid, CN=Scott Converse and a timestamp certificate. Preserve intake-to-signed hash mappings, confirm unchanged application contents, package only verified files, and generate checksums after signing. Verify the published download and installed signatures. Preserve rollback artifacts and user data.

For 0.5.2, the original unsigned package was replaced under the existing release at the owner’s instruction. Tag/source identity was preserved, and the release receipt records both original and signed identities.
