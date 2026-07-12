"""Controlled dependency loading for Stratum's yt-dlp module integration."""

from __future__ import annotations

import base64
import csv
import hashlib
import importlib.metadata
import os
from pathlib import Path
from pathlib import PurePosixPath
import sys


APPROVED_YT_DLP_RELEASE = "2026.07.04"
APPROVED_YT_DLP_PACKAGE_VERSION = "2026.7.4"
APPROVED_YT_DLP_WHEEL_SHA256 = "f11f2b11d5a8ac4059f9bdf29fa4407dc7c6bb00c5097e95ca22a7a9db518266"
CONTROLLED_DEPENDENCY_DIRECTORY = ".deps"
UNAPPROVED_YT_DLP_OPTIONAL_MODULES = (
    "Crypto",
    "Cryptodome",
    "brotli",
    "brotlicffi",
    "certifi",
    "curl_cffi",
    "mutagen",
    "requests",
    "secretstorage",
    "urllib3",
    "websockets",
    "xattr",
    "yt_dlp_ejs",
)


class DependencyPolicyError(RuntimeError):
    """Raised when the approved yt-dlp dependency cannot be proven."""


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _yt_dlp_distribution(root: Path) -> importlib.metadata.Distribution:
    matches = []
    for distribution in importlib.metadata.distributions(path=[str(root)]):
        name = (distribution.metadata.get("Name") or "").lower().replace("_", "-")
        if name == "yt-dlp":
            matches.append(distribution)
    if len(matches) != 1:
        raise DependencyPolicyError(
            f"Expected one controlled yt-dlp distribution in {root}; found {len(matches)}. "
            "Run scripts/bootstrap_ytdlp.ps1."
        )
    distribution = matches[0]
    if distribution.version != APPROVED_YT_DLP_PACKAGE_VERSION:
        raise DependencyPolicyError(
            f"Unapproved yt-dlp package version {distribution.version!r}; "
            f"required {APPROVED_YT_DLP_PACKAGE_VERSION}."
        )
    return distribution


def _verify_wheel_record(distribution: importlib.metadata.Distribution, root: Path) -> None:
    record = distribution.read_text("RECORD")
    if not record:
        raise DependencyPolicyError("Controlled yt-dlp installation has no wheel RECORD.")
    checked = 0
    for relative_name, encoded_hash, declared_size in csv.reader(record.splitlines()):
        if not encoded_hash:
            continue
        algorithm, separator, expected = encoded_hash.partition("=")
        if separator != "=" or algorithm != "sha256":
            raise DependencyPolicyError(f"Unsupported RECORD hash for {relative_name!r}.")
        record_path = PurePosixPath(relative_name)
        if record_path.parts[:2] == ("..", "..") and record_path.parts[2:3] in (("bin",), ("share",)):
            # pip --target keeps wheel script/data outputs inside the target even
            # though RECORD retains their normal environment-relative prefix.
            candidate = root.joinpath(*record_path.parts[2:]).resolve()
        else:
            candidate = Path(distribution.locate_file(relative_name)).resolve()
        if not _is_within(candidate, root) or not candidate.is_file():
            raise DependencyPolicyError(f"Controlled yt-dlp file is missing or escaped its root: {relative_name!r}.")
        payload = candidate.read_bytes()
        actual = base64.urlsafe_b64encode(hashlib.sha256(payload).digest()).rstrip(b"=").decode("ascii")
        if actual != expected or (declared_size and len(payload) != int(declared_size)):
            raise DependencyPolicyError(f"Controlled yt-dlp file failed RECORD verification: {relative_name!r}.")
        checked += 1
    if checked == 0:
        raise DependencyPolicyError("Controlled yt-dlp wheel RECORD contained no verifiable files.")


def verify_controlled_install(root: Path, *, verify_record: bool = True) -> importlib.metadata.Distribution:
    root = root.resolve()
    if not root.is_dir():
        raise DependencyPolicyError(f"Controlled dependency directory is missing: {root}")
    distribution = _yt_dlp_distribution(root)
    if verify_record:
        _verify_wheel_record(distribution, root)
    return distribution


def load_controlled_yt_dlp():
    """Load only the approved repo-local or PyInstaller-collected yt-dlp module."""
    frozen = bool(getattr(sys, "frozen", False))
    root = Path(getattr(sys, "_MEIPASS")) if frozen else Path(__file__).resolve().parent / CONTROLLED_DEPENDENCY_DIRECTORY
    verify_controlled_install(root, verify_record=not frozen)

    existing = sys.modules.get("yt_dlp")
    if existing is not None:
        existing_path = Path(getattr(existing, "__file__", "")).resolve()
        if not _is_within(existing_path, root):
            raise DependencyPolicyError(f"Refusing ambient yt_dlp module at {existing_path}.")

    os.environ["YTDLP_NO_PLUGINS"] = "1"
    if existing:
        module = existing
    else:
        original_path = list(sys.path)
        try:
            if not frozen:
                # yt-dlp imports its optional dependency inventory eagerly. Keep
                # ambient site packages invisible during that import so Phase B
                # capabilities cannot leak into this core-only baseline.
                sys.path[:] = [
                    str(root),
                    *(entry for entry in original_path if "site-packages" not in entry.lower()
                      and "dist-packages" not in entry.lower()
                      and Path(entry or ".").resolve() != root),
                ]
            import yt_dlp
            module = yt_dlp
        finally:
            if not frozen:
                sys.path[:] = [str(root), *(entry for entry in original_path
                                            if Path(entry or ".").resolve() != root)]
    module_path = Path(getattr(module, "__file__", "")).resolve()
    if not _is_within(module_path, root):
        raise DependencyPolicyError(f"Refusing yt_dlp outside the controlled dependency root: {module_path}.")
    module_version = getattr(getattr(module, "version", None), "__version__", None)
    if module_version != APPROVED_YT_DLP_RELEASE:
        raise DependencyPolicyError(
            f"Unapproved yt_dlp module version {module_version!r}; required {APPROVED_YT_DLP_RELEASE}."
        )
    return module


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python stratum_dependency_policy.py <controlled-root>")
    verified = verify_controlled_install(Path(sys.argv[1]))
    print(f"verified yt-dlp {verified.version} at {Path(sys.argv[1]).resolve()}")
