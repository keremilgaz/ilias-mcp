"""Build the Claude Desktop bundle from the same sources as the Python package."""

from __future__ import annotations

import argparse
import json
import runpy
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("dist"))
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    claude = root / "packaging" / "claude"
    manifest = json.loads((claude / "manifest.json").read_text("utf-8"))
    version = runpy.run_path(str(root / "src/ilias_mcp/__init__.py"))["__version__"]
    manifest["version"] = version
    args.output_dir.mkdir(parents=True, exist_ok=True)
    target = args.output_dir / f"ilias-mcp-{version}.mcpb"
    files = [root / name for name in ("pyproject.toml", "README.md", "LICENSE")]
    files.extend(sorted((root / "src/ilias_mcp").glob("*.py")))
    files.extend(sorted((root / "src/ilias_mcp/assets").glob("*.html")))
    with ZipFile(target, "w", ZIP_DEFLATED) as bundle:
        bundle.writestr("manifest.json", json.dumps(manifest, indent=2) + "\n")
        bundle.write(claude / "entry.py", manifest["server"]["entry_point"])
        for path in files:
            bundle.write(path, path.relative_to(root).as_posix())
    print(target)


if __name__ == "__main__":
    main()
