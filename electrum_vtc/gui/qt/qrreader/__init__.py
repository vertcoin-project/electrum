# Copyright (C) 2021 The Electrum developers
# Distributed under the MIT software license, see the accompanying
# file LICENCE or http://www.opensource.org/licenses/mit-license.php
#
# We have two toolchains to scan qr codes:
# 1. access camera via QtMultimedia, take picture, feed picture to zbar
# 2. let zbar handle whole flow (including accessing the camera)
#
# notes:
# - zbar needs to be compiled with platform-dependent extra config options to be able
#   to access the camera
# - zbar fails to access the camera on macOS
# - qtmultimedia seems to support more cameras on Windows than zbar
# - qtmultimedia is often not packaged with PyQt5
#   in particular, on debian, you need both "python3-pyqt5" and "python3-pyqt5.qtmultimedia"
# - older versions of qtmultimedia don't seem to work reliably
#
# Considering the above, we use QtMultimedia for Windows and macOS, as there
# most users run our binaries where we can make sure the packaged versions work well.
# On Linux where many people run from source, we use zbar.
#
# Note: this module is safe to import on all platforms.

import sys
from typing import Callable, Optional, TYPE_CHECKING, Mapping

from PyQt5.QtWidgets import QMessageBox, QWidget

from electrum_vtc.i18n import _
from electrum_vtc.util import UserFacingException
from electrum_vtc.logging import get_logger

from electrum_vtc.gui.qt.util import MessageBoxMixin, custom_message_box


if TYPE_CHECKING:
    from electrum_vtc.simple_config import SimpleConfig


_logger = get_logger(__name__)


def scan_qrcode(
        *,
        parent: Optional[QWidget],
        config: 'SimpleConfig',
        callback: Callable[[bool, str, Optional[str]], None],
) -> None:
    if sys.platform == 'darwin' or sys.platform in ('windows', 'win32'):
        _scan_qrcode_using_qtmultimedia(parent=parent, config=config, callback=callback)
    else:  # desktop Linux and similar
        _scan_qrcode_using_zbar(parent=parent, config=config, callback=callback)


def find_system_cameras() -> Mapping[str, str]:
    """Returns a camera_description -> camera_path map."""
    if sys.platform == 'darwin' or sys.platform in ('windows', 'win32'):
        try:
            from .qtmultimedia import find_system_cameras
        except ImportError as e:
            return {}
        else:
            return find_system_cameras()
    else:  # desktop Linux and similar
        from electrum_vtc import qrscanner
        return qrscanner.find_system_cameras()


# --- Internals below (not part of external API)

def _scan_qrcode_using_zbar(
        *,
        parent: Optional[QWidget],
        config: 'SimpleConfig',
        callback: Callable[[bool, str, Optional[str]], None],
) -> None:
    from electrum_vtc import qrscanner
    data = None
    try:
        data = qrscanner.scan_barcode(config.get_video_device())
    except UserFacingException as e:
        success = False
        error = str(e)
    except BaseException as e:
        _logger.exception('camera error')
        success = False
        error = repr(e)
    else:
        success = True
        error = ""
    callback(success, error, data)


# Use a global to prevent multiple QR dialogs created simultaneously
_qr_dialog = None


def _scan_qrcode_using_qtmultimedia(
        *,
        parent: Optional[QWidget],
        config: 'SimpleConfig',
        callback: Callable[[bool, str, Optional[str]], None],
) -> None:
    try:
        from .qtmultimedia import QrReaderCameraDialog, CameraError, MissingQrDetectionLib
    except ImportError as e:
        icon = QMessageBox.Warning
        title = _("QR Reader Error")
        message = _("QR reader failed to load. This may happen if "
                    "you are using an older version of PyQt5.") + "\n\n" + str(e)
        if isinstance(parent, MessageBoxMixin):
            parent.msg_box(title=title, text=message, icon=icon, parent=None)
        else:
            custom_message_box(title=title, text=message, icon=icon, parent=parent)
        return

    global _qr_dialog
    if _qr_dialog:
        _logger.warning("QR dialog is already presented, ignoring.")
        return
    _qr_dialog = None
    try:
        _qr_dialog = QrReaderCameraDialog(parent=parent, config=config)

        def _on_qr_reader_finished(success: bool, error: str, data):
            global _qr_dialog
            if _qr_dialog:
                _qr_dialog.deleteLater()
                _qr_dialog = None
            callback(success, error, data)

        _qr_dialog.qr_finished.connect(_on_qr_reader_finished)
        _qr_dialog.start_scan(config.get_video_device())
    except (MissingQrDetectionLib, CameraError) as e:
        _qr_dialog = None
        callback(False, str(e), None)
    except Exception as e:
        _logger.exception('camera error')
        _qr_dialog = None
        callback(False, repr(e), None)
