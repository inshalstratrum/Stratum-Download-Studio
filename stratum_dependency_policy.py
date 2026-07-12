"""Controlled dependency and tool loading for Stratum's yt-dlp integration."""

from __future__ import annotations

import base64
import csv
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys


APPROVED_YT_DLP_RELEASE = "2026.07.04"
CONTROLLED_DEPENDENCY_DIRECTORY = ".deps"
CONTROLLED_TOOLS_DIRECTORY = ".tools"

# This is the authoritative approved Python distribution manifest. The hashes
# identify the exact official PyPI wheels accepted by the lock file.
APPROVED_DISTRIBUTIONS = {
    "brotli": ("1.2.0", "e7c0af964e0b4e3412a0ebf341ea26ec767fa0b4cf81abb5e897c9338b5ad6a3", ("brotli",)),
    "certifi": ("2026.6.17", "2227dcbaafe0d2f59279d1762ddddc37783ed4354594f194ffc31d20f41fc3db", ("certifi",)),
    "cffi": ("2.0.0", "203a48d1fb583fc7d78a4c6655692963b860a417c0528492a6bc21f1aaefab25", ("cffi", "_cffi_backend")),
    "charset-normalizer": ("3.4.7", "92a0a01ead5e668468e952e4238cccd7c537364eb7d851ab144ab6627dbbe12f", ("charset_normalizer",)),
    "curl-cffi": ("0.15.0", "5a0c1896a0d5a5ac1eb89cd24b008d2b718dd1df6fd2f75451b59ca66e49e572", ("curl_cffi",)),
    "idna": ("3.18", "7f952cbe720b688055e3f87de14f5c3e5fdaa8bc3928985c4077ca689de849a2", ("idna",)),
    "markdown-it-py": ("4.2.0", "9f7ebbcd14fe59494226453aed97c1070d83f8d24b6fc3a3bcf9a38092641c4a", ("markdown_it",)),
    "mdurl": ("0.1.2", "84008a41e51615a49fc9966191ff91509e3c40b939176e643fd50a5c2196b8f8", ("mdurl",)),
    "mutagen": ("1.48.1", "4f077fe87d3fc7fba259aa63d8c026b18382ca6a42ef37c61e16f1b1b5b82fe7", ("mutagen",)),
    "pycparser": ("3.0", "b727414169a36b7d524c1c3e31839a521725078d7b2ff038656844266160a992", ("pycparser",)),
    "pycryptodomex": ("3.23.0", "52e5ca58c3a0b0bd5e100a9fbc8015059b05cffc6c66ce9d98b4b45e023443b9", ("Cryptodome",)),
    "pygments": ("2.20.0", "81a9e26dd42fd28a23a2d169d86d7ac03b46e2f8b59ed4698fb4785f946d0176", ("pygments",)),
    "requests": ("2.34.2", "2a0d60c172f83ac6ab31e4554906c0f3b3588d37b5cb939b1c061f4907e278e0", ("requests",)),
    "rich": ("15.0.0", "33bd4ef74232fb73fe9279a257718407f169c09b78a87ad3d296f548e27de0bb", ("rich",)),
    "urllib3": ("2.7.0", "9fb4c81ebbb1ce9531cce37674bbc6f1360472bc18ca9a553ede278ef7276897", ("urllib3",)),
    "websockets": ("16.0", "c0ee0e63f23914732c6d7e0cce24915c48f3f1512ec1d079ed01fc629dab269d", ("websockets",)),
    "yt-dlp": ("2026.7.4", "f11f2b11d5a8ac4059f9bdf29fa4407dc7c6bb00c5097e95ca22a7a9db518266", ("yt_dlp",)),
    "yt-dlp-ejs": ("0.8.0", "79300e5fca7f937a1eeede11f0456862c1b41107ce1d726871e0207424f4bdb4", ("yt_dlp_ejs",)),
}
APPROVED_YT_DLP_PACKAGE_VERSION = APPROVED_DISTRIBUTIONS["yt-dlp"][0]
APPROVED_YT_DLP_WHEEL_SHA256 = APPROVED_DISTRIBUTIONS["yt-dlp"][1]
APPROVED_CONTROLLED_MODULES = tuple(
    module for _version, _wheel_hash, modules in APPROVED_DISTRIBUTIONS.values() for module in modules
)
INTENTIONALLY_EXCLUDED_MODULES = ("Crypto", "brotlicffi", "secretstorage", "xattr")
FORBIDDEN_AMBIENT_RUNTIME_MODULES = ("yt_dlp_plugins",)

REQUIRED_PAYLOADS = {
    "brotli": ("_brotli*.pyd",),
    "certifi": ("certifi/cacert.pem",),
    "cffi": ("_cffi_backend*.pyd",),
    "curl-cffi": ("curl_cffi/_wrapper*.pyd",),
    "pycryptodomex": ("Cryptodome/**/*.pyd",),
    "websockets": ("websockets/speedups*.pyd",),
    "yt-dlp-ejs": ("yt_dlp_ejs/**/*.js",),
}


class DependencyPolicyError(RuntimeError):
    """Raised when a controlled dependency or tool cannot be proven."""


def _normalize_name(name: str) -> str:
    return name.lower().replace("_", "-")


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _verify_wheel_record(distribution: importlib.metadata.Distribution, root: Path) -> None:
    record = distribution.read_text("RECORD")
    if not record:
        raise DependencyPolicyError(f"Controlled {distribution.metadata['Name']} installation has no wheel RECORD.")
    checked = 0
    for relative_name, encoded_hash, declared_size in csv.reader(record.splitlines()):
        if not encoded_hash:
            continue
        algorithm, separator, expected = encoded_hash.partition("=")
        if separator != "=" or algorithm != "sha256":
            raise DependencyPolicyError(f"Unsupported RECORD hash for {relative_name!r}.")
        record_path = PurePosixPath(relative_name)
        if record_path.parts[:2] == ("..", "..") and record_path.parts[2:3] in (("bin",), ("share",)):
            candidate = root.joinpath(*record_path.parts[2:]).resolve()
        else:
            candidate = Path(distribution.locate_file(relative_name)).resolve()
        if not _is_within(candidate, root) or not candidate.is_file():
            raise DependencyPolicyError(f"Controlled file is missing or escaped its root: {relative_name!r}.")
        payload = candidate.read_bytes()
        actual = base64.urlsafe_b64encode(hashlib.sha256(payload).digest()).rstrip(b"=").decode("ascii")
        if actual != expected or (declared_size and len(payload) != int(declared_size)):
            raise DependencyPolicyError(f"Controlled file failed RECORD verification: {relative_name!r}.")
        checked += 1
    if checked == 0:
        raise DependencyPolicyError(f"Controlled {distribution.metadata['Name']} RECORD has no verifiable files.")


def verify_lock_file(lock_file: Path) -> None:
    text = lock_file.read_text(encoding="utf-8")
    if "--only-binary=:all:" not in text:
        raise DependencyPolicyError("Controlled lock does not require binary wheels.")
    for name, (version, wheel_hash, _modules) in APPROVED_DISTRIBUTIONS.items():
        if f"{name}=={version}" not in text or f"--hash=sha256:{wheel_hash}" not in text:
            raise DependencyPolicyError(f"Controlled lock is missing the approved {name} pin/hash.")


def verify_controlled_install(
    root: Path, *, verify_record: bool = True, allow_unrelated: bool = False,
) -> dict[str, importlib.metadata.Distribution]:
    root = root.resolve()
    if not root.is_dir():
        raise DependencyPolicyError(f"Controlled dependency directory is missing: {root}")
    found: dict[str, list[importlib.metadata.Distribution]] = {}
    for distribution in importlib.metadata.distributions(path=[str(root)]):
        found.setdefault(_normalize_name(distribution.metadata.get("Name") or ""), []).append(distribution)
    unexpected = set(found) - set(APPROVED_DISTRIBUTIONS)
    if unexpected and not allow_unrelated:
        raise DependencyPolicyError(f"Unexpected controlled distributions: {', '.join(sorted(unexpected))}.")
    verified = {}
    for name, (version, _wheel_hash, _modules) in APPROVED_DISTRIBUTIONS.items():
        matches = found.get(name, [])
        if len(matches) != 1:
            raise DependencyPolicyError(f"Expected one controlled {name} distribution; found {len(matches)}.")
        distribution = matches[0]
        if distribution.version != version:
            raise DependencyPolicyError(f"Unapproved {name} version {distribution.version!r}; required {version}.")
        if verify_record:
            _verify_wheel_record(distribution, root)
        for pattern in REQUIRED_PAYLOADS.get(name, ()):
            if not any(path.is_file() and _is_within(path, root) for path in root.glob(pattern)):
                raise DependencyPolicyError(f"Controlled {name} payload is missing: {pattern}.")
        verified[name] = distribution
    return verified


def _tool_manifest(repository_root: Path) -> dict:
    manifest_path = repository_root / "controlled-tools.json"
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))["deno"]
    except (OSError, KeyError, ValueError, TypeError) as exc:
        raise DependencyPolicyError("Controlled Deno manifest is missing or invalid.") from exc


def controlled_deno_path() -> Path:
    frozen = bool(getattr(sys, "frozen", False))
    if frozen:
        return Path(getattr(sys, "_MEIPASS")) / "tools" / "deno" / "deno.exe"
    return Path(__file__).resolve().parent / CONTROLLED_TOOLS_DIRECTORY / "deno" / "deno.exe"


def verify_controlled_deno(repository_root: Path, executable: Path | None = None) -> Path:
    manifest = _tool_manifest(repository_root)
    executable = (executable or controlled_deno_path()).resolve()
    expected_root = executable.parent.resolve()
    if executable.name != manifest["expected_executable"] or not _is_within(executable, expected_root):
        raise DependencyPolicyError("Controlled Deno executable has an invalid path.")
    if not executable.is_file():
        raise DependencyPolicyError("Controlled Deno is missing. Run scripts/bootstrap_ytdlp.ps1.")
    actual_hash = hashlib.sha256(executable.read_bytes()).hexdigest()
    if actual_hash != manifest["executable_sha256"]:
        raise DependencyPolicyError("Controlled Deno executable failed SHA-256 verification.")
    try:
        result = subprocess.run(
            [str(executable), "--version"], capture_output=True, text=True, timeout=15,
            check=False, shell=False, env={"PATH": "", "DENO_NO_UPDATE_CHECK": "1"},
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise DependencyPolicyError("Controlled Deno could not be verified.") from exc
    if result.returncode != 0 or not result.stdout.startswith(f"deno {manifest['version']}"):
        raise DependencyPolicyError("Controlled Deno reported an unapproved version.")
    return executable


def controlled_yt_dlp_options() -> dict:
    """Options shared by metadata and download calls; no ambient/remote runtime discovery."""
    return {"js_runtimes": {"deno": {"path": str(controlled_deno_path())}}, "remote_components": []}


def load_controlled_yt_dlp():
    """Load only the approved repo-local or PyInstaller-collected dependency set."""
    frozen = bool(getattr(sys, "frozen", False))
    repository_root = Path(__file__).resolve().parent
    root = Path(getattr(sys, "_MEIPASS")) if frozen else repository_root / CONTROLLED_DEPENDENCY_DIRECTORY
    verify_controlled_install(root, verify_record=not frozen, allow_unrelated=frozen)
    verify_controlled_deno(repository_root, controlled_deno_path())

    # An embedding host (including pytest) may have imported a common package
    # first. Evict that family so it cannot satisfy the controlled import.
    for module_name in APPROVED_CONTROLLED_MODULES:
        existing = sys.modules.get(module_name)
        existing_path = Path(getattr(existing, "__file__", "")) if existing else None
        if existing_path and not _is_within(existing_path, root):
            for loaded_name in tuple(sys.modules):
                if loaded_name == module_name or loaded_name.startswith(f"{module_name}."):
                    sys.modules.pop(loaded_name, None)
    for module_name in INTENTIONALLY_EXCLUDED_MODULES + FORBIDDEN_AMBIENT_RUNTIME_MODULES:
        existing = sys.modules.get(module_name)
        existing_path = Path(getattr(existing, "__file__", "")) if existing else None
        if existing_path and not _is_within(existing_path, root):
            raise DependencyPolicyError(f"Refusing ambient module {module_name} at {existing_path.resolve()}.")

    os.environ["YTDLP_NO_PLUGINS"] = "1"
    original_path = list(sys.path)
    try:
        if not frozen:
            sys.path[:] = [
                str(root), *(entry for entry in original_path if "site-packages" not in entry.lower()
                             and "dist-packages" not in entry.lower() and Path(entry or ".").resolve() != root),
            ]
        import yt_dlp
    finally:
        if not frozen:
            sys.path[:] = [str(root), *(entry for entry in original_path if Path(entry or ".").resolve() != root)]
    module_path = Path(getattr(yt_dlp, "__file__", "")).resolve()
    if not _is_within(module_path, root) or yt_dlp.version.__version__ != APPROVED_YT_DLP_RELEASE:
        raise DependencyPolicyError("Refusing an ambient or wrong-version yt_dlp module.")
    return yt_dlp


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        raise SystemExit("usage: python stratum_dependency_policy.py <controlled-root> [tools-root]")
    dependency_root = Path(sys.argv[1])
    verified = verify_controlled_install(dependency_root)
    verify_lock_file(Path(__file__).resolve().parent / "requirements-yt-dlp.lock")
    if len(sys.argv) == 3:
        verify_controlled_deno(Path(__file__).resolve().parent, Path(sys.argv[2]) / "deno" / "deno.exe")
    print(f"verified {len(verified)} controlled distributions at {dependency_root.resolve()}")
