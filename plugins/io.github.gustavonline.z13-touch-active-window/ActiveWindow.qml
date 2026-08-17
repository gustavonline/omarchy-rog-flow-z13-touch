import QtQuick
import Quickshell
import Quickshell.Wayland
import qs.Commons
import qs.Ui

BarWidget {
  id: root
  moduleName: "io.github.gustavonline.z13-touch-active-window"


  readonly property var toplevel: ToplevelManager.activeToplevel
  readonly property string title: toplevel ? (toplevel.title || toplevel.appId || "") : ""
  readonly property int maxLabelWidth: Number(setting("maxWidth", 280))
  readonly property int closeButtonWidth: Style.bar.statusSlot

  visible: title !== "" && !vertical
  implicitWidth: visible ? Math.min(maxLabelWidth, titleMetrics.advanceWidth) + Style.spacing.controlPaddingX * 2 + closeButtonWidth : 0
  implicitHeight: barSize

  TextMetrics {
    id: titleMetrics
    text: root.title
    font.family: root.bar ? root.bar.fontFamily : Style.font.family
    font.pixelSize: Style.font.body
  }

  Behavior on implicitWidth {
    NumberAnimation { duration: 180; easing.type: Easing.OutCubic }
  }

  Item {
    id: titleArea
    anchors.top: parent.top
    anchors.bottom: parent.bottom
    anchors.left: parent.left
    anchors.right: closeButton.left
    anchors.leftMargin: Style.space(8)
    clip: true

    Text {
      id: labelText
      anchors.verticalCenter: parent.verticalCenter
      anchors.left: parent.left
      width: parent.width
      text: root.title
      color: root.bar ? root.bar.barForeground : Color.foreground
      font.family: root.bar ? root.bar.fontFamily : Style.font.family
      font.pixelSize: Style.font.body
      elide: Text.ElideRight
      opacity: 0.85
    }

    MouseArea {
      anchors.fill: parent
      acceptedButtons: Qt.LeftButton
      preventStealing: true
      cursorShape: Qt.PointingHandCursor
      onClicked: if (root.toplevel) root.toplevel.activate()
      onEntered: if (root.bar) root.bar.showTooltip(root, root.title)
      onExited: if (root.bar) root.bar.hideTooltip(root)
    }
  }

  Item {
    id: closeButton
    anchors.top: parent.top
    anchors.bottom: parent.bottom
    anchors.right: parent.right
    width: root.closeButtonWidth

    Text {
      anchors.centerIn: parent
      text: "×"
      color: root.bar ? root.bar.barForeground : Color.foreground
      font.family: root.bar ? root.bar.fontFamily : Style.font.family
      font.pixelSize: Style.font.body
      opacity: 0.8
      renderType: Text.NativeRendering
    }

    MouseArea {
      anchors.fill: parent
      acceptedButtons: Qt.LeftButton
      preventStealing: true
      propagateComposedEvents: false
      cursorShape: Qt.PointingHandCursor
      onClicked: function(mouse) {
        if (root.toplevel) root.toplevel.close()
        mouse.accepted = true
      }
      onEntered: if (root.bar) root.bar.showTooltip(closeButton, "Close " + root.title)
      onExited: if (root.bar) root.bar.hideTooltip(closeButton)
    }
  }
}
