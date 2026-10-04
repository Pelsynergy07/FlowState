from unittest.mock import patch

import pytest
import win32con

from flowstate.inject import paste


def test_clipboard_snapshot_preserves_image_and_text_formats():
    data = {win32con.CF_UNICODETEXT: "original", win32con.CF_DIB: b"dib bytes",
            17: b"dibv5 bytes", 49152: b"png bytes"}
    with patch.object(paste.win32clipboard, "OpenClipboard"), \
         patch.object(paste.win32clipboard, "CloseClipboard"), \
         patch.object(paste.win32clipboard, "RegisterClipboardFormat", return_value=49152), \
         patch.object(paste.win32clipboard, "IsClipboardFormatAvailable", side_effect=lambda fmt: fmt in data), \
         patch.object(paste.win32clipboard, "GetClipboardData", side_effect=data.__getitem__):
        assert paste._save_clipboard() == data
    with patch.object(paste.win32clipboard, "OpenClipboard"), \
         patch.object(paste.win32clipboard, "CloseClipboard"), \
         patch.object(paste.win32clipboard, "EmptyClipboard"), \
         patch.object(paste.win32clipboard, "SetClipboardData") as setter:
        paste._restore_clipboard(data)
        assert [call.args for call in setter.call_args_list] == list(data.items())


def test_original_image_restored_even_if_paste_fails():
    snapshot = {win32con.CF_DIB: b"original image"}
    with patch.object(paste, "_save_clipboard", return_value=snapshot), \
         patch.object(paste, "_set_clipboard_text"), \
         patch.object(paste, "_send_ctrl_v", side_effect=RuntimeError("paste failed")), \
         patch.object(paste, "_restore_clipboard") as restore:
        with pytest.raises(RuntimeError):
            paste.paste_transcript("complete speech")
        restore.assert_called_once_with(snapshot)


def test_text_and_captured_images_are_pasted_separately_then_restored(tmp_path):
    image = tmp_path / "capture.png"
    image.touch()
    events = []
    snapshot = {win32con.CF_DIB: b"old image"}
    with patch.object(paste, "_save_clipboard", return_value=snapshot), \
         patch.object(paste, "_set_clipboard_text", side_effect=lambda text: events.append(text)), \
         patch.object(paste, "_set_clipboard_image", side_effect=lambda path: events.append(path)), \
         patch.object(paste, "_send_ctrl_v", side_effect=lambda: events.append("paste")), \
         patch.object(paste.time, "sleep"), \
         patch.object(paste, "_restore_clipboard", side_effect=lambda data: events.append(data)):
        paste.paste_transcript("all speech", [image])
    assert events == ["all speech", "paste", image, "paste", snapshot]
