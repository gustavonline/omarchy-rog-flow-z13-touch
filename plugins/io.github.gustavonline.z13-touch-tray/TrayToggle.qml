import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

// Keep Omarchy's packaged tray as the implementation so tray behaviour and
// fixes continue to arrive with normal system updates. This wrapper adds only
// the touch interaction that the stock hover-oriented chevron does not have.
BarWidget {
  id: root
  moduleName: "io.github.gustavonline.z13-touch-tray"

  property bool touchExpanded: false
  property bool coverAttached: true
  readonly property string coverStatePath: Quickshell.env("XDG_RUNTIME_DIR") + "/z13-cover-state"
  readonly property bool tabletMode: !coverAttached
  readonly property var stockTray: stockTrayLoader.item

  visible: stockTray
    ? stockTray.pinnedItems.length > 0 || stockTray.drawerCount > 0
    : false
  implicitWidth: stockTray ? stockTray.implicitWidth : 0
  implicitHeight: stockTray ? stockTray.implicitHeight : root.barSize

  function applyTouchState() {
    if (stockTray) stockTray.expanded = touchExpanded
  }

  function toggleTouchExpanded() {
    if (!tabletMode) return
    touchExpanded = !touchExpanded
    applyTouchState()
  }

  function applyCoverState(raw) {
    coverAttached = String(raw || "").trim() !== "detached"
    if (coverAttached) {
      touchExpanded = false
      applyTouchState()
    }
  }

  FileView {
    path: root.coverStatePath
    watchChanges: true
    printErrors: false
    onLoaded: root.applyCoverState(text())
    onFileChanged: root.applyCoverState(text())
  }

  Loader {
    id: stockTrayLoader
    anchors.fill: parent
    source: "file:///usr/share/omarchy/shell/plugins/bar/widgets/Tray.qml"

    onLoaded: {
      item.bar = root.bar
      item.moduleName = root.moduleName
      item.settings = root.settings
      root.applyTouchState()
    }
  }

  Binding {
    target: root.stockTray
    property: "bar"
    value: root.bar
    when: root.stockTray !== null
  }

  Binding {
    target: root.stockTray
    property: "moduleName"
    value: root.moduleName
    when: root.stockTray !== null
  }

  Binding {
    target: root.stockTray
    property: "settings"
    value: root.settings
    when: root.stockTray !== null
  }

  // The stock tray still follows hover while it is not pinned. When its
  // internal HoverHandler sees the pointer leave, restore the touch-pinned
  // open state on the next event-loop turn.
  Connections {
    target: root.stockTray
    ignoreUnknownSignals: true

    function onExpandedChanged() {
      if (root.touchExpanded && root.stockTray && !root.stockTray.expanded)
        Qt.callLater(root.applyTouchState)
    }
  }

  IpcHandler {
    target: "io.github.gustavonline.z13-touch-tray"

    function drawerState(): string {
      return root.touchExpanded ? "shown" : "hidden"
    }

    function toggleDrawer(): string {
      chevronTouchTarget.triggerPress(Qt.LeftButton)
      return root.touchExpanded ? "shown" : "hidden"
    }

    function clickRoute(): string {
      if (!root.bar || !root.stockTray || !root.parent || !root.parent.parent)
        return "unavailable"
      var localX = chevronTouchTarget.x + chevronTouchTarget.width / 2
      var localY = chevronTouchTarget.y + chevronTouchTarget.height / 2
      var target = root.bar.moduleClickTargetAt(root.parent.parent, localX, localY)
      return target === chevronTouchTarget ? "touch-toggle" : "stock-or-other"
    }

    function stockState(): string {
      if (!root.stockTray) return "not-loaded"
      return JSON.stringify({
        drawerCount: root.stockTray.drawerCount,
        expanded: root.stockTray.expanded,
        revealExtent: root.stockTray.revealExtent,
        touchExpanded: root.touchExpanded,
        visible: root.stockTray.visible
      })
    }
  }

  // The chevron moves left as the drawer opens. Track that public geometry so
  // only the chevron is overlaid; every tray icon keeps its native actions.
  WidgetButton {
    id: chevronTouchTarget

    visible: root.tabletMode && root.stockTray && root.stockTray.drawerCount > 0
    x: !root.stockTray || root.vertical ? 0 : root.stockTray.drawerExtent - root.stockTray.revealExtent
    y: !root.stockTray || !root.vertical ? 0 : root.stockTray.drawerExtent - root.stockTray.revealExtent
    width: !root.stockTray ? 0 : (root.vertical ? root.width : root.stockTray.trayItemExtent)
    height: !root.stockTray ? 0 : (root.vertical ? root.stockTray.trayItemExtent : root.height)
    bar: root.bar
    hasVisualContent: true
    labelVisible: false
    tooltipText: root.touchExpanded ? "Hide background apps" : "Show background apps"

    // The bar routes touch through registered WidgetButtons before ordinary
    // MouseAreas. Re-register once all children exist so this transparent
    // target stays above the stock chevron's mouse-only handler.
    Component.onCompleted: Qt.callLater(syncClickRegistration)

    onPressed: function(button) {
      if (button === Qt.RightButton) {
        root.stockTray.managePopupOpen = !root.stockTray.managePopupOpen
      } else if (button === Qt.LeftButton) {
        root.toggleTouchExpanded()
      }
    }
  }
}
