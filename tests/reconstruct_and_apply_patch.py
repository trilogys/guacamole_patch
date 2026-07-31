#!/usr/bin/env python3
"""Reconstruct sparse preimage files from a unified diff and verify it applies.

This catches malformed hunk counts/order before the official source is downloaded.
The build script additionally performs patch --dry-run against the real 1.6.0 source.
"""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

HUNK_RE = re.compile(r"^@@ -(\d+),(\d+) \+(\d+),(\d+) @@")


def main() -> int:
    if len(sys.argv) != 2:
        print(f"用法：{sys.argv[0]} <patch-file>", file=sys.stderr)
        return 2

    patch_path = Path(sys.argv[1]).resolve()
    lines = patch_path.read_text(encoding="utf-8").splitlines(keepends=True)
    files: dict[str, list[str]] = {}
    current: str | None = None
    i = 0

    while i < len(lines):
        line = lines[i]
        if line.startswith("--- a/"):
            current = line[len("--- a/"):].strip()
            files.setdefault(current, [])
            i += 2  # skip matching +++ line
            continue

        match = HUNK_RE.match(line)
        if match and current:
            old_start = int(match.group(1))
            old_count = int(match.group(2))
            target = files[current]
            needed = old_start - 1
            while len(target) < needed:
                target.append(f"/* sparse filler {len(target) + 1} */\n")

            old_lines: list[str] = []
            i += 1
            while i < len(lines) and not lines[i].startswith(("@@ ", "diff --git ", "--- a/")):
                marker = lines[i][:1]
                if marker in (" ", "-"):
                    old_lines.append(lines[i][1:])
                elif marker == "\\":
                    pass
                i += 1

            if len(old_lines) != old_count:
                raise AssertionError(
                    f"hunk 旧行数不匹配：{current}:{old_start}，"
                    f"声明 {old_count}，实际 {len(old_lines)}"
                )

            for offset, old_line in enumerate(old_lines):
                pos = old_start - 1 + offset
                while len(target) <= pos:
                    target.append(f"/* sparse filler {len(target) + 1} */\n")
                existing = target[pos]
                if not existing.startswith("/* sparse filler") and existing != old_line:
                    raise AssertionError(f"重叠 hunk 内容冲突：{current}:{pos + 1}")
                target[pos] = old_line
            continue

        i += 1

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        # Add exact upstream scope anchors which are outside the changed hunks.
        index_path = "guacamole/src/main/frontend/src/app/index/controllers/indexController.js"
        if index_path in files:
            anchors = {
                42: "    const $document              = $injector.get('$document');\n",
                46: "    const $window                = $injector.get('$window');\n",
                179: "    var sink = new Guacamole.InputSink();\n",
                183: "    var keyboard = new Guacamole.Keyboard($document[0]);\n",
                235: "    var hasActiveTunnel = function hasActiveTunnel() {\n",
            }
            content = files[index_path]
            for line_number, value in anchors.items():
                while len(content) < line_number:
                    content.append(f"/* sparse filler {len(content) + 1} */\n")
                content[line_number - 1] = value

        for rel, content in files.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("".join(content), encoding="utf-8")

        # Older patches did not modify clientController. Provide an unchanged
        # fixture only when it is absent from the current patch.
        client = root / "guacamole/src/main/frontend/src/app/client/controllers/clientController.js"
        if not client.exists():
            client.parent.mkdir(parents=True, exist_ok=True)
            client.write_text("// unchanged clientController fixture\n", encoding="utf-8")

        patch_bytes = patch_path.read_bytes()
        subprocess.run(
            ["patch", "--directory", str(root), "--strip=1", "--dry-run"],
            input=patch_bytes,
            check=True,
        )
        subprocess.run(
            ["patch", "--directory", str(root), "--strip=1"],
            input=patch_bytes,
            check=True,
        )
        subprocess.run(
            [sys.executable, str(Path(__file__).with_name("verify_patched_source.py")), str(root)],
            check=True,
        )

    print("补丁语法、hunk 结构与作用域回归检查通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
