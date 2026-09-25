#!/usr/bin/env python3
"""Exercise rotation startup and sensor disconnect without touching the desktop."""
import os
from pathlib import Path
import subprocess
import tempfile

script = Path(__file__).resolve().parents[1] / "rotation/z13-tablet-rotation"
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    config = root / ".config/omarchy"
    config.mkdir(parents=True)
    (config / "shell.json").write_text('{"bar":{"position":"top"}}')
    bindir = root / "bin"
    bindir.mkdir()
    commands = {
        "monitor-sensor": '#!/bin/sh\necho "Accelerometer orientation changed: right-up"\nsleep 0.1\n',
        "hyprctl": '''#!/bin/sh
case "$1" in
devices) echo '{"keyboards":[]}' ;;
monitors) echo '[{"name":"eDP-1","transform":1}]' ;;
eval) sleep 0.1 ;;
*) exit 2 ;;
esac
''',
        "omarchy": "#!/bin/sh\nexit 2\n",
    }
    for name, content in commands.items():
        path = bindir / name
        path.write_text(content)
        path.chmod(0o755)
    result = subprocess.run(
        ["bash", str(script)], capture_output=True, text=True, timeout=10,
        env={**os.environ, "HOME": str(root), "PATH": f"{bindir}:{os.environ['PATH']}"},
    )
    assert result.returncode == 1, result
    assert "transform 1 (right-up)" in result.stdout, result
    assert "accelerometer reader stopped unexpectedly" in result.stderr, result
    assert "Bad file descriptor" not in result.stderr, result
print("rotation startup and sensor disconnect: OK")
