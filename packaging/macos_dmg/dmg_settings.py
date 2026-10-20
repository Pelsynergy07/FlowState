# dmgbuild settings for FlowState-<version>.dmg (see build_macos.sh).
# Icon positions match the arrow and label pills drawn by make_background.py.
import os.path

app = defines["app"]  # noqa: F821  (dmgbuild passes -D app=/path/FlowState.app)
background_tiff = defines["background"]  # noqa: F821

format = "UDZO"
filesystem = "HFS+"
files = [app]
symlinks = {"Applications": "/Applications"}
icon_locations = {os.path.basename(app): (170, 150), "Applications": (490, 150)}
background = background_tiff
window_rect = ((200, 120), (660, 460))
default_view = "icon-view"
show_icon_preview = False
include_icon_view_settings = True
icon_size = 112
text_size = 13
show_status_bar = False
show_tab_view = False
show_toolbar = False
show_pathbar = False
show_sidebar = False
