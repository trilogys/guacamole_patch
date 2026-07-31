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
    client_template = (root / "guacamole/src/main/frontend/src/app/client/templates/client.html").read_text(encoding="utf-8")
    en = (root / "guacamole/src/main/frontend/src/translations/en.json").read_text(encoding="utf-8")
    zh = (root / "guacamole/src/main/frontend/src/translations/zh.json").read_text(encoding="utf-8")

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
    require(text_input, "focusTextInputTarget", "text input trusted-gesture focus restore")
    require(text_input, "if (immediate)", "text input synchronous trusted-gesture path")
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
        ("sinkElement.focus();", "raw input synchronous trusted-gesture restore"),
        ("sinkElement.value = '';", "clear stale native input value"),
        ("keyboardRestorePendingUserGesture", "long-suspension trusted-gesture marker"),
        ("cancelKeyboardRestoreTimer", "coalesced restore cancellation"),
        ("restoreRemoteKeyboardInputNow", "shared synchronous/deferred restore core"),
        ("keyboardUserGesture", "multi-phase pointer gesture restore"),
        ("keyboardKeyGesture", "first keydown and manual hotkey restore"),
        ("isRemoteKeyboardTarget", "restrict automatic restoration to remote surface"),
        ("'pointerdown'", "trusted pointer listener"),
        ("'mousedown'", "trusted mouse fallback listener"),
        ("'touchstart'", "trusted touch fallback listener"),
        ("'click'", "post-default-focus click listener"),
        ("'keydown'", "keyboard self-healing listener"),
        ("'pageshow'", "page cache restore listener"),
        ("'pagehide'", "page cache suspension listener"),
        ("'freeze'", "page lifecycle freeze listener"),
        ("'resume'", "page lifecycle resume listener"),
        ("'fullscreenchange'", "fullscreen focus recovery listener"),
        ("'pointerlockchange'", "pointer lock focus recovery listener"),
        ("'KeyK'", "Ctrl-Alt-K manual recovery hotkey"),
        ("forceMenu", "Ctrl-Alt-Shift menu recovery fallback"),
        ("guacToggleMenuRequested", "direct menu-toggle request after recovery"),
        ("!forceRecovery && !forceMenu", "manual shortcuts bypass stale event targets"),
        ("getModifierState('AltGraph')", "AltGr does not trigger local recovery shortcuts"),
        ("guacForceInputRecovery", "menu-driven forced recovery"),
        ("guacKeyboardFocusRequested", "恢复 ManagedClient 焦点"),
        ("guacInputFocusRestoreRequested", "协调文本/原始键盘焦点所有权"),
        ("inputFocusEvent.defaultPrevented", "文本模式可阻止隐藏输入框抢焦点"),
        ("querySelector('.text-input .target')", "文本输入目标不被误判为本地表单"),
        ("element.isContentEditable", "保护本地可编辑控件焦点"),
        ("$document[0].hasFocus()", "避免后台窗口错误恢复焦点"),
    ]:
        require(index, needle, label)

    if index.count("keyboardMenuShortcutActive = false;") < 5:
        raise AssertionError(
            "The menu shortcut latch must reset on key release and every "
            "background/page lifecycle path."
        )

    require(tiled, "guacTextInputFocusRequested", "接收文本输入焦点请求")
    require(tiled, "guacKeyboardFocusRequested", "接收原始键盘焦点请求")
    require(tiled, "ManagedClientGroup.verifyFocus", "恢复客户端焦点")

    # The client controller may request recovery but must not own keyboard/sink.
    require(client, "recoverKeyboardInput", "客户端菜单恢复入口")
    require(client, "$scope.$emit('guacForceInputRecovery')", "菜单向全局键盘控制器请求恢复")
    require(client, "$scope.$on('guacToggleMenuRequested'", "失效键盘恢复后直接切换菜单")
    require(client, "$scope.menu.shown = !$scope.menu.shown", "保留原生菜单开关语义")
    require(client_template, "CLIENT.ACTION_RECOVER_KEYBOARD", "菜单恢复按钮")
    require(client_template, "recoverKeyboardInput()", "菜单恢复按钮绑定")
    require(en, '"ACTION_RECOVER_KEYBOARD" : "Recapture keyboard"', "英文恢复按钮")
    require(zh, '"ACTION_RECOVER_KEYBOARD" : "重新捕获键盘"', "中文恢复按钮")
    require(en, "Ctrl-Alt-K", "英文恢复热键提示")
    require(zh, "Ctrl-Alt-K", "中文恢复热键提示")
    require(text_input, "isVisibleLocalInput", "只保护真正的本地输入控件")
    forbid(text_input, "focusedRect", "不得把任意可见远程元素误判成本地输入控件")

    forbid(client, "REMOTE_MODIFIER_KEYSYMS", "修饰键恢复误放入 clientController")
    forbid(client, "new Guacamole.InputSink", "InputSink 不得移入 clientController")

    print("已打补丁源码的作用域、模式隔离与关键逻辑检查通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
