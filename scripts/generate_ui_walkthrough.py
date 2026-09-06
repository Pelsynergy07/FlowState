import os, sys
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication
from flowstate.config import ConfigStore
from flowstate.ui.onboarding import OnboardingDialog
from flowstate.ui.tutorial import TutorialDialog
from flowstate.ui.settings_window import SettingsWindow

class DummySignals(QObject):
    recording_finished = Signal(str)
    recording_started = Signal()
    processing_started = Signal()
    error = Signal(str)
    drag_selection_started = Signal(int, int)
    drag_selection_moved = Signal(int, int)
    drag_selection_ended = Signal()

class DummyController:
    def __init__(self):
        self.config_store = ConfigStore()
        self.signals = DummySignals()
        self.is_recording = False
    def get_input_level(self):
        return 0.0
    def apply_config_change(self):
        pass

app = QApplication.instance() or QApplication(sys.argv)
ctrl = DummyController()
artifact_dir = r"C:\Users\Pranav Kumar\.gemini\antigravity-ide\brain\2542d745-cd64-4b0f-9635-a3ecb3bf696d"

# 1. Capture Onboarding Dialog
onboarding = OnboardingDialog(ctrl)
onboarding.show()
onboarding.grab().save(os.path.join(artifact_dir, "onboarding_preview.png"))
onboarding.close()

# 2. Capture Tutorial Step 1
tut = TutorialDialog(ctrl)
tut.show()
tut.grab().save(os.path.join(artifact_dir, "tutorial_step1_preview.png"))

# 3. Capture Tutorial Step 2
tut._go_next()
tut.grab().save(os.path.join(artifact_dir, "tutorial_step2_preview.png"))

# 4. Capture Tutorial Step 3
tut._go_next()
tut.grab().save(os.path.join(artifact_dir, "tutorial_step3_preview.png"))
tut.close()

# 5. Capture Settings Window (General Tab)
settings = SettingsWindow(ctrl.config_store, controller=ctrl)
settings.show()
settings.grab().save(os.path.join(artifact_dir, "settings_warm_preview.png"))
settings.close()

print("All preview screenshots captured successfully!")
