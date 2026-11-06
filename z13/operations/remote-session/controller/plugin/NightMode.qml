import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui
import qs.Ui as Ui

Ui.Panel {
  id: root
  moduleName: "io.github.gustavonline.night-mode"
  ipcTarget: "io.github.gustavonline.night-mode"
  manageIpc: false
  readonly property color foreground: bar ? bar.foreground : Color.foreground
  readonly property string fontFamily: bar ? bar.fontFamily : Style.font.family
  readonly property string controlPath: Quickshell.env("HOME") + "/.local/bin/omarchy-night-mode"
  property var status: ({ active: false, screenHeld: false, screenPoweredOff: false, automatic: true, schedule: "19:00–07:00", serviceActive: false, pausedUntil: "", error: "" })
  property string feedback: ""
  property bool busy: false
  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  function refresh() { if (!statusProcess.running) statusProcess.running = true }
  function runAction(action) {
    if (busy) return
    busy = true
    feedback = ""
    root.close()
    actionProcess.command = [controlPath, action]
    actionProcess.running = true
  }
  function stateLabel() {
    if (status.error) return "Kræver opmærksomhed"
    if (!status.serviceActive) return "Automatikken kører ikke"
    if (status.active) return status.screenPoweredOff ? (status.headless && status.headless.issue ? "Nattilstand aktiv · virtuel skærm ikke klar" : "Nattilstand aktiv") : "Nattilstand starter"
    if (status.screenHeld) return "Skærmen holdes sort"
    if (status.pausedUntil) return "Pause indtil kl. " + status.pausedUntil
    return status.automatic ? "Planlagt · " + status.schedule : "Automatik slået fra"
  }
  onOpenedChanged: if (opened) {
    root.refresh()
    Qt.callLater(function() { keyCatcher.forceActiveFocus() })
  }
  Component.onCompleted: refresh()
  Timer { interval: 5000; running: true; repeat: true; onTriggered: root.refresh() }

  Process {
    id: statusProcess
    command: [root.controlPath, "status"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        try { root.status = JSON.parse(String(text || "")) }
        catch (e) { root.feedback = "Kunne ikke læse nattilstandens status" }
      }
    }
    stderr: StdioCollector { id: statusError; waitForEnd: true }
    onExited: function(code) {
      if (code !== 0) root.feedback = String(statusError.text || "Status kunne ikke læses").trim()
    }
  }
  Process {
    id: actionProcess
    stdout: StdioCollector { waitForEnd: true }
    stderr: StdioCollector { id: actionError; waitForEnd: true }
    onExited: function(code) {
      root.busy = false
      if (code !== 0) root.feedback = String(actionError.text || "Kunne ikke ændre nattilstand").trim()
      root.refresh()
    }
  }
  IpcHandler {
    target: root.ipcTarget
    function open(): void { root.open() }
    function close(): void { root.close() }
    function toggle(): void { root.toggle() }
    function status(): string { return root.stateLabel() }
  }
  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: "󰖔"
    tooltipText: "Z13 Nattilstand · " + root.stateLabel()
    active: root.status.active || root.status.screenHeld
    onPressed: function(buttonCode) { root.toggle() }
  }
  KeyboardPanel {
    id: panel
    anchorItem: button
    owner: root
    bar: root.bar
    open: root.opened
    focusTarget: keyCatcher
    contentWidth: panel.fittedContentWidth(Style.space(370))
    contentHeight: panel.fittedContentHeight(content.implicitHeight, Style.space(520))
    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      onCloseRequested: root.close()
      onActivateRequested: root.refresh()
      Column {
        id: content
        width: parent.width
        spacing: Style.space(12)
        PanelHero {
          width: parent.width
          title: "Nattilstand"
          meta: "Z13 · " + (root.status.schedule || "19:00–07:00")
          foreground: root.foreground
          fontFamily: root.fontFamily
        }
        Text {
          width: parent.width
          text: root.stateLabel()
          color: root.status.error || !root.status.serviceActive ? Color.urgent : root.foreground
          font.family: root.fontFamily
          font.pixelSize: Style.font.body
          font.bold: true
          wrapMode: Text.WordWrap
        }
        Text {
          width: parent.width
          text: "Sort skærm og tastaturlys, lydløs og caffeinate. Baggrundsjob fortsætter. Den fysiske skærm forbliver sort hele natten, også hvis den virtuelle skærm til desktop-betjening ikke kan oprettes eller kontrolleres; så er desktop-betjening utilgængelig, og årsagen vises her. Tidligere indstillinger gendannes, når tilstanden slås fra."
          color: root.foreground
          opacity: 0.75
          font.family: root.fontFamily
          font.pixelSize: Style.font.bodySmall
          wrapMode: Text.WordWrap
        }
        Button {
          width: parent.width
          text: root.status.active || root.status.screenHeld ? "Slå fra nu" : "Slå til nu"
          enabled: !root.busy
          bordered: true
          foreground: root.foreground
          fontFamily: root.fontFamily
          fontSize: Style.font.bodySmall
          verticalPadding: Style.spacing.controlPaddingY
          onClicked: root.runAction(root.status.active || root.status.screenHeld ? "off" : "on")
        }
        Button {
          width: parent.width
          text: (root.status.automatic ? "✓  " : "○  ") + "Automatisk " + (root.status.schedule || "19:00–07:00")
          enabled: !root.busy
          bordered: true
          foreground: root.foreground
          fontFamily: root.fontFamily
          fontSize: Style.font.bodySmall
          verticalPadding: Style.spacing.controlPaddingY
          onClicked: root.runAction("schedule-toggle")
        }
        Text {
          width: parent.width
          text: "Væk bevidst med lysstyrke-op eller Super + Alt + N. Mus og almindelige tastetryk tænder ikke skærmen. Vækker du om natten, holder automatikken pause til næste kl. 19. Tiderne følger dansk sommer-/vintertid."
          color: root.foreground
          opacity: 0.75
          font.family: root.fontFamily
          font.pixelSize: Style.font.bodySmall
          wrapMode: Text.WordWrap
        }
        Text {
          visible: !!(root.status.headless && root.status.headless.issue)
          width: parent.width
          text: root.status.headless && root.status.headless.issue ? root.status.headless.issue : ""
          color: root.foreground
          opacity: 0.9
          font.family: root.fontFamily
          font.pixelSize: Style.font.caption
          wrapMode: Text.WordWrap
        }
        Text {
          visible: !!root.status.error || root.feedback !== ""
          width: parent.width
          text: root.status.error || root.feedback
          color: Color.urgent
          font.family: root.fontFamily
          font.pixelSize: Style.font.caption
          wrapMode: Text.WordWrap
        }
      }
    }
  }
}
