import QtQuick
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami

Item {
    id: orb
    property int slot: 1
    property bool compact: true
    property int buttonSize: 32
    property bool active: false
    property bool estimated: false
    property bool loaded: true
    property string actionState: "idle"
    property string description: ""

    signal singleRequested(int slot)
    signal appRequested()

    implicitWidth: compact ? buttonSize : 43
    implicitHeight: compact ? buttonSize : 43
    width: implicitWidth
    height: implicitHeight

    Rectangle {
        anchors.fill: parent
        radius: width * 0.28
        color: orb.actionState === "failed" ? "#a01c36" :
               orb.active ? "#1c4b41" : Qt.rgba(Kirigami.Theme.backgroundColor.r,
                   Kirigami.Theme.backgroundColor.g, Kirigami.Theme.backgroundColor.b, 0.40)
        border.width: orb.active || orb.actionState === "failed" || orb.actionState === "unverified" ? 2 : 1
        border.color: orb.actionState === "failed" ? "#ff6b7d" :
                      orb.actionState === "unverified" ? "#f3c15d" :
                      orb.active && orb.estimated ? "#f3c15d" :
                      orb.active ? "#56e7ad" : "#77879c"
    }

    Image {
        id: emblem
        anchors.centerIn: parent
        width: parent.width - 4
        height: parent.height - 4
        source: orb.slot === 1 ? Qt.resolvedUrl("../images/slot1.png") :
                orb.slot === 2 ? Qt.resolvedUrl("../images/slot2.png") :
                                 Qt.resolvedUrl("../images/slot3.png")
        fillMode: Image.PreserveAspectFit
        sourceSize.width: 128
        sourceSize.height: 128
        opacity: orb.loaded ? 1.0 : 0.37
        smooth: true
        asynchronous: false
    }

    // Never leave a button blank if the image loader cannot resolve an asset.
    Text {
        anchors.centerIn: parent
        visible: emblem.status !== Image.Ready
        text: String(orb.slot)
        font.bold: true
        font.pixelSize: Math.max(18, Math.floor(orb.width * 0.65))
        color: "#84fdf4"
        style: Text.Outline
        styleColor: "#111d27"
    }

    Controls.BusyIndicator {
        anchors.fill: parent
        anchors.margins: -2
        running: orb.actionState === "busy"
        visible: running
    }

    Rectangle {
        visible: orb.actionState === "failed"
        width: 20
        height: 20
        radius: 10
        anchors.right: parent.right
        anchors.top: parent.top
        color: "#d92548"
        border.width: 1
        border.color: "#ffe2e8"
        Text {
            anchors.centerIn: parent
            text: "✕"
            font.bold: true
            font.pixelSize: 14
            color: "white"
        }
    }

    Rectangle {
        visible: orb.actionState === "unverified"
        width: 20
        height: 20
        radius: 10
        anchors.right: parent.right
        anchors.top: parent.top
        color: "#b87810"
        border.width: 1
        border.color: "#ffe1a0"
        Text {
            anchors.centerIn: parent
            text: "?"
            font.bold: true
            font.pixelSize: 14
            color: "white"
        }
    }

    Rectangle {
        visible: orb.active && orb.actionState === "idle"
        anchors.bottom: parent.bottom
        anchors.horizontalCenter: parent.horizontalCenter
        width: 14
        height: 3
        radius: 2
        color: orb.estimated ? "#f3c15d" : "#65f8b4"
    }

    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton
        hoverEnabled: true
        onClicked: orb.singleRequested(orb.slot)
        onDoubleClicked: orb.appRequested()
        Controls.ToolTip.visible: containsMouse && !pressed
        Controls.ToolTip.delay: 700
        Controls.ToolTip.text: "Quick " + orb.slot + ": " + (orb.description || "Not assigned") +
           (orb.actionState === "failed" ? " · FAILED · CLICK TO RETRY" :
            orb.actionState === "unverified" ? " · STATUS UNKNOWN · CLICK TO RETRY" :
            orb.actionState === "busy" ? " · switching…" :
            orb.active && orb.estimated ? " · RUNNING (exact preset not exposed by Input Remapper 2.2.1)" :
            " · click: switch · double-click: app")
    }
}
