"""Deterministic Agent Version Hash Computation.

Per 17 §3:
agent_version = SHA-256 of the contents of all backend and prompt files,
sorted by relative path, excluding README, tests, web, and generated caches.
Newlines are normalized (CRLF -> LF) before hashing so Windows and Linux
environments yield identical version hashes.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import List, Optional

EXCLUDED_PARTS = {
    "tests",
    "test_",
    "__pycache__",
    ".pytest_cache",
    ".git",
    "node_modules",
}

EXCLUDED_EXTENSIONS = {
    ".pyc",
    ".pyo",
    ".pyd",
    ".db",
    ".sqlite",
    ".sqlite-wal",
    ".sqlite-shm",
    ".log",
}


def get_versioned_files(repo_root: Path) -> List[Path]:
    """Gather all eligible Python and prompt files in app/backend and app/backend/prompts."""
    files: List[Path] = []
    backend_dir = repo_root / "app" / "backend"

    if not backend_dir.exists():
        return files

    for p in backend_dir.rglob("*"):
        if not p.is_file():
            continue
        # Check excluded paths
        rel_str = str(p.relative_to(repo_root)).replace("\\", "/")
        if any(ex in rel_str for ex in EXCLUDED_PARTS):
            continue
        if p.suffix.lower() in EXCLUDED_EXTENSIONS:
            continue
        if p.name.startswith("test_") or p.name.endswith("_test.py"):
            continue
        # Include python files, prompt files, and sql files
        if p.suffix.lower() in {".py", ".txt", ".sql", ".json", ".md"}:
            files.append(p)

    files.sort(key=lambda x: str(x.relative_to(repo_root)).replace("\\", "/"))
    return files


def compute_agent_version(repo_root: Optional[Path] = None) -> str:
    """Computes deterministic SHA-256 hash of backend code and prompt contents."""
    if repo_root is None:
        repo_root = Path(__file__).resolve().parent.parent.parent.parent

    files = get_versioned_files(repo_root)
    hasher = hashlib.sha256()

    for f in files:
        rel_path = str(f.relative_to(repo_root)).replace("\\", "/")
        hasher.update(rel_path.encode("utf-8"))
        hasher.update(b"\n")
        try:
            content = f.read_bytes()
            # Normalize CRLF to LF
            content_lf = content.replace(b"\r\n", b"\n")
            hasher.update(content_lf)
        except Exception:
            pass

    return hasher.hexdigest()
