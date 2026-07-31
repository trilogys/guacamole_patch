#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


def require(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise AssertionError(f"缺少补丁逻辑：{label}\n期望片段：{needle}")


def forbid(text: str, needle: str, label: str) -> None:
    if needle in text:
        raise AssertionError(f"发现不应存在的逻辑：{label}\n片段：{needle}")


def main() -> int:
    if len(sys.argv) != 2:
        print(f"用法：{sys.argv[0]} <guacamole-client-source-dir>", file=sys.stderr)
        return 2

    root = Path(sys.argv[1]).resolve()
    text_input = (root / "guacamole/src/main/frontend/src/app/textInput/directives/guacTextInput.js").read_text(encoding="utf-8")
    tiled = (root / "guacamole/src/main/frontend/src/app/client/directives/guacTiledClients.js").read_text(encoding="utf-8")
    index = (root / "guacamole/src/main/frontend/src/app/index/controllers/indexController.js").read_text(encoding="utf-8")
    client = (root / "guacamole/src/main/frontend/src/app/client/controllers/clientController.js").read_text(encoding="utf-8")

    # All modified source files carry an explicit downstream modification notice.
    for text, label in [(text_input, "guacTextInput"), (tiled, "guacTiledClients"), (index, "indexController")]:
        require(text, "Downstream modification:", f"{label} 修改声明")

    # Local text-input mode
    require(text_input, "'$window'", "guacTextInput 注入 $window")
    require(text_input, "processTextInput", "统一处理文字、Backspace 与 Delete")
    require(text_input, "flushCompletedComposition", "处理 input/compositionend 乱序")
    require(text_input, "resetAfterBrowserFocusChange", "标签页切换后清除 composition 状态")
    require(text_input, "guacTextInputFocusRequested", "恢复文本输入的客户端焦点")
    require(text_input, "guacInputFocusRestoreRequested", "阻止隐藏 InputSink 抢占文本输入焦点")
    require(text_input, "event.preventDefault();", "文本模式声明拥有恢复焦点")
    require(text_input, "target.focus();", "文本模式重新聚焦可见 textarea")
    require(text_input, "target.blur();", "text input native IME context reset")
    require(text_input, "focusedRect", "延迟恢复时保护用户刚选中的可见控件")
    require(text_input, "removeEventListener", "销毁时清理文本输入监听器")

    # Raw keyboard / remote Microsoft Pinyin mode
    for needle, label in [
        ("const $document", "indexController 已注入 $document"),
        ("const $window", "indexController 已注入 $window"),
        ("var sink = new Guacamole.InputSink()", "indexController 拥有 InputSink"),
        ("var keyboard = new Guacamole.Keyboard", "indexController 拥有 keyboard"),
        ("var hasActiveTunnel", "indexController 可检查活动连接"),
        ("restoreRemoteKeyboardInput", "恢复原始键盘通道"),
        ("REMOTE_MODIFIER_KEYSYMS", "显式释放远端修饰键"),
        ("keyboard.reset();", "重置本地按键状态"),
        ("sink.focus();", "重新聚焦隐藏输入捕获器"),
    ("sinkElement.blur();", "raw input native IME context reset"),
        ("guacKeyboardFocusRequested", "恢复 ManagedClient 焦点"),
        ("guacInputFocusRestoreRequested", "协调文本/原始键盘焦点所有权"),
        ("inputFocusEvent.defaultPrevented", "文本模式可阻止隐藏输入框抢焦点"),
        ("querySelector('.text-input .target')", "文本输入目标不被误判为本地表单"),
        ("focused.isContentEditable", "保护本地可编辑控件焦点"),
        ("$document[0].hasFocus()", "避免后台窗口错误恢复焦点"),
    ]:
        require(index, needle, label)

    require(tiled, "guacTextInputFocusRequested", "接收文本输入焦点请求")
    require(tiled, "guacKeyboardFocusRequested", "接收原始键盘焦点请求")
    require(tiled, "ManagedClientGroup.verifyFocus", "恢复客户端焦点")

    # Guard against the v2 scope bug.
    forbid(client, "restoreRemoteKeyboardInput", "远程键盘恢复误放入 clientController")
    forbid(client, "REMOTE_MODIFIER_KEYSYMS", "修饰键恢复误放入 clientController")

    print("已打补丁源码的作用域、模式隔离与关键逻辑检查通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
