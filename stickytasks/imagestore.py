"""Content-addressed storage for images pasted into notes.

Images are written to disk as ``<sha256>.<ext>`` and referenced from note HTML
by bare filename.  Content addressing means pasting the same screenshot into
five tasks costs one file, and makes the store idempotent: re-saving identical
bytes is a no-op.

This module deliberately knows nothing about Qt so it can be tested headlessly.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

# Extensions we are willing to write.  Anything else is normalised to .png by
# the caller before it reaches here.
ALLOWED_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}


class ImageStore:
    def __init__(self, directory: Path | str):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def save_bytes(self, data: bytes, suffix: str = ".png") -> str:
        """Write ``data`` and return the filename to reference it by."""
        if not data:
            raise ValueError("refusing to store an empty image")
        suffix = suffix.lower()
        if suffix not in ALLOWED_SUFFIXES:
            suffix = ".png"
        name = hashlib.sha256(data).hexdigest()[:32] + suffix
        target = self.directory / name
        if not target.exists():
            tmp = target.with_suffix(target.suffix + ".tmp")
            tmp.write_bytes(data)
            tmp.replace(target)
        return name

    def path_for(self, name: str) -> Path:
        """Resolve a referenced name to a path inside the store.

        Only the basename is honoured, so a note containing
        ``src="../../etc/passwd"`` cannot reach outside the images directory.
        """
        return self.directory / Path(str(name).replace("\\", "/")).name

    def exists(self, name: str) -> bool:
        return self.path_for(name).is_file()

    def purge_unreferenced(self, referenced: set[str]) -> int:
        """Delete stored images no note mentions.  Returns the number removed."""
        removed = 0
        keep = {Path(r).name for r in referenced}
        for entry in self.directory.iterdir():
            if not entry.is_file() or entry.suffix.lower() not in ALLOWED_SUFFIXES:
                continue
            if entry.name not in keep:
                try:
                    entry.unlink()
                    removed += 1
                except OSError:
                    pass
        return removed

    def total_bytes(self) -> int:
        return sum(f.stat().st_size for f in self.directory.iterdir() if f.is_file())
