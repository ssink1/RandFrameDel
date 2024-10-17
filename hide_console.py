
import win32console
import win32gui
import atexit

window = win32console.GetConsoleWindow()
win32gui.ShowWindow(window, 0)

def show_console():
    win32gui.ShowWindow(window, 1)

atexit.register(show_console)
