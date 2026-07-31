# Changelog

## 1.6.0-inputfix7

- Recover keyboard and IME capture across blur, visibility, freeze, page-cache, fullscreen, and pointer-lock transitions.
- Retry recovery through pointer, mouse, touch, click, and first-key gestures without stealing focus from local controls.
- Make `Ctrl+Alt+Shift` independently recover input and toggle the Guacamole menu even when keyboard state is stale.
- Add `Ctrl+Alt+K` and a menu action as manual recovery paths.
- Reset stale shortcut latches when keyup events are lost and avoid AltGr conflicts.
- Restore the visible text-input target when focus lands on a remote non-form element.

## 1.6.0-inputfix6

- Recover native IME contexts after long browser freezes through the first trusted pointer gesture.
- Listen for page lifecycle `freeze`, `resume`, and `pageshow` events in addition to focus and visibility changes.
- Restore text-input and raw-keyboard modes synchronously when user activation is required by Chromium.
- Verify that release metadata contains the actual distributed patch SHA-256.
