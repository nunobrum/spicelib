from tkinter import Tk, TclError
import logging

_logger = logging.getLogger("spicelib.utils.clipboard")


class Clipboard:

    def __init__(self, verbose=False):
        self.verbose = verbose
        self.tk = Tk()
        self.tk.withdraw()

    def __del__(self):
        self.tk.quit()

    def copy(self, data:str) -> None:
        """
        Copy the text contents passed as a paramter onto the OS clipboard 

        :param data: Text to place on the OS clipboard
        :type data: str
        """
        self.clear()
        self.tk.clipboard_append(data)

    def paste(self, clear=False) -> str:
        """
        Return the clipboard contents
        optionally clear the contents

        :param clear: If true, clear the clipboard before returning the data
        :return: Text contents of the clipboard
        :rtype: str
        """
        try:
            contents = self.tk.clipboard_get()
        except TclError as er:
            if self.verbose:
                print(f"TCL error: {er}")
            contents = ""
        if contents is not None and contents != "" and clear:
            self.clear()
        return contents

    def clear(self, check=True) -> bool:
        """
        Clear the contents of the clipboard

        :param check: If true, check the clear was successful
        :return: True if the clipboard is empty after the call or if check is False
        :rtype: bool
        """
        self.tk.clipboard_clear()
        data = self.paste()
        return True if not check else data == ""


    def cut(self, data:str) -> bool:
        """
        As per copy(), but the clipboard is first cleared
        then we return true if successful thus allowing the
        caller to determine if it safe to delete the cut data from memory

        :param data: Text to place on the OS clipboard
        :type data: str
        :return: True if the clipboard is not empty after the call
        :rtype: bool
        """
        # Note we can't reliably compare data and rdata as the OS may
        # alter the encoding or structure between calls

        try:
            self.copy(data)
            rdata = self.paste()
        except self.tk.TclError:
            return False
        
        return rdata is not None and len(rdata) > 0


# Example use
if __name__ == "__main__":
    def test_clipboard():
        cb = Clipboard()
        import datetime
        dt = datetime.datetime.now(datetime.timezone.utc)

        existing = cb.paste()
        if len(existing):
            print(f"Existing clipboard: '{existing}'")
            print("Clearing the clipboard")
            res = cb.clear()
        else:
            print("Clipboard is currently empty")
    
        assert cb.paste() == "", "Failed to clear the clipboard"
        print("...clipboard is empty")
        text = f"Testing 123 @ {dt}"
        print("Trying a cut()")
        cb.cut(text)
        print("Trying a paste()")
        res = cb.paste()
        print("Comparing cut() and paste()")
        assert text == res, f"test fail: {text} != {res}"
        print("Test pass")
        if text == res:
            print("...and the data matched")

    test_clipboard()

