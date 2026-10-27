"""Browser lifecycle evidence; only window/browser closure permits automatic stop."""
import ctypes
import json
import os
from pathlib import Path
import time

REASONS = {
    'browser_closed': 'Закрыт браузер Chrome',
    'browser_window_closed': 'Закрыто окно браузера со встречей',
    'tab_closed': 'Закрыта вкладка встречи',
    'meeting_ended': 'Встреча в Dion завершена или выполнен выход из неё',
    'meeting_page_closed': 'Закрыта страница встречи: переход на другую страницу',
    'meeting_changed': 'Во вкладке открыта другая встреча',
    'manual_stop': 'Запись остановлена по команде пользователя',
}

AUTO_STOP_REASONS = frozenset({'browser_closed', 'browser_window_closed'})


def completion_message(title, reason):
    return f'Запись встречи «{title}» завершена. {REASONS[reason]}. Аудиозапись сохранена.'

OBSERVATION_REASONS = {
    'browser_closed': 'Не обнаружены открытые окна Chrome.',
    'browser_window_closed': 'Закрыто окно браузера с наблюдаемой вкладкой.',
    'tab_closed': 'Закрыта наблюдаемая вкладка Dion.',
    'meeting_ended': 'Карточки участников во вкладке Dion не видны не менее 8 секунд. Это может быть смена интерфейса, а не конец встречи.',
    'meeting_page_closed': 'Наблюдаемая вкладка перешла на другую страницу.',
    'meeting_changed': 'Во вкладке изменился идентификатор встречи.',
}


def observation_message(title, reason):
    return (f'Возможно, встреча «{title}» завершилась. '
            + OBSERVATION_REASONS.get(reason, 'Получен неподтверждённый сигнал от браузера.')
            + ' Запись продолжается до вашей команды остановки.')


def chrome_windows_open():
    """Inspect top-level Chrome windows, including minimized windows; no URLs/titles."""
    if os.name != 'nt':
        return None
    from ctypes import wintypes as w
    user = ctypes.WinDLL('user32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
    user.EnumWindows.argtypes = [callback_type, w.LPARAM]
    user.IsWindowVisible.argtypes = [w.HWND]
    user.GetClassNameW.argtypes = [w.HWND, w.LPWSTR, ctypes.c_int]
    user.GetWindowThreadProcessId.argtypes = [w.HWND, ctypes.POINTER(w.DWORD)]
    kernel.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
    kernel.OpenProcess.restype = w.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes = [w.HANDLE, w.DWORD, w.LPWSTR, ctypes.POINTER(w.DWORD)]
    kernel.CloseHandle.argtypes = [w.HANDLE]
    found, unknown = [], []
    @callback_type
    def visit(window, param):
        name = ctypes.create_unicode_buffer(256)
        user.GetClassNameW(window, name, len(name))
        if name.value != 'Chrome_WidgetWin_1' or not user.IsWindowVisible(window):
            return True
        pid = w.DWORD()
        user.GetWindowThreadProcessId(window, ctypes.byref(pid))
        handle = kernel.OpenProcess(0x1000, False, pid.value)
        if not handle:
            unknown.append(True)
            return True
        try:
            image = ctypes.create_unicode_buffer(32768)
            size = w.DWORD(len(image))
            if kernel.QueryFullProcessImageNameW(handle, 0, image, ctypes.byref(size)):
                if Path(image.value).name.lower() == 'chrome.exe':
                    found.append(True)
            else:
                unknown.append(True)
        finally:
            kernel.CloseHandle(handle)
        return True
    if not user.EnumWindows(visit, 0):
        return None
    return True if found else (None if unknown else False)


def select_binding(journals, choice=None):
    candidates = journals.get('meetings', [])
    if choice:
        selected = Path(choice).resolve()
        candidates = [c for c in candidates if Path(c['path']).resolve() == selected]
    if len(candidates) != 1:
        raise RuntimeError('Для наблюдения нужна одна активная вкладка Dion. '
                           'Откройте встречу; при нескольких вкладках укажите --meeting-journal.')
    meta_path = Path(candidates[0]['path']) / 'meta.json'
    meta = json.loads(meta_path.read_text('utf-8'))
    if meta.get('lifecycle_version') != 1:
        raise RuntimeError('Перезагрузите расширение Dion Speaker Helper: наблюдение недоступно.')
    root = meta_path.parents[2]
    lifecycle = root / 'lifecycle' / meta['client'] / f"{meta['tab']}.json"
    # Fresh journal alone is insufficient: the updated native host must also be ready.
    state = json.loads(lifecycle.read_text('utf-8'))
    if state.get('state') != 'active' or state.get('meeting_id') != meta['meeting_id']:
        raise RuntimeError('Активность вкладки Dion не подтверждена; наблюдение недоступно.')
    return {key: meta[key] for key in ('client', 'tab', 'meeting_id')} | {
        'lifecycle_path': str(lifecycle), 'bound_at': time.time()}


class MeetingMonitor:
    def __init__(self, binding, *, browser_probe=chrome_windows_open):
        self.binding = binding
        self.browser_probe = browser_probe
        try:
            self.browser_seen = browser_probe() is True
        except OSError:
            self.browser_seen = False
        self.browser_missing_since = None
        self.last_probe = float('-inf')
        self.browser_state = None

    def poll(self, now=None):
        now = time.monotonic() if now is None else now
        if now - self.last_probe >= 1:
            try:
                self.browser_state = self.browser_probe()
            except OSError:
                self.browser_state = None
            self.last_probe = now
            if self.browser_state is True:
                self.browser_seen = True
                self.browser_missing_since = None
            elif self.browser_state is False and self.browser_seen:
                if self.browser_missing_since is None:
                    self.browser_missing_since = now
            else:
                self.browser_missing_since = None
        if self.browser_missing_since is not None and now-self.browser_missing_since >= 2:
            return 'browser_closed'
        if not self.binding:
            return None  # Whole-browser fallback works even without a name journal.
        try:
            state = json.loads(Path(self.binding['lifecycle_path']).read_text('utf-8'))
        except (OSError, ValueError):
            return None  # Missing/stale journal is not meeting-end evidence.
        if state.get('client') != self.binding['client'] or state.get('tab') != self.binding['tab']:
            return None
        events = sorted(state.get('ends', []),
                        key=lambda event: event.get('reason') not in AUTO_STOP_REASONS)
        for event in events:
            if (event.get('meeting_id') == self.binding['meeting_id'] and
                    event.get('ended_at', 0) >= self.binding['bound_at'] and
                    event.get('reason') in REASONS):
                reason = event['reason']
                if reason == 'browser_window_closed' and self.browser_state is False:
                    return 'browser_closed'
                return reason
        if state.get('state') == 'active' and state.get('meeting_id') != self.binding['meeting_id']:
            return 'meeting_changed'
        return None
