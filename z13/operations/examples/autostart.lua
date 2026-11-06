-- Add to the owner’s existing Hyprland autostart, preserving its other entries.
local home = os.getenv("HOME")
o.launch_on_start("hyprsunset")
o.launch_on_start(home .. "/.local/bin/chatgpt-danish")
o.launch_on_start(home .. "/.local/bin/t3code")
