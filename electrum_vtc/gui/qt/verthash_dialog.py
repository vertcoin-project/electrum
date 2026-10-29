# Electrum-VTC: progress of the verthash datafile, while it is being generated.

import os
from typing import TYPE_CHECKING

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QVBoxLayout, QProgressBar, QLabel, QPushButton

from electrum_vtc import verthash
from electrum_vtc.i18n import _

from .util import WindowModalDialog, WWLabel, Buttons

if TYPE_CHECKING:
    from .main_window import ElectrumWindow


class VerthashDialog(WindowModalDialog):
    """Shown when the wallet window opens while verthash.dat is still being
    generated (in a child process, so the wallet stays usable). Closing it
    leaves the generation running; the status bar keeps showing its progress."""

    def __init__(self, window: 'ElectrumWindow'):
        WindowModalDialog.__init__(self, window, _('Verthash datafile'))
        self.setMinimumWidth(500)
        # where prepare() generates it
        path = window.config.VERTHASH_DATAFILE_PATH or verthash.datafile.default_path(window.config)
        folder = os.path.normpath(os.path.dirname(path))
        vbox = QVBoxLayout(self)
        vbox.addWidget(WWLabel(
            _('Electrum-VTC checks the proof of work of Vertcoin blocks with Verthash, '
              'which needs a 1.2 GB datafile, verthash.dat. It is created once, in {}, '
              'and this takes a few minutes.').format(folder)
            + '\n\n'
            + _('You can use your wallet meanwhile. New blocks are verified '
                'once the datafile is ready.')))
        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        vbox.addWidget(self.bar)
        self.status = QLabel()
        vbox.addWidget(self.status)
        self.close_button = QPushButton(_('Continue in background'))
        self.close_button.clicked.connect(self.close)
        vbox.addLayout(Buttons(self.close_button))
        # the generation's own events arrive about every 2 s; poll to stay simple
        self.timer = QTimer(self)
        self.timer.setInterval(500)
        self.timer.timeout.connect(self.refresh)
        self.timer.start()
        self.refresh()

    def refresh(self):
        df = verthash.datafile
        if df.is_ready():
            self.bar.setRange(0, 1000)
            self.bar.setValue(1000)
            self.status.setText(_('verthash.dat is ready.'))
            self.close_button.setText(_('Close'))
            self.timer.stop()
        elif df.error:
            self.status.setText(_('Could not create verthash.dat: {}').format(df.error))
            self.close_button.setText(_('Close'))
            self.timer.stop()
        elif df.progress is not None:
            if df.progress < 1:
                self.bar.setValue(int(df.progress * 1000))
                self.status.setText(_('Creating verthash.dat: {}%').format(int(df.progress * 100)))
            else:
                # generated; its checksum is being verified
                self.bar.setRange(0, 0)
                self.status.setText(_('Checking verthash.dat...'))
