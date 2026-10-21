"""Recording-only Windows reminders, independent of the assistant conversation."""
import json
import os
from pathlib import Path
import threading
import time


def next_deadline(elapsed, first=3600, interval=1800):
    """Next boundary after elapsed; do not replay missed notifications after sleep."""
    if elapsed < first:
        return first
    return first + (int((elapsed - first) // interval) + 1) * interval


def notify_windows(message):
    """Submit a native tray notification without launching a shell or recording audio."""
    import ctypes
    from ctypes import wintypes as w
    if os.name != 'nt':
        raise OSError('Windows desktop notifications require Windows')
    class GUID(ctypes.Structure):
        _fields_ = [('Data1', w.DWORD), ('Data2', w.WORD), ('Data3', w.WORD),
                    ('Data4', ctypes.c_ubyte * 8)]
    class Notice(ctypes.Structure):
        _fields_ = [('cbSize', w.DWORD), ('hWnd', w.HWND), ('uID', w.UINT),
                    ('uFlags', w.UINT), ('uCallbackMessage', w.UINT), ('hIcon', w.HICON),
                    ('szTip', w.WCHAR * 128), ('dwState', w.DWORD), ('dwStateMask', w.DWORD),
                    ('szInfo', w.WCHAR * 256), ('uTimeout', w.UINT),
                    ('szInfoTitle', w.WCHAR * 64), ('dwInfoFlags', w.DWORD),
                    ('guidItem', GUID), ('hBalloonIcon', w.HICON)]
    user = ctypes.WinDLL('user32', use_last_error=True)
    shell = ctypes.WinDLL('shell32', use_last_error=True)
    user.CreateWindowExW.argtypes = [w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD,
                                    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                    w.HWND, w.HMENU, w.HINSTANCE, w.LPVOID]
    user.CreateWindowExW.restype = w.HWND
    user.LoadIconW.argtypes = [w.HINSTANCE, w.LPCWSTR]
    user.LoadIconW.restype = w.HICON
    user.DestroyWindow.argtypes = [w.HWND]
    shell.Shell_NotifyIconW.argtypes = [w.DWORD, ctypes.POINTER(Notice)]
    shell.Shell_NotifyIconW.restype = w.BOOL
    window = user.CreateWindowExW(0, 'STATIC', 'Dion Secretary reminders', 0,
                                  0, 0, 0, 0, None, None, None, None)
    if not window:
        raise ctypes.WinError(ctypes.get_last_error())
    notice = Notice()
    notice.cbSize = ctypes.sizeof(Notice)
    notice.hWnd, notice.uID = window, 1
    notice.uFlags = 2 | 4  # NIF_ICON | NIF_TIP
    notice.hIcon = user.LoadIconW(None, ctypes.cast(ctypes.c_void_p(32516), w.LPCWSTR))
    notice.szTip = 'Dion Secretary'
    added = False
    try:
        if not shell.Shell_NotifyIconW(0, ctypes.byref(notice)):
            raise OSError('Windows rejected recording notification icon')
        added = True
        notice.uFlags = 16  # NIF_INFO
        notice.szInfoTitle = 'Dion Secretary'
        notice.szInfo = message if len(message) <= 255 else message[:252] + '...'
        notice.dwInfoFlags, notice.uTimeout = 1, 10000
        if not shell.Shell_NotifyIconW(1, ctypes.byref(notice)):
            raise OSError('Windows rejected recording notification')
        until = time.monotonic() + 12
        msg = w.MSG()
        user.PeekMessageW.argtypes = [ctypes.POINTER(w.MSG), w.HWND, w.UINT, w.UINT, w.UINT]
        user.TranslateMessage.argtypes = [ctypes.POINTER(w.MSG)]
        user.DispatchMessageW.argtypes = [ctypes.POINTER(w.MSG)]
        user.DispatchMessageW.restype = ctypes.c_ssize_t
        while time.monotonic() < until:
            while user.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
                user.TranslateMessage(ctypes.byref(msg))
                user.DispatchMessageW(ctypes.byref(msg))
            time.sleep(.1)
    finally:
        if added:
            shell.Shell_NotifyIconW(2, ctypes.byref(notice))
        user.DestroyWindow(window)


class RecordingReminders:
    def __init__(self, session, title, started, *, first=3600, interval=1800,
                 notifier=notify_windows):
        self.session = Path(session)
        self.message = f'Встреча "{title}" ещё записывается'
        self.started = started
        self.first, self.interval = first, interval
        self.notifier = notifier
        self.cancel = threading.Event()
        self.thread = threading.Thread(target=self.run, name='recording-reminders', daemon=True)

    def start(self):
        self.thread.start()

    def close(self):
        self.cancel.set()

    def run(self):
        due = self.first
        while not self.cancel.wait(max(0, self.started + due - time.monotonic())):
            if (self.session / 'stop.flag').exists():
                return
            event = {'seconds': round(time.monotonic() - self.started, 1), 'message': self.message}
            try:
                self.notifier(self.message)
                event['state'] = 'submitted_to_windows'
            except Exception as exc:
                # A desktop notification failure must never stop audio capture.
                event.update(state='error', error=str(exc))
            try:
                with (self.session / 'recording-reminders.jsonl').open('a', encoding='utf-8') as out:
                    out.write(json.dumps(event, ensure_ascii=False) + '\n')
            except OSError:
                pass
            due = next_deadline(time.monotonic() - self.started, self.first, self.interval)


def launch_stop_notification(session, message):
    """Detached notifier so WAV finalization and stop() never wait for the desktop UI."""
    import subprocess
    import sys
    session = Path(session)
    with (session / 'stop-notification.log').open('ab') as log:
        subprocess.Popen([sys.executable, '-X', 'utf8', '-B', str(Path(__file__).resolve()),
                          '--message', message, '--result', str(session / 'stop-notification.json')],
                         stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                         creationflags=subprocess.CREATE_NO_WINDOW, close_fds=True)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--message', required=True)
    parser.add_argument('--result', required=True)
    args = parser.parse_args()
    try:
        notify_windows(args.message)
        result = {'state': 'submitted_to_windows', 'message': args.message}
    except Exception as exc:
        result = {'state': 'error', 'error': str(exc), 'message': args.message}
    Path(args.result).write_text(json.dumps(result, ensure_ascii=False, indent=2), 'utf-8')
