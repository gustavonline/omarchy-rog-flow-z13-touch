# Release checklist

1. Keep the root and all companion `manifest.json` files on the same semantic
   version and add the matching `CHANGELOG.md` section.
2. Run `./test.sh` on a current Omarchy installation and in a fresh clone.
3. Run `./setup.sh` on a supported GZ302EA, then complete the physical checks
   in `z13/TESTING.md`, including attach/detach, secure fields, suspend/resume,
   rotation, theme switching, and removal recovery.
4. Confirm the repository contains no generated binaries, generated headers,
   local shell configuration, device captures, credentials, or machine-specific
   paths outside the documented GZ302EA hardware contract.
5. Confirm upstream wvkbd and Wayland licensing files remain present.
6. Push `main`, tag the suite version, and create a GitHub Release from the
   matching suite changelog section.
