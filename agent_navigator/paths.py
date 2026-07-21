from __future__ import annotations

import hashlib
import os
import re
import stat
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterator


POLICY_DIR = ".agent-policy"
LOCK_TIMEOUT_SECONDS = 10.0


def resolve_target(target: str | Path) -> Path:
    return Path(target).expanduser().resolve()


def policy_root(target: str | Path) -> Path:
    return resolve_target(target) / POLICY_DIR


def require_policy(target: str | Path) -> Path:
    root = policy_root(target)
    if not root.exists():
        raise SystemExit(
            f"No {POLICY_DIR}/ directory found under {resolve_target(target)}. "
            "Run `agent-navi init` first."
        )
    return root


def now_utc() -> datetime:
    fixed = os.environ.get("AGENT_POLICY_FIXED_NOW")
    if fixed:
        return datetime.fromisoformat(fixed.replace("Z", "+00:00")).astimezone(timezone.utc)
    return datetime.now(timezone.utc)


def now_stamp() -> str:
    return now_utc().strftime("%Y%m%d-%H%M%S")


def now_human() -> str:
    return now_utc().strftime("%Y-%m-%d %H:%M:%S UTC")


def slugify(value: str | None, fallback: str = "item") -> str:
    text = (value or "").strip().lower()
    ascii_text = text.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")
    return slug or fallback


def unique_path(directory: Path, filename: str, *, root: Path | None = None) -> Path:
    if root is not None:
        ensure_safe_directory(directory, root=root)
    else:
        directory.mkdir(parents=True, exist_ok=True)
    candidate = directory / filename
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    index = 2
    while True:
        next_candidate = directory / f"{stem}-{index}{suffix}"
        if not next_candidate.exists():
            return next_candidate
        index += 1


def write_text(
    path: Path,
    content: str,
    force: bool = True,
    *,
    root: Path | None = None,
    mode: int | None = None,
) -> bool:
    safe_root = root or path.parent
    ensure_safe_write_path(path, root=safe_root)
    with path_lock(path):
        ensure_safe_write_path(path, root=safe_root)
        if path.exists() and not force:
            if mode is not None:
                os.chmod(path, mode)
            return False
        _atomic_write_unlocked(path, ensure_trailing_newline(content), mode=mode)
        return True


def append_text(
    path: Path,
    content: str,
    *,
    root: Path | None = None,
    mode: int | None = None,
) -> None:
    def append(existing: str) -> str:
        if existing.strip():
            return existing.rstrip() + "\n\n" + content.lstrip()
        return content.lstrip()

    update_text(path, append, root=root, mode=mode)


def update_text(
    path: Path,
    transform: Callable[[str], str],
    *,
    root: Path | None = None,
    mode: int | None = None,
) -> str:
    safe_root = root or path.parent
    ensure_safe_write_path(path, root=safe_root)
    with path_lock(path):
        ensure_safe_write_path(path, root=safe_root)
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        updated = ensure_trailing_newline(transform(existing))
        if updated != existing or mode is not None:
            _atomic_write_unlocked(path, updated, mode=mode)
        return updated


def copy_file(
    source: Path,
    destination: Path,
    *,
    root: Path,
    mode: int = 0o600,
) -> Path:
    ensure_safe_write_path(destination, root=root)
    with path_lock(destination):
        ensure_safe_write_path(destination, root=root)
        if destination.exists():
            destination = unique_path(destination.parent, destination.name, root=root)
        fd, temporary_name = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
        temporary = Path(temporary_name)
        try:
            with source.open("rb") as input_file, os.fdopen(fd, "wb") as output_file:
                while chunk := input_file.read(1024 * 1024):
                    output_file.write(chunk)
                output_file.flush()
                os.fsync(output_file.fileno())
            os.chmod(temporary, mode)
            os.replace(temporary, destination)
            _fsync_directory(destination.parent)
        except BaseException:
            try:
                os.close(fd)
            except OSError:
                pass
            temporary.unlink(missing_ok=True)
            raise
    return destination


def ensure_trailing_newline(content: str) -> str:
    return content if content.endswith("\n") else content + "\n"


def safe_relative_target(repo: Path, relative_path: str) -> Path:
    root = Path(os.path.abspath(repo.expanduser()))
    path = Path(os.path.abspath(root / relative_path))
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise SystemExit(f"Refusing to write outside target repo: {relative_path}") from exc
    ensure_safe_write_path(path, root=root)
    return path


def ensure_safe_directory(directory: Path, *, root: Path, mode: int | None = None) -> Path:
    root_path = Path(os.path.abspath(root.expanduser()))
    directory_path = Path(os.path.abspath(directory.expanduser()))
    try:
        relative = directory_path.relative_to(root_path)
    except ValueError as exc:
        raise SystemExit(f"Refusing to create directory outside safe root: {directory_path}") from exc

    _reject_symlink(root_path)
    current = root_path
    for part in relative.parts:
        current /= part
        _reject_symlink(current)
        if current.exists() and not current.is_dir():
            raise SystemExit(f"Refusing to use non-directory path component: {current}")

    directory_path.mkdir(parents=True, exist_ok=True)
    _reject_symlink(root_path)
    current = root_path
    for part in relative.parts:
        current /= part
        _reject_symlink(current)
    if mode is not None:
        os.chmod(directory_path, mode)
    return directory_path


def ensure_safe_write_path(path: Path, *, root: Path) -> Path:
    root_path = Path(os.path.abspath(root.expanduser()))
    path = Path(os.path.abspath(path.expanduser()))
    try:
        path.relative_to(root_path)
    except ValueError as exc:
        raise SystemExit(f"Refusing to write outside safe root: {path}") from exc
    ensure_safe_directory(path.parent, root=root_path)
    _reject_symlink(path)
    if path.exists() and not path.is_file():
        raise SystemExit(f"Refusing to replace non-file path: {path}")
    return path


def _reject_symlink(path: Path) -> None:
    if path.is_symlink():
        raise SystemExit(f"Refusing to follow symbolic link while writing: {path}")


@contextmanager
def path_lock(path: Path) -> Iterator[None]:
    user_id = getattr(os, "getuid", lambda: "user")()
    lock_root = Path(tempfile.gettempdir()) / f"agent-navigator-locks-{user_id}"
    ensure_safe_directory(lock_root, root=lock_root, mode=0o700)
    digest = hashlib.sha256(str(Path(os.path.abspath(path))).encode("utf-8")).hexdigest()
    lock_path = lock_root / f"{digest}.lock"
    with lock_path.open("a+b") as handle:
        try:
            os.chmod(lock_path, 0o600)
        except OSError:
            pass
        _acquire_lock(handle)
        try:
            yield
        finally:
            _release_lock(handle)


def _acquire_lock(handle: object) -> None:
    deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
    if os.name == "nt":
        import msvcrt

        handle.seek(0)
        if not handle.read(1):
            handle.write(b"\0")
            handle.flush()
        while True:
            try:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                return
            except OSError:
                if time.monotonic() >= deadline:
                    raise SystemExit("Timed out waiting for another Agent Navigator writer.")
                time.sleep(0.05)

    import fcntl

    while True:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except BlockingIOError:
            if time.monotonic() >= deadline:
                raise SystemExit("Timed out waiting for another Agent Navigator writer.")
            time.sleep(0.05)


def _release_lock(handle: object) -> None:
    if os.name == "nt":
        import msvcrt

        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        return
    import fcntl

    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _atomic_write_unlocked(path: Path, content: str, *, mode: int | None) -> None:
    existing_mode = None
    if path.exists():
        existing_mode = stat.S_IMODE(path.stat().st_mode)
    file_mode = mode if mode is not None else existing_mode or 0o644
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, file_mode)
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    except BaseException:
        try:
            os.close(fd)
        except OSError:
            pass
        temporary.unlink(missing_ok=True)
        raise


def _fsync_directory(directory: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
