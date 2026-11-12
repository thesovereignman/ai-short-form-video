"""Rebuild the .skill archive from an explicit allowlist; never bundle secrets."""
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

root = Path(__file__).resolve().parents[1]
files = [root / "SKILL.md", root / ".env.example"]
for folder, glob in [("references", "*.md"), ("scripts", "*.py"), ("examples", "*.json")]:
    files.extend(sorted((root / folder).glob(glob)))
with ZipFile(root / "ai-short-form-video.skill", "w", compression=ZIP_DEFLATED) as archive:
    for file in files:
        info = ZipInfo("ai-short-form-video/" + file.relative_to(root).as_posix(), date_time=(2026, 1, 1, 0, 0, 0))
        info.compress_type = ZIP_DEFLATED
        info.external_attr = 0o100644 << 16
        archive.writestr(info, file.read_bytes())
print(f"Packaged {len(files)} allowlisted files")
