"""I-DS Phase 2B: resumable, single-stream HTTP file transfer.

This module deliberately does not modify yt-dlp media extraction. Only HTTP(S) file
URLs are accepted. Partials are job-scoped; completed outputs never overwrite files.
"""
from __future__ import annotations

import email.message
import hashlib
import ipaddress
import json
import mimetypes
import os
from pathlib import Path
import re
import shutil
import socket
import time
from typing import Callable
from urllib import error, parse, request


CHUNK_SIZE = 128 * 1024
RETRYABLE_HTTP = {408, 429, 500, 502, 503, 504}


class FileTransferError(Exception):
    pass


class FileTransferPaused(FileTransferError):
    pass


class FileTransferCancelled(FileTransferError):
    pass


def safe_file_name(value: str) -> str:
    """Reduce remote/user-provided names to one safe Windows filename."""
    if not isinstance(value, str):
        value = ""
    value = value.replace("\\", "/").split("/")[-1]
    value = re.sub(r'[\x00-\x1f\x7f<>:"/\\|?*]', "_", value).strip(" .")
    value = re.sub(r"\s+", " ", value)
    if not value or value in {".", ".."}:
        return "download.bin"
    if re.match(r"(?i)^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)", value):
        value = "_" + value
    suffix = Path(value).suffix[:20]
    stem = (Path(value).stem[: max(1, 180 - len(suffix))]).rstrip(" .")
    return stem + suffix if stem else "download.bin"


def suggested_name(url: str, disposition: str = "", hint: str = "", mime: str = "") -> str:
    if hint:
        return safe_file_name(hint)
    if disposition:
        msg = email.message.Message()
        msg["content-disposition"] = disposition
        name = msg.get_filename()
        if isinstance(name, tuple):
            name = name[-1]
        if name:
            return safe_file_name(str(name))
    parsed = parse.urlsplit(url)
    last = parse.unquote(parsed.path.rsplit("/", 1)[-1])
    if last and "." in last and not last.startswith("."):
        return safe_file_name(last)
    mime_base = mime.split(";", 1)[0].lower().strip()
    extension = mimetypes.guess_extension(mime_base) or ".bin"
    if extension == ".jpe":
        extension = ".jpg"
    return safe_file_name("download" + extension)


def check_public_url(url: str, allow_local: bool = False) -> str:
    if not isinstance(url, str) or len(url) > 8192 or any(ord(c) < 32 for c in url):
        raise FileTransferError("Invalid file URL")
    try:
        parts = parse.urlsplit(url)
        port = parts.port
    except ValueError as exc:
        raise FileTransferError("Invalid URL port") from exc
    if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
        raise FileTransferError("Only HTTP/HTTPS file links without embedded credentials are allowed")
    if port is not None and not (1 <= port <= 65535):
        raise FileTransferError("Unsupported port")
    host = parts.hostname
    if allow_local and host in {"127.0.0.1", "localhost", "::1"}:
        return url
    try:
        addresses = socket.getaddrinfo(host, port or (443 if parts.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except OSError as exc:
        raise FileTransferError("Could not resolve the file server") from exc
    if not addresses:
        raise FileTransferError("File host has no usable network address")
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            raise FileTransferError("Private, local, and reserved addresses are not downloadable")
    return url


class GuardedRedirect(request.HTTPRedirectHandler):
    def __init__(self, allow_local=False):
        super().__init__()
        self.allow_local = allow_local
        self.redirect_count = 0

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.redirect_count += 1
        if self.redirect_count > 5:
            raise FileTransferError("Too many redirects")
        check_public_url(newurl, self.allow_local)
        # Preserve standard non-sensitive request headers, never forward credentials.
        if parse.urlsplit(newurl).hostname != parse.urlsplit(req.full_url).hostname:
            req.headers.pop("Authorization", None)
            req.headers.pop("Cookie", None)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _read_meta(path: Path, url: str, job_id: str) -> dict:
    try:
        meta = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    fingerprint = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return meta if meta.get("url_sha256") == fingerprint and meta.get("job_id") == job_id else {}


def _save_meta(path: Path, meta: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as target:
        json.dump(meta, target, indent=2)
    os.replace(tmp, path)


def _parse_range(header: str):
    match = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+|\*)", header.strip())
    if not match:
        raise FileTransferError("Server returned invalid Content-Range")
    start, end = int(match[1]), int(match[2])
    total = None if match[3] == "*" else int(match[3])
    if end < start or (total is not None and end >= total):
        raise FileTransferError("Server returned inconsistent range")
    return start, end, total


def _reserve_output(save_dir: Path, preferred: str, partial: Path) -> Path:
    name = safe_file_name(preferred)
    stem, suffix = Path(name).stem, Path(name).suffix
    for index in range(10000):
        candidate = save_dir / (name if index == 0 else f"{stem} ({index}){suffix}")
        try:
            # NTFS and local file systems support creating a hard link exclusively.
            os.link(partial, candidate)
            partial.unlink()
            return candidate
        except FileExistsError:
            continue
        except OSError:
            # Some drives disallow hard links. Exclusive-copy fallback cannot overwrite.
            try:
                with candidate.open("xb") as output, partial.open("rb") as source:
                    shutil.copyfileobj(source, output, CHUNK_SIZE)
                    output.flush()
                    os.fsync(output.fileno())
                partial.unlink()
                return candidate
            except FileExistsError:
                continue
            except Exception:
                try:
                    candidate.unlink(missing_ok=True)
                except OSError:
                    pass
                raise
    raise FileTransferError("Could not reserve a unique file name")


def download_http_file(
    url: str,
    save_dir: str | Path,
    job_id: str,
    *,
    filename_hint: str = "",
    progress: Callable[[dict], None] | None = None,
    should_stop: Callable[[], str | None] | None = None,
    get_speed_limit: Callable[[], int] | None = None,
    allow_local: bool = False,
    timeout: int = 18,
    retries: int = 2,
) -> Path:
    """Transfer a file; partials survive errors/pause and are resumed only with validators.

    A completed result is returned only after size verification and exclusive output
    creation. Source bytes remain in a job-specific .part until final promotion.
    """
    check_public_url(url, allow_local)
    if not re.fullmatch(r"[0-9a-fA-F]{16,64}", job_id):
        raise FileTransferError("Invalid job identifier")
    root = Path(save_dir).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise FileTransferError("Save directory does not exist")

    partial = root / f".i-ds-{job_id}.part"
    meta_path = root / f".i-ds-{job_id}.json"
    metadata = _read_meta(meta_path, url, job_id)
    if partial.exists() and not metadata:
        # Unknown or stale partial must not be appended to an unrelated response.
        partial.unlink()
    offset = partial.stat().st_size if partial.exists() else 0
    validator = metadata.get("etag") or metadata.get("last_modified")
    if offset and not validator:
        offset = 0
    request_headers = {"User-Agent": "I-DS/2B (Windows file transfer)", "Accept-Encoding": "identity"}
    opener = request.build_opener(GuardedRedirect(allow_local))
    attempt = 0
    last_emit = 0.0
    while attempt <= retries:
        stop = should_stop() if should_stop else None
        if stop == "paused":
            raise FileTransferPaused("Paused")
        if stop == "cancelled":
            raise FileTransferCancelled("Cancelled")
        headers = dict(request_headers)
        if offset:
            headers["Range"] = f"bytes={offset}-"
            headers["If-Range"] = validator
        try:
            response = opener.open(request.Request(url, headers=headers, method="GET"), timeout=timeout)
            with response:
                check_public_url(response.geturl(), allow_local)
                status = response.status
                if status not in (200, 206):
                    raise FileTransferError(f"Download server returned HTTP {status}")
                if status == 206:
                    start, _end, total = _parse_range(response.headers.get("Content-Range", ""))
                    if start != offset or not offset:
                        raise FileTransferError("Server returned an unexpected partial range")
                else:
                    offset = 0
                    length = response.headers.get("Content-Length")
                    total = int(length) if length is not None and length.isdigit() else None
                if total is not None and total < offset:
                    raise FileTransferError("Server size is smaller than saved partial")
                etag = response.headers.get("ETag", "")
                last_modified = response.headers.get("Last-Modified", "")
                if status == 206 and validator not in (etag, last_modified):
                    raise FileTransferError("Server validator changed during resume")
                name = suggested_name(response.geturl(), response.headers.get("Content-Disposition", ""), filename_hint or metadata.get("filename", ""), response.headers.get("Content-Type", ""))
                content_type = response.headers.get("Content-Type", "").split(";", 1)[0].lower()
                html_requested = Path(parse.urlsplit(url).path).suffix.lower() in {".html", ".htm"} or Path(filename_hint).suffix.lower() in {".html", ".htm"}
                if content_type == "text/html" and not html_requested:
                    raise FileTransferError("Server returned a web page instead of a file")
                metadata = {
                    "job_id": job_id, "url_sha256": hashlib.sha256(url.encode("utf-8")).hexdigest(),
                    "filename": name, "etag": etag, "last_modified": last_modified,
                    "total": total, "content_type": content_type,
                }
                _save_meta(meta_path, metadata)
                started = time.monotonic()
                last_emit = 0
                downloaded = offset
                transfer_start_offset = offset
                with partial.open("ab" if offset else "wb") as target:
                    while True:
                        stop = should_stop() if should_stop else None
                        if stop == "paused":
                            raise FileTransferPaused("Paused")
                        if stop == "cancelled":
                            raise FileTransferCancelled("Cancelled")
                        block = response.read(CHUNK_SIZE)
                        if not block:
                            break
                        target.write(block)
                        downloaded += len(block)
                        if get_speed_limit:
                            rate = max(0, int(get_speed_limit() or 0))
                            if rate:
                                elapsed_needed = (downloaded - transfer_start_offset) / rate
                                while elapsed_needed > time.monotonic() - started:
                                    stop = should_stop() if should_stop else None
                                    if stop == "paused":
                                        raise FileTransferPaused("Paused")
                                    if stop == "cancelled":
                                        raise FileTransferCancelled("Cancelled")
                                    time.sleep(min(0.07, elapsed_needed - (time.monotonic() - started)))
                        if total is not None and downloaded > total:
                            raise FileTransferError("Server sent more bytes than declared")
                        now = time.monotonic()
                        if progress and (now - last_emit > 0.17 or (total and downloaded == total)):
                            speed = downloaded / max(0.01, now - started)
                            eta = max(0, int((total - downloaded) / speed)) if total and speed > 0 else None
                            progress({"name": name, "downloaded": downloaded, "total": total,
                                      "speed": speed, "eta": eta, "state": "downloading"})
                            last_emit = now
                    target.flush()
                    os.fsync(target.fileno())
                if total is not None and downloaded != total:
                    raise FileTransferError("Incomplete file: response ended before Content-Length")
                if downloaded <= 0:
                    raise FileTransferError("The server returned an empty file")
                stop = should_stop() if should_stop else None
                if stop == "paused":
                    raise FileTransferPaused("Paused")
                if stop == "cancelled":
                    raise FileTransferCancelled("Cancelled")
                destination = _reserve_output(root, name, partial)
                meta_path.unlink(missing_ok=True)
                if progress:
                    progress({"name": destination.name, "downloaded": downloaded,
                              "total": total or downloaded, "speed": 0, "eta": 0, "state": "completed"})
                return destination
        except (FileTransferPaused, FileTransferCancelled):
            raise
        except error.HTTPError as exc:
            if exc.code not in RETRYABLE_HTTP or attempt == retries:
                raise FileTransferError(f"Download server returned HTTP {exc.code}") from exc
        except (FileTransferError, OSError, error.URLError) as exc:
            if isinstance(exc, FileTransferError) and "Incomplete file" not in str(exc):
                raise
            if attempt == retries:
                raise FileTransferError("Download interrupted; partial data retained for retry") from exc
        attempt += 1
        time.sleep(min(1.5 * attempt, 3.0))
        validator = metadata.get("etag") or metadata.get("last_modified")
        offset = partial.stat().st_size if partial.exists() and validator else 0
    raise FileTransferError("Download failed")
