"""Pin a new hyundai_kia_connect_api version and bump the patch version.

Usage: python bump_library.py <new library version>
Edits manifest.json and requirements_test.txt in place.
"""

import json
import re
import sys
from pathlib import Path

LIB = "hyundai_kia_connect_api"
MANIFEST = Path("custom_components/moolink/manifest.json")
REQUIREMENTS = Path("requirements_test.txt")


def main(new_version: str) -> None:
    manifest = json.loads(MANIFEST.read_text())
    manifest["requirements"] = [
        f"{LIB}=={new_version}" if req.startswith(f"{LIB}==") else req
        for req in manifest["requirements"]
    ]
    major, minor, patch = (int(p) for p in manifest["version"].split("."))
    manifest["version"] = f"{major}.{minor}.{patch + 1}"
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")

    REQUIREMENTS.write_text(
        re.sub(
            rf"^{LIB}==.*$",
            f"{LIB}=={new_version}",
            REQUIREMENTS.read_text(),
            flags=re.MULTILINE,
        )
    )
    print(manifest["version"])


if __name__ == "__main__":
    main(sys.argv[1])
