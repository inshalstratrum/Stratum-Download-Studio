# Phase 2A.7C — Controlled yt-dlp Capabilities

Status: complete on 2026-07-12. Baseline: `054dabf1360089d814f40a60ef88728cd7bfc845`. Scope is dependency-completion Phase B only; yt-dlp remains `2026.07.04` (`2026.7.4` on PyPI).

## Approved Python distributions

Every artifact is an official `https://pypi.org/` wheel, installed with exact pins, `--require-hashes`, `--only-binary=:all:`, isolated pip and no resolver drift. The authoritative name/version/hash/import mapping is in `stratum_dependency_policy.py`; `requirements-yt-dlp.lock` is validated against it.

| Distribution | Version | Accepted Windows/Python wheel SHA-256 |
|---|---:|---|
| brotli | 1.2.0 | `e7c0af964e0b4e3412a0ebf341ea26ec767fa0b4cf81abb5e897c9338b5ad6a3` |
| certifi | 2026.6.17 | `2227dcbaafe0d2f59279d1762ddddc37783ed4354594f194ffc31d20f41fc3db` |
| cffi | 2.0.0 | `203a48d1fb583fc7d78a4c6655692963b860a417c0528492a6bc21f1aaefab25` |
| charset-normalizer | 3.4.7 | `92a0a01ead5e668468e952e4238cccd7c537364eb7d851ab144ab6627dbbe12f` |
| curl-cffi | 0.15.0 | `5a0c1896a0d5a5ac1eb89cd24b008d2b718dd1df6fd2f75451b59ca66e49e572` |
| idna | 3.18 | `7f952cbe720b688055e3f87de14f5c3e5fdaa8bc3928985c4077ca689de849a2` |
| markdown-it-py | 4.2.0 | `9f7ebbcd14fe59494226453aed97c1070d83f8d24b6fc3a3bcf9a38092641c4a` |
| mdurl | 0.1.2 | `84008a41e51615a49fc9966191ff91509e3c40b939176e643fd50a5c2196b8f8` |
| mutagen | 1.48.1 | `4f077fe87d3fc7fba259aa63d8c026b18382ca6a42ef37c61e16f1b1b5b82fe7` |
| pycparser | 3.0 | `b727414169a36b7d524c1c3e31839a521725078d7b2ff038656844266160a992` |
| pycryptodomex | 3.23.0 | `52e5ca58c3a0b0bd5e100a9fbc8015059b05cffc6c66ce9d98b4b45e023443b9` |
| Pygments | 2.20.0 | `81a9e26dd42fd28a23a2d169d86d7ac03b46e2f8b59ed4698fb4785f946d0176` |
| requests | 2.34.2 | `2a0d60c172f83ac6ab31e4554906c0f3b3588d37b5cb939b1c061f4907e278e0` |
| rich | 15.0.0 | `33bd4ef74232fb73fe9279a257718407f169c09b78a87ad3d296f548e27de0bb` |
| urllib3 | 2.7.0 | `9fb4c81ebbb1ce9531cce37674bbc6f1360472bc18ca9a553ede278ef7276897` |
| websockets | 16.0 | `c0ee0e63f23914732c6d7e0cce24915c48f3f1512ec1d079ed01fc629dab269d` |
| yt-dlp | 2026.7.4 | `f11f2b11d5a8ac4059f9bdf29fa4407dc7c6bb00c5097e95ca22a7a9db518266` |
| yt-dlp-ejs | 0.8.0 | `79300e5fca7f937a1eeede11f0456862c1b41107ce1d726871e0207424f4bdb4` |

The versions are yt-dlp 2026.7.4's official `pin` and `pin-curl-cffi` metadata closure. `yt-dlp-ejs 0.8.0` matches that release exactly. Native wheel selection was CPython 3.14/Windows x86-64; universal or ABI3 wheels are used where officially published.

## Controlled Deno and runtime policy

`controlled-tools.json` allowlists Deno `2.8.3`, Windows `x86_64-pc-windows-msvc`, official release URL `https://github.com/denoland/deno/releases/download/v2.8.3/deno-x86_64-pc-windows-msvc.zip`, archive SHA-256 `7fdd1f42e6b0855421ecf27bb406e2492ade1087c85e30ebf0deab6280ea743c`, executable `deno.exe`, and executable SHA-256 `c5db43554211b07181bf92702789466d3403e450cffc09e123583f1c315063ec`. Provenance is the official Deno v2.8.3 GitHub release; licence is MIT.

The bootstrap accepts only that URL and hash, rejects any archive member other than `deno.exe`, and promotes the tool to ignored `.tools/deno/`. The Python API passes `js_runtimes={'deno': {'path': <exact controlled path>}}` and `remote_components=[]` to both metadata and download operations. No shell, PATH lookup, Node, Bun, QuickJS, ambient Deno, npm/GitHub remote EJS repository, or global curl impersonation is enabled. Local `yt-dlp-ejs` supplies both solver scripts.

## Bootstrap, policy and rollback

Run `powershell -ExecutionPolicy Bypass -File scripts/bootstrap_ytdlp.ps1`. Python wheels stage under `.deps-staging/`; Deno stages under `.tools-staging/`. All 18 versions, every wheel RECORD, root containment, required native/data payloads, Deno path/version/archive hash/executable hash and lock completeness must pass before both targets are promoted. A promotion failure restores prior bundles; staging is always cleaned. Existing `.deps-rollback/` retains the pre-promotion 2A.7B core bundle locally. Durable rollback is checkout of baseline `054dabf` followed by its bootstrap. Global Python, user site, PATH, registry and pip are never modified or upgraded.

The policy rejects absent, duplicate, unexpected, wrong-version, escaped, RECORD-invalid or incomplete distributions. Preloaded ambient approved module families are evicted before controlled import; excluded/plugin modules are rejected. `YTDLP_NO_PLUGINS=1` remains mandatory. Required CA (`certifi`), EJS scripts, Brotli/WebSocket/cffi/curl/Cryptodome native payloads are verified.

## Frozen collection and evidence

PyInstaller validates the controlled roots before analysis, copies all 18 controlled metadata sets, EJS and CA data, approved native modules, and Deno at portable `tools/deno/deno.exe`. A clean PyInstaller 6.20.0/Python 3.14.4 one-file development build passed. Recursive inspection found exact metadata and approved data/native entries; `Crypto`, `brotlicffi`, `secretstorage`, `xattr`, arbitrary plugins and remote components had zero entries. Extracted embedded Deno matched its executable hash and returned version 2.8.3.

The development EXE is 116,325,205 bytes versus 45,338,979 bytes in 2A.7B: +70,986,226 bytes (about 67.7 MiB). Repo-local installed payloads are 55,333,090 bytes for `.deps` and 101,070,112 bytes for Deno. Cryptodome runtime modules are included but its internal self-test tree is excluded. Temporary build/output directories were outside the repository and removed after evidence capture. This is not a signed or commercial release build.

## Tests and capability result

- 14 focused dependency/capability tests passed: exact lock/install/import inventory, frozen-layout metadata isolation, local EJS, explicit Deno, Brotli local HTTP decoding through Requests/urllib3, local WebSocket echo, curl-cffi inventory without forced impersonation, Cryptodome AES-128 non-DRM fixture and Mutagen.
- 20 existing focused metadata, format, quick/options download, cancellation and final verification contracts passed.
- Python compilation and installed distribution/RECORD/tool validation passed.
- One final full suite run passed: 267 tests.
- Clean frozen build, automated startup smoke, recursive archive inspection, excluded-entry search and embedded Deno execution passed.
- Automated tests make no claim about current live-site compatibility.

## Exclusions, licences and remaining gates

`brotlicffi` is the non-CPython alternative to approved Brotli; `Crypto` conflicts with approved `Cryptodome`; `secretstorage` and `xattr` are platform-specific and unnecessary on Windows. Bun is deprecated; QuickJS and ambient Node/Deno are unnecessary alternatives. Nightly/master packages, arbitrary plugins/components and unpinned dependencies remain forbidden. These exclusions do not declare corresponding product media features unsupported.

Wheel metadata records MIT, MPL-2.0, BSD, Apache-2.0, Unlicense and related notices; `yt-dlp-ejs` additionally bundles MIT/ISC components. Mutagen is GPL-2.0-or-later and remains a commercial redistribution/legal decision gate. curl-cffi native redistribution notices and the complete release SBOM/licence/branding review also remain mandatory. FFmpeg/FFprobe provenance remains a separate existing release blocker.

Manual checks still required: YouTube standard; owned/public modern-EJS YouTube; Vimeo; public Facebook, Instagram Reel, TikTok and X split A/V; an identified Brotli/curl-cffi case; authorized AES-128 non-DRM HLS; Quick Download; Download with Options; final playback and FFprobe. Later canonical-social-routing failures may remain and must be recorded accurately.

Gallery-dl, Poppler, FFmpeg replacement, normalized media model, unified/canonical social routing, filename redesign, picker redesign, authenticated-site automation, new UI, Phase 2B, licensing implementation and commercial packaging were not started.
