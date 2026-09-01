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
        self.restore_pending_user_gesture = False
        self.native_context_stale = False
        self.synchronous_restores = 0
        self.menu_shown = False
        self.menu_shortcut_active = False

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
        self.perform_restore()

    def perform_restore(
        self,
        *,
        user_initiated: bool = False,
        ignore_existing_local_focus: bool = False,
    ) -> bool:
        if (
            self.hidden
            or not self.document_focused
            or not self.ready
            or not self.active_tunnel
            or (self.visible_local_input and not ignore_existing_local_focus)
        ):
            return False
        self.client_focused = True
        self.reset()
        self.remote_released.extend(MODIFIERS)
        native_focus_restored = user_initiated or not self.native_context_stale
        if self.text_input_target_active:
            self.text_target_focused = native_focus_restored
        else:
            self.sink_focused = native_focus_restored
        if user_initiated:
            self.native_context_stale = False
            self.synchronous_restores += 1
        return True

    def hide(self) -> None:
        self.hidden = True
        self.restore_queued = False
        self.restore_pending_user_gesture = True
        self.menu_shortcut_active = False
        self.reset()

    def freeze(self) -> None:
        self.hide()
        self.native_context_stale = True

    def show(self) -> None:
        self.hidden = False

    def pointer_event(self, event_type: str, *, local_control: bool = False) -> bool:
        if (
            not self.restore_pending_user_gesture
            or self.hidden
            or local_control
        ):
            return False
        restored = self.perform_restore(
            user_initiated=True,
            ignore_existing_local_focus=True,
        )
        if restored and event_type == "click":
            self.restore_pending_user_gesture = False
        return restored

    def keydown(
        self,
        *,
        force_recovery: bool = False,
        force_menu: bool = False,
        local_control: bool = False,
    ) -> bool:
        if force_menu and self.menu_shortcut_active:
            return False
        if force_menu:
            self.menu_shortcut_active = True
        if force_recovery or force_menu:
            self.restore_pending_user_gesture = True
        if (
            not self.restore_pending_user_gesture
            or self.hidden
            or (local_control and not force_recovery and not force_menu)
        ):
            return False
        restored = self.perform_restore(
            user_initiated=True,
            ignore_existing_local_focus=True,
        )
        if restored:
            self.restore_pending_user_gesture = False
            if force_menu:
                self.menu_shown = not self.menu_shown
        return restored

    def keyup(self) -> None:
        self.menu_shortcut_active = False

    def menu_recover(self) -> bool:
        self.restore_pending_user_gesture = True
        return self.keydown(force_recovery=True)


class UnstableWarningState:
    """Model the UI grace period layered over tunnel instability."""

    WARNING_DELAY = 3000
    AUTO_RECONNECT_DELAY = 5000
    AUTO_RECONNECT_MAX_ATTEMPTS = 2
    AUTO_RECONNECT_RESET_DELAY = 60000

    def __init__(self) -> None:
        self.now = 0
        self.hidden = False
        self.tunnel_state = "open"
        self.warning_visible = False
        self.warning_due: int | None = None
        self.reconnect_suggested = False
        self.active_transfer = False
        self.auto_reconnect_due: int | None = None
        self.auto_reconnect_attempts = 0
        self.auto_reconnects = 0
        self.attempt_reset_due: int | None = None

    def schedule_warning(self) -> None:
        self.warning_visible = False
        self.warning_due = None
        if not self.hidden:
            self.warning_due = self.now + self.WARNING_DELAY

    def set_tunnel_state(self, state: str) -> None:
        self.tunnel_state = state
        if state == "unstable":
            self.auto_reconnect_due = None
            self.attempt_reset_due = None
            self.schedule_warning()
        else:
            self.warning_visible = False
            self.warning_due = None
            if state == "open":
                self.queue_auto_reconnect()
                if self.auto_reconnect_attempts:
                    self.attempt_reset_due = self.now + self.AUTO_RECONNECT_RESET_DELAY
            else:
                self.auto_reconnect_due = None

    def set_hidden(self, hidden: bool) -> None:
        self.hidden = hidden
        if self.tunnel_state == "unstable":
            self.schedule_warning()

    def advance(self, milliseconds: int) -> None:
        self.now += milliseconds
        if self.warning_due is not None and self.now >= self.warning_due:
            self.warning_due = None
            if self.tunnel_state == "unstable" and not self.hidden:
                self.warning_visible = True
                self.reconnect_suggested = True

        if self.auto_reconnect_due is not None and self.now >= self.auto_reconnect_due:
            self.auto_reconnect_due = None
            if self.can_auto_reconnect():
                self.auto_reconnect_attempts += 1
                self.auto_reconnects += 1
                self.reconnect_suggested = False
                self.attempt_reset_due = self.now + self.AUTO_RECONNECT_RESET_DELAY

        if self.attempt_reset_due is not None and self.now >= self.attempt_reset_due:
            self.attempt_reset_due = None
            if self.tunnel_state == "open":
                self.auto_reconnect_attempts = 0

    def can_auto_reconnect(self) -> bool:
        return (
            self.recovery_available()
            and self.tunnel_state == "open"
            and not self.active_transfer
        )

    def queue_auto_reconnect(self) -> None:
        if (
            self.can_auto_reconnect()
            and self.auto_reconnect_attempts < self.AUTO_RECONNECT_MAX_ATTEMPTS
        ):
            delay = self.AUTO_RECONNECT_DELAY * (2 ** self.auto_reconnect_attempts)
            self.auto_reconnect_due = self.now + delay

    def set_active_transfer(self, active: bool) -> None:
        self.active_transfer = active
        if active:
            self.auto_reconnect_due = None
        else:
            self.queue_auto_reconnect()

    def dismiss_recovery(self) -> None:
        self.auto_reconnect_due = None
        self.reconnect_suggested = False

    def recovery_available(self) -> bool:
        return self.reconnect_suggested and self.tunnel_state in {"open", "unstable"}


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

    # A long browser freeze may invalidate Chromium's native editing context.
    # Deferred focus is insufficient. Early pointer/mouse events pre-restore the
    # context, while the bubbling click performs the final restore after browser
    # default focus actions have run.
    frozen = RemoteKeyboardState()
    frozen.freeze()
    frozen.show()
    assert frozen.queue_restore() is True
    frozen.execute_restore()
    assert frozen.client_focused is True
    assert frozen.sink_focused is False
    assert frozen.restore_pending_user_gesture is True
    assert frozen.pointer_event("pointerdown") is True
    assert frozen.restore_pending_user_gesture is True
    # Model the browser's default mousedown focus action stealing focus again.
    frozen.sink_focused = False
    assert frozen.pointer_event("mousedown") is True
    frozen.sink_focused = False
    assert frozen.pointer_event("click") is True
    assert frozen.sink_focused is True
    assert frozen.native_context_stale is False
    assert frozen.restore_pending_user_gesture is False
    assert frozen.synchronous_restores == 3

    # If a drag/touch sequence produces no final click, the first keydown must
    # complete recovery before Guacamole handles that same key event.
    key_fallback = RemoteKeyboardState()
    key_fallback.freeze()
    key_fallback.show()
    assert key_fallback.pointer_event("touchstart") is True
    key_fallback.sink_focused = False
    assert key_fallback.keydown() is True
    assert key_fallback.sink_focused is True
    assert key_fallback.restore_pending_user_gesture is False

    # Clicking a visible local control must not consume the pending trusted
    # gesture; a later click on the remote display can still recover input.
    frozen_local = RemoteKeyboardState()
    frozen_local.freeze()
    frozen_local.show()
    assert frozen_local.pointer_event("pointerdown", local_control=True) is False
    assert frozen_local.restore_pending_user_gesture is True
    assert frozen_local.pointer_event("click") is True
    assert frozen_local.sink_focused is True

    # Both manual fallbacks must recover even when the browser omitted all
    # lifecycle events and no pending marker exists.
    hotkey = RemoteKeyboardState()
    hotkey.native_context_stale = True
    assert hotkey.keydown(force_recovery=True) is True
    assert hotkey.sink_focused is True
    assert hotkey.restore_pending_user_gesture is False

    native_menu = RemoteKeyboardState()
    native_menu.native_context_stale = True
    native_menu.menu_shortcut_active = True
    native_menu.hide()
    native_menu.show()
    assert native_menu.menu_shortcut_active is False
    assert native_menu.keydown(force_menu=True) is True
    assert native_menu.sink_focused is True
    assert native_menu.menu_shown is True
    assert native_menu.restore_pending_user_gesture is False
    assert native_menu.keydown(force_menu=True) is False
    assert native_menu.menu_shown is True
    native_menu.keyup()
    assert native_menu.keydown(force_menu=True, local_control=True) is True
    assert native_menu.menu_shown is False

    menu_action = RemoteKeyboardState()
    menu_action.native_context_stale = True
    assert menu_action.menu_recover() is True
    assert menu_action.sink_focused is True
    assert menu_action.restore_pending_user_gesture is False

    # A brief unstable state must recover without flashing a warning.
    brief_stall = UnstableWarningState()
    brief_stall.set_tunnel_state("unstable")
    brief_stall.advance(UnstableWarningState.WARNING_DELAY - 1)
    assert brief_stall.warning_visible is False
    brief_stall.set_tunnel_state("open")
    brief_stall.advance(1)
    assert brief_stall.warning_visible is False
    assert brief_stall.reconnect_suggested is False

    # A sustained visible disruption must still warn before tunnel timeout.
    sustained_stall = UnstableWarningState()
    sustained_stall.set_tunnel_state("unstable")
    sustained_stall.advance(UnstableWarningState.WARNING_DELAY)
    assert sustained_stall.warning_visible is True
    assert sustained_stall.reconnect_suggested is True
    sustained_stall.set_tunnel_state("open")
    assert sustained_stall.warning_visible is False
    assert sustained_stall.reconnect_suggested is True
    assert sustained_stall.recovery_available() is True
    sustained_stall.set_tunnel_state("closed")
    assert sustained_stall.recovery_available() is False
    sustained_stall.dismiss_recovery()
    assert sustained_stall.reconnect_suggested is False

    # Background throttling must not produce a warning immediately on return.
    background_stall = UnstableWarningState()
    background_stall.set_hidden(True)
    background_stall.set_tunnel_state("unstable")
    background_stall.advance(15000)
    assert background_stall.warning_visible is False
    background_stall.set_hidden(False)
    background_stall.advance(UnstableWarningState.WARNING_DELAY - 1)
    assert background_stall.warning_visible is False
    background_stall.advance(1)
    assert background_stall.warning_visible is True

    # Hiding the page also clears a warning that was already visible.
    background_stall.set_hidden(True)
    assert background_stall.warning_visible is False
    assert background_stall.warning_due is None

    # A confirmed disruption that recovers queues one bounded reconnect after
    # the initial stable delay.
    auto_recovery = UnstableWarningState()
    auto_recovery.set_tunnel_state("unstable")
    auto_recovery.advance(UnstableWarningState.WARNING_DELAY)
    auto_recovery.set_tunnel_state("open")
    auto_recovery.advance(UnstableWarningState.AUTO_RECONNECT_DELAY - 1)
    assert auto_recovery.auto_reconnects == 0
    auto_recovery.advance(1)
    assert auto_recovery.auto_reconnects == 1
    assert auto_recovery.auto_reconnect_attempts == 1
    assert auto_recovery.reconnect_suggested is False

    # A second disruption backs off, while a third consecutive disruption is
    # left for manual recovery instead of entering a reconnect loop.
    auto_recovery.set_tunnel_state("unstable")
    auto_recovery.advance(UnstableWarningState.WARNING_DELAY)
    auto_recovery.set_tunnel_state("open")
    auto_recovery.advance(UnstableWarningState.AUTO_RECONNECT_DELAY * 2)
    assert auto_recovery.auto_reconnects == 2
    assert auto_recovery.auto_reconnect_attempts == 2
    auto_recovery.set_tunnel_state("unstable")
    auto_recovery.advance(UnstableWarningState.WARNING_DELAY)
    auto_recovery.set_tunnel_state("open")
    assert auto_recovery.auto_reconnect_due is None
    auto_recovery.advance(UnstableWarningState.AUTO_RECONNECT_DELAY * 4)
    assert auto_recovery.auto_reconnects == 2

    # A continuous stable minute resets the retry budget for a future event.
    auto_recovery.advance(UnstableWarningState.AUTO_RECONNECT_RESET_DELAY)
    assert auto_recovery.auto_reconnect_attempts == 0

    # Active transfers and an explicit request to keep the current session both
    # cancel automatic reconnect without clearing the manual recovery path.
    transfer_guard = UnstableWarningState()
    transfer_guard.set_tunnel_state("unstable")
    transfer_guard.advance(UnstableWarningState.WARNING_DELAY)
    transfer_guard.set_tunnel_state("open")
    transfer_guard.set_active_transfer(True)
    transfer_guard.advance(UnstableWarningState.AUTO_RECONNECT_DELAY * 2)
    assert transfer_guard.auto_reconnects == 0
    assert transfer_guard.reconnect_suggested is True
    transfer_guard.set_active_transfer(False)
    assert transfer_guard.auto_reconnect_due is not None
    transfer_guard.dismiss_recovery()
    transfer_guard.advance(UnstableWarningState.AUTO_RECONNECT_DELAY)
    assert transfer_guard.auto_reconnects == 0

    print("输入法、焦点所有权、修饰键、网络提示、自动重连和竞态状态回归测试通过。")


if __name__ == "__main__":
    main()
