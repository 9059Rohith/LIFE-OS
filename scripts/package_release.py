"""Package source and deployment instructions, excluding credentials and local state."""

import hashlib
import subprocess
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {
    ".git",
    ".private",
    ".venv",
    "node_modules",
    "__pycache__",
    "artifacts",
    "data",
    ".browser-profile",
}


def main():
    listed = (
        subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        )
        .stdout.decode("utf-8")
        .split("\0")
    )
    paths = []
    for relative in sorted(set(listed)):
        if not relative:
            continue
        path = ROOT / relative
        if (
            set(Path(relative).parts) & EXCLUDED
            or path.is_symlink()
            or not path.is_file()
            or (path.name.startswith(".env") and path.name != ".env.example")
            or path.suffix in {".db", ".log", ".zip", ".pyc"}
        ):
            continue
        if not path.resolve().is_relative_to(ROOT):
            raise RuntimeError("Source path leaves the workspace")
        paths.append(path)
    destination = ROOT / "artifacts/lifeos-source.zip"
    destination.parent.mkdir(exist_ok=True)
    with ZipFile(destination, "w", compression=ZIP_DEFLATED) as archive:
        for path in paths:
            archive.write(path, "lifeos/" + path.relative_to(ROOT).as_posix())
    checksum = hashlib.sha256(destination.read_bytes()).hexdigest()
    destination.with_suffix(".sha256").write_text(checksum + "  " + destination.name + "\n", encoding="utf-8")
    with ZipFile(destination) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("Archive integrity check failed")
    print(f"Packaged {len(paths)} source files: artifacts/lifeos-source.zip")
    print(f"SHA256: {checksum}")


if __name__ == "__main__":
    main()
