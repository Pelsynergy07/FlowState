import pytest
from PySide6.QtWidgets import QApplication
from flowstate.config import ConfigStore
from flowstate.ui.settings_window import SettingsWindow
from flowstate.update_check import UpdateInfo
from flowstate import __version__


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_settings_window_header_no_stamp_no_100_percent(qapp):
    config_store = ConfigStore()
    requested_updates = []

    def on_update_req(info):
        requested_updates.append(info)

    dlg = SettingsWindow(
        config_store=config_store,
        on_update_requested=on_update_req,
    )

    # 1. Check version badge default state
    assert dlg._version_badge is not None
    assert dlg._version_badge.getText() == f"v{__version__} // WIN64"

    # 2. Check download button initially hidden
    assert dlg._header_download_btn is not None
    assert dlg._header_download_btn.isHidden()

    # 3. Simulate update available
    sample_info = UpdateInfo(
        version="0.2.0",
        url="https://github.com/example/FlowState/releases/tag/v0.2.0",
        download_url="https://github.com/example/FlowState/releases/download/v0.2.0/FlowStateSetup.exe",
        asset_size=1000000,
    )
    dlg.set_update_info(sample_info)

    assert dlg._version_badge.getText() == "UPDATE AVAILABLE // v0.2.0"
    assert not dlg._header_download_btn.isHidden()
    assert dlg._header_download_btn.text() == "DOWNLOAD v0.2.0 →"

    # 4. Trigger download button
    dlg._header_download_btn.click()
    assert len(requested_updates) == 1
    assert requested_updates[0].version == "0.2.0"

    # 5. Reset to up-to-date
    dlg.set_update_info(None)
    assert dlg._version_badge.getText() == f"v{__version__} // WIN64"
    assert dlg._header_download_btn.isHidden()

    dlg.close()
