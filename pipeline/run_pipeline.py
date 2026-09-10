"""
pipeline/run_pipeline.py
========================
Convenience script: runs the full data pipeline end-to-end.

Usage (from project root):
    python pipeline/run_pipeline.py [--skip-embed] [--skip-gis]

Flags:
  --skip-embed   Skip embedding step (saves ~2-4 min on slow machines)
  --skip-gis     Skip GIS hazard grid computation

Steps:
  1. extract.py    — PDF → JSON
  2. chunk.py      — JSON → chunks
  3. embed.py      — chunks → embeddings + FAISS (optional)
  4. build_sqlite  — chunks → knowledge.sqlite
  5. compute_hazard_grid — → hazard_grid.sqlite
  6. Copy both SQLite files into app/assets/offline_package/
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

STEPS = [
    ("Extract PDFs",      ROOT / "pipeline" / "rag" / "extract.py"),
    ("Chunk text",        ROOT / "pipeline" / "rag" / "chunk.py"),
    ("Generate embeddings", ROOT / "pipeline" / "rag" / "embed.py"),
    ("Build knowledge DB", ROOT / "pipeline" / "package_builder" / "build_sqlite.py"),
    ("Compute hazard grid", ROOT / "pipeline" / "gis" / "compute_hazard_grid.py"),
]

SKIP_EMBED = "--skip-embed" in sys.argv
SKIP_GIS = "--skip-gis" in sys.argv


def run_step(name: str, script: Path) -> bool:
    print(f"\n{'═' * 60}")
    print(f"  STEP: {name}")
    print(f"{'═' * 60}")
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(ROOT),
    )
    if result.returncode != 0:
        print(f"\n✗ Step '{name}' failed (exit {result.returncode})")
        return False
    print(f"\n✓ {name} complete")
    return True


def copy_assets():
    src_knowledge = ROOT / "offline_package" / "knowledge.sqlite"
    src_hazard = ROOT / "offline_package" / "hazard_grid.sqlite"
    dst_dir = ROOT / "app" / "assets" / "offline_package"
    dst_dir.mkdir(parents=True, exist_ok=True)

    for src in [src_knowledge, src_hazard]:
        if src.exists():
            dst = dst_dir / src.name
            shutil.copy2(str(src), str(dst))
            size_kb = dst.stat().st_size // 1024
            print(f"  Copied: {src.name} → {dst}  ({size_kb} KB)")
        else:
            print(f"  WARNING: {src.name} not found — skipped copy")


def main():
    print("Disaster DSS — Full Pipeline Run")
    print(f"Root: {ROOT}")
    if SKIP_EMBED:
        print("  [--skip-embed] Embedding step will be skipped")
    if SKIP_GIS:
        print("  [--skip-gis] GIS step will be skipped")

    for name, script in STEPS:
        if "embed" in script.name and SKIP_EMBED:
            print(f"\nSkipping: {name}")
            continue
        if "hazard" in script.name and SKIP_GIS:
            print(f"\nSkipping: {name}")
            continue
        ok = run_step(name, script)
        if not ok:
            print("\nPipeline aborted.")
            sys.exit(1)

    print(f"\n{'═' * 60}")
    print("  Copying databases to Flutter asset directory…")
    print(f"{'═' * 60}")
    copy_assets()

    print("\n✓ Pipeline complete.")
    print("\nNext steps:")
    print("  cd app && flutter pub get && flutter run")


if __name__ == "__main__":
    main()
