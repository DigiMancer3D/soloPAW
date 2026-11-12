import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import org.kde.plasma.components as PlasmaComponents
import org.kde.plasma.plasma5support as P5Support
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.kirigami as Kirigami

PlasmoidItem {
    id: root
    preferredRepresentation: compactRepresentation
    toolTipMainText: "soloPAW Quick Presets"
    toolTipSubText: "Click a number to switch · double-click to open Profile Switcher"
    implicitWidth: verticalPanel ? 34 : 100
    implicitHeight: verticalPanel ? 100 : 34

    readonly property bool verticalPanel: Plasmoid.formFactor === PlasmaCore.Types.Vertical
        || Plasmoid.location === PlasmaCore.Types.LeftEdge
        || Plasmoid.location === PlasmaCore.Types.RightEdge
    property var names: ["Quick Preset 1", "Quick Preset 2", "Quick Preset 3"]
    property var loadedSlots: [false, false, false]
    property var states: ["idle", "idle", "idle"]
    property int activeSlot: 0
    property string resultMessage: "Click 1, 2, or 3 to activate a Quick Preset."
    property bool lastResultError: false
    property int pendingSlot: 0
    property bool requestingStatus: false
    property string lastDetection: "unknown"
    property string activeConfidence: "unknown"

    function setState(slot, state) {
        let updated = states.slice()
        updated[slot - 1] = state
        states = updated
    }

    function busy() {
        return states.indexOf("busy") >= 0
    }

    function helperCommand(verb, slot) {
        return "sh -c 'exec \"$HOME/.local/bin/solopaw-widget-helper\" " + verb +
            (slot ? " " + slot : "") + "'"
    }

    function refresh() {
        if (requestingStatus) return
        requestingStatus = true
        runSource.connectSource(helperCommand("status", 0))
    }

    function schedule(slot) {
        if (clickTimer.running) clickTimer.stop()
        pendingSlot = slot
        clickTimer.start()
    }

    function activate(slot) {
        if (busy()) {
            resultMessage = "A profile switch is already in progress."
            return
        }
        if (slot < 1 || slot > 3) return
        setState(slot, "busy")
        resultMessage = "Switching Quick Preset " + slot + "…"
        lastResultError = false
        timeoutGuard.restart()
        runSource.connectSource(helperCommand("activate", slot))
    }

    function openApp() {
        clickTimer.stop()
        runSource.connectSource(helperCommand("launch", 0))
    }

    function onActionResult(slot, data) {
        timeoutGuard.stop()
        let parsed = null
        try { parsed = JSON.parse(data["stdout"] || "") } catch(e) {}
        // CLI exit-code zero is NOT proof the injector started successfully.
        const verified = Number(data["exit code"]) === 0 && parsed
            && parsed.ok === true && parsed.verified === true
            && parsed.outcome === "verified"
        const applied = Number(data["exit code"]) === 0 && parsed
            && parsed.ok === true && parsed.outcome === "applied"
            && parsed.confidence === "state-only"
        if (verified || applied) {
            setState(slot, "idle")
            activeSlot = slot
            activeConfidence = verified ? "exact" : "state-only"
            resultMessage = parsed.message || ("Preset " + slot + " activated.")
            lastResultError = false
        } else {
            const uncertain = parsed && parsed.outcome === "unverified"
            setState(slot, uncertain ? "unverified" : "failed")
            resultMessage = parsed && parsed.message ? parsed.message :
                (data["stderr"] || "Switch failed; tap the icon to retry.")
            lastResultError = !uncertain
        }
        refresh()
    }


    Timer {
        id: clickTimer
        interval: 440
        repeat: false
        onTriggered: root.activate(root.pendingSlot)
    }

    Timer {
        id: timeoutGuard
        interval: 70000
        repeat: false
        onTriggered: {
            for (let i = 1; i <= 3; ++i) {
                if (root.states[i-1] === "busy") root.setState(i, "failed")
            }
            root.lastResultError = true
            root.resultMessage = "No switch result was received. Click the red X to retry."
        }
    }

    // Detect changes from the main Profile Switcher and external controls.
    // Low-frequency check; no separate background service.
    Timer {
        id: externalStatusTimer
        interval: 12000
        running: true
        repeat: true
        onTriggered: {
            if (!root.busy() && !root.requestingStatus) root.refresh()
        }
    }

    P5Support.DataSource {
        id: runSource
        engine: "executable"
        connectedSources: []
        onNewData: function(source, data) {
            disconnectSource(source)
            let cmd = String(source)
            if (cmd.indexOf(" activate ") >= 0) {
                let found = cmd.match(/activate ([123])'/)
                if (found) root.onActionResult(Number(found[1]), data)
                return
            }
            if (cmd.indexOf(" status'") >= 0) {
                root.requestingStatus = false
                try {
                    let result = JSON.parse(data["stdout"] || "")
                    if (!result.ok || !result.slots) {
                        if (!root.busy()) root.resultMessage = result.message || "No quick presets configured."
                        return
                    }
                    let n = root.names.slice()
                    let l = root.loadedSlots.slice()
                    let active = 0
                    let confidence = result.confidence || "unknown"
                    for (let i = 0; i < 3; ++i) {
                        let item = result.slots[i]
                        if (!item) continue
                        n[i] = item.label || ("Quick Preset " + (i+1))
                        l[i] = !!item.loaded
                        if (item.active) active = i + 1
                    }
                    root.names = n
                    root.loadedSlots = l
                    root.lastDetection = result.detected ?
                        (result.injector_state || "unknown") : "unverified"
                    if (!root.busy()) {
                        root.activeSlot = active
                        root.activeConfidence = confidence
                        // Clear a stale error when an external switch is now
                        // confirmed by the actual service.
                        if (active > 0 && root.states[active - 1] !== "idle") {
                            root.setState(active, "idle")
                            root.lastResultError = false
                            root.resultMessage = root.names[active - 1] + " is now active."
                        }
                    }

                } catch(e) {
                    if (!root.busy()) root.resultMessage = "Could not read preset names from the local app."
                }
                return
            }
            if (cmd.indexOf(" launch'") >= 0) {
                let parsed = null
                try { parsed = JSON.parse(data["stdout"] || "") } catch(e) {}
                if (Number(data["exit code"]) !== 0 || (parsed && !parsed.ok)) {
                    root.lastResultError = true
                    root.resultMessage = parsed && parsed.message ? parsed.message : "Could not open Profile Switcher."
                    root.expanded = true
                }
            }
        }
    }

    compactRepresentation: Item {
        id: compactRoot
        readonly property int buttonSize: 32
        readonly property int buttonSpacing: 2
        readonly property int stripLength: 3 * buttonSize + 2 * buttonSpacing
        implicitWidth: root.verticalPanel ? buttonSize + 2 : stripLength
        implicitHeight: root.verticalPanel ? stripLength : buttonSize + 2
        // The panel's Layout engine uses these hints to reserve actual space.
        // implicitWidth/implicitHeight on PlasmoidItem alone are NOT enough.
        Layout.minimumWidth: implicitWidth
        Layout.minimumHeight: implicitHeight
        Layout.preferredWidth: implicitWidth
        Layout.preferredHeight: implicitHeight
        clip: true

        Grid {
            id: buttonGrid
            anchors.centerIn: parent
            rows: root.verticalPanel ? 3 : 1
            columns: root.verticalPanel ? 1 : 3
            spacing: compactRoot.buttonSpacing
            Repeater {
                model: 3
                delegate: QuickOrb {
                    slot: index + 1
                    compact: true
                    buttonSize: compactRoot.buttonSize
                    description: root.names[index]
                    loaded: root.loadedSlots[index]
                    active: root.activeSlot === index + 1
                    estimated: root.activeConfidence === "state-only"
                    actionState: root.states[index]
                    onSingleRequested: function(slot) { root.schedule(slot) }
                    onAppRequested: root.openApp()
                }
            }
        }
    }

    fullRepresentation: Item {
        implicitWidth: root.verticalPanel ? 330 : 350
        implicitHeight: 390

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 12
            spacing: 9

            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                Image {
                    source: Qt.resolvedUrl("../images/logo.png")
                    fillMode: Image.PreserveAspectFit
                    Layout.preferredWidth: 38
                    Layout.preferredHeight: 38
                    sourceSize.width: 76
                    sourceSize.height: 76
                }
                PlasmaComponents.Label {
                    text: "soloPAW · QUICK PRESETS"
                    font.bold: true
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                }
                PlasmaComponents.ToolButton {
                    text: "↻"
                    display: Controls.AbstractButton.TextOnly
                    onClicked: root.refresh()
                    Controls.ToolTip.text: "Refresh names and running preset"
                    Controls.ToolTip.visible: hovered
                }
            }

            Repeater {
                model: 3
                delegate: Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 57
                    radius: 10
                    color: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g,
                                  Kirigami.Theme.textColor.b, 0.055)
                    border.width: root.activeSlot === index + 1 ? 1 : 0
                    border.color: root.activeConfidence === "state-only" ? "#f3c15d" : "#53e8b1"
                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 6
                        spacing: 9
                        QuickOrb {
                            slot: index + 1
                            compact: false
                            loaded: root.loadedSlots[index]
                            active: root.activeSlot === index + 1
                            estimated: root.activeConfidence === "state-only"
                            description: root.names[index]
                            actionState: root.states[index]
                            onSingleRequested: function(slot) { root.schedule(slot) }
                            onAppRequested: root.openApp()
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 2
                            PlasmaComponents.Label {
                                text: root.names[index]
                                font.bold: true
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }
                            PlasmaComponents.Label {
                                text: root.states[index] === "busy" ? "Switching…" :
                                      root.states[index] === "failed" ? "✕ Failed · tap to retry" :
                                      root.states[index] === "unverified" ? "? Unverified · tap to retry" :
                                      root.activeSlot === index + 1 ?
                                          (root.activeConfidence === "state-only" ? "● Running · preset from app hint" : "● Active · verified") :
                                      root.loadedSlots[index] ? "Tap to activate" : "Not assigned / preset missing"
                                color: root.states[index] === "failed" ? "#ff6977" :
                                       root.states[index] === "unverified" ? "#f3c15d" :
                                       root.activeSlot === index + 1 ?
                                           (root.activeConfidence === "state-only" ? "#f3c15d" : "#60dbae") :
                                           Kirigami.Theme.disabledTextColor
                                font.pixelSize: 11
                            }
                        }
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                PlasmaComponents.Button {
                    Layout.fillWidth: true
                    text: "Open Profile Switcher"
                    icon.name: "input-mouse"
                    onClicked: root.openApp()
                }
                PlasmaComponents.Button {
                    text: "Refresh"
                    icon.name: "view-refresh"
                    onClicked: root.refresh()
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: 10
                color: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g,
                              Kirigami.Theme.textColor.b, 0.055)
                border.width: 1
                border.color: root.lastResultError ? "#ff6b7d" : "#5fe0b1"
                PlasmaComponents.Label {
                    anchors.fill: parent
                    anchors.margins: 10
                    wrapMode: Text.WordWrap
                    verticalAlignment: Text.AlignVCenter
                    text: root.resultMessage
                }
            }
        }

        Component.onCompleted: root.refresh()
    }

    Component.onCompleted: refresh()
}
