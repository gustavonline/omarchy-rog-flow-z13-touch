import QtQuick
import Quickshell
import Quickshell.Io
import qs.Ui

BarWidget {
  id: root
  moduleName: "io.github.gustavonline.rog-flow-z13-touch"

  property bool oskServiceActive: false
  property bool busy: false
  property string feedback: ""

  visible: oskServiceActive
  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  function refreshServiceState() {
    if (!serviceState.running) serviceState.running = true
  }

  function toggleKeyboard() {
    if (!oskServiceActive || toggleProcess.running) return
    busy = true
    feedbackClearTimer.stop()
    feedback = ""
    toggleProcess.command = [
      "systemctl", "--user", "kill", "--kill-whom=main",
      "--signal=RTMIN", "--", "z13-osk.service"
    ]
    toggleProcess.running = true
  }

  Component.onCompleted: refreshServiceState()

  Process {
    id: serviceState
    command: ["systemctl", "--user", "is-active", "--quiet", "z13-osk.service"]
    onExited: function(exitCode) {
      root.oskServiceActive = exitCode === 0
    }
  }

  Process {
    id: toggleProcess
    running: false
    stderr: StdioCollector { id: toggleError; waitForEnd: true }
    onExited: function(exitCode) {
      root.busy = false
      if (exitCode === 0) {
        root.feedback = "Keyboard toggled"
        feedbackClearTimer.restart()
      } else {
        var details = String(toggleError.text || "Could not toggle touch keyboard").trim()
        root.feedback = details.length > 180 ? details.slice(0, 177) + "…" : details
      }
    }
  }

  Timer {
    interval: 1500
    repeat: true
    running: true
    onTriggered: root.refreshServiceState()
  }

  Timer {
    id: feedbackClearTimer
    interval: 3500
    repeat: false
    onTriggered: root.feedback = ""
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
    tooltipText: root.busy ? "Toggling touch keyboard…" : (root.feedback !== "" ? root.feedback : "Show or hide touch keyboard")
    enabled: !root.busy
    onPressed: function(button) {
      if (button === Qt.LeftButton) root.toggleKeyboard()
    }
  }
}
