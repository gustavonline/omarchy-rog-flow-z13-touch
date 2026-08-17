import QtQuick
import Quickshell
import Quickshell.Io
import qs.Ui

BarWidget {
  id: root
  moduleName: "io.github.gustavonline.rog-flow-z13-touch"

  property bool oskServiceActive: false

  visible: oskServiceActive
  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  function refreshServiceState() {
    if (!serviceState.running) serviceState.running = true
  }

  function toggleKeyboard() {
    if (!oskServiceActive) return
    Quickshell.execDetached([
      "systemctl", "--user", "kill", "--kill-whom=main",
      "--signal=RTMIN", "z13-osk.service"
    ])
  }

  Component.onCompleted: refreshServiceState()

  Process {
    id: serviceState
    command: ["systemctl", "--user", "is-active", "--quiet", "z13-osk.service"]
    onExited: function(exitCode) {
      root.oskServiceActive = exitCode === 0
    }
  }

  Timer {
    interval: 1500
    repeat: true
    running: true
    onTriggered: root.refreshServiceState()
  }

  IpcHandler {
    target: "io.github.gustavonline.rog-flow-z13-touch"

    function serviceState(): string {
      return root.oskServiceActive ? "available" : "cover-attached"
    }

    function toggle(): string {
      if (!root.oskServiceActive) return "unavailable"
      button.triggerPress(Qt.LeftButton)
      return "requested"
    }

    function clickRoute(): string {
      if (!root.bar || !root.parent || !root.parent.parent) return "unavailable"
      var target = root.bar.moduleClickTargetAt(
        root.parent.parent, root.width / 2, root.height / 2
      )
      return target === button ? "keyboard-toggle" : "other"
    }
  }

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: "\uf11c"
    tooltipText: "Show or hide touch keyboard"
    onPressed: function(button) {
      if (button === Qt.LeftButton) root.toggleKeyboard()
    }
  }
}
