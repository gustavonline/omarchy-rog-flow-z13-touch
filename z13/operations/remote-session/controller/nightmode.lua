-- User-owned Z13 night mode. Restored by the Omarchy post-update hook.
local home = os.getenv("HOME")
local held = io.open(home .. "/.local/state/omarchy-night-mode/screen-held", "r")
if held then
  held:close()
  hl.config({ misc = { mouse_move_enables_dpms = false, key_press_enables_dpms = false } })
end

hl.unbind("XF86MonBrightnessDown")
o.bind("XF86MonBrightnessDown", "Brightness down (hold screen black at minimum)", home .. "/.local/bin/omarchy-brightness-screen-off down", { locked = true, repeating = true })
hl.unbind("XF86MonBrightnessUp")
o.bind("XF86MonBrightnessUp", "Brightness up / exit night mode", home .. "/.local/bin/omarchy-brightness-screen-off up", { locked = true, repeating = true })
o.bind("SUPER + ALT + N", "Toggle Z13 night mode", home .. "/.local/bin/omarchy-night-mode toggle", { locked = true })

-- The helper checks AC + the selected network profile + an already unlocked session.
-- If it fails or is disabled, keep Omarchy's normal locking behavior.
hl.unbind("switch:on:Lid Switch")
local lid_ok, lid_error = pcall(function()
  o.bind("switch:on:Lid Switch", "Z13 conditional closed-cover session", "timeout --kill-after=1s 3s " .. home .. "/.local/bin/omarchy-night-mode lid-close >/dev/null 2>&1 || omarchy-system-lid-close", { locked = true })
end)
if not lid_ok then
  o.bind("switch:on:Lid Switch", "Native lid lock", "omarchy-system-lid-close", { locked = true })
  error(lid_error)
end
