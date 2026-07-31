#!/usr/bin/env python3
from __future__ import annotations

PADDING = 4
PAD = "\u200b"
MODIFIERS = [
    0xFE03,
    0xFFE1, 0xFFE2, 0xFFE3, 0xFFE4,
    0xFFE7, 0xFFE8, 0xFFE9, 0xFFEA,
    0xFFEB, 0xFFEC, 0xFFED, 0xFFEE,
]


class TextInputState:
    def __init__(self) -> None:
        self.composing = False
        self.value = PAD * (PADDING * 2)
        self.sent: list[str] = []
        self.focus_requests = 0
        self.target_focused = False

    def composition_start(self) -> None:
        self.composing = True

    def input(self, value: str) -> None:
        self.value = value
        if not self.composing:
            self.process()

    def composition_end(self) -> None:
        self.composing = False
        if self.value != PAD * (PADDING * 2):
            self.process()

    def browser_focus_change(self, hidden: bool) -> None:
        self.composing = False
        self.value = PAD * (PADDING * 2)
        if not hidden:
            self.focus_requests += 1

    def claim_global_focus_restore(self, visible_local_focus: bool = False) -> bool:
        """Return True to model Angular event.preventDefault()."""
        self.composing = False
        self.value = PAD * (PADDING * 2)
        self.focus_requests += 1
        if not visible_local_focus:
            self.target_focused = True
        return True

    def process(self) -> None:
        text = self.value.replace(PAD, "")
        if text:
            self.sent.append(text)
        self.value = PAD * (PADDING * 2)


class RemoteKeyboardState:
    def __init__(self) -> None:
        self.hidden = False
        self.document_focused = True
        self.ready = True
        self.active_tunnel = True
        self.visible_local_input = False
        self.text_input_target_active = False
        self.client_focused = False
        self.sink_focused = False
        self.text_target_focused = False
        self.pressed = {0xFFE1, 0xFFE3}
        self.remote_released: list[int] = []
        self.restore_queued = False

    def reset(self) -> None:
        self.remote_released.extend(self.pressed)
        self.pressed.clear()

    def queue_restore(self) -> bool:
        if (
            self.hidden
            or not self.document_focused
            or not self.ready
            or not self.active_tunnel
            or self.visible_local_input
            or self.restore_queued
        ):
            return False
        self.restore_queued = True
        return True

    def execute_restore(self) -> None:
        if not self.restore_queued:
            return
        self.restore_queued = False
        if (
            self.hidden
            or not self.document_focused
            or not self.ready
            or not self.active_tunnel
            or self.visible_local_input
        ):
            return
        self.client_focused = True
        self.reset()
        self.remote_released.extend(MODIFIERS)
        if self.text_input_target_active:
            self.text_target_focused = True
        else:
            self.sink_focused = True

    def hide(self) -> None:
        self.hidden = True
        self.restore_queued = False
        self.reset()


def main() -> None:
    # compositionend missing during tab switch must not permanently block input
    state = TextInputState()
    state.composition_start()
    state.input(PAD * PADDING + "zhong")
    state.browser_focus_change(True)
    state.browser_focus_change(False)
    state.input(PAD * PADDING + "中文" + PAD * PADDING)
    assert state.sent == ["中文"]
    assert state.composing is False
    assert state.focus_requests == 1

    # input-before-compositionend must flush exactly once
    reordered = TextInputState()
    reordered.composition_start()
    reordered.input(PAD * PADDING + "输入" + PAD * PADDING)
    assert reordered.sent == []
    reordered.composition_end()
    assert reordered.sent == ["输入"]

    # Text-input mode claims global focus restoration and keeps the visible target.
    text_mode = TextInputState()
    claimed = text_mode.claim_global_focus_restore()
    assert claimed is True
    assert text_mode.target_focused is True

    # If the user clicks a visible local control before the deferred focus runs,
    # text mode still claims the event but must not steal that new focus.
    text_with_local_control = TextInputState()
    claimed = text_with_local_control.claim_global_focus_restore(visible_local_focus=True)
    assert claimed is True
    assert text_with_local_control.target_focused is False

    # Raw-keyboard mode must recover client focus, release modifiers, and refocus sink.
    remote = RemoteKeyboardState()
    remote.hide()
    remote.hidden = False
    assert remote.queue_restore() is True
    # A simultaneous focus event must coalesce into the existing queued restore.
    assert remote.queue_restore() is False
    remote.execute_restore()
    assert remote.client_focused is True
    assert remote.sink_focused is True
    assert remote.pressed == set()
    assert all(keysym in remote.remote_released for keysym in MODIFIERS)

    # Text mode must still release modifiers but must not focus the hidden sink.
    remote_text = RemoteKeyboardState()
    remote_text.text_input_target_active = True
    assert remote_text.queue_restore() is True
    remote_text.execute_restore()
    assert remote_text.client_focused is True
    assert remote_text.text_target_focused is True
    assert remote_text.sink_focused is False
    assert all(keysym in remote_text.remote_released for keysym in MODIFIERS)

    # A visible local Guacamole form field must retain focus.
    local_form = RemoteKeyboardState()
    local_form.visible_local_input = True
    assert local_form.queue_restore() is False
    local_form.execute_restore()
    assert local_form.client_focused is False
    assert local_form.sink_focused is False

    # Hiding the page cancels any queued focus restoration.
    cancelled = RemoteKeyboardState()
    assert cancelled.queue_restore() is True
    cancelled.hide()
    cancelled.execute_restore()
    assert cancelled.sink_focused is False

    print("输入法、焦点所有权、修饰键和竞态状态回归测试通过。")


if __name__ == "__main__":
    main()
