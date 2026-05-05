import datetime
import uuid
import sys, psutil
# Beta expiry date
BETA_EXPIRY = datetime.date(2026, 5, 31)
# Allowed MAC addresses (last 8 hex digits, lowercase, no separators)
ALLOWED_MAC_SUFFIXES = [
    '2489',  # add allowed suffixes here
]
def get_all_mac_suffixes():
    suffixes = set()
    for iface, addrs in psutil.net_if_addrs().items():
        for addr in addrs:
            if addr.family == psutil.AF_LINK:
                mac = addr.address.replace('-', '').replace(':', '').lower()
                if len(mac) == 12 and mac != '000000000000':
                    suffixes.add(mac[-4:])
    return suffixes
def check_beta():
    if datetime.date.today() > BETA_EXPIRY:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror('ACard', '测试版本已过期 请下载正式版ACard')
        sys.exit()

    return

    suffixes = get_all_mac_suffixes()
    if not suffixes.intersection(ALLOWED_MAC_SUFFIXES):
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror('ACard', '你不是测试人员 请等待正式版发布')
        sys.exit()
check_beta()
import sys
import os
from datetime import datetime
class Tee:
    """Write to multiple streams simultaneously."""
    def __init__(self, *streams):
        self.streams = [s for s in streams if s is not None]
    def write(self, data):
        for s in self.streams:
            s.write(data)
            s.flush()  # Ensure each line is written to disk immediately
    def flush(self):
        for s in self.streams:
            s.flush()
def setup_logging():
    # Determine where the exe (or script) lives
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
    else:
        exe_dir = os.path.dirname(os.path.abspath(__file__))
    log_path = os.path.join(exe_dir, 'ACard.log')
    log_file = open(log_path, 'a', encoding='utf-8')
    # Tee to both original console and log file
    sys.stdout = Tee(sys.__stdout__, log_file)
    sys.stderr = Tee(sys.__stderr__, log_file)
    print(f'=== {datetime.now().isoformat()} ===')
setup_logging()
def exception_hook(exctype, value, traceback):
    print(''.join(__import__('traceback').format_exception(exctype, value, traceback)))
    sys.__excepthook__(exctype, value, traceback)
sys.excepthook = exception_hook
_last_time = None

import os
import threading
import uuid
import base64
import wave
import io
from mss import mss
import sqlite3
import socket
import sys
import time
import psutil
import math
import hashlib
import json
import subprocess
import tempfile
import time
import re
import requests
from functools import partial
from pynput import keyboard, mouse
from ctypes import *
from collections import deque
from pathlib import Path
from pynput import keyboard, mouse
import ctypes
import numpy as np
import xml.etree.ElementTree as ET
from ctypes import wintypes
from ctypes import CDLL, CFUNCTYPE, c_bool, c_char_p, c_float, c_int, c_int32, c_uint64, c_void_p, c_wchar_p
def get_base():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))
BASE = get_base()
# load DLL first, before importing Qt. This is required
dll = CDLL(os.path.join(BASE, 'CVUtils.dll'))
native_dll = CDLL(os.path.join(BASE, 'NativeUtils.dll'))

from PyQt5.QtWidgets import QApplication, QMessageBox, QFileDialog, QMainWindow, QWidget, QMenu, QSlider, QToolTip, QLabel, QVBoxLayout, QLineEdit, QHBoxLayout, QToolButton, QStyle, QStyleOptionSlider, QStackedWidget, QComboBox, QPushButton, QSystemTrayIcon, QMenu, QAction
from PyQt5.QtCore import Qt, QRect, QEvent, QObject, pyqtSignal, QTimer, QBuffer, QIODevice, QPoint, QMetaObject
from PyQt5.QtGui import QPainter, QColor, QPen, QPixmap, QImage, QCursor, QFont, QIcon

UI_TEXT = {
    'messagebox_title': ('ACard', 'ACard'),
    'no_anki_in_config': ('Download Anki from <a href="https://apps.ankiweb.net">apps.ankiweb.net</a><br>Then select anki.exe','登录<a href="https://apps.ankiweb.net">apps.ankiweb.net</a>下载Anki<br>然后选择anki.exe'),
    'select_anki': ('Select anki.exe', '选择anki.exe'),
    'no_anki_connection': ('Failed to connect to Anki', '无法连接Anki'),
    'dup': ('ACard is already running', 'ACard已启动'),
    'blank': ('Blank', '无'),
    'install_anki_connect': ('Install Anki Connect:<br>1. Open Anki<br>2. Press Ctrl+Shift+A<br>3. Click Get Add-ons...<br>4. put 2055492159 as Code<br>5. Click OK','安装Anki Connect<br>1. 打开Anki<br>2. 按下Ctrl+Shift+A<br>3. 点击 获取插件...<br>4. 代码处输入2055492159<br>5. 点击确定'),
    'dict': ('Dictionary', '字典'),
    'monitor': ('Monitor', '显示器'),
    'cut': ('Cut', '剪切'),
    'copy': ('Copy', '复制'),
    'paste': ('Paste', '粘贴'),
    'hotkey': ('Hotkey', '快捷键'),
    'use_scroll': ('↑↑↑↑↑Use scroll wheel to playback↑↑↑↑↑', '↑↑↑↑↑滑动鼠标滚轮控制回放↑↑↑↑↑'),
    'quit': ('Quit', '退出')
}
def load_config():
    from platformdirs import user_config_dir
    import json
    path = os.path.join(user_config_dir('ACard', appauthor=False), 'config.json')
    try:
        with open(path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except FileNotFoundError:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if ui_index == 1:
            default_dst_lang = "中文"
        else:
            default_dst_lang = "English"
        DEFAULT_CONFIG = {
            "anki_path": "",
            "anki_connect_successful": False,
            "anki_deck_name": "ACard",
            "anki_model_name": "ACardModel",
            "anki_model_version_and_hash": [0,""],
            "monitor_index": 1,
            "max_fps": [[5, 8], [10, 4], [120, 2]],
            "min_memory_gb": 1.5,
            "max_memory_percentage": 0.5,
            "jpeg_quality": 75,
            "window_pos": None,
            "hotkey": [{"type": "mouse", "button": "middle"}],
            "playback_hint_left": 10,
            "src_lang": "日本語",
            "dst_lang": default_dst_lang,
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(DEFAULT_CONFIG, f, indent=4, ensure_ascii=False)
        config = DEFAULT_CONFIG
    return path, config
def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(__file__), relative_path)
def get_ui_index():  # Check system language. Use English by default. If Chinese system is detected, use Chinese
    try:
        import locale
        lang = locale.getlocale()[0]
        if 'chinese' in lang.lower():
            return 1
    except:
        pass
    return 0
def update_config(key, value):
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = config
    data[key] = value
    config[key] = value  # keep in-memory copy in sync
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
def ui(key):
    return UI_TEXT[key][ui_index]
def check_get_anki_path():
    # check if anki_path is in config
    if config['anki_path'] == '':
        msg = QMessageBox()
        msg.setWindowTitle(ui('messagebox_title'))
        msg.setText(ui('no_anki_in_config'))
        msg.setTextFormat(Qt.RichText)
        msg.setTextInteractionFlags(Qt.TextBrowserInteraction)
        msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        result = msg.exec_()
        if result == QMessageBox.Ok:
            #  guess anki path
            #  this is necessary because some users might not know how to select anki.exe
            if os.name == 'nt':  # Windows
                default_dir = os.path.join(os.environ['LOCALAPPDATA'], 'Programs', 'Anki')
                if not os.path.exists(default_dir):
                    default_dir = os.path.join(os.environ['LOCALAPPDATA'], 'Programs')
                    if not os.path.exists(default_dir):
                        default_dir = os.path.join(os.environ['LOCALAPPDATA'])
            else: # Linux/macOS
                default_dir = os.path.expanduser('~')
                default_dir = os.path.join(default_dir, 'Anki')
            anki_path, _ = QFileDialog.getOpenFileName(
                None,
                ui('select_anki'),
                default_dir,
                ''
                '*.exe;;*.lnk'
            )
            if not anki_path:
                return
            else:
                update_config('anki_path', anki_path)
                return anki_path
        if result == QMessageBox.Cancel:
            return
    else:
        return config['anki_path']
def check_anki_connect():
    if not config['anki_connect_successful']:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.3)
            if s.connect_ex((ANKI_HOST, ANKI_PORT)) != 0:
                # reminder user to download anki connect
                show_install_msg()
def show_install_msg():
    global install_msg_showing
    msg = QMessageBox()
    msg.setWindowTitle(ui('messagebox_title'))
    msg.setText(ui('install_anki_connect'))
    msg.setTextFormat(Qt.RichText)
    msg.setStandardButtons(QMessageBox.Ok)

    # Make text selectable
    for label in msg.findChildren(QLabel):
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)

    msg.exec_()
    install_msg_showing = False
def open_anki(anki_path):
    # open anki
    if anki_path:
        proc = subprocess.Popen([anki_path])
    # test need to (1) check if anki is already running (2) check if anki is now opened by acard (3) install anki connect automatically (4) hide anki (5) check deck and model
def check_dup():  #test test test need revise. if another program like citrix is using same pid, this will fail
    import psutil
    lockfile = os.path.join(tempfile.gettempdir(), 'acard.lock')
    if os.path.exists(lockfile):
        with open(lockfile) as f:
            pid = int(f.read())
        if psutil.pid_exists(pid):
            msg = QMessageBox()
            msg.setWindowTitle(ui('messagebox_title'))
            msg.setText(ui('dup'))
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec_()
            anki_thread.join()  # wait until anki is opened
            sys.exit()
        else:
            # process not exist → stale lock
            os.remove(lockfile)
    # create lock
    with open(lockfile, 'w') as f:
        f.write(str(os.getpid()))
_conn_dict = None
_conn_dict_ready = threading.Event()
_current_dict_key = None
def _load_db(filename, conn_var, ready_event):
    conn = sqlite3.connect(os.path.join(BASE, filename), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    globals()[conn_var] = conn
    ready_event.set()
def moji_session():
    global session
    session = requests.Session()
    session.headers.update({
        "accept": "*/*",
        "accept-language": "zh-CN,zh;q=0.9",
        "content-type": "application/json",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "origin": "https://www.mojidict.com",
        "referer": "https://www.mojidict.com/"
    })
    session.post("https://api.mojidict.com/parse/functions/word-clickSearchV2",json={"searchText":"moji","_ApplicationId":"E62VyFVLMiW7kvbtVq3p"})
    moji_keep_alive_thread()
def moji_keep_alive_thread():
    global last_moji_search_time
    dummy = {}
    dummy_event = threading.Event()
    while True:
        if time.time() - last_moji_search_time > 590:  # not sure how long moji session will expire. in my test at 2026/03/01, longest survivor is 1192s
        # if last search was recent, do not refresh the session
        # moji search is connected via racing in this project. if too many connections at the same time, the session will fail
        # when keep alive session is running, there is a small chance that it coincides with a real search. In this case, session number will double and real session might fail
        # to lower this probability, keep alive session will not run if a real search happend recently
            last_moji_search_time = time.time()
            for _ in range(3):  # used for racing. 3 try for each moji search
                threading.Thread(target=search_mojidict_exact, args=('テスト', dummy, dummy_event), daemon=True).start()
                threading.Thread(target=search_mojidict_fuzzy, args=('テスト', dummy, dummy_event), daemon=True).start()
        time.sleep(5)
current_modifiers = set()  # tracks currently held modifier keys
MODIFIER_KEYS = {
    keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r,
    keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r,
    keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r,
}
def on_press(key):
    global current_modifiers
    if key in MODIFIER_KEYS:
        current_modifiers.add(key)
    if hotkey_mode == 0:
        if key not in MODIFIER_KEYS:  # only record when a non-modifier key is pressed
            mods = []
            if any(k in current_modifiers for k in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r)):
                mods.append('ctrl')
            if any(k in current_modifiers for k in (keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r)):
                mods.append('shift')
            if any(k in current_modifiers for k in (keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r)):
                mods.append('alt')

            canonical = keyboard_listener.canonical(key)
            if hasattr(canonical, 'char') and canonical.char and canonical.char.isprintable():
                key_str = canonical.char
            elif isinstance(canonical, keyboard.Key):
                key_str = f'Key.{canonical.name}'
            else:
                # KeyCode without char, look up by vk
                matched = None
                for k in keyboard.Key:
                    if hasattr(k.value, 'vk') and k.value.vk == canonical.vk:
                        matched = k
                        break
                key_str = f'Key.{matched.name}' if matched else str(canonical.vk)

            hk = {'type': 'keyboard', 'modifiers': mods, 'key': key_str}
            update_config('hotkey', [hk])
            window.hotkey_captured_signal.emit()
    if hotkey_mode == 1:
        if key not in MODIFIER_KEYS:
            for h in config['hotkey']:
                if h['type'] == 'keyboard':
                    mods = h.get('modifiers', [])
                    key_match = h.get('key', '')
                    # Check modifiers
                    ctrl_ok = ('ctrl' in mods) == any(k in current_modifiers for k in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r))
                    shift_ok = ('shift' in mods) == any(k in current_modifiers for k in (keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r))
                    alt_ok = ('alt' in mods) == any(k in current_modifiers for k in (keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r))
                    if ctrl_ok and shift_ok and alt_ok:
                        canonical = keyboard_listener.canonical(key)
                        if hasattr(canonical, 'char') and canonical.char and canonical.char.isprintable():
                            pressed_key_str = canonical.char
                        elif isinstance(canonical, keyboard.Key):
                            pressed_key_str = f'Key.{canonical.name}'
                        else:
                            matched = None
                            for k in keyboard.Key:
                                if hasattr(k.value, 'vk') and k.value.vk == canonical.vk:
                                    matched = k
                                    break
                            pressed_key_str = f'Key.{matched.name}' if matched else str(canonical.vk)
                        if pressed_key_str == key_match:
                            on_click_snip()
                            break
    if hotkey_mode == 2:
        step = snip.slider.pageStep()
        if key == keyboard.Key.up or key == keyboard.Key.page_up:
            window.slider_set_signal.emit(snip.slider.value() - step)
        elif key == keyboard.Key.down or key == keyboard.Key.page_down:
            window.slider_set_signal.emit(snip.slider.value() + step)
        elif key == keyboard.Key.left:
            window.slider_set_signal.emit(snip.slider.value() - 1)
        elif key == keyboard.Key.right:
            window.slider_set_signal.emit(snip.slider.value() + 1)
        elif key == keyboard.Key.home:
            window.slider_set_signal.emit(snip.slider.minimum())
        elif key == keyboard.Key.end:
            window.slider_set_signal.emit(snip.slider.maximum())
def on_release(key):
    global current_modifiers
    if key in MODIFIER_KEYS:
        current_modifiers.discard(key)
_snip_open_time = 0
_snip_close_time = 0
_snip_opened_by_right = False
def on_click(x, y, button, pressed):
    if hotkey_mode == 0:
        if pressed and button != mouse.Button.left:
            btn_str = 'middle' if button == mouse.Button.middle else 'right' if button == mouse.Button.right else str(button)
            hk = {'type': 'mouse', 'button': btn_str}
            update_config('hotkey', [hk])
            window.hotkey_captured_signal.emit()
    if hotkey_mode == 1:
        if pressed:
            btn_str = 'middle' if button == mouse.Button.middle else 'right' if button == mouse.Button.right else str(button)
            if btn_str and any(h['type'] == 'mouse' and h['button'] == btn_str for h in config['hotkey']):
                if not (_snip_opened_by_right and time.time() - _snip_close_time < 0.1):
                    on_click_snip()
            if button == mouse.Button.left:
                if window.isVisible():
                    win_geo = window.geometry()
                    if not win_geo.contains(x, y):
                        window.hide_signal.emit()
    if hotkey_mode == 2:
        if button == mouse.Button.right and pressed:
            if _snip_opened_by_right and time.time() - _snip_open_time < 0.1:
                pass
            else:
                if snip.dragging:
                    window.cancel_drag_signal.emit()
                else:
                    window.close_snip_signal.emit()
                    global lock_length
                    lock_length = 0
def on_scroll(x, y, dx, dy):
    if hotkey_mode == 2:
        window.scroll_signal.emit(dy)
def _snip_scroll(delta):
    snip._scroll_step = min(snip._scroll_step * 1.2 + 1, 15)
    snip._scroll_timer.start()
    step = snip.slider.singleStep() * snip._scroll_step
    if delta > 0:
        snip.slider.setValue(snip.slider.value() - int(step))
    elif delta < 0:
        snip.slider.setValue(snip.slider.value() + int(step))
def force_activate(hwnd):
    foreground_hwnd = ctypes.windll.user32.GetForegroundWindow()
    foreground_tid = ctypes.windll.user32.GetWindowThreadProcessId(foreground_hwnd, None)
    current_tid = ctypes.windll.kernel32.GetCurrentThreadId()
    if foreground_tid != current_tid:
        ctypes.windll.user32.AttachThreadInput(foreground_tid, current_tid, True)
        ctypes.windll.user32.SetForegroundWindow(hwnd)
        ctypes.windll.user32.AttachThreadInput(foreground_tid, current_tid, False)
    else:
        ctypes.windll.user32.SetForegroundWindow(hwnd)
def convert_max_fps():  # convert max_fps tier to show current tier's range and total frame
    global max_fps
    # fps at a later time cannot be bigger than earlier time because it would have already been deleted
    for i in range(0, len(max_fps)):
        for j in range(i+1, len(max_fps)):
            if max_fps[j][1] > max_fps[i][1]:
                max_fps[j][1] = max_fps[i][1]
    # convert range and append total frame for later calculation
    for i in range(len(max_fps) - 1, -1, -1):
        # max_fps[i][0] = max_fps[i][0] - max_fps[i-1][0]  # test
        if max_fps[i][0] < 0:
            max_fps[i][0] = 0
        if i == 0:
            current_layer_start = 0
        else:
            current_layer_start = max_fps[i-1][0]
        max_fps[i].append(int((max_fps[i][0]-current_layer_start)*max_fps[i][1]))
        max_fps[i][0] *= 1000  # convert to ms
class CvMat(c_void_p): pass
class OcrHandle(c_void_p): pass
GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000
def show_and_exclude_from_capture(window):
    user32.SetWindowDisplayAffinity.argtypes = [wintypes.HWND, wintypes.DWORD]
    user32.SetWindowDisplayAffinity.restype = wintypes.BOOL
    with lock:
        window.show()
        hwnd = int(window.winId())
        ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style | WS_EX_NOACTIVATE)
        user32.SetWindowDisplayAffinity(hwnd, 0)
        #ok = user32.SetWindowDisplayAffinity(hwnd, 0x00000011)
    #if not ok:
        #raise ctypes.WinError(ctypes.get_last_error())
def frame_interview(fps,cut_target,delete_frame_index):
# It took me 2 weeks to come up with this algorithm. Quite difficult to fully explain in comments. Contact me if you need more detail. Github qazzzlyt
# The short explanation is, it takes screenshot and delete old ones, like a deque with maxium length
# But I cannot use a deque due to:
# (1) fps is dynamic
# (2) screenshot loop should not stop/reset when displayed in QT
# (3) screenshot thread keep running and access same object with main thread
# So I created this algorithm to "interview" each frame and decide which frame should be deleted
    global screenshot
    total_deleted_frame = 0
    current_layer = len(fps) - 1
    if current_layer == 0:
        current_layer_deadline = this_screenshot_time
    else:
        current_layer_deadline = this_screenshot_time - fps[current_layer - 1][0]
    current_layer_frame_interval = 1000 / fps[current_layer][1]
    ideal_frame_time = this_screenshot_time - fps[current_layer][0]
    best_candidate = -1

    for i in range (lock_length, len(screenshot)):

        if screenshot[i][2]:  # If this frame is not to be deleted yet
            if screenshot[i][1] > current_layer_deadline:
            # check next layer
                if current_layer > 0:
                    current_layer -= 1
                    current_layer_deadline = this_screenshot_time - fps[current_layer - 1][0]
                current_layer_frame_interval = 1000 / fps[current_layer][1]
            if ideal_frame_time <= screenshot[i][1] - current_layer_frame_interval:
            # check if multiple frames need to be skipped
                ideal_frame_time = current_layer_deadline - int(math.ceil((current_layer_deadline - screenshot[i][1]) / current_layer_frame_interval)) * current_layer_frame_interval
                best_candidate = -1
            # compete with previous candidate
            if best_candidate != -1:
                if screenshot[i][1] > screenshot[best_candidate][1]:
                    lost_candidate = i
                else:
                    lost_candidate = best_candidate
                    best_candidate = i
                screenshot[lost_candidate][2] = False  # previous best candidate need delete
                delete_frame_index.add(lost_candidate)
                total_deleted_frame += 1
                if cut_target != -1:
                    if total_deleted_frame >= cut_target:
                        break
            else:       
                best_candidate = i
    return total_deleted_frame
def screenshot_thread():
    global this_screenshot_time
    sct = mss()
    mon = sct.monitors[config['monitor_index']] # test
    while True:
        qimg_rgb, width, height = screenshot_qimg_rgb(sct,mon)
        
        screenshot.append([qimg_rgb,this_screenshot_time,True])

        # reset delete index
        delete_frame_index = set()
        for i in range(len(screenshot)):
            screenshot[i][2] = True

        # delete picture outside max fps range
        delete_due_to_max_fps = frame_interview(max_fps,-1,delete_frame_index)

        vm = psutil.virtual_memory()
        total_memory = vm.total
        used_memory = vm.used

        process = psutil.Process(os.getpid())
        python_memory = process.memory_info().rss

        if python_memory / 1073741824 < min_memory_gb:
            cut_target = 0
        else:
            max_memory_byte = (total_memory - used_memory + python_memory) * max_memory_percentage
            excess_memory_byte = python_memory - max_memory_byte
            if excess_memory_byte > 0:
                cut_target = int(excess_memory_byte / (width * height * 3))
            else:
                cut_target = 0

        current_fps = [row.copy() for row in max_fps]  # deep copy max_fps
        if cut_target > delete_due_to_max_fps:
        #  take heaviest frame range, cut to half, and take next, until cut_target is reached
            previous_layer_end = 0
            for i in range(len(current_fps)):
            # cut start time will be affected by lock time and earliest frame time
                if lock_length >= 1:
                    lock_time = screenshot[lock_length-1][1]
                else:
                    lock_time = 0
                cut_start_time = min(max(this_screenshot_time - lock_time, previous_layer_end),current_fps[i][0])
                current_fps[i][2] = int(current_fps[i][2] * (cut_start_time - previous_layer_end) / (current_fps[i][0] - previous_layer_end))
                previous_layer_end = current_fps[i][0]
            planned_cut = 0
            frame_cut = cut_target - delete_due_to_max_fps
            for k in range(frame_cut):
                cut_layer = 0
                for i in range(1, len(current_fps)):
                    if current_fps[i][2] >= current_fps[cut_layer][2]:
                        cut_layer = i
                if current_fps[cut_layer][2] > 1:
                    planned_cut += int(current_fps[cut_layer][2]/2)
                    current_fps[cut_layer][1] /= 2
                    current_fps[cut_layer][2] = current_fps[cut_layer][2] - int(current_fps[cut_layer][2]/2)
                else:
                    break
                if cut_target <= planned_cut:
                    break
            frame_interview(current_fps,cut_target,delete_frame_index)

        # delete first screenshot if it is too old
        # there is a limitation in frame_interview that first screenshot will never be deleted
        if len(screenshot) > 1:
            if screenshot[0][1] < this_screenshot_time - max_fps[-1][0] and lock_length == 0:
                delete_frame_index.add(0)

        # delete frame
        if delete_frame_index:
            with lock:  # check and delete must be atomic to avoid deleting frames when it is used by main thread
                if min(delete_frame_index) >= lock_length:
                    screenshot[:] = [x for i, x in enumerate(screenshot) if i not in delete_frame_index]

        # get highest current fps
        highest_fps = 0
        for i in range(len(current_fps)):
            if current_fps[i][1] > highest_fps:
                highest_fps = current_fps[i][1]
        lowest_frame_interval  = 1000 / highest_fps

        if screenshot_thread_stop.is_set():  # check if stop event from config
            return
    
        # decide time of next screenshot time
        # to save resource, screenshot frequency will not be faster than current hight fps
        # to avoid rounding issue in future calculation, next screenshot time is based on multiple of frame interval
        t = time.time() * 1000
        next_screenshot_time = this_screenshot_time + (int((t - this_screenshot_time) / lowest_frame_interval) + 1) * lowest_frame_interval
        sleep_time = (next_screenshot_time - t)/1000
        # print((t-this_screenshot_time)/1000)  # test, show how long it takes
        # print('len of screenshot ' + str(len(screenshot)))
        # print(current_fps)
        this_screenshot_time = next_screenshot_time
    
        time.sleep(sleep_time)
class Bridge(QObject):
    click_snip = pyqtSignal()
    anki_new_note_done = pyqtSignal(str,str)
def init_ocr(det, rec, dict_path):
    if not dll.OcrLoadRuntime():
        raise RuntimeError('OcrLoadRuntime failed')

    @ErrorCallback
    def on_error(msg):
        raise RuntimeError(msg.decode('utf-8', 'ignore'))

    ocr = dll.OcrInit(det, rec, dict_path, 1, False, 0, b'CPU', on_error)
    if not ocr:
        raise RuntimeError('OcrInit failed')

    return ocr, on_error  # return on_error to keep it alive
def screenshot_qimg_rgb(sct,mon):
    img = sct.grab(mon)

    width = img.width
    height = img.height
    qimg = QImage(
        img.bgra,
        width,
        height,
        width * 4,
        QImage.Format_ARGB32
    )

    return qimg.convertToFormat(QImage.Format_RGB888), width, height
class Snip(QWidget):
    def __init__(self):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        
        self.start_pos = None
        self.end_pos = None
        self.dragging = False

        self.sct = mss()
        self.mon = self.sct.monitors[config['monitor_index']]  # test
        self.setGeometry(
            self.mon["left"],
            self.mon["top"],
            self.mon["width"],
            self.mon["height"]
        )

        hint_h = int(self.mon["height"] * 0.05)

        self.mask_color = QColor(0, 0, 0, 100)
        self.border_pen = QPen(QColor(255, 0, 0), 1)
        self.setCursor(Qt.CrossCursor)

#        pixmap = QPixmap(24, 24)
#        pixmap.fill(Qt.transparent)
#        painter = QPainter(pixmap)
#        painter.setPen(QPen(Qt.black, 3))
#        painter.drawLine(12, 0, 12, 23)
#        painter.drawLine(0, 12, 23, 12)
#        painter.setPen(QPen(Qt.white, 1))
#        painter.drawLine(12, 0, 12, 23)
#        painter.drawLine(0, 12, 23, 12)
#        painter.end()
#        self.setCursor(QCursor(pixmap, 12, 12))

        slider_w = int(self.mon["width"] * 0.85)
        slider_h = int(self.mon["height"] * 0.0625)
        x = (self.mon["width"] - slider_w) // 2
        y = int(self.mon["height"] * 0.05)
        self.panel = QWidget(self)
        self.panel.setGeometry(x, y, slider_w, slider_h + hint_h)

        self.slider_container = QWidget(self.panel)
        self.slider_container.setGeometry(0, 0, slider_w, slider_h)
        
        self.slider = QSlider(Qt.Horizontal, self.slider_container)

        self.slider.setPageStep(3)

        pad = 16
        self.slider.setGeometry(pad, pad, slider_w - pad * 2, slider_h - pad * 2)

        self.slider.show()
        self.slider.setCursor(Qt.ArrowCursor)
        self.slider.valueChanged.connect(self.on_slider_changed)
        self.slider_container.setObjectName("slider_container")
        self.slider_container.setStyleSheet("#slider_container{border:2px solid transparent;}#slider_container:hover{border:2px solid white;}")
        QApplication.instance().installEventFilter(self)
        self.slider_container.installEventFilter(self)
        QTimer.singleShot(0, self._fix_slider_hover)

        self._scroll_step = 1
        self._scroll_timer = QTimer()
        self._scroll_timer.setSingleShot(True)
        self._scroll_timer.setInterval(200)  # Reset
        self._scroll_timer.timeout.connect(self._reset_scroll_speed)

        if config['playback_hint_left'] > 0:
            self.hint_label = QLabel(ui('use_scroll'), self.panel)
            self.hint_label.setAlignment(Qt.AlignCenter)
            font_size = slider_h - pad
            font = self.hint_label.font()
            font.setPixelSize(font_size)
            self.hint_label.setFont(font)
            self.hint_label.setStyleSheet(f"color: rgba(255,255,255,180); background: transparent; font-size: {font_size}px;")
            fm = self.hint_label.fontMetrics()
            font_h = fm.height() + fm.leading()
            label_y = slider_h + (hint_h - font_h) // 2
            self.hint_label.setGeometry(0, label_y, slider_w, font_h)
            self.hint_label.show()
    
    def _reset_scroll_speed(self):  
        """Reset step multiplier when scrolling stops."""
        self._scroll_step = 1
        
    def on_slider_changed(self, value):
         self.background = screenshot[value][0]
         self.snip_time = screenshot[value][1] / 1000
         self.update()

    def _fix_slider_hover(self):
        pos = self.slider_container.mapFromGlobal(QCursor.pos())
        if self.slider_container.rect().contains(pos):
            self.slider_container.setAttribute(Qt.WA_UnderMouse, True)

    def start(self):
        global lock_length
        with lock:  # make sure screenshot does not change while getting lock_length. this is extremely important
            lock_length = len(screenshot)
        screenshot[lock_length-1][0], _, _, = screenshot_qimg_rgb(self.sct,self.mon)
        screenshot[lock_length-1][1] = time.time() * 1000
        self.setUpdatesEnabled(False)
        self.slider.setRange(0, lock_length - 1)
        self.slider.setValue(lock_length - 1)  # test. need to use moving average
        self.setUpdatesEnabled(True)
        show_and_exclude_from_capture(self)
        #self.activateWindow()
        self.audio = None

    def eventFilter(self, obj, event):

        if obj == self.slider:
            if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                opt = QStyleOptionSlider()
                self.slider.initStyleOption(opt)
                handle_rect = self.slider.style().subControlRect(
                    QStyle.CC_Slider, opt, QStyle.SC_SliderHandle, self.slider
                )
                # Click on handle -> let Qt handle drag normally
                if handle_rect.contains(event.pos()):
                    return False
                # Click on track -> jump to position
                x = event.pos().x()
                ratio = x / self.slider.width()
                value = self.slider.minimum() + ratio * (self.slider.maximum() - self.slider.minimum())
                self.slider.setValue(round(value))
                return True
    
        if obj == self.slider_container:
            if event.type() == QEvent.MouseButtonPress:
                if event.button() == Qt.LeftButton and not self.slider.geometry().contains(event.pos()):
                    self._dragging = True
                    self._drag_start = event.globalPos()
                    self._container_start = self.panel.pos()
                    return True

            elif event.type() == QEvent.MouseMove:
                if not getattr(self, "_dragging", False):
                    if self.slider.geometry().contains(event.pos()):
                        self.slider_container.setCursor(Qt.ArrowCursor)
                    else:
                        self.slider_container.setCursor(Qt.SizeAllCursor)
                if getattr(self, "_dragging", False):
                    delta = event.globalPos() - self._drag_start
                    self.panel.move(self._container_start + delta)
                    return True

            elif event.type() == QEvent.MouseButtonRelease:
                self._dragging = False
                return True
            
        return super().eventFilter(obj, event)

    def paintEvent(self, event):
        if not hasattr(self, 'background'):
            return
        p = QPainter(self)

        clip = event.rect()

        p.drawImage(clip, self.background, clip)
        p.fillRect(clip, self.mask_color)

        if self.start_pos and self.end_pos:
            rect = QRect(self.start_pos, self.end_pos).normalized()

            if rect.width() > 0 and rect.height() > 0:
                exposed = rect.intersected(clip)
                if not exposed.isEmpty():
                    p.drawImage(exposed, self.background, exposed)

                p.setPen(self.border_pen)
                p.drawRect(rect)
            
    def keyPressEvent(self, event):
        global lock_length
        if event.key() == Qt.Key_Escape:
            if self.dragging:
                self.cancel_drag()
            else:
                self.close_snip()
                lock_length = 0

    def cancel_drag(self):
        self.start_pos = None
        self.end_pos = None
        self.dragging = False
        self.update()
        window.show
    
    def close_snip(self):
        global hotkey_mode
        self.hide()
        self.start_pos = None
        self.end_pos = None
        self.dragging = False
        hotkey_mode = 1
        self._scroll_step = 1

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.start_pos = event.pos()
            self.end_pos = event.pos()
            self.dragging = True
            self.update()

    def mouseMoveEvent(self, event):
        if self.start_pos is None:
            return

        old_rect = QRect(self.start_pos, self.end_pos).normalized()
        self.end_pos = event.pos()
        new_rect = QRect(self.start_pos, self.end_pos).normalized()
        dirty = old_rect.united(new_rect).adjusted(-4, -4, 4, 4)
        self.update(dirty)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.start_pos:
            self.end_pos = event.pos()
            rect = QRect(self.start_pos, self.end_pos).normalized()
            cropped = self.background.copy(rect)
            click_time = time.time()
            recorder.capture_last(self.snip_time,click_time)  # test need move to thread
            self.close_snip()
            print('lock_length ' + str(lock_length-1) + ' slider value ' + str(self.slider.value()))  # text
            if config['playback_hint_left'] > 0:
                if lock_length-1 > self.slider.value():  # means slider is used by user
                    n = config['playback_hint_left']-1
                    update_config('playback_hint_left',n)
                    if n <= 0:
                        self.hint_label.deleteLater()
            run_ocr_and_after(self.snip_time, ocr, on_error, cropped, self.background, self.slider.value(), rect, self.audio, self.audio_start_time)  # test need better thread arrangement
def run_ocr_and_after(snip_time, ocr, on_error, image, qimg_full, snip_index, rect, audio_bytes, audio_start_time):
    global window
    global processing
    global lock_length

    ocr_result = run_ocr(image,ocr,on_error,2)

    if ocr_result:
    # if ocr successful, go search dictionary
        word = ocr_result[0][0]
        word_info = {}
        search_dict_thread = threading.Thread(target=lambda: word_info.update(search_dict(word))) # test need to consider no result
        search_dict_thread.start()

        #saved_width = window.width()  
        #window.setUpdatesEnabled(False)
        #window_display_word_blank()
        
        #window.setFixedWidth(saved_width)
        #show_and_exclude_from_capture(window)
        
        #refresh_window(False)
        #if window.isMinimized():
            #window.showNormal()
        #window.raise_()

        
        start_pos = rect.topLeft()
        points = [
            start_pos + QPoint(int(ocr_result[0][1][0]), int(ocr_result[0][1][1])),
            start_pos + QPoint(int(ocr_result[0][1][2]), int(ocr_result[0][1][3])),
            start_pos + QPoint(int(ocr_result[0][1][4]), int(ocr_result[0][1][5])),
            start_pos + QPoint(int(ocr_result[0][1][6]), int(ocr_result[0][1][7])),
        ]  # test need to adapt to partial screen shoot
        points = quad_to_rect_if_close(points, 0.15)
        pixmap = QPixmap.fromImage(qimg_full)
        window.setUpdatesEnabled(False)
        window_change_picture(pixmap)
        window.word.setText(word)
        search_dict_thread.join()
        if word_info['spell'] !=  '':
            window_display_word(word_info['spell'], word_info['pron'], word_info['accent'], word_info['romaji'], word_info['excerpt'], word_info['fuzzy'],None,False)
            #window.setMaximumSize(16777215, 16777215)
            show_and_exclude_from_capture(window)
            if window.isMinimized():
                window.showNormal()
                window.raise_()
            refresh_window(True)
            #window.setMinimumSize(0, 0)
            # create new note in anki
            word_info['word'] = word
            word_info['word_position'] = '[' + str(points[0].x()) + ',' + str(points[0].y()) + '],[' + str(points[1].x()) + ',' + str(points[1].y()) + '],[' + str(points[2].x()) + ',' + str(points[2].y()) + '],[' + str(points[3].x()) + ',' + str(points[3].y()) + ']'
            processing = True

            if len(audio_bytes) > 0:
                subtitle_sentences, snip_index_in_sentences = detect_subtitle(points,snip_index,snip_time,audio_bytes,rect,word,ocr,on_error)  # test need delete, do not need audio bytes
                frame_duration_ms = 20
                rms, rms_moving_average = detect_audio(audio_bytes, frame_duration_ms)

                # test need delete
                import csv
                folder_path = os.path.join(os.path.expanduser("~"), "Downloads", time.strftime("%Y%m%d_%H%M%S", time.localtime(snip_time)))  #test need delete
                with open(os.path.join(folder_path, 'sentences.csv'), 'r', encoding='utf-8', newline='') as f:
                    rows = list(csv.reader(f))
                for i in range(max(len(rows), len(rms))):
                    if i >= len(rows): rows.append(['', ''])
                    rows[i] += [f'{rms[i]:.6f}' if i < len(rms) else '',
                                f'{rms_moving_average[i]:.6f}' if i < len(rms_moving_average) else '']
                rows[0].append(f'{snip.audio_start_time:.3f}')
                with open(os.path.join(folder_path, 'sentences.csv'), 'w', encoding='utf-8', newline='') as f:
                    csv.writer(f).writerows(rows)  
                
                audio_bytes, play_start_time, play_end_time = analyze_audio(audio_bytes,audio_start_time,rms,rms_moving_average,frame_duration_ms,snip_index_in_sentences,subtitle_sentences)
                word_info['audio_range'] = f"{float(play_start_time)},{float(play_end_time)}"
                audio_bytes_normalized = normalize_audio(audio_bytes, rms)
                audio_wav = pcm_to_wav_bytes(audio_bytes_normalized)  #test
                audio_mp3 = wav_to_mp3(audio_wav)
            else:
                audio_mp3 = None
            threading.Thread(target=anki_new_note, args=(word_info,qimg_full,audio_mp3,), daemon = True).start()
        else:
            window_display_word_blank()
            refresh_window(False)
            print('search dict fail for ' + word)
    else:
        lock_length = 0
        print('no ocr result')  # test need tool tip
        #QToolTip.showText(QCursor.pos(), "No OCR result", window, QRect(), 2000)
        #QTimer.singleShot(2000, QToolTip.hideText)
def run_ocr(image,ocr,on_error,directional):
    bits = image.bits()
    bits.setsize(image.byteCount())

    mat = dll.cvMatFromRGB888(int(bits), image.width(), image.height(), image.bytesPerLine())
    if not mat:
        raise RuntimeError('cvMatFromRGB888 failed')

    ocr_result = []

    @DetectCallback
    def on_detect(x1, y1, x2, y2, x3, y3, x4, y4, text):
        ocr_result.append((text.decode('utf-8', 'ignore'), (x1, y1, x2, y2, x3, y3, x4, y4)))

    dll.OcrDetect(ocr, mat, directional, on_detect, on_error)
    dll.cvMatDestroy(mat)

    return ocr_result
def refresh_window(need_adjust_size):
    window.layout().activate()
    if need_adjust_size:
        window.adjustSize()
    QApplication.sendPostedEvents()
    window.setUpdatesEnabled(True)
    QApplication.processEvents()
def quad_to_rect_if_close(points, threshold):
    p0, p1, p2, p3 = points  # top-left, top-right, bottom-right, bottom-left

    width = ((p1 - p0).x() ** 2 + (p1 - p0).y() ** 2) ** 0.5
    height = ((p3 - p0).x() ** 2 + (p3 - p0).y() ** 2) ** 0.5

    top_dy = abs(p1.y() - p0.y())
    bot_dy = abs(p2.y() - p3.y())
    left_dx = abs(p3.x() - p0.x())
    right_dx = abs(p2.x() - p1.x())

    if (top_dy / height < threshold and bot_dy / height < threshold and
        left_dx / width < threshold and right_dx / width < threshold):
        x0 = max(p0.x(), p3.x())
        x1 = min(p1.x(), p2.x())
        y0 = max(p0.y(), p1.y())
        y1 = min(p3.y(), p2.y())
        return [QPoint(x0, y0), QPoint(x1, y0), QPoint(x1, y1), QPoint(x0, y1)]

    return points
def quad_to_smaller_rect(points):
    # ocr det will normally take a quad larger than actual text border
    # here i change it to a smaller rect to (1) remove impact from background change (2) make later calculation a little bit faster
    x1 = max(points[0].x(), points[3].x())  # left:  take larger
    x2 = min(points[1].x(), points[2].x())  # right: take smaller
    y1 = max(points[0].y(), points[1].y())  # top:   take larger
    y2 = min(points[2].y(), points[3].y())  # bottom: take smaller
    margin = min(x2 - x1, y2 - y1) * 0.2
    return QRect(round(x1 + margin), round(y1 + margin), round(x2 - x1 - margin * 2), round(y2 - y1 - margin * 2))
def detect_subtitle(points,snip_index,snip_time,audio_bytes,rect,word,ocr,on_error):
    global lock_length

    # same direction with original ocr
    # this is because rect will be expanded vertically for further ocr
    # if no adjustment here, the ocr is more likely to become vertical
    rect_small = quad_to_smaller_rect(points)
    w = rect_small.width()
    h = rect_small.height()
    if w >= h * 1.8:
        direction = 0  # horizontal
    elif h >= w * 1.8:
        direction = 1  # vertical
    else:
        direction = 2  # auto

    folder_path = os.path.join(os.path.expanduser("~"), "Downloads", time.strftime("%Y%m%d_%H%M%S", time.localtime(snip_time)))  #test need delete
    os.makedirs(folder_path)  #test need delete

    sentences = []
    snip_hog = compute_hog(screenshot[snip_index][0],rect_small)

    for i in range(lock_length):
        this_frame_time = screenshot[i][1]/1000
        if (snip_time - AUDIO_BEFORE_SNIP_SECOND) <= this_frame_time and this_frame_time <= (snip_time + AUDIO_AFTER_SNIP_SECOND):
            if i == snip_index:
                snip_index_in_sentences = len(sentences)
            sentences.append([-1,this_frame_time,False])  # (diff,time,ocr_same)

    # expand rect
    expand = rect.height() * 5
    rect_expanded = rect.adjusted(0, -expand, 0, expand)

    # loop left to find start
    last_hog = snip_hog
    ocr_budget_move = 2
    ocr_budget_ambiguous = 2
    for i in range(snip_index_in_sentences-1,-1,-1):
        last_hog, ocr_budget_ambiguous, ocr_budget_move, rect_small = sentences_one_compare(i,snip_index_in_sentences,snip_index,rect_small,sentences,rect_expanded,word,ocr_budget_ambiguous,last_hog,ocr_budget_move,direction)
        screenshot[i - snip_index_in_sentences + snip_index][0].copy(rect_small).save(os.path.join(folder_path, f"{screenshot[i][1]/1000:.3f}.png"))  #test need delete

    # loop left to find end
    last_hog = snip_hog
    ocr_budget_move = 2
    ocr_budget_ambiguous = 2
    for i in range(snip_index_in_sentences+1,len(sentences)):
        last_hog, ocr_budget_ambiguous, ocr_budget_move, rect_small = sentences_one_compare(i,snip_index_in_sentences,snip_index,rect_small,sentences,rect_expanded,word,ocr_budget_ambiguous,last_hog,ocr_budget_move,direction)
        screenshot[i - snip_index_in_sentences + snip_index][0].copy(rect_small).save(os.path.join(folder_path, f"{screenshot[i][1]/1000:.3f}.png"))  #test need delete

#    for i in range(lock_length):
#        this_frame_time = screenshot[i][1]/1000
#        if (snip_time - AUDIO_BEFORE_SNIP_SECOND) <= this_frame_time and this_frame_time <= (snip_time + AUDIO_AFTER_SNIP_SECOND):
#            if i != snip_index:
#                diff = float(np.linalg.norm(compute_hog(screenshot[i][0], rect_small) - snip_hog))
#            else:
#                diff = 0
#                snip_index_in_sentences = len(sentences)
#            sentences.append((diff,this_frame_time))
#            screenshot[i][0].copy(rect_small).save(os.path.join(folder_path, f"{this_frame_time:.3f}.png"))  #test need delete

    #test need delete
    import csv
    with open(os.path.join(folder_path, "sentences.csv"), "w", newline="") as f:
        csv.writer(f).writerows([["diff","frame_time"]] + list(sentences))
    audio_wav =  pcm_to_wav_bytes(audio_bytes)  #test
    audio_mp3 = wav_to_mp3(audio_wav)
    with open(os.path.join(folder_path, "audio.mp3"), "wb") as f:
        f.write(audio_mp3)
    
    lock_length = 0
    return sentences, snip_index_in_sentences
def sentences_one_compare(i,snip_index_in_sentences,snip_index,rect_small,sentences,rect_expanded,word,ocr_budget_ambiguous,last_hog,ocr_budget_move,direction):
    ambiguous_diff_min = 0.04
    ambiguous_diff_max = 0.12
    k = i - snip_index_in_sentences + snip_index
    this_hog = compute_hog(screenshot[k][0], rect_small)
    diff = float(np.linalg.norm(this_hog - last_hog))
    sentences[i][0] = diff
    need_ocr = False
    if diff > ambiguous_diff_min and ocr_budget_move > 0:
        need_ocr = True
        ocr_budget_move -= 1
    elif ambiguous_diff_min < diff and diff < ambiguous_diff_max and ocr_budget_ambiguous > 0:
        ocr_budget_ambiguous -= 1
        need_ocr = True
    if need_ocr:
        ocr_result = run_ocr(screenshot[k][0].copy(rect_expanded), ocr, on_error, direction)
        if ocr_result:
            matched = next((result for result in ocr_result if result[0] == word), None)
            if matched:
                sentences[i][2] = True
                coords = matched[1]
                offset = rect_expanded.topLeft()
                points = [
                    offset + QPoint(int(coords[0]), int(coords[1])),
                    offset + QPoint(int(coords[2]), int(coords[3])),
                    offset + QPoint(int(coords[4]), int(coords[5])),
                    offset + QPoint(int(coords[6]), int(coords[7])),
                ]
                rect_small = quad_to_smaller_rect(points)
                this_hog = compute_hog(screenshot[k][0], rect_small)
            print(ocr_result)
    return this_hog, ocr_budget_ambiguous, ocr_budget_move, rect_small
def compute_hog(qimg_full,rect_small):
    cropped = qimg_full.copy(rect_small).convertToFormat(QImage.Format_Grayscale8)
    ptr = cropped.bits()
    ptr.setsize(cropped.byteCount())
    arr = np.array(ptr, dtype=np.float32).reshape((rect_small.height(), cropped.bytesPerLine()))
    np_img = arr[:, :rect_small.width()]

    gx = np.diff(np_img, axis=1, append=np_img[:, -1:])
    gy = np.diff(np_img, axis=0, append=np_img[-1:, :])
    mag = np.sqrt(gx**2 + gy**2)
    ang = np.arctan2(gy, gx) * 180 / np.pi % 180
    hist, _ = np.histogram(ang, bins=8, range=(0, 180), weights=mag)
    return hist / (hist.sum() + 1e-8)
def window_display_word(spell, pron, accent, romaji, excerpt, fuzzy, pixmap, change_picture):
    if change_picture:
        window_change_picture(pixmap)
    window.label_spell.setText(spell)
    if (pron + accent) and romaji:
        pipe = ' | '
    else:
        pipe = ''
    window.label_pron.setText(pron + accent + pipe + romaji)
    if excerpt and fuzzy: 
        lf = '<br><br>'
    else:
        lf = ''
    window.label_excerpt.setText(excerpt + lf + fuzzy)
    toggle_to_main()
def window_change_picture(pixmap):
    if pixmap:
        margin = window.layout().contentsMargins()
        label_width = window.width() - margin.left() - margin.right()
        scaled_pixmap = pixmap.scaled(label_width, pixmap.height(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        window.label_screenshot.setPixmap(scaled_pixmap)
    else:
        window.label_screenshot.clear()
def window_display_word_blank():
    window_display_word('','','','','','','',True)
    window.anki_id = None
def anki_new_note(fields,qimg_full,audio):
    t = time.strftime("%Y%m%d_%H%M%S")
    if qimg_full:
        buf = QBuffer()
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        qimg_full.save(buf, "JPEG", int(config['jpeg_quality']))
        img_bytes = buf.data().data()
        screenshot_name = anki_upload_media(img_bytes, fields['word'] + t + '.jpg')
        if screenshot_name:
            fields['screenshot'] = f'<img src="{screenshot_name['result']}">'
    if audio:
        audio_name = anki_upload_media(audio, fields['word'] + t + '.mp3')
        if audio_name:
            fields['audio'] = f'<img src="{audio_name["result"]}">'  # pretend to be a img so anki will not auto delete it. if label it as a sound, anki will force to auto play it, which i do not want
    result = invoke("addNote", note={
        "deckName": DECK_NAME,
        "modelName": MODEL_NAME,
        "fields": fields,
        "options": {"allowDuplicate": True}
    })
    if result:
        if result['error']:
            print(result['error'])
        else:
            bridge.anki_new_note_done.emit(str(result['result']),fields['word'])
def anki_new_note_after(anki_id,word):
    global processing
    anki_list.insert(0,[anki_id,word])
    window.anki_id = anki_id
    processing = False
    threading.Thread(target=anki_sync, daemon = True).start()
def anki_upload_media(media_byte, filename):
    b64 = base64.b64encode(media_byte).decode("utf-8")
    return invoke("storeMediaFile", filename=filename, data=b64)   
def anki_download_media(filename):
    result = invoke("retrieveMediaFile", filename=filename)
    if result["result"] is False:
        return None
    b64 = result["result"]
    data = base64.b64decode(b64)
    return data
def anki_get_and_display(anki_id):
    result = invoke('notesInfo', notes=[int(anki_id)])
    # test need to consider when note deleted in anki
    fields = result['result'][0]['fields']
    pixmap = QPixmap()
    pixmap.loadFromData(anki_download_media(fields['screenshot']['value'].split('"')[1]))
    window_display_word(fields['spell']['value'], fields['pron']['value'], fields['accent']['value'], fields['romaji']['value'], fields['excerpt']['value'], fields['fuzzy']['value'],pixmap,True)
    window.word.setText(fields['word']['value'])
    window.anki_id = anki_id
def anki_delete_note():  # test need more detailed delete
    window.delete_btn.setChecked(True)
    check_processing()
    window.delete_btn.setChecked(False)
    if window.anki_id:  # test need to consider blank
        threading.Thread(target=invoke, args=("deleteNotes",), kwargs={"notes": [int(window.anki_id)]}, daemon=True).start()
        for i in range(len(anki_list)):
            if str(anki_list[i][0]) == str(window.anki_id):
                anki_list.remove(anki_list[i])
                break
        # display the older card in list
        if anki_list:
            if i == len(anki_list):  # display the newer card if deleted card is the oldest one
                i -= 1
            anki_get_and_display(anki_list[i][0])
        else:
            window.word.setText('')
            window_display_word_blank()
def anki_sync():
    return  # test test test
    global anki_sync_running
    if not anki_sync_running:
        anki_sync_running = True

        # anki will show a status of 'sync complete' after sync
        # i don't want user keep seeing this
        # the only solution i found is to move anki outside window and then move back
        anki_hwnd = user32.FindWindowW(None, None)
        while anki_hwnd:
            buf = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(anki_hwnd, buf, 256)
            if buf.value.endswith('- Anki'):  # test need better way to capture anki window
                break
            anki_hwnd = user32.GetWindow(anki_hwnd, 2)  # GW_HWNDNEXT
        else:
            anki_hwnd = None
        # record original position
        rect = ctypes.wintypes.RECT()
        user32.GetWindowRect(anki_hwnd, ctypes.byref(rect))
        orig_x = max(rect.left, 0)
        orig_y = max(rect.top, 0)
        w = rect.right - rect.left
        h = rect.bottom - rect.top

        # move anki
        user32.MoveWindow(anki_hwnd, -10000, -10000, w, h, False)
        time.sleep(0.5)
        invoke("sync")
        # move back
        time.sleep(2)
        user32.MoveWindow(anki_hwnd, orig_x, orig_y, w, h, False)
        
        anki_sync_running = False
def invoke(action, **params):
    global install_msg_showing
    # check if anki is open
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        if s.connect_ex((ANKI_HOST, ANKI_PORT)) != 0:  # test test test need more detail to process anki open
            anki_path = config['anki_path']
            if anki_path:
                open_anki(anki_path)
            if not config['anki_connect_successful']:
                if not install_msg_showing:
                    install_msg_showing = True
                    window.show_msg_signal.emit()
                return
            # Poll 15 seconds for AnkiConnect
            deadline = time.time() + 15
            while time.time() < deadline:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s2:
                    s2.settimeout(0.3)
                    if s2.connect_ex((ANKI_HOST, ANKI_PORT)) == 0:
                        break
                time.sleep(0.5)
            else:
                msg = QMessageBox()
                msg.setWindowTitle(ui('messagebox_title'))
                msg.setText(ui('no_anki_connection'))
                msg.setStandardButtons(QMessageBox.Ok)
                msg.exec_()
                return
    if not config['anki_connect_successful']:
        update_config('anki_connect_successful', True)
    return requests.post(ANKI_URL, json={"action": action, "params": params, "version": 6}).json()
def refresh_word():
    global processing
    check_processing()
    processing = True
    word = window.word.text()
    if word:
        word_info = search_dict(word)
        window_display_word(word_info['spell'], word_info['pron'], word_info['accent'], word_info['romaji'], word_info['excerpt'], word_info['fuzzy'],None,False)
        word_info['word'] = word
        invoke("updateNoteFields", note={
            "id": int(window.anki_id),
            "fields": word_info
        })
        for i in range(len(anki_list)):
            if str(anki_list[i][0]) == str(window.anki_id):
                anki_list[i][1] = word
                break
        processing = False
        threading.Thread(target=anki_sync, daemon = True).start()
    processing = False
def refresh_history_menu():
    window.history_menu.clear()
    check_processing()
    hwnd = int(window.history_menu.winId())
    user32.SetWindowDisplayAffinity(hwnd, 0)
    user32.SetWindowDisplayAffinity(hwnd, 0x00000011)
    if anki_list:
        window.history_menu.setStyleSheet("QMenu::item:selected { background-color: #444; color: white; }")
        for anki_id, word in anki_list:
            action = window.history_menu.addAction(word)
            action.triggered.connect(partial(anki_get_and_display, anki_id))
    else:
        window.history_menu.setStyleSheet("")
        window.history_menu.addAction(ui('blank'))
def on_click_snip():
    global hotkey_mode, _snip_open_time, _snip_opened_by_right  
    hotkey_mode = 2
    _snip_open_time = time.time()
    _snip_opened_by_right = any(h['type'] == 'mouse' and h['button'] == 'right' for h in config['hotkey'])
    bridge.click_snip.emit()
def search_dict(word):
    result = {
        "spell": "",
        "pron": "",
        "accent": "",
        "romaji": "",
        "excerpt": "",
        "fuzzy": "",
        #"sync": ""
    }
    src = config.get('src_lang', SRC_LANGS[0])
    dst = config.get('dst_lang', DST_LANGS[0])
    
    if src == '日本語' and dst == '中文':

        return search_moji_api(word, result)

def _parse_genius(val):
    # spell: strip rank and hdot tags
    m = re.search(r'<headword class="main"[^>]*>(.*?)</headword>', val)
    spell_raw = m.group(1) if m else ''
    spell = re.sub(r'<rank[^>]*>.*?</rank>', '', spell_raw)
    spell = re.sub(r'<hdot>.*?</hdot>', '', spell)
    spell = re.sub(r'<hhyphen>.*?</hhyphen>', '', spell)
    spell = re.sub(r'<[^>]+>', '', spell).strip()

    # pron: content between hatsuon tags
    pron_m = re.search(r'<hatsuon_start>.*?</hatsuon_start>(.*?)<hatsuon_end>', val, re.DOTALL)
    pron = re.sub(r'<[^>]+>', '', pron_m.group(1)).strip() if pron_m else ''

    # pos: first red FM pos tag
    pos_m = re.search(r'<pos class="red FM">(.*?)</pos>', val)
    pos = re.sub(r'<[^>]+>', '', pos_m.group(1)).strip() if pos_m else ''

    # excerpt: top 3 numbered senses, bold meanings only
    sense_groups = re.findall(r'<MeaningG[^>]*class="[^"]*語義[^"]*"[^>]*>(.*?)</MeaningG>', val, re.DOTALL)
    lines = []
    for sg in sense_groups[:3]:
        num_m = re.search(r'<gogibangou[^>]*>(\d+)</gogibangou>', sg)
        if not num_m:
            continue
        bolds = re.findall(r'<b>(.*?)</b>', sg)
        bolds = [re.sub(r'<[^>]+>', '', b).strip() for b in bolds if b.strip()]
        if bolds:
            lines.append(f"({num_m.group(1)}) {'・'.join(bolds[:3])}")
    
    # fallback for proper nouns / single-sense entries
    if not lines:
        pos_group = re.search(r'<MeaningG[^>]*class="[^"]*品詞[^"]*"[^>]*>(.*?)</MeaningG>', val, re.DOTALL)
        if pos_group:
            text = re.sub(r'<[^>]+>', '', pos_group.group(1)).strip()
            text = re.sub(r'^━━\s*\S+\s*', '', text).strip()
            m = re.search(r'[。．.]', text)
            lines.append(text[:m.start()+1] if m else text[:500])
    
    excerpt = '<br>'.join(lines)

    return spell, pron, pos, excerpt

def search_genius(word, result):
    _conn_dict_ready.wait()
    try:
        c = _conn_dict.cursor()

        row = c.execute("SELECT value FROM dict WHERE key=?", (word,)).fetchone()
        if not row:
            row = c.execute("SELECT value FROM dict WHERE key=? COLLATE NOCASE", (word,)).fetchone()

        if row:
            val = row[0]
            # Follow links
            for _ in range(5):
                if val.startswith('@@@LINK='):
                    r2 = c.execute("SELECT value FROM dict WHERE key=?", (val[8:].strip(),)).fetchone()
                    val = r2[0] if r2 else val
                    if not val.startswith('@@@LINK='):
                        break
                else:
                    break
            spell, pron, pos, excerpt = _parse_genius(val)
            result["spell"]   = spell
            result["pron"]    = f'/{pron}/' if pron else ''
            result["excerpt"] = f'[{pos}] {excerpt}' if pos else excerpt

        # Fuzzy: prefix match
        fuzzy_rows = c.execute(
            "SELECT key, value FROM dict WHERE key LIKE ? AND lower(key) != lower(?) LIMIT 5",
            (f"{word}%", word)
        ).fetchall()
        fuzzy_blocks = []
        for r in fuzzy_rows:
            val = r['value']
            if val.startswith('@@@LINK='):
                continue
            # skip compound/child entries
            if '<headword class="child">' in val:
                continue
            s, p, po, ex = _parse_genius(val)
            if not s:
                continue
            header = f"{s} /{p}/" if p else s
            fuzzy_blocks.append(f"{header}<br>[{po}] {ex}" if po else f"{header}<br>{ex}")
        result["fuzzy"] = "<br><br>".join(fuzzy_blocks[:3])

    except Exception as e:
        print(f"genius search fail: {e}")

    return result
def _parse_moji_mdx(html):
    spell = pron = accent = excerpt = ""
 
    m = re.search(r'class="entry_name">(.*?)</h3>', html)
    if m:
        full = re.sub(r'<[^>]+>', '', m.group(1))
        m2 = re.match(r'^(.*?)【(.*?)】$', full.strip())
        if m2:
            spell   = m2.group(1).strip()
            reading = m2.group(2).strip()
            am = re.search(r'[①②③④⑤⑥⑦⑧⑨⑩◎]$', reading)
            if am:
                accent = am.group(0)
                pron   = reading[:am.start()].strip()
            else:
                pron = reading
        else:
            spell = full.strip()
 
    pos_list = re.findall(r'class="cixing_title">(.*?)</div>', html)
    pos = "·".join(re.sub(r'<[^>]+>', '', p).strip() for p in pos_list[:2] if p.strip())
 
    exps = re.findall(r'class="explanation">(.*?)</div>', html)
    exps_clean = [re.sub(r'<[^>]+>', '', e).strip() for e in exps[:3] if e.strip()]
 
    parts = []
    if pos:
        parts.append(f"[{pos}]")
    parts.extend(exps_clean)
    excerpt = " ".join(parts)
 
    return spell, pron, accent, excerpt
def search_moji(word, result):
    _conn_dict_ready.wait()
    try:
        c = _conn_dict.cursor()
 
        row = c.execute("SELECT value FROM dict WHERE key=?", (word,)).fetchone()
        if not row:
            row = c.execute(
                "SELECT value FROM dict WHERE key LIKE ?", (f"{word}【%",)
            ).fetchone()
 
        if not row:

            rows = c.execute(
                "SELECT key FROM dict WHERE key LIKE ? AND key LIKE '%【%' LIMIT 5",
                (f"{word}%",)
            ).fetchall()
            if rows:
                result["fuzzy"] = "<br>".join(
                    re.sub(r'【.*?】', '', r[0]).strip() for r in rows
                )
            return result
 
        val = row[0]

        for _ in range(5):
            if val.startswith("@@@LINK="):
                r2 = c.execute(
                    "SELECT value FROM dict WHERE key=?", (val[8:].strip(),)
                ).fetchone()
                val = r2[0] if r2 else val
                if not val.startswith("@@@LINK="):
                    break
            else:
                m = re.search(r'href="entry://(.*?)"', val)
                if m:
                    r2 = c.execute(
                        "SELECT value FROM dict WHERE key=?", (m.group(1).strip(),)
                    ).fetchone()
                    if r2:
                        val = r2[0]
                        continue
                break
 
        spell, pron, accent, excerpt = _parse_moji_mdx(val)
        result["spell"]   = spell
        result["pron"]    = pron
        result["accent"]  = accent
        result["excerpt"] = excerpt
 
    except Exception as e:
        print(f"moji mdx search fail: {e}")
 
    return result
SKIP_LABELS = {
    "熟語", "関連", "異読", "成語", "囲み",
    "主見出し", "発音", "比較", "日:中", "用法", "市制",
    "大写", "地支", "１", "２", "３", "４", "５"
}
NOTE_LABELS = {"補足", "参考", "注意", "語法", "語源", "反義"}
def tokenize_shogakukan(html):
    tokens = []
    parts = re.split(r'(<[^>]+>)', html)
    current_color = None
    buffer = []
    for part in parts:
        if not part:
            continue
        tag = re.match(r'<font[^>]*color\s*=\s*["\']?\s*(\w+)["\']?', part, re.IGNORECASE)
        if tag:
            text = "".join(buffer).strip()
            if text:
                tokens.append((current_color or "plain", text))
            buffer = []
            current_color = tag.group(1).lower()
        elif part.lower() == '</font>':
            text = "".join(buffer).strip()
            if text:
                tokens.append((current_color or "plain", text))
            buffer = []
            current_color = None
        elif re.match(r'<(br|p)[\s/]*>', part, re.IGNORECASE):
            text = "".join(buffer).strip()
            if text:
                tokens.append((current_color or "plain", text))
            buffer = []
        elif part.startswith('<'):
            pass
        else:
            buffer.append(part)
    text = "".join(buffer).strip()
    if text:
        tokens.append((current_color or "plain", text))
    return tokens
def parse_shogakukan(html):
    result = {"spell": "", "pron": "", "excerpt": ""}
    header = re.search(
        r'<font[^>]*color\s*=\s*["\']?\s*red["\']?[^>]*>【(.*?)】</font>',
        html, re.IGNORECASE
    )
    if not header:
        return result
    result["spell"] = header.group(1).strip()
    before = html[:header.start()]
    result["pron"] = re.sub(r'<[^>]+>', '', before).strip()
 
    tokens = tokenize_shogakukan(html[header.end():])
 
    sense_lines   = []
    current_line  = []
    skip_example  = False
    skip_block    = False
    domain        = ""
    sense_count   = 0
    in_note_paren = False
 
    i = 0
    while i < len(tokens):
        color, text = tokens[i]
 
        if color == "green":
            if text == "例：":
                skip_example = True
            elif re.match(r'^〈.+〉$', text):
                domain = text
                skip_block = False
            i += 1
            continue
 
        if color == "blue":
            if not skip_example and not skip_block:
                current_line.append(text)
            i += 1
            continue
 
        if color in ("black", "plain"):
            if text == "(" and i + 1 < len(tokens) and tokens[i+1][0] == "red":
                label = tokens[i+1][1]
                label_name = label[1:-1] if re.match(r'^【.+】$', label) else ""
                if label_name in NOTE_LABELS:
                    in_note_paren = True
                    i += 1
                    continue
 
            if in_note_paren:
                if "）" in text:
                    _, after_paren = text.split("）", 1)
                    rest = after_paren.strip()
                    if rest and not skip_example and not skip_block:
                        current_line.append(rest)
                    in_note_paren = False
                i += 1
                continue
 
            sense_match = re.match(r'^\((\d+)\)(.*)', text)
            if sense_match:
                if current_line:
                    sense_lines.append(" ".join(current_line))
                    current_line = []
                skip_example  = False
                skip_block    = False
                in_note_paren = False
                sense_count  += 1
                if sense_count > 5:
                    break
                num    = sense_match.group(1)
                rest   = sense_match.group(2).strip()
                prefix = f"({num})"
                if domain:
                    prefix = f"{domain} {prefix}"
                    domain = ""
                current_line.append(f"{prefix} {rest}" if rest else prefix)
            else:
                if not skip_example and not skip_block:
                    current_line.append(text)
            i += 1
            continue
 
        if color == "red":
            skip_example = False
            if re.match(r'^【.+】$', text):
                label = text[1:-1]
                if label in SKIP_LABELS:
                    skip_block    = True
                    in_note_paren = False
                    if current_line:
                        sense_lines.append(" ".join(current_line))
                        current_line = []
                elif label in NOTE_LABELS:
                    if in_note_paren:
                        current_line.append(f"[{label}]")
                    else:
                        if current_line:
                            sense_lines.append(" ".join(current_line))
                            current_line = []
                        current_line.append(f"[{label}]")
            i += 1
            continue
 
        i += 1
 
    if current_line:
        sense_lines.append(" ".join(current_line))
    if domain:
        sense_lines.insert(0, domain)
    result["excerpt"] = "<br>".join(sense_lines)
    return result
def search_shogakukan(word, result):
    _conn_dict_ready.wait()
    try:
        c = _conn_dict.cursor()
        row = c.execute("SELECT value FROM dict WHERE key=?", (word,)).fetchone()
        if not row:
            row = c.execute("SELECT value FROM dict WHERE TRIM(key)=?", (word,)).fetchone()
        if row:
            val = row[0]
            if val.startswith("@@@LINK="):
                row2 = c.execute("SELECT value FROM dict WHERE key=?", (val[8:].strip(),)).fetchone()
                val = row2[0] if row2 else val
            parsed = parse_shogakukan(val)
            result["spell"]   = parsed["spell"]
            result["pron"]    = parsed["pron"]
            result["excerpt"] = parsed.get("excerpt", "")
    except Exception as e:
        print(f"shogakukan search fail: {e}")
    return result
POS_MAP = {
    # Godan verbs
    "Godan verb with 'u' ending": "Godan-u",
    "Godan verb with 'u' ending (special class)": "Godan-u(sp)",
    "Godan verb with 'tsu' ending": "Godan-tsu",
    "Godan verb with 'ru' ending": "Godan-ru",
    "Godan verb with 'ru' ending (irregular verb)": "Godan-ru(irr)",
    "Godan verb with 'ku' ending": "Godan-ku",
    "Godan verb with 'gu' ending": "Godan-gu",
    "Godan verb with 'su' ending": "Godan-su",
    "Godan verb with 'bu' ending": "Godan-bu",
    "Godan verb with 'mu' ending": "Godan-mu",
    "Godan verb with 'nu' ending": "Godan-nu",
    "Godan verb - Iku/Yuku special class": "Godan-iku",
    "Godan verb - -aru special class": "Godan-aru",
    # Ichidan verbs
    "Ichidan verb": "Ichidan",
    "Ichidan verb - kureru special class": "Ichidan-kureru",
    "Ichidan verb - zuru verb (alternative form of -jiru verbs)": "Ichidan-zuru",
    # Special verbs
    "Kuru verb - special class": "Kuru",
    "Suru verb - included": "Suru",
    "Suru verb - special class": "Suru(sp)",
    "su verb - precursor to the modern suru": "Su",
    "auxiliary verb": "Aux.verb",
    "auxiliary adjective": "Aux.adj",
    "auxiliary": "Aux",
    "intransitive verb": "vi",
    "transitive verb": "vt",
    "irregular nu verb": "v-nu(irr)",
    "irregular ru verb, plain form ends with -ri": "v-ru(irr)",
    # Archaic verbs (keep short)
    "Nidan verb (upper class) with 'bu' ending (archaic)": "Nidan-u-bu",
    "Nidan verb (upper class) with 'gu' ending (archaic)": "Nidan-u-gu",
    "Nidan verb (upper class) with 'hu/fu' ending (archaic)": "Nidan-u-fu",
    "Nidan verb (upper class) with 'ku' ending (archaic)": "Nidan-u-ku",
    "Nidan verb (upper class) with 'ru' ending (archaic)": "Nidan-u-ru",
    "Nidan verb (upper class) with 'tsu' ending (archaic)": "Nidan-u-tsu",
    "Nidan verb (upper class) with 'yu' ending (archaic)": "Nidan-u-yu",
    "Nidan verb (lower class) with 'dzu' ending (archaic)": "Nidan-l-dzu",
    "Nidan verb (lower class) with 'gu' ending (archaic)": "Nidan-l-gu",
    "Nidan verb (lower class) with 'hu/fu' ending (archaic)": "Nidan-l-fu",
    "Nidan verb (lower class) with 'ku' ending (archaic)": "Nidan-l-ku",
    "Nidan verb (lower class) with 'mu' ending (archaic)": "Nidan-l-mu",
    "Nidan verb (lower class) with 'nu' ending (archaic)": "Nidan-l-nu",
    "Nidan verb (lower class) with 'ru' ending (archaic)": "Nidan-l-ru",
    "Nidan verb (lower class) with 'su' ending (archaic)": "Nidan-l-su",
    "Nidan verb (lower class) with 'tsu' ending (archaic)": "Nidan-l-tsu",
    "Nidan verb (lower class) with 'u' ending and 'we' conjugation (archaic)": "Nidan-l-we",
    "Nidan verb (lower class) with 'yu' ending (archaic)": "Nidan-l-yu",
    "Nidan verb (lower class) with 'zu' ending (archaic)": "Nidan-l-zu",
    "Nidan verb with 'u' ending (archaic)": "Nidan-u",
    "Yodan verb with 'bu' ending (archaic)": "Yodan-bu",
    "Yodan verb with 'gu' ending (archaic)": "Yodan-gu",
    "Yodan verb with 'hu/fu' ending (archaic)": "Yodan-fu",
    "Yodan verb with 'ku' ending (archaic)": "Yodan-ku",
    "Yodan verb with 'mu' ending (archaic)": "Yodan-mu",
    "Yodan verb with 'ru' ending (archaic)": "Yodan-ru",
    "Yodan verb with 'su' ending (archaic)": "Yodan-su",
    "Yodan verb with 'tsu' ending (archaic)": "Yodan-tsu",
    # Adjectives
    "adjective (keiyoushi)": "I-adj",
    "adjective (keiyoushi) - yoi/ii class": "I-adj(yoi)",
    "adjectival nouns or quasi-adjectives (keiyodoshi)": "Na-adj",
    "archaic/formal form of na-adjective": "Na-adj(arch)",
    "pre-noun adjectival (rentaishi)": "Pre-noun adj",
    "noun or verb acting prenominally": "Pre-noun",
    "'taru' adjective": "Taru-adj",
    "'ku' adjective (archaic)": "Ku-adj",
    "'shiku' adjective (archaic)": "Shiku-adj",
    # Nouns
    "noun (common) (futsuumeishi)": "Noun",
    "noun or participle which takes the aux. verb suru": "Noun (suru)",
    "nouns which may take the genitive case particle 'no'": "Noun (no)",
    "noun, used as a prefix": "Noun (prefix)",
    "noun, used as a suffix": "Noun (suffix)",
    # Adverbs
    "adverb (fukushi)": "Adverb",
    "adverb taking the 'to' particle": "Adverb (to)",
    # Other
    "expressions (phrases, clauses, etc.)": "Expression",
    "interjection (kandoushi)": "Interjection",
    "conjunction": "Conjunction",
    "particle": "Particle",
    "pronoun": "Pronoun",
    "prefix": "Prefix",
    "suffix": "Suffix",
    "counter": "Counter",
    "numeric": "Numeric",
    "copula": "Copula",
    "unclassified": "Uncl",
}
def _format_excerpt(senses):
    lines = []
    for s in senses[:3]:
        glosses = ', '.join(s.get('glosses', []))
        pos     = shorten_pos(s.get('pos', []))
        lines.append(f"[{pos}] {glosses}" if pos else glosses)
    return "<br>".join(lines)
def search_jmdict(word, result):
    _conn_dict_ready.wait()
    try:
        c = _conn_dict.cursor()

        # --- Exact match ---
        row = c.execute(
            "SELECT kanji, reading, senses FROM entries WHERE kanji = ? LIMIT 1",
            (word,)
        ).fetchone()
        if not row:
            row = c.execute(
                "SELECT kanji, reading, senses FROM entries WHERE reading = ? LIMIT 1",
                (word,)
            ).fetchone()
        if row:
            result["spell"]   = row["kanji"] if row["kanji"] else row["reading"]
            result["pron"]    = row["reading"]
            result["excerpt"] = _format_excerpt(json.loads(row["senses"]))

        # --- Fuzzy: prefix match, skip exact, take 3 ---
        fuzzy_rows = c.execute(
            "SELECT kanji, reading, senses FROM entries WHERE kanji LIKE ? AND kanji != ? LIMIT 3",
            (f"{word}%", word)
        ).fetchall()
        if not fuzzy_rows:
            fuzzy_rows = c.execute(
                "SELECT kanji, reading, senses FROM entries WHERE reading LIKE ? AND reading != ? LIMIT 3",
                (f"{word}%", word)
            ).fetchall()

        fuzzy_blocks = []
        for r in fuzzy_rows:
            header  = f"{r['kanji']} | {r['reading']}" if r['reading'] else r['kanji']
            excerpt = _format_excerpt(json.loads(r['senses']))
            fuzzy_blocks.append(f"{header}<br>{excerpt}")

        result["fuzzy"] = "<br><br>".join(fuzzy_blocks)

    except Exception as e:
        print(f"jmdict search fail: {e}")

    return result
def shorten_pos(parts_of_speech):
    shortened = [POS_MAP.get(p, p) for p in parts_of_speech]
    return ", ".join(shortened)
def search_jisho(word, result):
    try:
        url = f"https://jisho.org/api/v1/search/words?keyword={word}"
        res = session.get(url, timeout=6).json()
        data = res.get("data", [])
        if not data:
            return result

        # excerpt: first entry, up to 3 senses
        entry = data[0]
        japanese = entry.get("japanese", [{}])
        senses = entry.get("senses", [])

        result["spell"] = japanese[0].get("word", word)
        result["pron"] = japanese[0].get("reading", "")

        excerpt_lines = []
        for s in senses[:3]:
            defs = ", ".join(s.get("english_definitions", []))
            pos = shorten_pos(s.get("parts_of_speech", []))
            excerpt_lines.append(f"[{pos}] {defs}" if pos else defs)
        result["excerpt"] = "<br>".join(excerpt_lines)

        # fuzzy: data[1:4], each entry formatted as spell | reading \n [pos] defs
        fuzzy_blocks = []
        for entry in data[1:4]:
            japanese = entry.get("japanese", [{}])
            senses = entry.get("senses", [])
            spell = japanese[0].get("word", "")
            reading = japanese[0].get("reading", "")
            header = f"{spell} | {reading}" if spell else reading
            if senses:
                defs = ", ".join(senses[0].get("english_definitions", []))
                pos = shorten_pos(senses[0].get("parts_of_speech", []))
                body = f"[{pos}] {defs}" if pos else defs
            else:
                body = ""
            fuzzy_blocks.append(f"{header}<br>{body}")
        result["fuzzy"] = "<br><br>".join(fuzzy_blocks)

    except Exception as e:
        print(f"jisho search fail: {e}")
    return result
def search_moji_api(word,result):
    global last_moji_search_time
    last_moji_search_time = time.time()
    done_event_fuzzy = threading.Event()
    done_event_exact = threading.Event()
    for _ in range(3):
        threading.Thread(target=search_mojidict_fuzzy, args=(word,result,done_event_fuzzy), daemon = True).start()
        threading.Thread(target=search_mojidict_exact, args=(word,result,done_event_exact), daemon = True).start()
    done_event_fuzzy.wait(timeout=6)
    done_event_exact.wait(timeout=6)
    return result
def search_mojidict_fuzzy(word,result,done_event_fuzzy):
    t = time.time()
    try:
        data = {
        "functions": [
                    {
                        "name": "search-all",
                        "params": {
                            "text": word,
                            "types": [
                                102,
                                106,
                                103,
                            ],
                        },
                    },
                ],
        "_ClientVersion": "js3.4.1",
        "_ApplicationId": "E62VyFVLMiW7kvbtVq3p",
        "g_os": "PCWeb",
        "g_ver": "v4.8.8.20240829",
        "_InstallationId": dummy_uuid,
        }

        response = session.post(
        "https://api.mojidict.com/parse/functions/union-api",
        json=data,
        timeout=5
        )

        fuzzy_result = ''
        response_json = response.json()["result"]["results"]["search-all"]["result"]["word"]["searchResult"]
        k = min(len(response_json), 3)  # only take top 3 results
        for i in range(k):
            fuzzy_result += response_json[i].get("title", "") or ''
            fuzzy_result += "<br>"
            fuzzy_result += response_json[i].get("excerpt", "") or ''
            fuzzy_result += "<br><br>"

        result["fuzzy"] = fuzzy_result.strip().removesuffix("<br><br>")
        print('fuzzy ' + str(time.time()-t))
    except Exception as e:
        print("moji fuzzy fail")
    done_event_fuzzy.set()
def search_mojidict_exact(word,result,done_event_exact):
    t = time.time()
    try:
        data = {
            "searchText": word,
            "langEnv": "zh-CN_ja",
            "_ClientVersion": "js3.4.1",
            "_ApplicationId": "E62VyFVLMiW7kvbtVq3p",
            "g_os": "PCWeb",
            "g_ver": "v4.8.8.20240829",
            "_InstallationId": dummy_uuid,
        }
    
        response = session.post(
            "https://api.mojidict.com/parse/functions/word-clickSearchV2",
            json=data,
            timeout=5
        )
        response_json = response.json()["result"]["result"]
        
        word_info = response_json["word"][0]
        result["spell"] = word_info.get("spell","") or ''
        result["pron"] = word_info.get("pron","")  or ''
        result["accent"] = word_info.get("accent","")  or ''
        result["romaji"] = word_info.get("romaji","")  or ''
        result["excerpt"] = word_info.get("excerpt","")  or ''
        print('exact ' + str(time.time()-t))
    except Exception as e:
        print("moji exact fail")
    done_event_exact.set()
class DraggableTitleBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._drag_pos = None
        self.setAttribute(Qt.WA_StyledBackground, True)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - window.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self._drag_pos is not None:
            window.move(event.globalPos() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
SRC_LANGS = ["日本語","中文", "English"]
DST_LANGS = ["日本語","中文", "English"]        
def set_qt_layout():
    window.anki_id = None

    mon = snip.sct.monitors[config['monitor_index']]
    screen_h = mon['height']
    font_size_large = max(20, int(screen_h * 0.015))
    font_size_small = max(10, int(screen_h * 0.006))
    font_size_title = max(11, int(screen_h * 0.006))
    font_size_btn = max(16, int(screen_h * 0.009))
    bar_height = max(32, int(screen_h * 0.029))

    # test also need warm up
    central = QWidget()
    window.setCentralWidget(central)
    window.setWindowTitle('ACard')

    layout = QVBoxLayout(central)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    layout.setAlignment(Qt.AlignTop)
    
    title_widget = DraggableTitleBar(central)
    title_widget.setStyleSheet("background-color: #2b2b2b;")
    layout.addWidget(title_widget) 

    title_margin = max(8, int(screen_h * 0.009))
    title_bar = QHBoxLayout(title_widget)
    title_bar.setContentsMargins(title_margin, 0, 0, 0)
    title_bar.setSpacing(0)

    window.label_title = QLabel("ACard", title_widget)
    window.label_title.setFont(QFont("Microsoft YaHei", font_size_title))
    window.label_title.setStyleSheet("color: #ffffff;")
    title_bar.addWidget(window.label_title)
    title_bar.addStretch()
    
    btn_style = "QToolButton { border: none; color: white; } QToolButton:hover { background-color: #444; } QToolButton:checked { background-color: #666; }"
    close_style = "QToolButton { border: none; color: white; } QToolButton:hover { background-color: #e81123; }"

    window.history_btn = QToolButton(title_widget)
    window.history_btn.setText('🕘')
    window.history_btn.setFont(QFont('Segoe UI Symbol', font_size_btn))
    window.history_btn.setPopupMode(QToolButton.InstantPopup)
    window.history_btn.setStyleSheet(btn_style)
    window.history_menu = QMenu(window)
    window.history_menu.setFont(QFont('Segoe UI Symbol', font_size_btn))
    window.history_menu.aboutToShow.connect(refresh_history_menu)
    window.history_btn.setMenu(window.history_menu)
    title_bar.addWidget(window.history_btn)
    
    window.settings_btn = QToolButton(title_widget)
    window.settings_btn.setText('⚙')
    window.settings_btn.setFont(QFont('Segoe UI Symbol', font_size_btn))
    window.settings_btn.setStyleSheet(btn_style)
    window.settings_btn.clicked.connect(toggle_settings)
    window.settings_btn.setCheckable(True)
    title_bar.addWidget(window.settings_btn)

    window.close_btn = QToolButton(title_widget)
    window.close_btn.setText('✕')
    window.close_btn.setFont(QFont('Segoe UI Symbol', font_size_btn))
    window.close_btn.clicked.connect(window.close)
    window.close_btn.setStyleSheet(close_style)
    title_bar.addWidget(window.close_btn)

    window.stack = QStackedWidget(central)
    layout.addWidget(window.stack)

    main_page = QWidget()
    window.stack.addWidget(main_page)

    main_layout = QVBoxLayout(main_page)
    main_layout.setContentsMargins(10, 0, 10, 0)
    main_layout.setSpacing(0)

    row = QHBoxLayout()
    main_layout.addLayout(row)

    window.word = QLineEdit(central)
    window.word.setFont(QFont('Segoe UI Symbol', font_size_btn))
    window.word.setContextMenuPolicy(Qt.CustomContextMenu)
    window.word.customContextMenuRequested.connect(lambda pos: show_custom_context_menu(window.word, pos, font_size_small))
    row.addWidget(window.word)

    window.search_btn = QToolButton(window)
    window.search_btn.setText('📝')
    window.search_btn.setFont(QFont('Segoe UI Symbol', font_size_btn))
    window.search_btn.clicked.connect(refresh_word)
    window.word.returnPressed.connect(window.search_btn.animateClick)
    row.addWidget(window.search_btn)

    window.delete_btn = QToolButton(window)
    window.delete_btn.setText('✖')
    window.delete_btn.setFont(QFont('Segoe UI Symbol', font_size_btn))
    window.delete_btn.clicked.connect(anki_delete_note)
    window.delete_btn.setCheckable(True)
    row.addWidget(window.delete_btn)

    window.label_spell = QLabel("", central)
    window.label_spell.setAlignment(Qt.AlignHCenter)
    window.label_spell.setTextInteractionFlags(Qt.TextSelectableByMouse)
    window.label_spell.setStyleSheet("QLabel {selection-background-color: #3399ff;selection-color: white;}")
    font = QFont("Microsoft YaHei", font_size_large)
    font.setBold(True)
    window.label_spell.setFont(font)
    main_layout.addWidget(window.label_spell)

    window.label_pron = QLabel("", central)
    window.label_pron.setAlignment(Qt.AlignHCenter)
    window.label_pron.setTextInteractionFlags(Qt.TextSelectableByMouse)
    window.label_pron.setStyleSheet("QLabel {selection-background-color: #3399ff;selection-color: white;}")
    font = QFont("Microsoft YaHei", font_size_small)
    font.setBold(False)
    window.label_pron.setFont(font)
    main_layout.addWidget(window.label_pron)

    window.label_excerpt = QLabel("", central)
    window.label_excerpt.setAlignment(Qt.AlignLeft | Qt.AlignTop)
    window.label_excerpt.setTextInteractionFlags(Qt.TextSelectableByMouse)
    window.label_excerpt.setStyleSheet("QLabel {selection-background-color: #3399ff;selection-color: white;}")
    window.label_excerpt.setWordWrap(True)
    font = QFont("Microsoft YaHei", font_size_small)
    font.setBold(False)
    window.label_excerpt.setFont(font)
    main_layout.addWidget(window.label_excerpt)

    for label in [window.label_spell, window.label_pron, window.label_excerpt]:
        label.setContextMenuPolicy(Qt.CustomContextMenu)
        label.customContextMenuRequested.connect(
            lambda pos, w=label: show_copy_context_menu(w, pos, font_size_small)
        )

    window.label_screenshot = QLabel("", central)
    main_layout.addWidget(window.label_screenshot)

    settings_page = QWidget()
    window.stack.addWidget(settings_page)

    font_size_settings = max(10, int(screen_h * 0.006))
    font_settings = QFont("Microsoft YaHei", font_size_settings)

    settings_layout = QVBoxLayout(settings_page)

    settings_layout.setContentsMargins(10, 0, 10, 0)
    settings_layout.setAlignment(Qt.AlignTop)

    lang_row = QHBoxLayout()

    lang_label = QLabel(ui('dict'))
    lang_row.addWidget(lang_label)
    lang_label.setFont(font_settings)

    window.src_lang = QComboBox()
    window.src_lang.addItems(SRC_LANGS)
    window.src_lang.setCurrentIndex(SRC_LANGS.index(config.get('src_lang', SRC_LANGS[0])))
    lang_row.addWidget(window.src_lang)
    window.src_lang.setFont(font_settings)
    window.src_lang.currentIndexChanged.connect(on_src_lang_changed)

    arrow = QLabel("→")
    arrow.setAlignment(Qt.AlignCenter)
    lang_row.addWidget(arrow)
    arrow.setFont(font_settings)
    
    window.dst_lang = QComboBox()
    window.dst_lang.addItems(DST_LANGS)
    window.dst_lang.setCurrentIndex(DST_LANGS.index(config.get('dst_lang', DST_LANGS[0])))
    lang_row.addWidget(window.dst_lang)
    window.dst_lang.setFont(font_settings)
    window.dst_lang.currentIndexChanged.connect(on_dst_lang_changed)

    settings_layout.addLayout(lang_row)

    window.screen_combo = QComboBox()
    window.screen_combo.setFont(font_settings)
    for i, mon in enumerate(snip.sct.monitors[1:], 1):  # skip monitors[0] (virtual desktop)
        window.screen_combo.addItem(f"{ui('monitor')} {i}  {mon['width']}x{mon['height']}")
    window.screen_combo.setCurrentIndex(config['monitor_index'] - 1)  # monitors[1] = index 0 in combo
    screen_row = QHBoxLayout()
    screen_label = QLabel(ui('monitor'))
    screen_label.setFont(font_settings)
    screen_row.addWidget(screen_label)
    screen_row.addWidget(window.screen_combo)
    settings_layout.addLayout(screen_row)    
    window.screen_combo.currentIndexChanged.connect(check_screen_change)

    window.hotkey_captured_signal.connect(on_hotkey_captured)
    hotkey_row = QHBoxLayout()
    hotkey_label = QLabel(ui('hotkey'))
    hotkey_label.setFont(font_settings)
    window.hotkey_btn = QPushButton(hotkey_to_str(config['hotkey']))
    window.hotkey_btn.setFont(font_settings)
    window.hotkey_btn.clicked.connect(start_hotkey_capture)
    btn_style = "QToolButton { border: none; border-top: 2px solid transparent; color: white; padding-top: 2px; } QToolButton:hover { border-top: 2px solid #888; } QToolButton:checked { border-top: 2px solid white; }"
    window.hotkey_btn.setCheckable(True)
    hotkey_row.addWidget(hotkey_label)
    hotkey_row.addWidget(window.hotkey_btn)
    settings_layout.addLayout(hotkey_row)
def on_src_lang_changed(index):
    new_lang = SRC_LANGS[index]
    if new_lang != config.get('src_lang', SRC_LANGS[0]):
        update_config('src_lang', new_lang)
        start_dict()
def on_dst_lang_changed(index):
    new_lang = DST_LANGS[index]
    if new_lang != config.get('dst_lang', DST_LANGS[0]):
        update_config('dst_lang', new_lang)
        start_dict()
NUMPAD_VK = {
    96: 'Num0', 97: 'Num1', 98: 'Num2', 99: 'Num3', 100: 'Num4',
    101: 'Num5', 102: 'Num6', 103: 'Num7', 104: 'Num8', 105: 'Num9',
    110: 'Num.', 111: 'Num/', 106: 'Num*', 109: 'Num-', 107: 'Num+',
}
def hotkey_to_str(hk_list):
    hk = hk_list[0] if hk_list else {}
    if hk['type'] == 'mouse':
        return f"Mouse {hk['button'].capitalize()}"
    else:
        mods = '+'.join(m.capitalize() for m in hk.get('modifiers', []))
        raw_key = hk.get('key', '')
        # Convert for display
        if raw_key.startswith('Key.'):
            display_key = raw_key.replace('Key.', '').capitalize()
        elif raw_key.isdigit():
            vk = int(raw_key)
            display_key = NUMPAD_VK.get(vk, f'VK{vk}')
        else:
            display_key = raw_key.upper() if len(raw_key) == 1 else raw_key.capitalize()
        return f"{mods}+{display_key}" if mods else display_key
def str_to_key(key_str):
    if key_str.startswith('Key.'):
        return keyboard.Key[key_str.replace('Key.', '')]
    elif key_str.isdigit():
        return keyboard.KeyCode(vk=int(key_str))
    else:
        return keyboard.KeyCode.from_char(key_str)
def start_hotkey_capture():
    global hotkey_mode
    hotkey_mode = 0
    window.hotkey_btn.setChecked(True)
    window.centralWidget().setFocus()
    window.hotkey_btn.setText('...')
def on_hotkey_captured():
    global hotkey_mode
    hotkey_mode = 1
    window.hotkey_btn.setChecked(False)
    window.hotkey_btn.setText(hotkey_to_str(config['hotkey']))
def show_custom_context_menu(widget, pos, font_size):
    menu = QMenu(widget)
    menu.setFont(QFont("Microsoft YaHei", font_size))
    menu.setStyleSheet("QMenu::item:selected { background-color: #444; color: white; }")
    
    cut = menu.addAction(ui('cut'))
    copy = menu.addAction(ui('copy'))
    paste = menu.addAction(ui('paste'))
    
    cut.triggered.connect(widget.cut)
    copy.triggered.connect(widget.copy)
    paste.triggered.connect(widget.paste)
    
    cut.setEnabled(widget.hasSelectedText())
    copy.setEnabled(widget.hasSelectedText())
    
    menu.exec_(widget.mapToGlobal(pos))
def show_copy_context_menu(widget, pos, font_size):
    selected = widget.selectedText()
    if not selected:
        return
    menu = QMenu(widget)
    menu.setFont(QFont("Microsoft YaHei", font_size))
    menu.setStyleSheet("QMenu::item:selected { background-color: #444; color: white; }")
    copy = menu.addAction(ui('copy'))
    copy.triggered.connect(lambda: QApplication.clipboard().setText(selected))
    menu.exec_(widget.mapToGlobal(pos))
def check_screen_change(index):
    new_monitor_index = index + 1  # convert to mss index
    if new_monitor_index == config['monitor_index']:
        return  # same monitor, do nothing
    else:
        update_config('monitor_index', new_monitor_index)
        threading.Thread(target=_do_screen_change, daemon=True).start()
def _do_screen_change():
    global screenshot, screenshot_thread_handle
    hotkey_mode = -1
    screenshot_thread_stop.set()
    
    snip.close()
    bridge.click_snip.disconnect()

    screenshot_thread_handle.join()

    screenshot = []
    screenshot_thread_stop.clear()
    screenshot_thread_handle = threading.Thread(target=screenshot_thread, daemon=True)
    screenshot_thread_handle.start()

    window.reinit_snip_signal.emit()
def _reinit_snip_main_thread():
    global snip, hotkey_mode
    snip = Snip()
    time.sleep(0.5)  # test if click too fast after change monitor, error will happen in paintEvent. need better logic here
    hotkey_mode = 1
    bridge.click_snip.connect(snip.start)
    window.close_snip_signal.connect(snip.close_snip)
    window.cancel_drag_signal.connect(snip.cancel_drag)
def toggle_settings():
    if window.stack.currentIndex() == 0:
        toggle_to_setting()
    else:
        toggle_to_main()
def toggle_to_main():
        if window.stack.currentIndex() != 0:
            window.stack.setCurrentIndex(0)
            window.settings_btn.setChecked(False)
def toggle_to_setting():
    window.stack.setCurrentIndex(1)
    window.settings_btn.setChecked(True)
def check_processing():
    for i in range(100):
        if processing:
            QApplication.processEvents()
            time.sleep(0.05)
        else:
            break
    else:
        print('time out in waiting for processing')  # test need more detail
def pcm_to_wav_bytes(pcm_data, rate=44100, channels=2, bits=16):
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(bits // 8)
        wf.setframerate(rate)
        wf.writeframes(pcm_data)
    return buf.getvalue()
def normalize_audio(wav_bytes, rms, target_peak_rms=0, bits=16):
    peak_rms = np.max(rms)
    if peak_rms >= target_peak_rms:
        return wav_bytes
    gain = target_peak_rms / (peak_rms + 1e-6)
    dtype = np.int16 if bits == 16 else np.int32
    samples = np.frombuffer(wav_bytes, dtype=dtype).astype(np.float32)
    max_val = 2 ** (bits - 1)
    samples = np.clip(samples * gain, -max_val, max_val - 1)
    return samples.astype(dtype).tobytes()
def detect_audio(audio_bytes, frame_duration_ms):
    rate = recorder.RATE
    channels = recorder.CHANNELS

    dtype_map = {8: np.int8, 16: np.int16, 32: np.int32}
    pcm_np = np.frombuffer(audio_bytes, dtype=dtype_map[recorder.BITS])
    
    sample_per_frame = int(rate * frame_duration_ms / 1000)
    n_frame = len(pcm_np) // (sample_per_frame * channels)

    frame = pcm_np[:n_frame * sample_per_frame * channels].reshape(n_frame,sample_per_frame,channels) 
    frame = frame.astype(np.float32)
    max_val = 2 ** (recorder.BITS - 1)
    rms = np.sqrt(
        np.einsum('ijk,ijk->i', frame, frame)
        / (frame.shape[1] * frame.shape[2])
    ) / max_val

    segment = 150
    cumsum = np.cumsum(np.pad(rms, segment//2, mode='edge'))
    rms_moving_average = (cumsum[segment:] - cumsum[:-segment]) / segment

    return rms, rms_moving_average
def analyze_audio(audio_bytes,audio_start_time,rms,rms_moving_average,frame_duration_ms,snip_index_in_sentences,subtitle_sentences):
    subtitle_start_time = 0
    subtitle_end_time = 0

    # get start and end from subtitle
    subtitle_diff_min = 0.07
    subtitle_diff_ideal = 0.13
    subtitle_start_quality = 0
    for i in range(snip_index_in_sentences,-1,-1):
        if subtitle_sentences[i][0] < subtitle_diff_min or subtitle_sentences[i][2]:
            subtitle_start_time = subtitle_sentences[i][1]
        else:
            subtitle_start_quality = min((subtitle_sentences[i][0]-subtitle_diff_min) / (subtitle_diff_ideal-subtitle_diff_min), 1)
            break
    subtitle_end_quality = 0
    for i in range(snip_index_in_sentences,len(subtitle_sentences)):
        if subtitle_sentences[i][0] < subtitle_diff_min or subtitle_sentences[i][2]:
            subtitle_end_time = subtitle_sentences[i][1]
        else:
            subtitle_end_quality = min((subtitle_sentences[i][0]-subtitle_diff_min) / (subtitle_diff_ideal-subtitle_diff_min), 1)
            break

    # change to frame
    length_rms = len(rms)
    subtitle_start_frame = time_to_audio_frame(audio_start_time,frame_duration_ms,length_rms,subtitle_start_time)
    subtitle_end_frame = time_to_audio_frame(audio_start_time,frame_duration_ms,length_rms,subtitle_end_time)

    # shift start and end to middle to find first letter
    one_letter_audio_ms = 150
    letter_audio_frame_target = one_letter_audio_ms // frame_duration_ms
    letter_audio_frame_now = 0
    for i in range(subtitle_start_frame,len(rms)):
        if rms[i] > 0.007:
            letter_audio_frame_now +=1
        else:
            letter_audio_frame_now -= 2
            letter_audio_frame_now = max(letter_audio_frame_now,0)
        if letter_audio_frame_now >= letter_audio_frame_target:
            subtitle_start_frame_to_right = i
            break
    else:
        subtitle_start_frame_to_right = subtitle_start_frame
    letter_audio_frame_now = 0
    for i in range(subtitle_end_frame,-1,-1):
        if rms[i] > 0.007:
            letter_audio_frame_now +=1
        else:
            letter_audio_frame_now -= 2
            letter_audio_frame_now = max(letter_audio_frame_now,0)
        if letter_audio_frame_now >= letter_audio_frame_target:
            subtitle_end_frame_to_left = i
            break
    else:
        subtitle_end_frame_to_left = subtitle_end_frame

    # shift start and end to side to find blank
    blank_audio_ms_start = 200 - subtitle_start_quality * 100
    blank_frame_target_start = blank_audio_ms_start // frame_duration_ms
    blank_frame_now = 0
    for i in range(subtitle_start_frame_to_right,-1,-1):
        if rms[i] < 0.01 or rms[i] < rms_moving_average[i]:
            blank_frame_now += 1
        else:
            blank_frame_now -= 2
            blank_frame_now = max(blank_frame_now,0)
        if blank_frame_now >= blank_frame_target_start:
            subtitle_start_frame_to_right_to_left = i
            break
    else:
        subtitle_start_frame_to_right_to_left = 0
    blank_audio_ms_end = 300 - subtitle_end_quality * 100
    blank_frame_target_end = blank_audio_ms_end // frame_duration_ms
    blank_frame_now = 0
    for i in range(subtitle_end_frame_to_left,len(rms)):
        if rms[i] < 0.01 or rms[i] < rms_moving_average[i]:
            blank_frame_now += 1
        else:
            blank_frame_now -= 2
            blank_frame_now = max(blank_frame_now,0)
        if blank_frame_now >= blank_frame_target_end:
            subtitle_end_frame_to_left_to_right = i
            break
    else:
        subtitle_end_frame_to_left_to_right = len(rms) -1

    # test need delete
    print(subtitle_start_frame)
    print(subtitle_end_frame)
    print(subtitle_start_frame_to_right)
    print(subtitle_end_frame_to_left)
    print(subtitle_start_frame_to_right_to_left)
    print(subtitle_end_frame_to_left_to_right)

    play_start_bytes = int(subtitle_start_frame_to_right_to_left * frame_duration_ms * recorder.BYTES_PER_SEC / 1000)
    play_end_bytes =  int(subtitle_end_frame_to_left_to_right * frame_duration_ms * recorder.BYTES_PER_SEC / 1000)

    play_start_bytes = snap_to_min_energy(audio_bytes, play_start_bytes,recorder.BYTES_PER_SAMPLE, recorder.BYTES_PER_SEC,-200)
    play_end_bytes = snap_to_min_energy(audio_bytes, play_end_bytes,recorder.BYTES_PER_SAMPLE, recorder.BYTES_PER_SEC,400)

    # trim a bigger range compared to play time
    min_gap_ms = 80
    min_gap_frame = int(min_gap_ms / frame_duration_ms)
    min_gap_frame_left = min_gap_frame

    trim_start_frame = -1
    trim_time_target_before_play_start = 3.5
    trim_start_frame_left = int(trim_time_target_before_play_start * 1000 / frame_duration_ms)
    for i in range(subtitle_start_frame_to_right_to_left,-1,-1):
        if rms[i] > 0.015:
            min_gap_frame_left = min_gap_frame
        else:
            min_gap_frame_left -= 1
        if min_gap_frame_left < 0:
            trim_start_frame_left -= 1
        if trim_start_frame_left <= 0:
            trim_start_frame = i
            break

    trim_end_frame = -1
    trim_time_target_after_play_end = 3
    trim_end_frame_left = int(trim_time_target_after_play_end * 1000 / frame_duration_ms)
    for i in range(subtitle_end_frame_to_left_to_right,len(rms)):
        if rms[i] > 0.015:
            min_gap_frame_left = min_gap_frame
        else:
            min_gap_frame_left -= 1
        if min_gap_frame_left < 0:
            trim_end_frame_left -= 1
        if trim_end_frame_left <= 0:
            trim_end_frame = i
            break

    if trim_start_frame == -1:
        trim_start_bytes = play_start_bytes
    else:
        trim_start_bytes = int(trim_start_frame * frame_duration_ms * recorder.BYTES_PER_SEC / 1000)
        trim_start_bytes = snap_to_min_energy(audio_bytes, trim_start_bytes,recorder.BYTES_PER_SAMPLE, recorder.BYTES_PER_SEC,-2000)

    if trim_end_frame == -1:
        trim_end_bytes = play_end_bytes
    else:
        trim_end_bytes = int(trim_end_frame * frame_duration_ms * recorder.BYTES_PER_SEC / 1000)
        trim_end_bytes = snap_to_min_energy(audio_bytes, trim_end_bytes,recorder.BYTES_PER_SAMPLE, recorder.BYTES_PER_SEC,1000)
    
    if trim_start_bytes == trim_end_bytes:
        trim_start_bytes = 0
        trim_end_bytes = len(audio_bytes) - 1

    play_start_bytes -= trim_start_bytes
    play_end_bytes -= trim_start_bytes

    play_start_time =  play_start_bytes / recorder.BYTES_PER_SEC
    play_end_time = play_end_bytes / recorder.BYTES_PER_SEC

    return audio_bytes[trim_start_bytes:trim_end_bytes], play_start_time, play_end_time
def snap_to_min_energy(audio_bytes, target_byte, bytes_per_sample,bytes_per_sec, search_ms, window_ms=10):
    aligned_target = target_byte - target_byte % bytes_per_sample
    if search_ms == 0:
        return aligned_target

    # Align all byte offsets to sample boundaries.
    search_bytes = int(abs(search_ms) * bytes_per_sec / 1000)
    search_bytes -= search_bytes % bytes_per_sample
    window_bytes = int(window_ms * bytes_per_sec / 1000)
    window_bytes -= window_bytes % bytes_per_sample
    half_window_bytes = window_bytes // 2
    half_window_bytes -= half_window_bytes % bytes_per_sample

    # Signed search span: positive = rightward from target, negative = leftward.
    if search_ms > 0:
        search_lo_byte = aligned_target
        search_hi_byte = aligned_target + search_bytes
    else:
        search_lo_byte = aligned_target - search_bytes
        search_hi_byte = aligned_target

    # Read a region large enough for every candidate's full window.
    region_lo = max(0, search_lo_byte - half_window_bytes)
    region_hi = min(len(audio_bytes), search_hi_byte + half_window_bytes)
    region_lo -= region_lo % bytes_per_sample
    region_hi -= region_hi % bytes_per_sample
    if region_hi - region_lo < window_bytes + bytes_per_sample:
        return aligned_target

    samples = np.frombuffer(audio_bytes[region_lo:region_hi], dtype=np.int16).astype(np.int64)

    # Cumulative sum of squares -> any window's energy in O(1).
    # int64 is required: int16^2 accumulated over the region can overflow int32.
    cumsum_sq = np.concatenate(([0], np.cumsum(samples * samples)))

    half_n = half_window_bytes // bytes_per_sample

    # Candidate sample range, clamped so the window never goes out of bounds.
    cand_lo = max(half_n, (search_lo_byte - region_lo) // bytes_per_sample)
    cand_hi = min(len(samples) - half_n, (search_hi_byte - region_lo) // bytes_per_sample + 1)
    if cand_hi <= cand_lo:
        return aligned_target

    # Vectorized energy for every candidate at once.
    energies = (cumsum_sq[cand_lo + half_n : cand_hi + half_n]
                - cumsum_sq[cand_lo - half_n : cand_hi - half_n])
    best_idx = cand_lo + int(np.argmin(energies))

    return region_lo + best_idx * bytes_per_sample
def time_to_audio_frame(audio_start_time,frame_duration_ms,length_rms,target_time):
    i = int((target_time - audio_start_time) * 1000 // frame_duration_ms)
    i = min(max(i,0),length_rms-1)
    return i
def wav_to_mp3(wav_bytes, kbps=64):
    result = []
    def cb(ptr, size):
        result.append(ptr[:size])
    _bass_code_cast(_bass_code_cast_CB(cb), wav_bytes, len(wav_bytes), b'mp3', kbps, 0)
    return b''.join(result)
def anki_create_deck():
    if config['anki_deck_name'] not in invoke("deckNames"):
        invoke("createDeck", deck=config['anki_deck_name'])
def anki_create_model():
    ANKI_MODEL_VERSION = 1
    FRONT_TEMPLATE = """<div style="font-size: min(48px, 8vh)">{{spell}}</div>

<script>
// Purpose of this script: (1) stop ongoing audio from previous card (2) clean up memory from previous card (3) preload back side because it is heavy

function fadeStop(obj, ms) {
    if (!obj) return; 
    if (obj.gain) {
        var now = obj.ctx.currentTime;
        obj.gain.gain.cancelScheduledValues(now);
        obj.gain.gain.setValueAtTime(obj.gain.gain.value, now);

        // Equal-power S-curve: starts slow, fast in middle, slow at end
        var steps = 64;
        var curve = new Float32Array(steps);
        var startVol = obj.gain.gain.value;
        for (var i = 0; i < steps; i++) {
            var t = i / (steps - 1);
            // Cosine-based fade-out: smooth at both ends
            curve[i] = (startVol * (Math.cos(t * Math.PI) + 1)) / 2;
        }
        obj.gain.gain.setValueCurveAtTime(curve, now, ms / 1000);
        setTimeout(function () {
            try {
            obj.node.stop();
            } catch (e) {}
        }, ms);
    }
}
function computeWaveformBars(buffer, targetWidth) {
    var data = buffer.getChannelData(0);
    var step = Math.max(1, Math.floor(data.length / targetWidth));
    // First pass: peak amplitude
    var peak = 0;
    for (var i = 0; i < data.length; i++) {
        var v = Math.abs(data[i]);
        if (v > peak) peak = v;
    }
    if (peak === 0) peak = 1;
    // Second pass: per-bar min/max, normalized
    var bars = new Float32Array(targetWidth * 2);
    for (var x = 0; x < targetWidth; x++) {
        var mn = 1,
            mx = -1;
        var s = x * step;
        var e = Math.min(s + step, data.length);
        for (var j = s; j < e; j++) {
            var v2 = data[j];
            if (v2 < mn) mn = v2;
            if (v2 > mx) mx = v2;
        }
        bars[x * 2] = mn / peak;
        bars[x * 2 + 1] = mx / peak;
    }
    return bars;
}
// === Clear everything from previous card ===
(function clearPreviousCardState() {
    // 1. Fade out and stop previous audio
    var FADE_MS = 600;
    if (window.top._audio) {
        fadeStop(window.top._audio, FADE_MS);
        window.top._audio = null;
    }

    // 2. Remove leftover event listeners from previous card's back side
    if (window.top._apListeners) {
        for (var i = 0; i < window.top._apListeners.length; i++) {
            var item = window.top._apListeners[i];
            try {
            item.target.removeEventListener(item.type, item.fn, item.opts);
            } catch (e) {}
        }
        window.top._apListeners = null;
    }

    // 3. Clear stale global function from previous back side
    try {
        window.playRange = null;
    } catch (e) {}

    // 4. Clear ALL cache entries (audio buffers, waveform bars, bitmaps)
    if (window.top._apCache) {
        var keys = Object.keys(window.top._apCache);
        for (var i = 0; i < keys.length; i++) {
            var entry = window.top._apCache[keys[i]];
            if (entry && entry.bitmap && entry.bitmap.close) {
            try {
                entry.bitmap.close();
            } catch (e) {}
            }
            delete window.top._apCache[keys[i]];
        }
    }

    // 5. Close the previous card's playback AudioContext after fade-out completes
    if (window.top._apAudioCtx) {
        var ctxToClose = window.top._apAudioCtx;
        window.top._apAudioCtx = null;
        setTimeout(function () {
            try { ctxToClose.close(); } catch (e) {}
        }, FADE_MS + 100);   // Slightly longer than fade duration
    }
})();
setTimeout(function () {
    // Preload audio + waveform + play time + image bitmap for the back side
        var m = `{{audio}}`.match(/src="([^"]+)"/);
        var fname = m ? m[1] : "";
        if (!fname) return;
        if (!window.top._apCache) window.top._apCache = {};

        // Parse audio_range field
        var playTime = null;
        var rawPT = "{{audio_range}}".trim();
        if (rawPT) {
            var parts = rawPT.split(",");
            if (parts.length === 2) {
            var s = parseFloat(parts[0]);
            var e = parseFloat(parts[1]);
            if (isFinite(s) && isFinite(e) && s < e) playTime = [s, e];
            }
        }

        // Extract image src from rendered {{screenshot}} HTML
        function extractImgSrc(html) {
            var m = /<img[^>]+src="([^"]+)"/.exec(html);
            return m ? m[1] : null;
        }

        var screenshotHtml = `{{screenshot}}`;
        var imgSrc = extractImgSrc(screenshotHtml);
        var bitmapPromise = null;
        if (imgSrc && typeof createImageBitmap === "function") {
            bitmapPromise = fetch(imgSrc)
            .then(function (r) {
                return r.blob();
            })
            .then(function (blob) {
                return createImageBitmap(blob);
            });
        }

        var AudioCtx = window.AudioContext || window.webkitAudioContext;
        if (!AudioCtx) return;
        var ac = new AudioCtx();
        fetch(fname)
            .then(function (r) {
            return r.arrayBuffer();
            })
            .then(function (b) {
            return ac.decodeAudioData(b);
            })
            .then(function (decoded) {
            var bars = computeWaveformBars(decoded, 1200);
            var entry = {
                buffer: decoded,
                bars: bars,
                playTime: playTime,
                bitmap: null,
            };
            window.top._apCache[fname] = entry;
            ac.close();
            if (bitmapPromise) {
                bitmapPromise.then(function (bm) {
                    entry.bitmap = bm;
                });
            }
            })
            .catch(function () {
            try {
                ac.close();
            } catch (e) {}
            });
}, 0);
</script>
"""
    BACK_TEMPLATE = """<div style="font-size: min(48px, 8vh)">{{spell}}</div>

<div style="font-size: 20px">
<span id="pron">{{pron}}{{accent}}</span>
<span id="separator">|</span>
<span id="romaji">{{romaji}}</span>
</div>
<script>
if (
    document.getElementById("pron").innerHTML == "" ||
    document.getElementById("romaji").innerHTML == ""
) {
    document.getElementById("separator").innerHTML = "";
}
</script>

<div id="main-wrap"><div id="left-col">
<div
id="word-img-wrap"
style="position: relative; display: block; cursor: pointer"
onclick="playRange()"
>
<canvas
    id="word-img-canvas"
    style="display: block; width: 100%; height: auto"
></canvas>
<div id="word-img-fallback" style="display: none">{{screenshot}}</div>
<svg
    id="sv"
    style="position: absolute; top: 0; left: 0; pointer-events: none"
>
    <polygon id="pl" fill="none" stroke="red" stroke-width="1" />
</svg>
</div>
<script>
// Try to render screenshot from preloaded ImageBitmap; fall back to <img>
function renderScreenshot() {
    var canvas = document.getElementById('word-img-canvas');
    var fallback = document.getElementById('word-img-fallback');
    if (!canvas) return;

    // Get the audio filename to look up cache
    var m = `{{audio}}`.match(/src="([^"]+)"/);
    var fname = m ? m[1] : "";
    var cache = window.top._apCache && window.top._apCache[fname];
    var bitmap = cache && cache.bitmap;

    if (bitmap) {
    // Fast path: draw bitmap to canvas
    var dpr = window.devicePixelRatio || 1;
var displayWidth = window.innerWidth;
var displayHeight = displayWidth * bitmap.height / bitmap.width;
var maxH = window.innerHeight < window.innerWidth ? screen.width * 0.35 : screen.height * 0.5;
if (displayHeight > maxH) {
    displayHeight = maxH;
    displayWidth = maxH * bitmap.width / bitmap.height;
}

    canvas.style.width = displayWidth + 'px';
    canvas.style.height = displayHeight + 'px';
    var textWrap = document.getElementById('text-wrap');
    if (textWrap) textWrap.style.width = displayWidth + 'px';
    var apWrap = document.querySelector('.ap-wrap');
    if (apWrap) apWrap.style.width = displayWidth + 'px';
    canvas.width = bitmap.width;   // Use intrinsic size for crisp rendering
    canvas.height = bitmap.height;
    var ctx = canvas.getContext('2d');
    ctx.drawImage(bitmap, 0, 0);
    return true;
    }
    // Fallback: hide canvas, show original <img>
    canvas.style.display = 'none';
    fallback.style.display = 'block';
    // Sync width after fallback img loads
    var fbImg = fallback.querySelector('img');
    function syncFallbackWidth() {
        var apWrap = document.querySelector('.ap-wrap');
        if (!apWrap || !fbImg.naturalWidth) return;
        var dispW = fbImg.offsetWidth;
        apWrap.style.width = dispW + 'px';
    }
    if (fbImg) {
    fbImg.complete ? syncFallbackWidth() :fbImg.addEventListener('load', syncFallbackWidth);
    }
    return false;
}
function fadeStop(obj, ms) {
    if (!obj) return;
    if (obj.gain) {
    var now = obj.ctx.currentTime;
    obj.gain.gain.cancelScheduledValues(now);
    obj.gain.gain.setValueAtTime(obj.gain.gain.value, now);
    var steps = 64;
    var curve = new Float32Array(steps);
    var startVol = obj.gain.gain.value;
    for (var i = 0; i < steps; i++) {
        var t = i / (steps - 1);
        curve[i] = startVol * (Math.cos(t * Math.PI) + 1) / 2;
    }
    obj.gain.gain.setValueCurveAtTime(curve, now, ms / 1000);
    setTimeout(function () {
        try { obj.node.stop(); } catch (e) {}
    }, ms);
    }
}
function drawBox() {
    var wrap = document.getElementById('word-img-wrap');
    if (!wrap) return;
    // Use the visible element (canvas or fallback img) for measurements
    var canvas = document.getElementById('word-img-canvas');
    var fallbackImg = wrap.querySelector('#word-img-fallback img');
    var displayEl = (canvas && canvas.style.display !== 'none') ? canvas : fallbackImg;
    if (!displayEl) return;

    // Intrinsic dimensions
    var natW, natH;
    if (displayEl === canvas) {
    natW = canvas.width;
    natH = canvas.height;
    } else {
    natW = fallbackImg.naturalWidth;
    natH = fallbackImg.naturalHeight;
    if (!natW) return;  // Image not loaded yet
    }
    var dispW = displayEl.offsetWidth;
    var dispH = displayEl.offsetHeight;
    var rx = dispW / natW;
    var ry = dispH / natH;
    var sv = document.getElementById('sv');
    sv.style.width = dispW + 'px';
    sv.style.height = dispH + 'px';
    sv.style.left = displayEl.offsetLeft + 'px';
    sv.style.top = displayEl.offsetTop + 'px';
    document.getElementById('pl').setAttribute('points',
    [{{word_position}}].map(function(p) { return p[0]*rx + ',' + p[1]*ry; }).join(' '));
}
// Render screenshot first, then draw box
renderScreenshot();
drawBox();
// If fallback path: image may load later, wait for it
var fbImg = document.querySelector('#word-img-fallback img');
if (fbImg && !fbImg.complete) {
    fbImg.addEventListener('load', drawBox);
}
function updateLayout() {
    var isMobile = /iPhone|iPad|Android|HarmonyOS/i.test(navigator.userAgent);
    var isLandscape = window.innerWidth > window.innerHeight;
    document.body.classList.toggle('landscape', isMobile && isLandscape);
}
updateLayout();
var _resizeTimer = null;
window.addEventListener('resize', function() {
    if (_resizeTimer) clearTimeout(_resizeTimer);
    _resizeTimer = setTimeout(function() {
        updateLayout();
        renderScreenshot();
        drawBox();
    }, 150);
});
window.addEventListener('orientationchange', function() {
    setTimeout(function() {
        updateLayout();
        renderScreenshot();
        drawBox();
    }, 300);
});
</script>

<div class="ap-wrap">
<div class="ap-track" id="ap-track">
    <canvas id="ap-wave"></canvas>
    <div class="ap-range" id="ap-range"></div>
    <div class="ap-progress" id="ap-progress"></div>
    <div class="ap-handle ap-handle-start" id="ap-h-start" data-role="start">
        <div class="ap-handle-visual"></div>
    </div>
    <div class="ap-handle ap-handle-end" id="ap-h-end" data-role="end">
        <div class="ap-handle-visual"></div>
    </div>
</div>
</div>
</div>
<script>
(function () {
    var m = `{{audio}}`.match(/src="([^"]+)"/);
    const filename = m ? m[1] : "";
    if (!filename) {
        document.querySelector(".ap-wrap").innerHTML =
            '';
        return;
    }
    const track = document.getElementById("ap-track");
    const canvas = document.getElementById("ap-wave");
    const rangeEl = document.getElementById("ap-range");
    const progEl = document.getElementById("ap-progress");
    const hStart = document.getElementById("ap-h-start");
    const hEnd = document.getElementById("ap-h-end");
    // localStorage key based on filename (unique per audio clip)
    const STORAGE_KEY = "ap-range:" + filename;
    // Track listeners on window.top so the next front side can remove them
    if (!window.top._apListeners) window.top._apListeners = [];
    function addTracked(target, type, fn, opts) {
        target.addEventListener(type, fn, opts);
        window.top._apListeners.push({
            target: target,
            type: type,
            fn: fn,
            opts: opts,
        });
    }
    function loadRange() {
        try {
            const raw = localStorage.getItem(STORAGE_KEY);
            if (!raw) return null;
            const obj = JSON.parse(raw);
            if (typeof obj.start === "number" && typeof obj.end === "number") {
            return obj;
            }
            return null;
        } catch (e) {
            return null;
        }
    }
    function saveRange() {
        try {
            localStorage.setItem(
            STORAGE_KEY,
            JSON.stringify({
                start: startT,
                end: endT,
                updated: Date.now(),
            }),
            );
        } catch (e) {
            // Storage quota exceeded or disabled, ignore
        }
    }
    let duration = 0;
    let startT = 0;
    let endT = 0;
    let audioBuffer = null;
    let audioCtx = null;
    let currentSource = null;
    let webStart = 0; // audioCtx.currentTime when playback started
    let webOffset = 0; // playback offset (in audio time) when started
    let rafId = null;
    function updateUI() {
        if (!duration) return;
        const sp = (startT / duration) * 100;
        const ep = (endT / duration) * 100;
        rangeEl.style.left = sp + "%";
        rangeEl.style.width = ep - sp + "%";
        hStart.style.left = sp + "%";
        hEnd.style.left = ep + "%";
        const trackW = track.clientWidth;
        const gapPx = ((ep - sp) / 100) * trackW;
        const visualW = Math.max(0, Math.min(20, gapPx - 2));
        const startVis = hStart.querySelector(".ap-handle-visual");
        const endVis = hEnd.querySelector(".ap-handle-visual");
        if (startVis) startVis.style.width = visualW + "px";
        if (endVis) endVis.style.width = visualW + "px";
    }
    function updateProgressFromTime(t) {
        if (!duration) return;
        progEl.style.left = (t / duration) * 100 + "%";
    }
    function drawWaveform(buffer) {
        const dpr = window.devicePixelRatio || 1;
        const w = track.clientWidth;
        const h = track.clientHeight;
        canvas.width = w * dpr;
        canvas.height = h * dpr;
        const ctx = canvas.getContext("2d");
        ctx.scale(dpr, dpr);
        const data = buffer.getChannelData(0);
        const step = Math.max(1, Math.floor(data.length / w));
        const mid = h / 2;
        let peak = 0;
        for (let i = 0; i < data.length; i++) {
            const v = Math.abs(data[i]);
            if (v > peak) peak = v;
        }
        if (peak === 0) peak = 1;
        const scale = 0.9 / peak;
        ctx.fillStyle = "#9bb8e6";
        for (let x = 0; x < w; x++) {
            let mn = 1,
            mx = -1;
            const start = x * step;
            const end = Math.min(start + step, data.length);
            for (let i = start; i < end; i++) {
            const v = data[i];
            if (v < mn) mn = v;
            if (v > mx) mx = v;
            }
            const y1 = mid + mn * mid * scale;
            const y2 = mid + mx * mid * scale;
            ctx.fillRect(x, y1, 1, Math.max(1, y2 - y1));
        }
    }
    function drawWaveformFromBars(bars) {
        const dpr = window.devicePixelRatio || 1;
        const w = track.clientWidth;
        const h = track.clientHeight;
        canvas.width = w * dpr;
        canvas.height = h * dpr;
        const ctx = canvas.getContext("2d");
        ctx.scale(dpr, dpr);
        const totalBars = bars.length / 2;
        const mid = h / 2;
        const ratio = totalBars / w;
        const scale = 0.9;
        ctx.fillStyle = "#9bb8e6";
        for (let x = 0; x < w; x++) {
            const idx = Math.floor(x * ratio) * 2;
            const mn = bars[idx];
            const mx = bars[idx + 1];
            const y1 = mid + mn * mid * scale;
            const y2 = mid + mx * mid * scale;
            ctx.fillRect(x, y1, 1, Math.max(1, y2 - y1));
        }
    }
    function stopCurrent() {
        if (currentSource) {
            // Clear the global ref first if it points to our current source
            if (window.top._audio && window.top._audio.node === currentSource) {
            window.top._audio = null;
            }
            try {
            currentSource.onended = null;
            currentSource.stop();
            } catch (e) {}
            try {
            currentSource.disconnect();
            } catch (e) {}
            currentSource = null;
        }
        if (rafId != null) {
            cancelAnimationFrame(rafId);
            rafId = null;
        }
    }
function playRangeInternal() {
    stopCurrent();
    if (!audioBuffer || !audioCtx || !duration) return;
    if (audioCtx.state === "suspended") audioCtx.resume();
    const source = audioCtx.createBufferSource();
    const gain = audioCtx.createGain();
    source.buffer = audioBuffer;
    source.connect(gain);
    gain.connect(audioCtx.destination);
    const offset = startT;
    const playDur = Math.max(0, endT - startT);
    source.start(0, offset, playDur);
    currentSource = source;
    webStart = audioCtx.currentTime;
    webOffset = offset;

// Smart fade: duration scales with loudness at start/end
    const MAX_FADE_S = 0.3;
    const MAX_VOL = 0.01;
    const sr = audioBuffer.sampleRate;
    const data = audioBuffer.getChannelData(0);
    const fadeSamples = Math.floor(sr * MAX_FADE_S);
    const startSample = Math.floor(startT * sr);
    const endSample = Math.floor(endT * sr);

    // Average volume at start → fade-in duration
    let startSum = 0;
    for (let i = startSample; i < Math.min(startSample + fadeSamples, data.length); i++)
        startSum += Math.abs(data[i]);
    const startVol = startSum / fadeSamples;
    const fadeInS = Math.min(startVol / MAX_VOL, 1) * MAX_FADE_S;

    // Average volume at end → fade-out duration
    let endSum = 0;
    for (let i = Math.max(0, endSample - fadeSamples); i < Math.min(endSample, data.length); i++)
        endSum += Math.abs(data[i]);
    const endVol = endSum / fadeSamples;
    // Cap to half of playDur so fade always fits within the clip
    const fadeOutS = Math.min(
        Math.min(endVol / MAX_VOL, 1) * MAX_FADE_S,
        playDur * 0.5
    );

    const now = audioCtx.currentTime;
    if (fadeInS > 0) {
        gain.gain.setValueAtTime(0, now);
        gain.gain.linearRampToValueAtTime(1, now + fadeInS);
    } else {
        gain.gain.setValueAtTime(1, now);
    }
    if (fadeOutS > 0) {
        const fadeOutStart = now + playDur - fadeOutS;
        gain.gain.setValueAtTime(1, fadeOutStart);
        gain.gain.linearRampToValueAtTime(0, fadeOutStart + fadeOutS);
    }

    // Register globally so the next card's front side can fade-stop this playback
    window.top._audio = {
        node: source,
        gain: gain,
        ctx: audioCtx,
    };
    rafId = requestAnimationFrame(watchProgress);
}
    function watchProgress() {
        if (!currentSource) {
            rafId = null;
            return;
        }
        const elapsed = audioCtx.currentTime - webStart;
        const t = webOffset + elapsed;
        if (t >= endT) {
            stopCurrent();
            updateProgressFromTime(endT);
            return;
        }
        updateProgressFromTime(t);
        rafId = requestAnimationFrame(watchProgress);
    }
    // Load audio: fetch -> decode -> draw waveform -> auto play once
    (function loadAudio() {
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        if (!AudioCtx) {
            document.querySelector(".ap-wrap").innerHTML =
            '<div style="color:#c00">Web Audio not supported.</div>';
            return;
        }
        audioCtx = new AudioCtx();
        window.top._apAudioCtx = audioCtx;   // Track for cleanup by next card's front side
        function onDecoded(decoded, prerenderedBars, prerenderedPlayTime) {
            audioBuffer = decoded;
            duration = decoded.duration;
            // Priority: localStorage > field audio_range > full track
            let initStart = null,
            initEnd = null;
            // 1. Try localStorage
            const saved = loadRange();
            if (
            saved &&
            saved.start < saved.end &&
            saved.end <= duration + 0.01
            ) {
            initStart = Math.max(0, saved.start);
            initEnd = Math.min(duration, saved.end);
            }
            // 2. Fallback to prerendered play time (or parse field if not provided)
            if (initStart === null) {
            let pt = prerenderedPlayTime;
            if (!pt) {
                const raw = "{{audio_range}}".trim();
                if (raw) {
                    const parts = raw.split(",");
                    if (parts.length === 2) {
                        const s = parseFloat(parts[0]);
                        const e = parseFloat(parts[1]);
                        if (isFinite(s) && isFinite(e) && s < e) pt = [s, e];
                    }
                }
            }
            if (pt && pt[1] <= duration + 0.01) {
                initStart = Math.max(0, pt[0]);
                initEnd = Math.min(duration, pt[1]);
            }
            }
            // 3. Fallback to full track
            if (initStart === null) {
            initStart = 0;
            initEnd = duration;
            }
            startT = initStart;
            endT = initEnd;
            updateUI();
            updateProgressFromTime(0);
            if (prerenderedBars) {
            drawWaveformFromBars(prerenderedBars);
            } else {
            drawWaveform(decoded);
            }
            playRangeInternal();
        }
        const cached = window.top._apCache && window.top._apCache[filename];
        if (cached) {
            // New format: {buffer, bars, playTime}; old format: just buffer
            if (cached.buffer) {
            onDecoded(cached.buffer, cached.bars, cached.playTime);
            } else {
            onDecoded(cached);
            }
            return;
        }
        // Fallback: fetch and decode now
        fetch(filename)
            .then((r) => r.arrayBuffer())
            .then((buf) => audioCtx.decodeAudioData(buf))
            .then(onDecoded)
            .catch((err) => {
            document.querySelector(".ap-wrap").innerHTML =
                '<div style="color:#c00">Failed to load: ' +
                filename +
                "</div>";
            console.log("Audio load failed:", err);
            });
    })();
    // Drag handles
    let dragging = null;
    function pointerPos(e) {
        const rect = track.getBoundingClientRect();
        const x = (e.touches ? e.touches[0].clientX : e.clientX) - rect.left;
        return Math.max(0, Math.min(1, x / rect.width));
    }
    function onDown(e) {
        dragging = e.currentTarget.dataset.role;
        if (e.currentTarget.setPointerCapture && e.pointerId != null) {
            try {
            e.currentTarget.setPointerCapture(e.pointerId);
            } catch (err) {}
        }
        e.preventDefault();
        e.stopPropagation();
    }
    function onMove(e) {
        if (!dragging || !duration) return;
        const t = pointerPos(e) * duration;
        if (dragging === "start") {
            startT = Math.min(t, endT - 0.05);
        } else {
            endT = Math.max(t, startT + 0.05);
        }
        updateUI();
        e.preventDefault();
    }
    function onUp() {
        if (dragging) saveRange();
        dragging = null;
    }
    addTracked(hStart, "pointerdown", onDown);
    addTracked(hEnd, "pointerdown", onDown);
    addTracked(document, "pointermove", onMove);
    addTracked(document, "pointerup", onUp);
    addTracked(hStart, "touchstart", onDown, { passive: false });
    addTracked(hEnd, "touchstart", onDown, { passive: false });
    addTracked(document, "touchmove", onMove, { passive: false });
    addTracked(document, "touchend", onUp);
    // Expose play function for screenshot click
    window.playRange = function () {
        if (typeof fadeStop === "function" && window.top._audio) {
            fadeStop(window.top._audio, 200);
            window.top._audio = null;
        }
        playRangeInternal();
    };
    // Re-draw canvases when the page becomes visible again
    // (iOS WKWebView frees GPU memory on lock screen / app background)
    function redrawAll() {
        // Redraw waveform
        if (audioBuffer) {
            const cached = window.top._apCache && window.top._apCache[filename];
            if (cached && cached.bars) {
            drawWaveformFromBars(cached.bars);
            } else {
            drawWaveform(audioBuffer);
            }
        }
        // Redraw screenshot canvas
        if (typeof renderScreenshot === "function") {
            renderScreenshot();
        }
    }
    function onVisible() {
        if (document.visibilityState === "visible") {
            // Delay: GPU memory may not be restored immediately on iOS
            setTimeout(redrawAll, 100);
            // Second attempt: covers slower GPU restore after long suspension (30+ min)
            setTimeout(redrawAll, 700);
        }
    }
    addTracked(document, "visibilitychange", onVisible);
    addTracked(window, "pageshow", function () {
    setTimeout(redrawAll, 100);
// iOS: after long suspension, 'focus' fires more reliably than visibilitychange
addTracked(window, "focus", function () {
    setTimeout(redrawAll, 100);
    setTimeout(redrawAll, 700);
});
});
})();
</script>

<div id="text-wrap">
{{#excerpt}}
<div style="font-size: 18px; text-align: left">{{excerpt}}</div>
{{/excerpt}} {{#excerpt}}{{#fuzzy}}<br />{{/fuzzy}}{{/excerpt}} {{#fuzzy}}
<div style="font-size: 18px; text-align: left">{{fuzzy}}</div>
{{/fuzzy}}
</div></div>

<div style="text-align: center">
<a
    href="#"
    onclick="this.href='https://cn.bing.com/search?q='+encodeURIComponent('{{spell}}' +' 語源')"
    style="
        display: inline-block;
        margin-left: 150px;
        padding: 12px 22px;
        background: #4f46e5;
        color: #fff;
        border-radius: 10px;
        text-decoration: none;
        font-size: 18px;
    "
>
    語源
</a>
</div>

<button onclick="exportRanges()">复制音频时间</button>
<button onclick="importRanges()">导入音频时间</button>
<script>
function exportRanges() {
    if (window._exportShowing) return;
    window._exportShowing = true;

    const data = {};
    for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (key.startsWith('ap-range:')) {
            data[key] = JSON.parse(localStorage.getItem(key));
        }
    }
    const json = JSON.stringify(data);

    var div = document.createElement('div');
    div.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.8);z-index:9999;display:flex;flex-direction:column;align-items:center;justify-content:center;';

var ta = document.createElement('div');
ta.textContent = json;
ta.contentEditable = 'true';
ta.style.cssText = 'width:80%;height:3em;font-size:12px;background:white;color:black;padding:8px;overflow:auto;word-break:break-all;';

ta.addEventListener('click', function() {
    ta.select();
});

var label = document.createElement('div');
label.innerHTML = '1.复制以下文本<br>2.点击Anki的"编辑"<br>3.找到"time"字段并黏贴<br>4.同步本设备<br>5.同步另一设备<br>6.在另一设备打开 <span style="text-decoration:underline">同一词条</span> 并点击"导入音频时间"'
label.style.cssText = 'color:white;margin-bottom:8px;font-size:14px;text-align:left;';

    var btn = document.createElement('button');
    btn.textContent = '关闭';
    btn.style.cssText = 'margin-top:16px;padding:8px 24px;font-size:16px;';
    btn.onclick = function() {
        document.body.removeChild(div);
        window._exportShowing = false;
    };

    div.appendChild(label);
    div.appendChild(ta);
    div.appendChild(btn);
    document.body.appendChild(div);

    setTimeout(function() {
        var range = document.createRange();
        range.selectNodeContents(ta);
        var sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(range);
    }, 100);
}
function importRanges() {
    var json = '{{time}}'.trim()
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>');
    if (!json) {
        alert(`time字段为空
先同步另一设备，再打开同一词条`);
        return;
    }
    try {
        var data = JSON.parse(json);
        var count = 0;
        for (var key in data) {
            if (key.startsWith('ap-range:')) {
                var existing = localStorage.getItem(key);
if (existing) {
    var existingObj = JSON.parse(existing);
    if (existingObj.updated === undefined || data[key].updated === undefined) continue;
    if (existingObj.updated >= data[key].updated) continue;
}
localStorage.setItem(key, JSON.stringify(data[key]));
count++;
                localStorage.setItem(key, JSON.stringify(data[key]));
                count++;
            }
        }
        alert('导入完成，更新了 ' + count + ' 条记录');
    } catch(e) {
        alert('解析失败：' + e.message);
    }
}
</script>
"""
    CSS = """img {
max-width: 100%;
height: auto;
}

#left-col { align-items: center; }
#text-wrap { width: fit-content; margin: 0 auto; }

#main-wrap { display: flex; flex-direction: column; }
#left-col { display: flex; flex-direction: column; }
#text-wrap { margin: 0 auto; }
body.landscape #main-wrap { flex-direction: row; align-items: flex-start; gap: 16px; }
body.landscape #text-wrap { flex: 1; text-align: left; margin: 0; }

#word-img-fallback img {
max-width: 100%;
max-height: 60vh;
object-fit: contain;
}

.card {
font-family: BIZ UDGothic;
font-size: 20px;
line-height: 1.5;
text-align: center;
color: black;
background-color: white;
}

.ap-track {
position: relative;
height: 20px;
background: 
#f5f5f5;
border-radius: 6px;
touch-action: none;
}
#ap-wave {
position: absolute;
top: 0; left: 0;
width: 100%;
height: 100%;
display: block;
border-radius: 6px;
}
.ap-range {
position: absolute;
top: 0; bottom: 0;
background: rgba(26, 115, 232, 0.18);
pointer-events: none;
border-radius: 4px;
}
/* Outer handle = invisible hit area, larger than the visual */
.ap-handle {
position: absolute;
top: -15px;
width: 40px;
height: calc(100% + 30px);
cursor: ew-resize;
z-index: 2;
background: transparent;
touch-action: none;
}
/* Inner visual = the actual visible bracket, fixed to track height */
.ap-handle-visual {
position: absolute;
top: 15px;
bottom: 15px;
width: 20px;
pointer-events: none;
max-width: 100%;
}
/* Top bar of the bracket */
.ap-handle-visual::before {
content: '';
position: absolute;
top: 0;
left: 0;
right: 0;
height: 1px;
background: 
#1a73e8;
}
/* Bottom bar of the bracket */
.ap-handle-visual::after {
content: '';
position: absolute;
bottom: 0;
left: 0;
right: 0;
height: 1px;
background: 
#1a73e8;
}
/* Start handle: vertical line on the LEFT, anchored to time point */
.ap-handle-start {
transform: translateX(-20%);
}
.ap-handle-start .ap-handle-visual {
left: 20%;
border-left: 1px solid 
#1a73e8;
}
/* End handle: vertical line on the RIGHT, anchored to time point */
.ap-handle-end {
transform: translateX(-80%);
}
.ap-handle-end .ap-handle-visual {
right: 20%;
border-right: 1px solid 
#1a73e8;
}
/* Active state: thicker top and bottom bars only */
.ap-handle:active .ap-handle-visual::before,
.ap-handle:active .ap-handle-visual::after {
height: 3px;
}
.ap-handle-start:active .ap-handle-visual { border-left-color: 
#0b57c4; }
.ap-handle-end:active .ap-handle-visual { border-right-color: 
#0b57c4; }"""
    FRONT_TEMPLATE = FRONT_TEMPLATE.strip('\n')
    BACK_TEMPLATE = BACK_TEMPLATE.strip('\n')
    CSS = CSS.strip('\n')

    if ui_index == 0:
        SYNC_UI = (
            ('"time"字段为空', 'field "time" is empty'),
            ('先同步另一设备，再打开同一词条', 'sync another device first, then open the same note'),
            ('导入完成，更新了', 'Import complete, '),
            ('条记录', 'records updated'),
            ('解析失败：', 'Error: '),
            ('1.复制以下文本<br>2.点击Anki的"编辑"<br>3.找到"time"字段并黏贴<br>4.同步本设备<br>5.同步另一设备<br>6.在另一设备打开 <span style="text-decoration:underline">同一词条</span> 并点击"导入音频时间"',
            '1.Copy below text<br>2.Click "Edit" in Anki<br>3.Paste to field "time"<br>4.Sync this device<br>5.Sync another device<br>6.On another device, open <span style="text-decoration:underline">the same note</span> and click "Import Audio Time"'),
            ('复制音频时间', 'Copy Audio Time'),
            ('导入音频时间', 'Import Audio Time'),
            ('关闭', 'Close'),
        )

        for zh, en in SYNC_UI:
            BACK_TEMPLATE = BACK_TEMPLATE.replace(zh, en)

    need_update_config = False

    if MODEL_NAME not in invoke("modelNames")['result']:
        invoke("createModel",
            modelName=MODEL_NAME,
            inOrderFields=[
                "spell",
                "pron",
                "accent",
                "romaji",
                "excerpt",
                "screenshot",
                "word",
                "fuzzy",
                "word_position",
                "audio",
                "audio_range",
                "reserved1",
                "reserved2",
                "reserved3",
                "reserved4",
                "reserved5",                
                "time",
            ],
            css=CSS,
            isCloze=False,
            cardTemplates=[{
                "Name": MODEL_NAME,
                "Front": FRONT_TEMPLATE,
                "Back": BACK_TEMPLATE,
            }]
        )
        need_update_config = True
    else:
        # check model version. however, before overwrite old model, check if it user modified it manually
        # if yes, assume user need the modified model so will not update newer model to anki
        if config['anki_model_version_and_hash'][0] < ANKI_MODEL_VERSION:
            model_hash = anki_current_model_hash()
            if model_hash == config['anki_model_version_and_hash'][1] or config['anki_model_version_and_hash'][0] == 0:
                invoke("updateModelTemplates", model={
                    "name": MODEL_NAME,
                    "templates": {
                        MODEL_NAME: {
                            "Front": FRONT_TEMPLATE,
                            "Back": BACK_TEMPLATE,
                        }
                    }
                })
                invoke("updateModelStyling", model={
                    "name": MODEL_NAME,
                    "css": CSS
                })
                need_update_config = True
    
    if need_update_config:
        time.sleep(3)  # not sure if model update reflect immediately
        model_hash = anki_current_model_hash()
        update_config('anki_model_version_and_hash',[ANKI_MODEL_VERSION,model_hash])
def anki_current_model_hash():
    model_data = str(invoke("modelTemplates", modelName=MODEL_NAME)) + str(invoke("modelStyling", modelName=MODEL_NAME)) + str(invoke("modelFieldNames", modelName=MODEL_NAME))
    model_data.replace(' ', '').replace('\n', '').replace('\t', '').replace('\r', '')
    return hashlib.md5(model_data.encode()).hexdigest()
def ttt(label=""):  # test need delete
    global _last_time
    now = time.time()
    if _last_time is not None:
        print(f"[{label}] {now - _last_time:.3f}s")
    else:
        print(f"[{label}] start")
    _last_time = now
ctypes.windll.kernel32.SetProcessWorkingSetSize(
    ctypes.windll.kernel32.GetCurrentProcess(),
    -1, -1
)
ui_index = get_ui_index()
config_path, config = load_config()
app = QApplication(sys.argv)
class AppEventFilter(QObject):
    def eventFilter(self, obj, event):
        if isinstance(obj, QMenu) and event.type() == QEvent.Show:
            hwnd = int(obj.winId())
            user32.SetWindowDisplayAffinity(hwnd, 0)
            user32.SetWindowDisplayAffinity(hwnd, 0x00000011)
        return False
app_event_filter = AppEventFilter()
QApplication.instance().installEventFilter(app_event_filter)
install_msg_showing = False
anki_path = check_get_anki_path()
anki_thread = threading.Thread(target=open_anki, args=(anki_path,), daemon = True)
anki_thread.start()  # test
check_dup()
ANKI_HOST = '127.0.0.1'
ANKI_PORT = 8765
ANKI_URL = f'http://{ANKI_HOST}:{ANKI_PORT}'
DECK_NAME = config['anki_deck_name']
MODEL_NAME = config['anki_model_name']
check_anki_connect()
processing = False  # global variable to check if some thread is in processing
session = None # moji session
dummy_uuid = str(uuid.uuid4())
hotkey_mode = 1  # -1 = ignore all, 0 = config, 1 = main, 2 = in snip
keyboard_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
mouse_listener = mouse.Listener(on_click=on_click, on_scroll=on_scroll)
last_moji_search_time = 0
anki_sync_running = False

max_fps = [row[:] for row in config['max_fps']]  # Copy to avoid modifying config
max_record_time = max_fps[-1][0]
AUDIO_BEFORE_SNIP_SECOND = 60  # when a snip is taken, take this seconds before the snip time as draft audio for further analysis
AUDIO_AFTER_SNIP_SECOND = 15
class LoopbackRecorder:
    DLL_PATH = os.path.join(BASE, 'LoopbackCapture.dll')

    RATE = 44100
    CHANNELS = 2
    BITS = 16 

    BYTES_PER_SAMPLE = CHANNELS * (BITS // 8)
    BYTES_PER_SEC = RATE * BYTES_PER_SAMPLE
    
    BUFFER_SECONDS = max_record_time + AUDIO_BEFORE_SNIP_SECOND

    MAX_BYTES = BYTES_PER_SEC * BUFFER_SECONDS

    utilsdll = cdll.LoadLibrary(DLL_PATH)

    AudioCallback = CFUNCTYPE(None, POINTER(c_char), c_size_t)

    SetAudioCallback = utilsdll.SetAudioCallback
    SetAudioCallback.argtypes = [AudioCallback]
    SetAudioCallback.restype = c_int

    StartCaptureAsync = utilsdll.StartCaptureAsync
    StartCaptureAsync.argtypes = [POINTER(c_void_p)]
    StartCaptureAsync.restype = c_int

    def __init__(self):
        self.ptr = c_void_p()
        self.lock = threading.Lock()
        self.ring = deque()
        self.size = 0
        self.last_audio = b''

        self.cb = self.AudioCallback(self._on_data)
        self.SetAudioCallback(self.cb)
        self.StartCaptureAsync(pointer(self.ptr))

    def _on_data(self, ptr, sz):
        if not ptr or sz == 0:
            return

        data = string_at(ptr, sz)

        with self.lock:
            self.ring.append(data)
            self.size += sz

            while self.size > self.MAX_BYTES:
                old = self.ring.popleft()
                self.size -= len(old)

    def capture_last(self,snip_time,click_time):
        with self.lock:
            data = b''.join(self.ring)

        data_start_time = click_time - len(data) // self.BYTES_PER_SEC
        snip.audio_start_time = max(snip_time - AUDIO_BEFORE_SNIP_SECOND, data_start_time)
        save_start_byte = len(data) - int(self.BYTES_PER_SEC * (click_time - snip.audio_start_time))
        save_start_byte = save_start_byte - save_start_byte % self.BYTES_PER_SAMPLE

        audio_end_time = snip_time + AUDIO_AFTER_SNIP_SECOND
        save_end_byte = len(data) - int(self.BYTES_PER_SEC * (click_time - audio_end_time))
        save_end_byte = save_end_byte - save_end_byte % self.BYTES_PER_SAMPLE
        save_end_byte = min(save_end_byte, len(data))
        save_end_byte = max(save_end_byte, 0)

        data = data[save_start_byte:save_end_byte]

        snip.audio = data
        print(f'captured {len(data)} bytes')
        return
recorder = LoopbackRecorder()
min_memory_gb = config['min_memory_gb']
max_memory_percentage = config['max_memory_percentage']
convert_max_fps()
screenshot = []
anki_list = []
lock = threading.Lock()
user32 = ctypes.WinDLL("user32", use_last_error=True)
lock_length = 0
this_screenshot_time = int(time.time()) * 1000  # initial run at whole second to reduce rounding effect
screenshot_thread_stop = threading.Event()
screenshot_thread_handle = threading.Thread(target=screenshot_thread, daemon=True)
screenshot_thread_handle.start()
threading.Thread(target=moji_session,daemon=True).start()
threading.Thread(target=anki_create_deck,daemon=True).start()
threading.Thread(target=anki_create_model,daemon=True).start()

# for ocr
ErrorCallback  = CFUNCTYPE(None, c_char_p)
DetectCallback = CFUNCTYPE(None, c_float, c_float, c_float, c_float, c_float, c_float, c_float, c_float, c_char_p)
dll.cvMatFromRGB888.argtypes = (c_void_p, c_int, c_int, c_int)
dll.cvMatFromRGB888.restype  = CvMat
dll.cvMatDestroy.argtypes    = (CvMat,)
dll.cvMatDestroy.restype     = None
dll.OcrLoadRuntime.restype   = c_bool
dll.OcrInit.argtypes         = (c_wchar_p, c_wchar_p, c_wchar_p, c_int32, c_bool, c_uint64, c_char_p, ErrorCallback)
dll.OcrInit.restype          = OcrHandle
dll.OcrDetect.argtypes       = (OcrHandle, CvMat, c_int32, DetectCallback, ErrorCallback)
dll.OcrDetect.restype        = None
dll.OcrDestroy.argtypes      = (OcrHandle,)
dll.OcrDestroy.restype       = None
# for mp3 test put to warm up
_bass_code_cast = native_dll.bass_code_cast
_bass_code_cast_CB = CFUNCTYPE(None, POINTER(c_char), c_size_t)
_bass_code_cast.argtypes = _bass_code_cast_CB, c_char_p, c_size_t, c_char_p, c_int, c_int

os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "0"
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
snip = Snip()
bridge = Bridge()
bridge.click_snip.connect(snip.start)

# test put to warm up
ocr, on_error = init_ocr(
    os.path.join(BASE, 'det.onnx'),
    os.path.join(BASE, 'rec.onnx'),
    os.path.join(BASE, 'dict.txt'),
)

class MainWindow(QMainWindow):
    show_msg_signal = pyqtSignal()
    reinit_snip_signal = pyqtSignal()
    close_snip_signal = pyqtSignal()
    cancel_drag_signal = pyqtSignal()
    scroll_signal = pyqtSignal(int)
    hotkey_captured_signal = pyqtSignal()
    hide_signal = pyqtSignal()
    slider_set_signal = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        # Debounce timer: only save after movement settles
        self._pos_save_timer = QTimer(self)
        self._pos_save_timer.setSingleShot(True)
        self._pos_save_timer.setInterval(300)
        self._pos_save_timer.timeout.connect(self._save_position)
        self._restore_done = False
        self.show_msg_signal.connect(self.show_install_msg)
        self.reinit_snip_signal.connect(_reinit_snip_main_thread)
        self.close_snip_signal.connect(snip.close_snip)
        self.cancel_drag_signal.connect(snip.cancel_drag)
        self.scroll_signal.connect(_snip_scroll)
        self.hide_signal.connect(self.hide)
        self.slider_set_signal.connect(lambda v: snip.slider.setValue(v))

    def restore_position(self):
        pos = config.get('window_pos')
        if isinstance(pos, list) and len(pos) == 2:
            point = QPoint(int(pos[0]), int(pos[1]))
            # Only restore if the point is still on some connected screen,
            # otherwise the window could end up invisible (e.g. unplugged monitor)
            for screen in QApplication.screens():
                if screen.availableGeometry().contains(point):
                    self.move(point)
                    break
        self._restore_done = True

    def moveEvent(self, event):
        super().moveEvent(event)
        # Ignore move events fired before/during restore
        if self._restore_done:
            self._pos_save_timer.start()

    def _save_position(self):  # keep same positon when application open next time
        p = self.pos()
        update_config('window_pos', [p.x(), p.y()])

    def closeEvent(self, event):
        # Flush any pending save before exit
        if self._restore_done:
            self._save_position()
        super().closeEvent(event)

    def show_install_msg(self):
        msg = QMessageBox()
        msg.setWindowTitle(ui('messagebox_title'))
        msg.setText(ui('install_anki_connect'))
        msg.setTextFormat(Qt.RichText)
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec_()
window = MainWindow()
bridge.anki_new_note_done.connect(anki_new_note_after)
window.restore_position()
window.setStyleSheet("background-color: #f0f0f0; color: #000000;")
window.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
window.setWindowOpacity(0.9)
show_and_exclude_from_capture(window)
set_qt_layout()
window.label_spell.setText('感谢参加ACard测试\n测试期间请不要发视频\nPress middle mouse button')  # test

# Create tray icon
tray = QSystemTrayIcon(window)
tray.setIcon(QIcon(resource_path("icon.ico")))
tray.setToolTip("ACard")
#right-click menu
menu = QMenu()
action_quit = QAction(ui('quit'))
action_quit.triggered.connect(app.quit)
menu.addAction(action_quit)
tray.setContextMenu(menu)
tray.show()
tray.activated.connect(lambda reason: window.show() if reason == QSystemTrayIcon.Trigger else None)
app.aboutToQuit.connect(tray.hide)

keyboard_listener.start()
mouse_listener.start()
sys.exit(app.exec_())