import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import QtQuick.Controls.Material

import QtQml

import "controls"

ElDialog
{
    id: root

    property var crashData

    property bool _sending: false

    width: parent.width
    height: parent.height
    z: 1000  // assure topmost of all other dialogs. note: child popups need even higher!
    // disable padding in ElDialog as it is overwritten here and shows no effect, this dialog needs padding though
    needsSystemBarPadding: false

    header: null

    ColumnLayout {
        anchors.topMargin: app.statusBarHeight  // edge-to-edge layout padding
        anchors.bottomMargin: app.navigationBarHeight
        anchors.fill: parent
        enabled: !_sending

        Image {
            Layout.alignment: Qt.AlignCenter
            Layout.preferredWidth: 128
            Layout.preferredHeight: 128
            source: '../../icons/bug.png'
        }
        Label {
            text: qsTr('Sorry!')
            font.pixelSize: constants.fontSizeLarge
        }

        Label {
            Layout.fillWidth: true
            text: qsTr('Something went wrong while executing Electrum-VTC.')
        }
        Label {
            Layout.fillWidth: true
            text: qsTr('To help us diagnose and fix the problem, you can send us a bug report that contains useful debug information:')
            wrapMode: Text.Wrap
        }
        Button {
            Layout.alignment: Qt.AlignCenter
            text: qsTr('Show report contents')
            onClicked: {
                if (crashData.traceback)
                    console.log('traceback: ' + crashData.traceback.stack)
                var dialog = report.createObject(app, {
                    reportText: crashData.reportstring
                })
                dialog.open()
            }
        }
        // vtc: crash reports would go to electrum.org, so sending them is disabled
        Label {
            Layout.fillWidth: true
            text: qsTr('Please copy the report contents and open an issue on GitHub.')
            wrapMode: Text.Wrap
        }
        Item {
            Layout.fillHeight: true
            Layout.preferredWidth: 1
        }
        RowLayout {
            Button {
                Layout.fillWidth: true
                Layout.preferredWidth: 1
                text: qsTr('Copy report')
                onClicked: AppController.textToClipboard(crashData.reportstring)
            }
            Button {
                Layout.fillWidth: true
                Layout.preferredWidth: 1
                text: qsTr('Close')
                onClicked: close()
            }
        }
    }

    BusyIndicator {
        anchors.centerIn: parent
        running: _sending
    }

    Component {
        id: report
        ElDialog {
            property string reportText

            width: parent.width
            height: parent.height
            z: 1001  // above root
            needsSystemBarPadding: false

            header: null

            Flickable {
                anchors.fill: parent
                anchors.topMargin: app.statusBarHeight
                anchors.bottomMargin: app.navigationBarHeight
                contentHeight: reportLabel.implicitHeight
                interactive: height < contentHeight

                Label {
                    id: reportLabel
                    text: reportText
                    wrapMode: Text.Wrap
                    width: parent.width
                    textFormat: Text.RichText
                }
            }
            onClosed: destroy()
        }
    }

    Connections {
        target: AppController
        function onSendingBugreportSuccess(text) {
            _sending = false
            var dialog = app.messageDialog.createObject(app, {
                text: text,
                richText: true,
                z: 1001  // assure topmost of all other dialogs
            })
            dialog.open()
            close()
        }
        function onSendingBugreportFailure(text) {
            _sending = false
            var dialog = app.messageDialog.createObject(app, {
                title: qsTr('Error'),
                iconSource: Qt.resolvedUrl('../../icons/warning.png'),
                text: text,
                richText: true,
                z: 1001  // assure topmost of all other dialogs
            })
            dialog.open()
        }
        function onSendingBugreport() {
            _sending = true
        }
    }
}
