import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import QtQuick.Controls.Material

import org.electrum 1.0

// vtc: shows progress while the verthash datafile is generated (once, ~1.2 GB),
// which is needed to verify block headers above the last checkpoint.
Rectangle {
    id: root

    property bool generating: Network.verthashProgress >= 0
    property bool failed: Network.verthashError != ''

    visible: generating || failed
    implicitHeight: visible ? layout.implicitHeight : 0
    color: constants.colorAlpha(failed ? constants.colorError : constants.colorWarning, 0.1)

    ColumnLayout {
        id: layout
        width: parent.width
        spacing: 0

        Label {
            Layout.fillWidth: true
            Layout.leftMargin: constants.paddingLarge
            Layout.rightMargin: constants.paddingLarge
            Layout.topMargin: constants.paddingMedium
            font.pixelSize: constants.fontSizeSmall
            wrapMode: Text.Wrap
            text: root.failed
                ? qsTr('Verthash datafile unavailable: %1').arg(Network.verthashError)
                : Network.verthashProgress < 1
                    ? qsTr('Generating Verthash datafile (one time, 1.2 GB): %1%').arg(Math.floor(Network.verthashProgress * 100))
                    : qsTr('Verifying Verthash datafile...')
        }

        ProgressBar {
            Layout.fillWidth: true
            Layout.leftMargin: constants.paddingLarge
            Layout.rightMargin: constants.paddingLarge
            Layout.bottomMargin: constants.paddingMedium
            visible: root.generating
            indeterminate: Network.verthashProgress >= 1
            value: Network.verthashProgress
        }
    }
}
