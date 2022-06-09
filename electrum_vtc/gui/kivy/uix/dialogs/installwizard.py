
from functools import partial
import threading
import os
from typing import TYPE_CHECKING

from kivy.app import App
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import ObjectProperty, StringProperty, OptionProperty
from kivy.core.window import Window
from kivy.uix.button import Button
from kivy.uix.togglebutton import ToggleButton
from kivy.utils import platform
from kivy.uix.widget import Widget
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.utils import platform

from electrum.base_wizard import BaseWizard
from electrum.util import is_valid_email


from . import EventsDialog
from ...i18n import _
from .password_dialog import PasswordDialog

if TYPE_CHECKING:
    from electrum.gui.kivy.main_window import ElectrumWindow


# global Variables

Builder.load_string('''
#:import Window kivy.core.window.Window
#:import _ electrum.gui.kivy.i18n._
#:import KIVY_GUI_PATH electrum.gui.kivy.KIVY_GUI_PATH


<WizardTextInput@TextInput>
    border: 4, 4, 4, 4
    font_size: '15sp'
    padding: '15dp', '15dp'
    background_color: (1, 1, 1, 1) if self.focus else (0.454, 0.698, 0.909, 1)
    foreground_color: (0.31, 0.31, 0.31, 1) if self.focus else (0.835, 0.909, 0.972, 1)
    hint_text_color: self.foreground_color
    background_active: f'atlas://{KIVY_GUI_PATH}/theming/atlas/light/create_act_text_active'
    background_normal: f'atlas://{KIVY_GUI_PATH}/theming/atlas/light/create_act_text_active'
    size_hint_y: None
    height: '48sp'

<WizardButton@Button>:
    root: None
    size_hint: 1, None
    height: '48sp'
    on_press: if self.root: self.root.dispatch('on_press', self)
    on_release: if self.root: self.root.dispatch('on_release', self)

<BigLabel@Label>
    color: .854, .925, .984, 1
    size_hint: 1, None
    text_size: self.width, None
    height: self.texture_size[1]
    bold: True

<-WizardDialog>
    text_color: .854, .925, .984, 1
    value: ''
    #auto_dismiss: False
    size_hint: None, None
    canvas.before:
        Color:
            rgba: .239, .588, .882, 1
        Rectangle:
            size: Window.size

    crcontent: crcontent
    # add electrum icon
    BoxLayout:
        orientation: 'vertical' if self.width < self.height else 'horizontal'
        padding:
            min(dp(27), self.width/32), min(dp(27), self.height/32),\
            min(dp(27), self.width/32), min(dp(27), self.height/32)
        spacing: '10dp'
        GridLayout:
            id: grid_logo
            cols: 1
            pos_hint: {'center_y': .5}
            size_hint: 1, None
            height: self.minimum_height
            Label:
                color: root.text_color
                text: 'ELECTRUM'
                size_hint: 1, None
                height: self.texture_size[1] if self.opacity else 0
                font_size: '33sp'
                font_name: f'{KIVY_GUI_PATH}/data/fonts/tron/Tr2n.ttf'
        GridLayout:
            cols: 1
            id: crcontent
            spacing: '1dp'
        Widget:
            size_hint: 1, 0.3
        GridLayout:
            rows: 1
            spacing: '12dp'
            size_hint: 1, None
            height: self.minimum_height
            WizardButton:
                id: back
                text: _('Back')
                root: root
            WizardButton:
                id: next
                text: _('Next')
                root: root
                disabled: root.value == ''


<WizardMultisigDialog>
    value: 'next'
    Widget
        size_hint: 1, 1
    Label:
        color: root.text_color
        size_hint: 1, None
        text_size: self.width, None
        height: self.texture_size[1]
        text: _("Choose the number of signatures needed to unlock funds in your wallet")
    Widget
        size_hint: 1, 1
    GridLayout:
        cols: 2
        spacing: '14dp'
        size_hint: 1, 1
        height: self.minimum_height
        Label:
            color: root.text_color
            text: _('From {} cosigners').format(n.value)
        Slider:
            id: n
            range: 2, 5
            step: 1
            value: 2
        Label:
            color: root.text_color
            text: _('Require {} signatures').format(m.value)
        Slider:
            id: m
            range: 1, n.value
            step: 1
            value: 2
    Widget
        size_hint: 1, 1
    Label:
        id: backup_warning_label
        color: root.text_color
        size_hint: 1, None
        text_size: self.width, None
        height: self.texture_size[1]
        opacity: int(m.value != n.value)
        text: _("Warning: to be able to restore a multisig wallet, " \
                "you should include the master public key for each cosigner " \
                "in all of your backups.")


<WizardChoiceDialog>
    message : ''
    Widget:
        size_hint: 1, 1
    Label:
        color: root.text_color
        size_hint: 1, None
        text_size: self.width, None
        height: self.texture_size[1]
        text: root.message
    Widget
        size_hint: 1, 1
    GridLayout:
        row_default_height: '48dp'
        id: choices
        cols: 1
        spacing: '14dp'
        size_hint: 1, None

<WizardConfirmDialog>
    message : ''
    Widget:
        size_hint: 1, 1
    Label:
        color: root.text_color
        size_hint: 1, None
        text_size: self.width, None
        height: self.texture_size[1]
        text: root.message
    Widget
        size_hint: 1, 1

<WizardTOSDialog>
    message : ''
    size_hint: 1, 1
    ScrollView:
        size_hint: 1, 1
        TextInput:
            color: root.text_color
            size_hint: 1, None
            text_size: self.width, None
            height: self.minimum_height
            text: root.message
            disabled: True

<WizardEmailDialog>
    Label:
        color: root.text_color
        size_hint: 1, None
        text_size: self.width, None
        height: self.texture_size[1]
        text: 'Please enter your email address'
    WizardTextInput:
        id: email
        on_text: Clock.schedule_once(root.on_text)
        multiline: False
        on_text_validate: Clock.schedule_once(root.on_enter)

<WizardKnownOTPDialog>
    message : ''
    message2: ''
    Widget:
        size_hint: 1, 1
    Label:
        color: root.text_color
        size_hint: 1, None
        text_size: self.width, None
        height: self.texture_size[1]
        text: root.message
    Widget
        size_hint: 1, 1
    WizardTextInput:
        id: otp
        on_text: Clock.schedule_once(root.on_text)
        multiline: False
        on_text_validate: Clock.schedule_once(root.on_enter)
    Widget
        size_hint: 1, 1
    Label:
        color: root.text_color
        size_hint: 1, None
        text_size: self.width, None
        height: self.texture_size[1]
        text: root.message2
    Widget
        size_hint: 1, 1
        height: '48sp'
    BoxLayout:
        orientation: 'horizontal'
        WizardButton:
            id: cb
            text: _('Request new secret')
            on_release: root.request_new_secret()
            size_hint: 1, None
        WizardButton:
            id: abort
            text: _('Abort creation')
            on_release: root.abort_wallet_creation()
            size_hint: 1, None


<WizardNewOTPDialog>
    message : ''
    message2 : ''
    Label:
        color: root.text_color
        size_hint: 1, None
        text_size: self.width, None
        height: self.texture_size[1]
        text: root.message
    QRCodeWidget:
        id: qr
        size_hint: 1, 1
    Label:
        color: root.text_color
        size_hint: 1, None
        text_size: self.width, None
        height: self.texture_size[1]
        text: root.message2
    WizardTextInput:
        id: otp
        on_text: Clock.schedule_once(root.on_text)
        multiline: False
        on_text_validate: Clock.schedule_once(root.on_enter)

<MButton@Button>:
    size_hint: 1, None
    height: '33dp'
    on_release:
        self.parent.update_amount(self.text)

<WordButton@Button>:
    size_hint: None, None
    padding: '5dp', '5dp'
    text_size: None, self.height
    width: self.texture_size[0]
    height: '30dp'
    on_release:
        if self.parent: self.parent.new_word(self.text)


<SeedButton@Button>:
    height: dp(100)
    border: 4, 4, 4, 4
    halign: 'justify'
    valign: 'top'
    font_size: '18dp'
    text_size: self.width - dp(24), self.height - dp(12)
    color: .1, .1, .1, 1
    background_normal: f'atlas://{KIVY_GUI_PATH}/theming/atlas/light/white_bg_round_top'
    background_down: self.background_normal
    size_hint_y: None


<SeedLabel@Label>:
    font_size: '12sp'
    text_size: self.width, None
    size_hint: 1, None
    height: self.texture_size[1]
    halign: 'justify'
    valign: 'middle'
    border: 4, 4, 4, 4

<SeedDialogHeader@GridLayout>
    text: ''
    options_dialog: None
    rows: 1
    size_hint: 1, None
    height: self.minimum_height
    BigLabel:
        size_hint: 9, None
        text: root.text
    IconButton:
        id: options_button
        height: '30dp'
        width: '30dp'
        size_hint: 1, None
        icon: f'atlas://{KIVY_GUI_PATH}/theming/atlas/light/gear'
        on_release:
            root.options_dialog() if root.options_dialog else None

<RestoreSeedDialog>
    message: ''
    word: ''
    SeedDialogHeader:
        id: seed_dialog_header
        text: 'ENTER YOUR SEED PHRASE'
        options_dialog: root.options_dialog
    GridLayout:
        cols: 1
        padding: 0, '12dp'
        spacing: '12dp'
        size_hint: 1, None
        height: self.minimum_height
        SeedButton:
            id: text_input_seed
            text: ''
            on_text: Clock.schedule_once(root.on_text)
        SeedLabel:
            text: root.message
        BoxLayout:
            id: suggestions
            height: '35dp'
            size_hint: 1, None
            new_word: root.on_word
        BoxLayout:
            id: line1
            update_amount: root.update_text
            size_hint: 1, None
            height: '30dp'
            MButton:
                text: 'Q'
            MButton:
                text: 'W'
            MButton:
                text: 'E'
            MButton:
                text: 'R'
            MButton:
                text: 'T'
            MButton:
                text: 'Y'
            MButton:
                text: 'U'
            MButton:
                text: 'I'
            MButton:
                text: 'O'
            MButton:
                text: 'P'
        BoxLayout:
            id: line2
            update_amount: root.update_text
            size_hint: 1, None
            height: '30dp'
            Widget:
                size_hint: 0.5, None
                height: '33dp'
            MButton:
                text: 'A'
            MButton:
                text: 'S'
            MButton:
                text: 'D'
            MButton:
                text: 'F'
            MButton:
                text: 'G'
            MButton:
                text: 'H'
            MButton:
                text: 'J'
            MButton:
                text: 'K'
            MButton:
                text: 'L'
            Widget:
                size_hint: 0.5, None
                height: '33dp'
        BoxLayout:
            id: line3
            update_amount: root.update_text
            size_hint: 1, None
            height: '30dp'
            Widget:
                size_hint: 1, None
            MButton:
                text: 'Z'
            MButton:
                text: 'X'
            MButton:
                text: 'C'
            MButton:
                text: 'V'
            MButton:
                text: 'B'
            MButton:
                text: 'N'
            MButton:
                text: 'M'
            MButton:
                text: ' '
            MButton:
                text: '<'

<AddXpubDialog>
    title: ''
    message: ''
    BigLabel:
        text: root.title
    GridLayout
        cols: 1
        padding: 0, '12dp'
        spacing: '12dp'
        size_hint: 1, None
        height: self.minimum_height
        SeedButton:
            id: text_input
            text: ''
            on_text: Clock.schedule_once(root.check_text)
        SeedLabel:
            text: root.message
    GridLayout
        rows: 1
        spacing: '12dp'
        size_hint: 1, None
        height: self.minimum_height
        IconButton:
            id: scan
            height: '48sp'
            on_release: root.scan_xpub()
            icon: f'atlas://{KIVY_GUI_PATH}/theming/atlas/light/camera'
            size_hint: 1, None
        WizardButton:
            text: _('Paste')
            on_release: root.do_paste()
        WizardButton:
            text: _('Clear')
            on_release: root.do_clear()


<ShowXpubDialog>
    xpub: ''
    message: _('Here is your master public key. Share it with your cosigners.')
    BigLabel:
        text: "MASTER PUBLIC KEY"
    GridLayout
        cols: 1
        padding: 0, '12dp'
        spacing: '12dp'
        size_hint: 1, None
        height: self.minimum_height
        SeedButton:
            id: text_input
            text: root.xpub
        SeedLabel:
            text: root.message
    GridLayout
        rows: 1
        spacing: '12dp'
        size_hint: 1, None
        height: self.minimum_height
        WizardButton:
            text: _('QR code')
            on_release: root.do_qr()
        WizardButton:
            text: _('Copy')
            on_release: root.do_copy()
        WizardButton:
            text: _('Share')
            on_release: root.do_share()

<ShowSeedDialog>
    spacing: '12dp'
    value: 'next'
    SeedDialogHeader:
        text: "PLEASE WRITE DOWN YOUR SEED PHRASE"
        options_dialog: root.options_dialog
    GridLayout:
        id: grid
        cols: 1
        pos_hint: {'center_y': .5}
        size_hint_y: None
        height: self.minimum_height
        spacing: '12dp'
        SeedButton:
            text: root.seed_text
        SeedLabel:
            text: root.message

<LineDialog>
    BigLabel:
        text: root.title
    SeedLabel:
        text: root.message
    TextInput:
        id: passphrase_input
        multiline: False
        size_hint: 1, None
        height: '48dp'
        on_text: Clock.schedule_once(root.on_text)
    SeedLabel:
        text: root.warning

<ChoiceLineDialog>
    BigLabel:
        text: root.title
    SeedLabel:
        text: root.message1
    GridLayout:
        row_default_height: '48dp'
        id: choices
        cols: 1
        spacing: '14dp'
        size_hint: 1, None
    SeedLabel:
        text: root.message2
    TextInput:
        id: text_input
        multiline: False
        size_hint: 1, None
        height: '48dp'

''')



class WizardDialog(EventsDialog):
    ''' Abstract dialog to be used as the base for all Create Account Dialogs
    '''
    crcontent = ObjectProperty(None)

    def __init__(self, wizard, **kwargs):
        self.auto_dismiss = False
        super(WizardDialog, self).__init__()
        self.wizard = wizard
        self.ids.back.disabled = not wizard.can_go_back()
        self.app = App.get_running_app()
        self.run_next = kwargs['run_next']

        self._trigger_size_dialog = Clock.create_trigger(self._size_dialog, -1)
        # note: everything bound here needs to be unbound as otherwise the
        # objects will be kept around and keep receiving the callbacks
        Window.bind(size=self._trigger_size_dialog,
                    rotation=self._trigger_size_dialog,
                    on_keyboard=self.on_keyboard)
        self._trigger_size_dialog()
        self._on_release = False

    def _size_dialog(self, dt):
        if self.app.ui_mode[0] == 'p':
            self.size = Window.size
        else:
            #tablet
            if self.app.orientation[0] == 'p':
                #portrait
                self.size = Window.size[0]/1.67, Window.size[1]/1.4
            else:
                self.size = Window.size[0]/2.5, Window.size[1]

    def add_widget(self, widget, index=0):
        if not self.crcontent:
            super(WizardDialog, self).add_widget(widget)
        else:
            self.crcontent.add_widget(widget, index=index)

    def on_keyboard(self, instance, key, keycode, codepoint, modifier):
        if key == 27:
            if self.wizard.can_go_back():
                self.dismiss()
                self.wizard.go_back()
            else:
                if not self.app.is_exit:
                    self.app.is_exit = True
                    self.app.show_info(_('Press again to exit'))
                else:
                    self._on_release = False
                    self.dismiss()
            return True

    def on_dismiss(self):
        Window.unbind(size=self._trigger_size_dialog,
                      rotation=self._trigger_size_dialog,
                      on_keyboard=self.on_keyboard)
        if self.app.wallet is None and not self._on_release:
            self.app.stop()

    def get_params(self, button):
        return (None,)

    def on_release(self, button):
        if self._on_release is True:
            return
        self._on_release = True
        self.dismiss()
        if not button:
            self.wizard.terminate(aborted=True)
            return
        if button is self.ids.back:
            self.wizard.go_back()
            return
        params = self.get_params(button)
        self.run_next(*params)


class WizardMultisigDialog(WizardDialog):

    def get_params(self, button):
        m = self.ids.m.value
        n = self.ids.n.value
        return m, n


class WizardOTPDialogBase(WizardDialog):

    def get_otp(self):
        otp = self.ids.otp.text
        if len(otp) != 6:
            return
        try:
            return int(otp)
        except:
            return

    def on_text(self, dt):
        self.ids.next.disabled = self.get_otp() is None

    def on_enter(self, dt):
        # press next
        next = self.ids.next
        if not next.disabled:
            next.dispatch('on_release')


class WizardKnownOTPDialog(WizardOTPDialogBase):

    def __init__(self, wizard, **kwargs):
        WizardOTPDialogBase.__init__(self, wizard, **kwargs)
        self.message = _("This wallet is already registered with TrustedCoin. To finalize wallet creation, please enter your Google Authenticator Code.")
        self.message2 =_("If you have lost your Google Authenticator account, you can request a new secret. You will need to retype your seed.")
        self.request_new = False

    def get_params(self, button):
        return (self.get_otp(), self.request_new)

    def request_new_secret(self):
        self.request_new = True
        self.on_release(True)

    def abort_wallet_creation(self):
        self._on_release = True
        self.wizard.terminate(aborted=True)
        self.dismiss()


class WizardNewOTPDialog(WizardOTPDialogBase):

    def __init__(self, wizard, **kwargs):
        WizardOTPDialogBase.__init__(self, wizard, **kwargs)
        otp_secret = kwargs['otp_secret']
        uri = "otpauth://totp/%s?secret=%s"%('trustedcoin.com', otp_secret)
        self.message = "Please scan the following QR code in Google Authenticator. You may also use the secret key: %s"%otp_secret
        self.message2 = _('Then, enter your Google Authenticator code:')
        self.ids.qr.set_data(uri)

    def get_params(self, button):
        return (self.get_otp(), False)

class WizardTOSDialog(WizardDialog):

    def __init__(self, wizard, **kwargs):
        WizardDialog.__init__(self, wizard, **kwargs)
        self.ids.next.text = 'Accept'
        self.ids.next.disabled = False
        self.message = kwargs['tos']

class WizardEmailDialog(WizardDialog):

    def get_params(self, button):
        return (self.ids.email.text,)

    def on_text(self, dt):
        self.ids.next.disabled = not is_valid_email(self.ids.email.text)

    def on_enter(self, dt):
        # press next
        next = self.ids.next
        if not next.disabled:
            next.dispatch('on_release')

class WizardConfirmDialog(WizardDialog):

    def __init__(self, wizard, **kwargs):
        super(WizardConfirmDialog, self).__init__(wizard, **kwargs)
        self.message = kwargs.get('message', '')
        self.value = 'ok'

    def on_parent(self, instance, value):
        if value:
            self._back = _back = partial(self.app.dispatch, 'on_back')

    def get_params(self, button):
        return (True,)


class WizardChoiceDialog(WizardDialog):

    def __init__(self, wizard, **kwargs):
        super(WizardChoiceDialog, self).__init__(wizard, **kwargs)
        self.title = kwargs.get('message', '')
        self.message = kwargs.get('message', '')
        choices = kwargs.get('choices', [])
        self.init_choices(choices)

    def init_choices(self, choices):
        layout = self.ids.choices
        layout.bind(minimum_height=layout.setter('height'))
        for action, text in choices:
            l = WizardButton(text=text)
            l.action = action
            l.height = '48dp'
            l.root = self
            layout.add_widget(l)

    def on_parent(self, instance, value):
        if value:
            self._back = _back = partial(self.app.dispatch, 'on_back')

    def get_params(self, button):
        return (button.action,)


class LineDialog(WizardDialog):
    title = StringProperty('')
    message = StringProperty('')
    warning = StringProperty('')

    def __init__(self, wizard, **kwargs):
        WizardDialog.__init__(self, wizard, **kwargs)
        self.title = kwargs.get('title', '')
        self.message = kwargs.get('message', '')
        self.ids.next.disabled = True
        self.test = kwargs['test']

    def get_text(self):
        return self.ids.passphrase_input.text

    def on_text(self, dt):
        self.ids.next.disabled = not self.test(self.get_text())

    def get_params(self, b):
        return (self.get_text(),)

class CLButton(ToggleButton):
    def on_release(self):
        self.root.script_type = self.script_type
        self.root.set_text(self.value)

class ChoiceLineDialog(WizardChoiceDialog):
    title = StringProperty('')
    message1 = StringProperty('')
    message2 = StringProperty('')

    def __init__(self, wizard, **kwargs):
        WizardDialog.__init__(self, wizard, **kwargs)
        self.title = kwargs.get('title', '')
        self.message1 = kwargs.get('message1', '')
        self.message2 = kwargs.get('message2', '')
        self.choices = kwargs.get('choices', [])
        default_choice_idx = kwargs.get('default_choice_idx', 0)
        self.ids.next.disabled = False
        layout = self.ids.choices
        layout.bind(minimum_height=layout.setter('height'))
        for idx, (script_type, title, text) in enumerate(self.choices):
            b = CLButton(text=title, height='30dp', group=self.title, allow_no_selection=False)
            b.script_type = script_type
            b.root = self
            b.value = text
            layout.add_widget(b)
            if idx == default_choice_idx:
                b.trigger_action(duration=0)

    def set_text(self, value):
        self.ids.text_input.text = value

    def get_params(self, b):
        return (self.ids.text_input.text, self.script_type)

class ShowSeedDialog(WizardDialog):
    seed_text = StringProperty('')
    message = (_("Write your seed phrase down on paper.") + " " +
               _("The seed phrase will allow you to recover your wallet in case you forget your password or lose your device.") + "\n\n" +
               _("WARNING") + ":\n" +
               "- " + _("Never disclose your seed.") + "\n" +
               "- " + _("Never type it on a website.") + "\n" +
               "- " + _("Do not store it electronically."))

    def __init__(self, wizard, **kwargs):
        super(ShowSeedDialog, self).__init__(wizard, **kwargs)
        self.seed_text = kwargs['seed_text']
        self.opt_ext = True
        self.is_ext = False

    def on_parent(self, instance, value):
        if value:
            self._back = _back = partial(self.ids.back.dispatch, 'on_release')

    def options_dialog(self):
        from .seed_options import SeedOptionsDialog
        def callback(ext, _):
            self.is_ext = ext
        d = SeedOptionsDialog(self.opt_ext, False, self.is_ext, False, callback)
        d.open()

    def get_params(self, b):
        return (self.is_ext,)


class WordButton(Button):
    pass

class WizardButton(Button):
    pass


class RestoreSeedDialog(WizardDialog):

    def __init__(self, wizard, **kwargs):
        super(RestoreSeedDialog, self).__init__(wizard, **kwargs)
        self._test = kwargs['test']
        from electrum.mnemonic import Mnemonic
        from electrum.old_mnemonic import wordlist as old_wordlist
        self.words = set(Mnemonic('en').wordlist).union(set(old_wordlist))
        self.ids.text_input_seed.text = ''
        self.message = _('Please type your seed phrase using the virtual keyboard.')
        self.title = _('Enter Seed')
        self.opt_ext = kwargs['opt_ext']
        self.opt_bip39 = kwargs['opt_bip39']
        self.is_ext = False
        self.is_bip39 = False

    def options_dialog(self):
        from .seed_options import SeedOptionsDialog
        def callback(ext, bip39):
            self.is_ext = ext
            self.is_bip39 = bip39
            self.update_next_button()
        d = SeedOptionsDialog(self.opt_ext, self.opt_bip39, self.is_ext, self.is_bip39, callback)
        d.open()

    def get_suggestions(self, prefix):
        for w in self.words:
            if w.startswith(prefix):
                yield w

    def update_next_button(self):
        from electrum.keystore import bip39_is_checksum_valid
        text = self.get_text()
        if self.is_bip39:
            is_seed, is_wordlist = bip39_is_checksum_valid(text)
        else:
            is_seed = bool(self._test(text))
        self.ids.next.disabled = not is_seed

    def on_text(self, dt):
        self.update_next_button()

        text = self.ids.text_input_seed.text
        if not text:
            last_word = ''
        elif text[-1] == ' ':
            last_word = ''
        else:
            last_word = text.split(' ')[-1]

        enable_space = False
        self.ids.suggestions.clear_widgets()
        suggestions = [x for x in self.get_suggestions(last_word)]

        if last_word in suggestions:
            b = WordButton(text=last_word)
            self.ids.suggestions.add_widget(b)
            enable_space = True

        for w in suggestions:
            if w != last_word and len(suggestions) < 10:
                b = WordButton(text=w)
                self.ids.suggestions.add_widget(b)

        i = len(last_word)
        p = set()
        for x in suggestions:
            if len(x)>i: p.add(x[i])

        for line in [self.ids.line1, self.ids.line2, self.ids.line3]:
            for c in line.children:
                if isinstance(c, Button):
                    if c.text in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
                        c.disabled = (c.text.lower() not in p) and bool(last_word)
                    elif c.text == ' ':
                        c.disabled = not enable_space

    def on_word(self, w):
        text = self.get_text()
        words = text.split(' ')
        words[-1] = w
        text = ' '.join(words)
        self.ids.text_input_seed.text = text + ' '
        self.ids.suggestions.clear_widgets()

    def get_text(self):
        ti = self.ids.text_input_seed
        return ' '.join(ti.text.strip().split())

    def update_text(self, c):
        c = c.lower()
        text = self.ids.text_input_seed.text
        if c == '<':
            text = text[:-1]
        else:
            text += c
        self.ids.text_input_seed.text = text

    def on_parent(self, instance, value):
        if value:
            tis = self.ids.text_input_seed
            tis.focus = True
            #tis._keyboard.bind(on_key_down=self.on_key_down)
            self._back = _back = partial(self.ids.back.dispatch,
                                         'on_release')

    def on_key_down(self, keyboard, keycode, key, modifiers):
        if keycode[0] in (13, 271):
            self.on_enter()
            return True

    def on_enter(self):
        #self._remove_keyboard()
        # press next
        next = self.ids.next
        if not next.disabled:
            next.dispatch('on_release')

    def _remove_keyboard(self):
        tis = self.ids.text_input_seed
        if tis._keyboard:
            tis._keyboard.unbind(on_key_down=self.on_key_down)
            tis.focus = False

    def get_params(self, b):
        seed_type = 'bip39' if self.is_bip39 else 'electrum'
        return (self.get_text(), seed_type, self.is_ext)


class ConfirmSeedDialog(RestoreSeedDialog):

    def __init__(self, *args, **kwargs):
        RestoreSeedDialog.__init__(self, *args, **kwargs)
        self.ids.seed_dialog_header.ids.options_button.disabled = True
        self.ids.text_input_seed.text = kwargs['seed']

    def get_params(self, b):
        return (self.get_text(),)
    def options_dialog(self):
        pass


class ShowXpubDialog(WizardDialog):

    def __init__(self, wizard, **kwargs):
        WizardDialog.__init__(self, wizard, **kwargs)
        self.xpub = kwargs['xpub']
        self.ids.next.disabled = False

    def do_copy(self):
        self.app._clipboard.copy(self.xpub)

    def do_share(self):
        self.app.do_share(self.xpub, _("Master Public Key"))

    def do_qr(self):
        from .qr_dialog import QRDialog
        popup = QRDialog(_("Master Public Key"), self.xpub, True)
        popup.open()


class AddXpubDialog(WizardDialog):

    def __init__(self, wizard, **kwargs):
        WizardDialog.__init__(self, wizard, **kwargs)
        def is_valid(x):
            try:
                return kwargs['is_valid'](x)
            except:
                return False
        self.is_valid = is_valid
        self.title = kwargs['title']
        self.message = kwargs['message']
        self.allow_multi = kwargs.get('allow_multi', False)

    def check_text(self, dt):
        self.ids.next.disabled = not bool(self.is_valid(self.get_text()))

    def get_text(self):
        ti = self.ids.text_input
        return ti.text.strip()

    def get_params(self, button):
        return (self.get_text(),)

    def scan_xpub(self):
        def on_complete(text):
            if self.allow_multi:
                self.ids.text_input.text += text + '\n'
            else:
                self.ids.text_input.text = text
        self.app.scan_qr(on_complete)

    def do_paste(self):
        self.ids.text_input.text = self.app._clipboard.paste()

    def do_clear(self):
        self.ids.text_input.text = ''




class InstallWizard(BaseWizard, Widget):

    def __init__(self, *args, **kwargs):
        BaseWizard.__init__(self, *args, **kwargs)
        self.app = App.get_running_app()

    def terminate(self, *, storage=None, db=None, aborted=False):
        # storage must be None because manual upgrades are disabled on Kivy
        assert storage is None
        if not aborted:
            password = self.pw_args.password
            storage, db = self.create_storage(self.path)
            self.app.on_wizard_success(storage, db, password)
        else:
            try: os.unlink(self.path)
            except FileNotFoundError: pass
            self.reset_stack()
            self.confirm_dialog(message=_('Wallet creation failed'), run_next=lambda x: self.app.on_wizard_aborted())

    def choice_dialog(self, **kwargs):
        choices = kwargs['choices']
        if len(choices) > 1:
            WizardChoiceDialog(self, **kwargs).open()
        else:
            f = kwargs['run_next']
            f(choices[0][0])

    def multisig_dialog(self, **kwargs): WizardMultisigDialog(self, **kwargs).open()
    def show_seed_dialog(self, **kwargs): ShowSeedDialog(self, **kwargs).open()
    def line_dialog(self, **kwargs): LineDialog(self, **kwargs).open()
    def derivation_and_script_type_gui_specific_dialog(self, **kwargs): ChoiceLineDialog(self, **kwargs).open()

    def confirm_seed_dialog(self, **kwargs):
        kwargs['title'] = _('Confirm Seed')
        kwargs['message'] = _('Please retype your seed phrase, to confirm that you properly saved it')
        kwargs['opt_bip39'] = self.opt_bip39
        kwargs['opt_ext'] = self.opt_ext
        ConfirmSeedDialog(self, **kwargs).open()

    def restore_seed_dialog(self, **kwargs):
        kwargs['opt_bip39'] = self.opt_bip39
        kwargs['opt_ext'] = self.opt_ext
        RestoreSeedDialog(self, **kwargs).open()

    def confirm_dialog(self, **kwargs):
        WizardConfirmDialog(self, **kwargs).open()

    def tos_dialog(self, **kwargs):
        WizardTOSDialog(self, **kwargs).open()

    def email_dialog(self, **kwargs):
        WizardEmailDialog(self, **kwargs).open()

    def otp_dialog(self, **kwargs):
        if kwargs['otp_secret']:
            WizardNewOTPDialog(self, **kwargs).open()
        else:
            WizardKnownOTPDialog(self, **kwargs).open()

    def add_xpub_dialog(self, **kwargs):
        kwargs['message'] += ' ' + _('Use the camera button to scan a QR code.')
        AddXpubDialog(self, **kwargs).open()

    def add_cosigner_dialog(self, **kwargs):
        kwargs['title'] = _("Add Cosigner") + " %d"%kwargs['index']
        kwargs['message'] = _('Please paste your cosigners master public key, or scan it using the camera button.')
        AddXpubDialog(self, **kwargs).open()

    def show_xpub_dialog(self, **kwargs): ShowXpubDialog(self, **kwargs).open()

    def show_message(self, msg): self.show_error(msg)

    def show_error(self, msg):
        Clock.schedule_once(lambda dt: self.app.show_error(msg))

    def request_password(self, run_next, force_disable_encrypt_cb=False):
        if self.app.password is not None:
            run_next(self.app.password, True)
            return
        def on_success(old_pw, pw):
            assert old_pw is None
            run_next(pw, True)
        def on_failure():
            self.show_error(_('Password mismatch'))
            self.request_password(run_next)
        popup = PasswordDialog(
            self.app,
            check_password=lambda x:True,
            on_success=on_success,
            on_failure=on_failure,
            is_change=True,
            is_password=True,
            message=_('Choose a password'))
        popup.open()

    def action_dialog(self, action, run_next):
        f = getattr(self, action)
        f()
