#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


TARGETS = [
    "guacamole/src/main/frontend/src/app/textInput/directives/guacTextInput.js",
    "guacamole/src/main/frontend/src/app/client/directives/guacTiledClients.js",
    "guacamole/src/main/frontend/src/app/index/controllers/indexController.js",
]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    if len(sys.argv) != 2:
        print(f"用法：{sys.argv[0]} <package-dir>", file=sys.stderr)
        return 2

    root = Path(sys.argv[1]).resolve()
    patch_path = root / "patches/0001-fix-ime-and-keyboard-after-tab-switch.patch"
    patch = patch_path.read_text(encoding="utf-8")

    require("client/controllers/clientController.js" not in patch,
            "远程键盘恢复不得放入缺少 keyboard/sink 的 clientController")
    require("\nindex " not in "\n" + patch,
            "正式补丁不得包含伪造的 git postimage blob 哈希")

    for path in TARGETS:
        require(f"diff --git a/{path} b/{path}" in patch, f"缺少文件补丁头：{path}")
        require(f"--- a/{path}" in patch and f"+++ b/{path}" in patch,
                f"缺少标准 unified diff 路径：{path}")

    required = [
        "restoreRemoteKeyboardInput",
        "Downstream modification:",
        "REMOTE_MODIFIER_KEYSYMS",
        "0xFE03, /* AltGr",
        "hasActiveTunnel()",
        "sink.focus();",
        "keyboard.reset();",
        "guacKeyboardFocusRequested",
        "guacTextInputFocusRequested",
        "guacInputFocusRestoreRequested",
        "inputFocusEvent.defaultPrevented",
        "querySelector('.text-input .target')",
        "focusedRect",
        "processTextInput",
        "compositionend",
        "visibilitychange",
        "focused.isContentEditable",
        "tagName === 'textarea'",
        "tagName === 'button'",
        "tagName === 'a'",
    ]
    for needle in required:
        require(needle in patch, f"补丁缺少关键逻辑：{needle}")

    build = (root / "build.sh").read_text(encoding="utf-8")
    for needle, label in [
        ("--dry-run", "构建前补丁 dry-run"),
        ("-DskipTests=false", "默认运行 Guacamole 上游测试"),
        ("verify_patched_source.py", "已打补丁源码检查"),
        ("SOURCE_SHA256=\"81f9fd5a", "Guacamole 1.6.0 源码哈希"),
        ("sha256sum --check --status SHA256SUMS", "补丁包内部完整性检查"),
        ("SUPPORTED_VERSION=\"1.6.0\"", "版本锁定"),
        ("BUILD_WORK_DIR=\"$(mktemp -d", "安全的独立临时目录"),
        ("local/guacamole:", "本地镜像命名空间"),
        ("PULL_BASE_IMAGES", "可控的基础镜像拉取策略"),
        ("docker image inspect", "构建结果检查"),
        ("/opt/guacamole/bin/initdb.sh", "镜像冒烟测试"),
        ("org.opencontainers.image.licenses=Apache-2.0", "OCI 许可证标签"),
    ]:
        require(needle in build, f"构建脚本缺少：{label}")

    require('rm -rf -- "${WORK_DIR}"' not in build,
            "不得直接递归删除用户指定的 WORK_DIR")
    require("--pull" not in build.split("DOCKER_BUILD_ARGS=(", 1)[0],
            "不得无条件拉取浮动基础镜像")

    compose = (root / "docker-compose.override.yml").read_text(encoding="utf-8")
    require("local/guacamole:1.6.0-inputfix5" in compose,
            "Compose 覆盖文件未使用 v5 本地镜像标签")

    metadata_path = root / "RELEASE_METADATA.json"
    require(metadata_path.exists(), "缺少 RELEASE_METADATA.json")
    metadata = metadata_path.read_text(encoding="utf-8")
    require('"release_status": "controlled-deployment-candidate"' in metadata,
            "发布状态必须明确为受控部署候选版")
    require('"end_to_end_rdp_validation": false' in metadata,
            "不得把尚未完成的端到端验证标记为已完成")

    license_path = root / "LICENSE"
    notice_path = root / "NOTICE"
    require(license_path.exists(), "缺少 Apache License 2.0 全文")
    require("Apache License" in license_path.read_text(encoding="utf-8"), "LICENSE 内容异常")
    notice = notice_path.read_text(encoding="utf-8")
    require("Apache Guacamole" in notice and "modified" in notice.lower(),
            "NOTICE 必须包含上游归属和修改声明")

    print("补丁包结构、作用域、安全与合规检查通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
