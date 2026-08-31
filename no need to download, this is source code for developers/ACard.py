__version__ = "0.0.3"

# ── Auto-updater ──────────────────────────────────────────────────────────────
import hashlib, json, os, platform, shutil, subprocess, sys
import tempfile, threading, time
from pathlib import Path
from urllib.request import Request, urlopen

GITHUB_OWNER = "qazzzlyt"
GITHUB_REPO  = "ACard"
_APP_NAME    = "ACard"


def _ulog(msg):
    # the updater thread sleeps 5s before doing anything, by which time
    # setup_logging() has already teed stdout into ACard.log
    try:
        print('[update] ' + str(msg), flush=True)
    except Exception:
        pass

def _update_dir() -> Path:
    d = Path(tempfile.gettempdir()) / f"{_APP_NAME}-update"
    d.mkdir(parents=True, exist_ok=True)
    return d

def _pending_path() -> Path:
    return _update_dir() / "pending.json"

def _current_exe() -> Path:
    return Path(sys.executable).resolve()

def _asset_name() -> str:
    return "ACard.exe"

def _parse_ver(tag: str):
    try:
        return tuple(int(x) for x in tag.lstrip("v").split("."))
    except ValueError:
        return (0,)

def _staging_dir() -> Path:
    """Same drive as the exe (the two-stage swap needs that), but invisible
    to the user: LOCALAPPDATA when the exe sits on the system drive, else a
    hidden folder at the exe drive's root."""
    cur = _current_exe()
    local = Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir())) / _APP_NAME
    if local.drive.lower() == cur.drive.lower():
        return local / "update"
    return Path(cur.drive + "\\") / f"{_APP_NAME}.staging"

def _staged_path() -> Path:
    return _staging_dir() / (_asset_name() + ".new")

def _hide_path(path: Path) -> None:
    try:
        import ctypes
        ctypes.windll.kernel32.SetFileAttributesW(str(path), 0x02)  # hidden
    except Exception:
        pass

def _sweep_stale_files() -> None:
    """Startup janitor: delete anything not referenced by a valid
    pending.json (orphans from killed downloads / interrupted staging)."""
    keep = set()
    p = _pending_path()
    if p.exists():
        try:
            info = json.loads(p.read_text(encoding="utf-8"))
            staged = Path(info.get("staged_path", ""))
            if staged.is_file() and _sha256(staged) == info.get("checksum"):
                keep.add(str(staged).lower())
            else:
                p.unlink(missing_ok=True)
        except Exception:
            p.unlink(missing_ok=True)
    for d in (_update_dir(), _staging_dir()):
        try:
            if not d.is_dir():
                continue
            for f in d.iterdir():
                if f.name in ("pending.json", "cleanup.bat"):
                    continue  # cleanup.bat may still be mid-run, never touch
                if f.is_file() and str(f).lower() not in keep:
                    try:
                        f.unlink()
                    except OSError:
                        pass
            if d.name.endswith(".staging") and not any(d.iterdir()):
                d.rmdir()
        except OSError:
            pass

def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def _generate_exit_bat():
    """Generate a bat that (always) deletes this _MEI folder after exit,
    and (if a pending update exists) replaces the exe first."""
    if not getattr(sys, 'frozen', False):
        return

    cur = _current_exe()
    mei = sys._MEIPASS  # current _MEI folder to delete after exit
    probe = os.path.join(mei, 'base_library.zip')  # check if files in folder already deleted

    # Check for a valid pending update (optional part)
    new_exe = None
    p = _pending_path()
    if p.exists():
        try:
            info = json.loads(p.read_text(encoding="utf-8"))
            candidate = Path(info.get("staged_path", ""))
            cksum = info["checksum"]
            if candidate.is_file() and _sha256(candidate) == cksum:
                new_exe = candidate
            else:
                p.unlink(missing_ok=True)
                if str(candidate) not in ("", "."):
                    candidate.unlink(missing_ok=True)
        except Exception:
            p.unlink(missing_ok=True)

    bat = _update_dir() / "cleanup.bat"

    # Build the optional update (move) block
    if new_exe:
        update_block = (
            f'set count=0\n'
            f':retry\n'
            f'set /a count+=1\n'
            f'if %count% gtr 120 goto delmei\n'
            # copy overwrites the existing file object in place, so the
            # desktop icon keeps its position (move = delete + recreate)
            f'copy /y "{new_exe}" "{cur}" >nul 2>&1\n'
            f'if errorlevel 1 (\n'
            f'    ping -n 2 127.0.0.1 >nul\n'
            f'    goto retry\n'
            f')\n'
            f'del /a /f "{new_exe}"\n'
            f'del "{p}"\n'
            f'rmdir "{new_exe.parent}" 2>nul\n'
        )
    else:
        update_block = ''

    bat.write_text(
        f'@echo off\n'
        f'chcp 65001 >nul\n'
        f'{update_block}'
        f':delmei\n'
        f'set count2=0\n'
        f':retrymei\n'
        f'set /a count2+=1\n'
        f'if %count2% gtr 120 goto end\n'
        f'rmdir /s /q "{mei}" 2>nul\n'
        f'if exist "{probe}" (\n'
        f'    ping -n 2 127.0.0.1 >nul\n'
        f'    goto retrymei\n'
        f')\n'
        f':end\n'
        f'del "%~f0"\n',
        encoding="utf-8-sig"
    )
    subprocess.Popen(
        [
            'powershell', '-WindowStyle', 'Hidden', '-NonInteractive', '-Command',
            f'Start-Process -FilePath cmd -ArgumentList \'/c "{bat}"\' -WindowStyle Hidden'
        ],
        creationflags=0x08000000,
        close_fds=True
    )


def _check_and_download():
    """Check GitHub; silently download + stage if a newer version exists."""
    # Skip if the temp drive has less than 500MB free
    try:
        free = shutil.disk_usage(tempfile.gettempdir()).free
        if free < 500 * 1024 * 1024:
            _ulog(f"abort: temp drive has only {free / 1e6:.0f} MB free")
            return
    except OSError as e:
        _ulog(f"abort: cannot read temp disk usage: {e!r}")
        return

    t0 = time.time()
    try:
        url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
        req = Request(url, headers={"Accept": "application/vnd.github.v3+json",
                                    "User-Agent": f"{_APP_NAME}-updater"})
        with urlopen(req, timeout=30) as r:
            release = json.loads(r.read())
        _ulog(f"api ok in {time.time() - t0:.1f}s, "
              f"latest={release.get('tag_name')!r}, running={__version__!r}")
    except Exception as e:
        _ulog(f"api FAILED after {time.time() - t0:.1f}s: {e!r}")
        return

    if _parse_ver(release.get("tag_name", "")) <= _parse_ver(__version__):
        _ulog("already up to date")
        return

    dl_url = next(
        (a["browser_download_url"] for a in release.get("assets", [])
         if a["name"] == _asset_name()),
        None,
    )
    if not dl_url:
        _ulog(f"abort: no asset named {_asset_name()!r} in the release "
              f"(assets: {[a.get('name') for a in release.get('assets', [])]})")
        return

    staged = _staged_path()
    p = _pending_path()
    if p.exists():
        try:
            info = json.loads(p.read_text(encoding="utf-8"))
            if (info.get("version") == release["tag_name"]
                    and staged.is_file()
                    and _sha256(staged) == info.get("checksum")):
                _ulog(f"{release['tag_name']} already staged, "
                      f"applies on next exit")
                return          # this release is already staged and ready
        except Exception as e:
            _ulog(f"pending.json unreadable, ignoring it: {e!r}")

    dest = _update_dir() / _asset_name()
    h = hashlib.sha256()
    _ulog(f"downloading {release['tag_name']} from {dl_url}")
    t1 = time.time()
    got = 0
    try:
        req2 = Request(dl_url, headers={"User-Agent": f"{_APP_NAME}-updater"})
        with urlopen(req2, timeout=3600) as r, open(dest, "wb") as f:
            while chunk := r.read(65536):
                f.write(chunk)
                h.update(chunk)
                got += len(chunk)
        dt = time.time() - t1
        _ulog(f"downloaded {got / 1e6:.1f} MB in {dt:.0f}s "
              f"({got / 1e6 / max(dt, 0.1):.2f} MB/s)")
    except Exception as e:
        _ulog(f"download FAILED after {time.time() - t1:.0f}s, "
              f"{got / 1e6:.1f} MB received: {e!r}")
        dest.unlink(missing_ok=True)
        return

    # Stage on the exe's DRIVE (not next to the exe): proves the target
    # drive has room, and turns the final swap into a same-drive copy.
    # Any failure here leaves the current exe untouched.
    try:
        sdir = _staging_dir()
        sdir.mkdir(parents=True, exist_ok=True)
        _hide_path(sdir)
        if shutil.disk_usage(sdir.anchor).free < dest.stat().st_size + 100 * 1024 * 1024:
            dest.unlink(missing_ok=True)
            return
        shutil.copyfile(dest, staged)
        ok = _sha256(staged) == h.hexdigest()
    except OSError as e:
        _ulog(f"staging FAILED: {e!r}")
        ok = False
    if not ok:
        _ulog("staging discarded (copy failed or checksum mismatch)")
        for junk in (staged, dest):
            try:
                junk.unlink(missing_ok=True)
            except OSError:
                pass
        return

    dest.unlink(missing_ok=True)     # temp copy no longer needed
    _pending_path().write_text(
        json.dumps({"version": release["tag_name"],
                    "staged_path": str(staged),
                    "checksum": h.hexdigest()}, indent=2),
        encoding="utf-8",
    )
    _ulog(f"staged {release['tag_name']} at {staged}, applies on next exit")

def _update_loop():
    time.sleep(5)
    _ulog(f"updater started, running {__version__}")
    try:
        _sweep_stale_files()
    except Exception as e:
        _ulog(f"sweep failed: {e!r}")
    while True:
        try:
            _check_and_download()
        except Exception as e:
            _ulog(f"unexpected error: {e!r}")
        time.sleep(30 * 60)     # re-check every 30 minutes while running

if getattr(sys, 'frozen', False):
    threading.Thread(target=_update_loop, daemon=True).start()

# ── End auto-updater ──────────────────────────────────────────────────────────

import datetime
import uuid
import sys, psutil
# Beta expiry date
BETA_EXPIRY = datetime.date(2026, 8, 31)
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
        messagebox.showerror(
            'ACard',
            '测试版本已过期 请下载正式版ACard. Test version expired. Download formal version.'
        )
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


_log_file = None
_log_path = None
LOG_MAX_BYTES = 5 * 1024 * 1024
LOG_KEEP_BYTES = 3 * 1024 * 1024


def setup_logging():
    global _log_file, _log_path
    # Determine where the exe (or script) lives
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
    else:
        exe_dir = os.path.dirname(os.path.abspath(__file__))
    log_path = os.path.join(os.path.expanduser("~"), "Downloads", "acard",
                            "ACard.log")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    log_file = open(log_path, 'a', encoding='utf-8')
    # Tee to both original console and log file
    sys.stdout = Tee(sys.__stdout__, log_file)
    sys.stderr = Tee(sys.__stderr__, log_file)
    _log_file = log_file
    _log_path = log_path
    print(f'=== {datetime.now().isoformat()} ===')


def rotate_log_if_needed():
    # Run once at exit: if the log grew past the cap, trim it in place,
    # keeping only the newest tail so there is only ever one file.
    # Second call is a no-op.
    global _log_file
    if _log_file is None:
        return
    log_file, _log_file = _log_file, None
    # Detach std streams so any late write can't hit a closed file
    sys.stdout = sys.__stdout__ or open(os.devnull, 'w')
    sys.stderr = sys.__stderr__ or open(os.devnull, 'w')
    try:
        log_file.close()
        if os.path.getsize(_log_path) > LOG_MAX_BYTES:
            with open(_log_path, 'rb') as f:
                f.seek(-LOG_KEEP_BYTES, os.SEEK_END)
                tail = f.read()
            newline = tail.find(b'\n')  # drop the possibly half-cut first line
            if newline != -1:
                tail = tail[newline + 1:]
            with open(_log_path, 'wb') as f:
                f.write(tail)
    except Exception:
        pass


setup_logging()


def exception_hook(exctype, value, traceback):
    print(''.join(
        __import__('traceback').format_exception(exctype, value, traceback)))
    sys.__excepthook__(exctype, value, traceback)


sys.excepthook = exception_hook
_last_time = None

import os
import threading
import shutil
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
import random
from functools import partial
from pynput import keyboard, mouse
from collections import deque
from pathlib import Path
import pyaudio
import numpy as np
import xml.etree.ElementTree as ET
import unicodedata
from ctypes import wintypes, CDLL, create_unicode_buffer, CFUNCTYPE, WINFUNCTYPE, Structure, WinDLL, windll, byref, cast, POINTER, pointer, cdll, string_at, sizeof, c_char, c_bool, c_char_p, c_float, c_int, c_int32, c_uint64, c_void_p, c_wchar_p, c_long, c_longlong, c_ulong, c_short, c_size_t


def get_base():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


BASE = get_base()
# load DLL first, before importing Qt. This is required
dll = CDLL(os.path.join(BASE, 'CVUtils.dll'))
native_dll = CDLL(os.path.join(BASE, 'NativeUtils.dll'))

from PyQt5.QtWidgets import QApplication, QMessageBox, QFileDialog, QMainWindow, QWidget, QMenu, QSlider, QToolTip, QLabel, QVBoxLayout, QLineEdit, QTextEdit, QSizePolicy, QHBoxLayout, QToolButton, QStyle, QStyleOptionSlider, QStackedWidget, QComboBox, QPushButton, QSystemTrayIcon, QMenu, QAction
from PyQt5.QtCore import Qt, QRect, QEvent, QObject, pyqtSignal, QTimer, QBuffer, QIODevice, QPoint, QMetaObject, QEventLoop
from PyQt5.QtGui import QPainter, QColor, QPen, QPixmap, QImage, QCursor, QFont, QIcon, QPolygon

UI_TEXT = {
    'messagebox_title': ('ACard', 'ACard'),
    'no_anki_in_config':
    ('Download Anki from <a href="https://apps.ankiweb.net">apps.ankiweb.net</a><br>Then select anki.exe',
     '登录<a href="https://apps.ankiweb.net">apps.ankiweb.net</a>下载Anki<br>然后选择anki.exe'
     ),
    'select_anki': ('Select anki.exe', '选择anki.exe'),
    'wrong_anki':
    ('File is Wrong. Download Anki and select', '文件错误.下载并选择Anki'),
    'no_anki_connection': ('Failed to connect to Anki', '无法连接Anki'),
    'dup': ('ACard is already running', 'ACard已启动'),
    'blank': ('(Blank)', '(无)'),
    'install_anki_connect':
    ('Install Anki Connect:<br>1. Open Anki<br>2. Press Ctrl+Shift+A<br>3. Click Get Add-ons...<br>4. put 2055492159 as Code<br>5. Click OK',
     '安装Anki Connect<br>1. 打开Anki<br>2. 按下Ctrl+Shift+A<br>3. 点击 获取插件...<br>4. 代码处输入2055492159<br>5. 点击确定'
     ),
    'dict': ('Dictionary', '字典'),
    'monitor': ('Monitor', '显示器'),
    'search_dup': ('Combine to note?', '合并到已有词条?'),
    'search_dup_add_fail': ('Failed to combine to note', '合并词条失败'),
    'delete_dup': ('Delete note with multiple entries?', '词条包含多条音画,全部删除?'),
    'cut': ('Cut', '剪切'),
    'copy': ('Copy', '复制'),
    'paste': ('Paste', '粘贴'),
    'undo': ('Undo', '撤销'),
    'redo': ('Redo', '重做'),
    'search': ('Search', '搜索'),
    'hotkey': ('Hotkey', '快捷键'),
    'use_scroll': ('↑↑↑↑↑Use arrow keys or scroll wheel to playback↑↑↑↑↑',
                   '↑↑↑↑↑按"方向键"或"滑动鼠标滚轮"控制回放↑↑↑↑↑'),
    'quit': ('Quit', '退出'),
    'processing': ('Previous note under processing...', '上一词条处理中...'),
    'no_ocr_result': ('No text detected', '未检测到文字'),
    'not_found': ('Not found in dictionary', '查词失败'),
    'donate': ('Donate', '捐助'),
    'afadian': ('afadian', '爱发电'),
    'patreon': ('Patreon', 'Patreon'),
}


def load_config():
    from platformdirs import user_config_dir
    import json
    path = os.path.join(user_config_dir('ACard', appauthor=False),
                        'config.json')
    try:
        with open(path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except FileNotFoundError:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(DEFAULT_CONFIG, f, indent=4, ensure_ascii=False)
        config = DEFAULT_CONFIG
    return path, config


def repair_config(
):  # if new config item not in old version, take default value
    for key, value in DEFAULT_CONFIG.items():
        if key not in config:
            update_config(key, value)


def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(__file__), relative_path)


def get_ui_index(
):  # Check system language. Use English by default. If Chinese system is detected, use Chinese
    try:
        import locale
        lang = locale.getlocale()[0]
        if 'chinese' in lang.lower():
            return 1
    except:
        pass
    return 0


_config_lock = threading.Lock()

def update_config(key, value):
    with _config_lock:  # serialize writers, prevent lost updates
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except FileNotFoundError:
            data = config
        except json.JSONDecodeError:
            # Do NOT fall back to in-memory config blindly; it may be corrupt.
            # Keep existing data on disk; abort this write instead of wiping the file.
            return
        data[key] = value
        config[key] = value  # keep in-memory copy in sync
        # Atomic write: the real file is never truncated, readers always see a full file
        dir_name = os.path.dirname(config_path)
        fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix='.tmp')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            os.replace(tmp_path, config_path)  # atomic on same filesystem
        except Exception:
            os.unlink(tmp_path)
            raise


def ui(key):
    return UI_TEXT[key][ui_index]


def check_get_anki_path():
    # check if anki_path is in config
    if config['anki_path'] == '':
        if os.name == 'nt':  # Windows
            localappdata = os.environ.get('LOCALAPPDATA', '')
            userprofile = os.environ.get('USERPROFILE', '')
            candidates = [
                os.path.join(localappdata, 'Programs', 'Anki', 'anki.exe'),
                os.path.join(userprofile, 'Desktop', 'Anki', 'anki.exe'),
            ]
            for auto_path in candidates:
                if os.path.exists(auto_path):
                    update_config('anki_path', auto_path)
                    return auto_path
        msg = QMessageBox()
        msg.setWindowTitle(ui('messagebox_title'))
        msg.setText(ui('no_anki_in_config'))
        msg.setTextFormat(Qt.RichText)
        msg.setTextInteractionFlags(Qt.TextBrowserInteraction)
        msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        result = msg.exec_()
        if result == QMessageBox.Ok:
            return pick_anki_exe()
        elif result == QMessageBox.Cancel:
            return
    else:
        return config['anki_path']


def pick_anki_exe():
    # Must be called from main thread
    if os.name == 'nt':
        default_dir = os.path.join(os.environ.get('LOCALAPPDATA', ''),
                                   'Programs', 'Anki')
        if not os.path.exists(default_dir):
            default_dir = os.path.join(os.environ.get('LOCALAPPDATA', ''),
                                       'Programs')
        if not os.path.exists(default_dir):
            default_dir = os.environ.get('LOCALAPPDATA', '')
    else:
        default_dir = os.path.expanduser('~')

    anki_path, _ = QFileDialog.getOpenFileName(None, ui('select_anki'),
                                               default_dir,
                                               '*(anki.exe);;*.exe;;*.lnk')
    if not anki_path:
        return None
    if os.path.getsize(anki_path) > 50 * 1024 * 1024:
        qmsg(ui('wrong_anki'))
        return None
    update_config('anki_path', anki_path)
    return anki_path


def open_anki(anki_path):
    if anki_path:
        anki_just_closed = False
        # if need to install anki connect
        if not config['anki_connect_successful']:
            if not anki_connect_is_running():
                for proc in psutil.process_iter(['exe']):
                    if proc.info['exe'] and 'AnkiProgramFiles' in proc.info[
                            'exe']:
                        proc.kill()
                        anki_just_closed = True
                auto_install_anki_connect()

        if anki_just_closed:
            time.sleep(2)

        # open anki
        for proc in psutil.process_iter(['exe']):
            if proc.info['exe'] and 'AnkiProgramFiles' in proc.info['exe']:
                break
        else:
            env = os.environ.copy()
            if getattr(sys, 'frozen', False):
                meipass = sys._MEIPASS
                env['PATH'] = os.pathsep.join(
                    p for p in env.get('PATH', '').split(os.pathsep)
                    if p != meipass)
            try:
                subprocess.Popen([anki_path],
                                 env=env,
                                 cwd=os.path.dirname(anki_path))
            except Exception as e:
                qmsg(f"Failed to start Anki: {e}")
            time.sleep(10)


    # test need to (1) check if anki is already running (2) check if anki is now opened by acard (3) install anki connect automatically (4) hide anki (5) check deck and model
def auto_install_anki_connect():
    addons_dir = os.path.join(os.environ['APPDATA'], 'Anki2', 'addons21')
    if not os.path.exists(addons_dir):
        return

    dst = os.path.join(addons_dir, '2055492159')
    if os.path.exists(dst):
        return

    src = os.path.join(BASE, '2055492159')
    shutil.copytree(src, dst)


def check_dup():
    import psutil
    lockfile = os.path.join(tempfile.gettempdir(), 'acard.lock')
    if os.path.exists(lockfile):
        with open(lockfile) as f:
            pid = int(f.read())
        if psutil.pid_exists(pid):
            try:
                proc = psutil.Process(pid)
                is_acard = 'acard' in proc.name().lower()
            except psutil.NoSuchProcess:
                is_acard = False

            if is_acard:
                qmsg(ui('dup'))
                anki_thread.join()
                sys.exit()
            else:
                # pid recycled by another program → stale lock
                os.remove(lockfile)
        else:
            # process not exist → stale lock
            os.remove(lockfile)
    # create lock
    with open(lockfile, 'w') as f:
        f.write(str(os.getpid()))


def qmsg(str):
    msg = QMessageBox()
    msg.setWindowTitle(ui('messagebox_title'))
    msg.setText(str)
    msg.setTextFormat(Qt.RichText)
    msg.setStandardButtons(QMessageBox.Ok)

    # Make text selectable
    for label in msg.findChildren(QLabel):
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)

    msg.exec_()


_conn_dict = None
_conn_dict_ready = threading.Event()
_current_dict_key = None


def _load_db(filename, conn_var, ready_event):
    conn = sqlite3.connect(os.path.join(BASE, filename),
                           check_same_thread=False)
    conn.row_factory = sqlite3.Row
    globals()[conn_var] = conn
    ready_event.set()


def moji_session(stop_event):
    global session
    session = requests.Session()
    session.headers.update({
        "accept": "*/*",
        "accept-language": "zh-CN,zh;q=0.9",
        "content-type": "application/json",
        "user-agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "origin": "https://www.mojidict.com",
        "referer": "https://www.mojidict.com/"
    })
    session.post("https://api.mojidict.com/parse/functions/word-clickSearchV2",
                 json={
                     "searchText": "moji",
                     "_ApplicationId": "E62VyFVLMiW7kvbtVq3p"
                 })
    moji_keep_alive_thread(stop_event)


def moji_keep_alive_thread(stop_event):
    global last_moji_search_time
    dummy = {}
    dummy_event = threading.Event()
    while not stop_event.is_set():
        if time.time(
        ) - last_moji_search_time > 590:  # not sure how long moji session will expire. in my test at 2026/03/01, longest survivor is 1192s
            # if last search was recent, do not refresh the session
            # moji search is connected via racing in this project. if too many connections at the same time, the session will fail
            # when keep alive session is running, there is a small chance that it coincides with a real search. In this case, session number will double and real session might fail
            # to lower this probability, keep alive session will not run if a real search happend recently
            last_moji_search_time = time.time()
            for _ in range(3):  # used for racing. 3 try for each moji search
                threading.Thread(target=search_mojidict_exact,
                                 args=('テスト', dummy, dummy_event),
                                 daemon=True).start()
                threading.Thread(target=search_mojidict_fuzzy,
                                 args=('テスト', dummy, dummy_event),
                                 daemon=True).start()
        time.sleep(5)


# Mouse hook constants
WH_MOUSE_LL = 14
WM_LBUTTONDOWN = 0x0201
WM_RBUTTONDOWN = 0x0204
WM_MBUTTONDOWN = 0x0207
WM_XBUTTONDOWN = 0x020B
WM_MOUSEWHEEL = 0x020A
WM_RBUTTONUP = 0x0205


class MSLLHOOKSTRUCT(Structure):
    _fields_ = [
        ("pt", wintypes.POINT),
        ("mouseData", c_ulong),
        ("flags", c_ulong),
        ("time", c_ulong),
        ("dwExtraInfo", c_ulong),
    ]


def _wm_to_btn_str(wParam, lParam):
    """Convert WM mouse message to button string matching config format."""
    if wParam == WM_MBUTTONDOWN:
        return 'middle'
    if wParam == WM_RBUTTONDOWN:
        return 'right'
    if wParam == WM_XBUTTONDOWN:
        xbtn = (
            cast(lParam, POINTER(MSLLHOOKSTRUCT))[0].mouseData >> 16) & 0xFFFF
        return f'x{xbtn}'
    return None


def _mouse_hook_proc(nCode, wParam, lParam):
    global lock_length, _rb_down_suppressed, last_slider_time_ms, hide_on_click
    if nCode >= 0 and pressed_mouse_hotkey(wParam, lParam):  # HKDEBUG
        hk_log(f'MOUSE {_wm_to_btn_str(wParam, lParam)}')    # HKDEBUG

    def passthrough():
        return windll.user32.CallNextHookEx(None, nCode, wParam,
                                            c_longlong(lParam))

    if nCode < 0 or hotkey_mode == -1:
        return passthrough()

    if hotkey_mode == 0:
        if wParam in (WM_RBUTTONDOWN, WM_MBUTTONDOWN, WM_XBUTTONDOWN):
            btn_str = _wm_to_btn_str(wParam, lParam)
            if btn_str:
                hk = {'type': 'mouse', 'button': btn_str}
                update_config('hotkey', [hk])
                window.hotkey_captured_signal.emit()
        return passthrough()

    elif hotkey_mode == 1:
        if wParam in (WM_RBUTTONDOWN, WM_MBUTTONDOWN, WM_XBUTTONDOWN):
            if pressed_mouse_hotkey(wParam, lParam):
                if time.time() - _snip_open_close_time > 0.1:
                    on_click_snip()
                return 1
        if wParam == WM_RBUTTONUP:
            if _rb_down_suppressed:
                _rb_down_suppressed = False
                return 1
        if wParam == WM_LBUTTONDOWN:
            if window.isVisible():
                info = cast(lParam, POINTER(MSLLHOOKSTRUCT))[0]
                if hide_on_click and QApplication.activePopupWidget() is None and not window.geometry().contains(QPoint(info.pt.x,info.pt.y)) and window.stack.currentIndex() != 1:
                    window.hide_signal.emit()
                    hide_on_click = False
        return passthrough()

    elif hotkey_mode == 2:
        if wParam == WM_LBUTTONDOWN:
            info = cast(lParam, POINTER(MSLLHOOKSTRUCT))[0]
            hwnd = windll.user32.WindowFromPoint(info.pt)
            pid = c_ulong()
            windll.user32.GetWindowThreadProcessId(hwnd, byref(pid))
            return passthrough() if pid.value == os.getpid() else 1

        if wParam == WM_RBUTTONDOWN:
            if time.time() - _snip_open_close_time > 0.1:
                if snip.dragging:
                    window.cancel_drag_signal.emit()
                else:
                    window.close_snip_signal.emit(False)
            _rb_down_suppressed = True
            return 1
        elif pressed_mouse_hotkey(wParam, lParam):
            if time.time() - _snip_open_close_time > 0.1:
                window.close_snip_signal.emit(False)
            return 1

        if wParam == WM_MOUSEWHEEL:
            info = cast(lParam, POINTER(MSLLHOOKSTRUCT))[0]
            delta = c_short(info.mouseData >> 16).value
            window.scroll_signal.emit(1 if delta > 0 else -1)
            return 1
        return passthrough()

    return passthrough()


def pressed_mouse_hotkey(wParam, lParam):
    btn_str = _wm_to_btn_str(wParam, lParam)
    if btn_str and any(h['type'] == 'mouse' and h['button'] == btn_str
                       for h in config['hotkey']):
        return True
    return False


def _start_mouse_hook():
    """Start the low-level mouse hook in its own thread."""
    HOOKPROC = WINFUNCTYPE(c_long, c_int, wintypes.WPARAM, wintypes.LPARAM)
    cb = HOOKPROC(_mouse_hook_proc)
    # Override argtypes set by pynput to use our own HOOKPROC type
    windll.user32.SetWindowsHookExW.argtypes = [
        c_int, HOOKPROC, c_void_p, c_ulong
    ]
    windll.user32.SetWindowsHookExW.restype = c_void_p
    hook = windll.user32.SetWindowsHookExW(WH_MOUSE_LL, cb, None, 0)
    msg = wintypes.MSG()
    while windll.user32.GetMessageW(byref(msg), None, 0, 0) != 0:
        windll.user32.TranslateMessage(byref(msg))
        windll.user32.DispatchMessageW(byref(msg))
    windll.user32.UnhookWindowsHookEx(hook)


current_modifiers = set()  # tracks currently held modifier keys
MODIFIER_KEYS = {
    keyboard.Key.ctrl,
    keyboard.Key.ctrl_l,
    keyboard.Key.ctrl_r,
    keyboard.Key.shift,
    keyboard.Key.shift_l,
    keyboard.Key.shift_r,
    keyboard.Key.alt,
    keyboard.Key.alt_l,
    keyboard.Key.alt_r,
}


def on_press(key):
    global current_modifiers, lock_length
    if key in MODIFIER_KEYS:
        current_modifiers.add(key)
    if pressed_keyboard_hotkey(key):   # HKDEBUG
        hk_log(f'KEY {key}')           # HKDEBUG
    if hotkey_mode == 0:
        if key not in MODIFIER_KEYS:  # only record when a non-modifier key is pressed
            mods = []
            if any(k in current_modifiers
                   for k in (keyboard.Key.ctrl, keyboard.Key.ctrl_l,
                             keyboard.Key.ctrl_r)):
                mods.append('ctrl')
            if any(k in current_modifiers
                   for k in (keyboard.Key.shift, keyboard.Key.shift_l,
                             keyboard.Key.shift_r)):
                mods.append('shift')
            if any(k in current_modifiers
                   for k in (keyboard.Key.alt, keyboard.Key.alt_l,
                             keyboard.Key.alt_r)):
                mods.append('alt')

            canonical = keyboard_listener.canonical(key)
            if hasattr(canonical, 'char'
                       ) and canonical.char and canonical.char.isprintable():
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
                key_str = f'Key.{matched.name}' if matched else str(
                    canonical.vk)

            hk = {'type': 'keyboard', 'modifiers': mods, 'key': key_str}
            update_config('hotkey', [hk])
            window.hotkey_captured_signal.emit()
    elif hotkey_mode == 1:
        if pressed_keyboard_hotkey(key):
            on_click_snip()
        if any(k in current_modifiers
               for k in (keyboard.Key.ctrl, keyboard.Key.ctrl_l,
                         keyboard.Key.ctrl_r)):  # for copy in window
            canonical = keyboard_listener.canonical(key)
            if hasattr(canonical, 'char'
                       ) and canonical.char and canonical.char.lower() == 'c':
                if window.isVisible():
                    selected = (widget_selected_text(window.label_spell)
                                or widget_selected_text(window.label_pron)
                                or widget_selected_text(window.label_excerpt))
                    if selected:
                        window.copy_text_signal.emit(selected)
    elif hotkey_mode == 2:
        step = max(snip.slider.maximum() // 4, 2)
        if key == keyboard.Key.up:
            window.slider_set_signal.emit(snip.slider.value() - 4)
        elif key == keyboard.Key.down:
            window.slider_set_signal.emit(snip.slider.value() + 4)
        elif key == keyboard.Key.left:
            window.slider_set_signal.emit(snip.slider.value() - 1)
        elif key == keyboard.Key.right:
            window.slider_set_signal.emit(snip.slider.value() + 1)
        elif key == keyboard.Key.page_up:
            window.slider_set_signal.emit(snip.slider.value() - step)
        elif key == keyboard.Key.page_down:
            window.slider_set_signal.emit(snip.slider.value() + step)
        elif key == keyboard.Key.home:
            window.slider_set_signal.emit(snip.slider.minimum())
        elif key == keyboard.Key.end:
            window.slider_set_signal.emit(snip.slider.maximum())
        elif key == keyboard.Key.esc or pressed_keyboard_hotkey(key):
            window.close_snip_signal.emit(False)


def pressed_keyboard_hotkey(key):
    if key not in MODIFIER_KEYS:
        for h in config['hotkey']:
            if h['type'] == 'keyboard':
                mods = h.get('modifiers', [])
                key_match = h.get('key', '')
                # Check modifiers
                ctrl_ok = ('ctrl'
                           in mods) == any(k in current_modifiers
                                           for k in (keyboard.Key.ctrl,
                                                     keyboard.Key.ctrl_l,
                                                     keyboard.Key.ctrl_r))
                shift_ok = ('shift'
                            in mods) == any(k in current_modifiers
                                            for k in (keyboard.Key.shift,
                                                      keyboard.Key.shift_l,
                                                      keyboard.Key.shift_r))
                alt_ok = ('alt' in mods) == any(k in current_modifiers
                                                for k in (keyboard.Key.alt,
                                                          keyboard.Key.alt_l,
                                                          keyboard.Key.alt_r))
                if ctrl_ok and shift_ok and alt_ok:
                    canonical = keyboard_listener.canonical(key)
                    if hasattr(
                            canonical, 'char'
                    ) and canonical.char and canonical.char.isprintable():
                        pressed_key_str = canonical.char
                    elif isinstance(canonical, keyboard.Key):
                        pressed_key_str = f'Key.{canonical.name}'
                    else:
                        matched = None
                        for k in keyboard.Key:
                            if hasattr(k.value,
                                       'vk') and k.value.vk == canonical.vk:
                                matched = k
                                break
                        pressed_key_str = f'Key.{matched.name}' if matched else str(
                            canonical.vk)
                    if pressed_key_str == key_match:
                        return True
    return False


def on_release(key):
    global current_modifiers
    if key in MODIFIER_KEYS:
        current_modifiers.discard(key)


# ==== HKDEBUG BEGIN — delete this whole block when done =====================
HK_DEBUG = True


def hk_log(what):
    """One line per press of the configured hotkey, dumping everything that
    can affect whether the hotkey fires and whether snip can be exited.
    Runs on the mouse-hook thread, so every read is defensive: one broken
    field must never cost the whole line."""
    if not HK_DEBUG:
        return

    def g(fn):
        try:
            return fn()
        except Exception as e:
            return f'<{type(e).__name__}>'

    try:
        s = globals().get('snip')
        w = globals().get('window')
        now = time.time()
        stamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        print(' | '.join([
            f'[HK {stamp}] {what}',
            # what decides whether the hotkey fires at all
            f'mode={hotkey_mode}'
            f' hk={g(lambda: config["hotkey"])}'
            f' since_openclose={round(now - _snip_open_close_time, 2)}'
            f' rb_supp={_rb_down_suppressed}'
            f' mods={g(lambda: sorted(str(m)[4:] for m in current_modifiers))}'
            f' kb_alive={g(lambda: keyboard_listener.is_alive())}',
            # snip state: a stuck drag / virtual cursor blocks the exit
            f'snip#{g(lambda: id(s) % 100000 if s is not None else None)}'
            f' vis={g(lambda: s.isVisible())}'
            f' drag={getattr(s, "dragging", "?")}'
            f' pos={getattr(s, "start_pos", "?")}->{getattr(s, "end_pos", "?")}'
            f' raw_on={getattr(s, "_raw_on", "?")}'
            f' vmode={getattr(s, "_vmode", "?")}'
            f' vdrag={getattr(s, "_vslider_drag", "?")}'
            f'/{getattr(s, "_vpanel_drag", "?")}'
            f' vhover={getattr(s, "_vhover", "?")}'
            f' slider={g(lambda: s.slider.value())}'
            f'/{g(lambda: s.slider.maximum())}'
            f' scroll={getattr(s, "_scroll_step", "?")}'
            f' last_ms={getattr(s, "last_slider_time_ms", "?")}',
            # close_snip does screenshot[slider.value()] -> IndexError risk
            f'shots={g(lambda: len(screenshot))}'
            f' shot_thread={g(lambda: screenshot_thread_handle.is_alive())}'
            f' shot_stop={g(lambda: screenshot_thread_stop.is_set())}',
            # window + signal wiring; close_recv > 1 means duplicate connects
            f'win_vis={g(lambda: w.isVisible())}'
            f' page={g(lambda: w.stack.currentIndex())}'
            f' hide_on_click={globals().get("hide_on_click", "?")}'
            f' lock={globals().get("lock_length", "?")}'
            f' close_recv={g(lambda: w.receivers(w.close_snip_signal))}',
        ]))
    except Exception as e:
        print(f'[HK] log failed: {e!r}')
# ==== HKDEBUG END ==========================================================


_snip_open_close_time = 0
_rb_down_suppressed = False


def _snip_scroll(delta):
    snip._scroll_step = min(snip._scroll_step * 1.1 + 1, 4)
    snip._scroll_timer.start()
    step = snip.slider.singleStep() * snip._scroll_step
    if delta > 0:
        snip.slider.setValue(snip.slider.value() - int(step))
    elif delta < 0:
        snip.slider.setValue(snip.slider.value() + int(step))


def force_activate(hwnd):
    foreground_hwnd = windll.user32.GetForegroundWindow()
    foreground_tid = windll.user32.GetWindowThreadProcessId(
        foreground_hwnd, None)
    current_tid = windll.kernel32.GetCurrentThreadId()
    if foreground_tid != current_tid:
        windll.user32.AttachThreadInput(foreground_tid, current_tid, True)
        windll.user32.SetForegroundWindow(hwnd)
        windll.user32.AttachThreadInput(foreground_tid, current_tid, False)
    else:
        windll.user32.SetForegroundWindow(hwnd)


def convert_max_fps(
):  # convert max_fps tier to show current tier's range and total frame
    global max_fps
    # fps at a later time cannot be bigger than earlier time because it would have already been deleted
    for i in range(0, len(max_fps)):
        for j in range(i + 1, len(max_fps)):
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
            current_layer_start = max_fps[i - 1][0]
        max_fps[i].append(
            int((max_fps[i][0] - current_layer_start) * max_fps[i][1]))
        max_fps[i][0] *= 1000  # convert to ms


class CvMat(c_void_p):
    pass


class OcrHandle(c_void_p):
    pass


GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080


def show_and_exclude_from_capture(window, no_activate=True):
    user32.SetWindowDisplayAffinity.argtypes = [wintypes.HWND, wintypes.DWORD]
    user32.SetWindowDisplayAffinity.restype = wintypes.BOOL
    with lock:
        window.show()
        hwnd = int(window.winId())
        if no_activate:
            # a dialog needs to stay activatable: NOACTIVATE costs it the
            # keyboard, and TOOLWINDOW means nothing for a modal box
            ex_style = windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE,
                                         ex_style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW)
        user32.SetWindowDisplayAffinity(hwnd, 0)
        ok = user32.SetWindowDisplayAffinity(hwnd, 0x00000011)

    #if not ok:
    #raise WinError(get_last_error())


def frame_interview(fps, cut_target, delete_frame_index):
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
        current_layer_deadline = this_screenshot_time - fps[current_layer -
                                                            1][0]
    current_layer_frame_interval = 1000 / fps[current_layer][1]
    ideal_frame_time = this_screenshot_time - fps[current_layer][0]
    best_candidate = -1

    for i in range(lock_length, len(screenshot)):

        if screenshot[i][2]:  # If this frame is not to be deleted yet
            if screenshot[i][1] > current_layer_deadline:
                # check next layer
                if current_layer > 0:
                    current_layer -= 1
                    current_layer_deadline = this_screenshot_time - fps[
                        current_layer - 1][0]
                current_layer_frame_interval = 1000 / fps[current_layer][1]
            if ideal_frame_time <= screenshot[i][
                    1] - current_layer_frame_interval:
                # check if multiple frames need to be skipped
                ideal_frame_time = current_layer_deadline - int(
                    math.ceil((current_layer_deadline - screenshot[i][1]) /
                              current_layer_frame_interval)
                ) * current_layer_frame_interval
                best_candidate = -1
            # compete with previous candidate
            if best_candidate != -1:
                if screenshot[i][1] > screenshot[best_candidate][1]:
                    lost_candidate = i
                else:
                    lost_candidate = best_candidate
                    best_candidate = i
                screenshot[lost_candidate][
                    2] = False  # previous best candidate need delete
                if screenshot[lost_candidate][1] != getattr(
                        snip, 'last_slider_time_ms',
                        None):  # bypass last slider
                    delete_frame_index.add(lost_candidate)
                total_deleted_frame += 1
                if cut_target != -1:
                    if total_deleted_frame >= cut_target:
                        break
            else:
                best_candidate = i
    return total_deleted_frame


system_drive = os.environ.get("SystemDrive",
                              "C:") + "\\"  # for disk calculation


def screenshot_login():
    global screenshot_users, lock_length
    with lock:  # lock screenshot length to avoid deleting frames when it is used by main thread
        screenshot_users += 1
        lock_length = len(screenshot)  # lock screenshot length to avoid deleting frames when it is used by main thread


def screenshot_logout():
    global screenshot_users, lock_length
    with lock:  # lock screenshot length to avoid deleting frames when it is used by main thread
        screenshot_users -= 1
        if screenshot_users <= 0:
            lock_length = 0
    print(screenshot_users)


def screenshot_thread():
    global this_screenshot_time, high_cpu_seconds
    sct = mss()
    mon = sct.monitors[config['monitor_index']]  # test
    while True:
        qimg_rgb, width, height = screenshot_qimg_rgb(sct, mon)
        
        screenshot.append([qimg_rgb, this_screenshot_time, True])

        # reset delete index
        delete_frame_index = set()
        for i in range(len(screenshot)):
            screenshot[i][2] = True

        # delete picture outside max fps range
        delete_due_to_max_fps = frame_interview(max_fps, -1,
                                                delete_frame_index)

        process = psutil.Process(os.getpid())
        python_memory = process.memory_info().rss

        if python_memory / 1073741824 < min_memory_gb:
            cut_target = 0
        else:
            vm = psutil.virtual_memory()
            total_memory = vm.total
            used_memory = vm.used
            max_memory_byte = (total_memory - used_memory +
                               python_memory) * max_memory_percentage

            free_disk = shutil.disk_usage(system_drive).free
            max_disk_byte = free_disk * max_disk_percentage

            max_byte = min(max_memory_byte, max_disk_byte)
            excess_memory_byte = python_memory - max_byte
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
                    lock_time = screenshot[lock_length - 1][1]
                else:
                    lock_time = 0
                cut_start_time = min(
                    max(this_screenshot_time - lock_time, previous_layer_end),
                    current_fps[i][0])
                current_fps[i][2] = int(
                    current_fps[i][2] * (cut_start_time - previous_layer_end) /
                    (current_fps[i][0] - previous_layer_end))
                previous_layer_end = current_fps[i][0]
            planned_cut = 0
            frame_cut = cut_target - delete_due_to_max_fps
            for k in range(frame_cut):
                cut_layer = 0
                for i in range(1, len(current_fps)):
                    if current_fps[i][2] >= current_fps[cut_layer][2]:
                        cut_layer = i
                if current_fps[cut_layer][2] > 1:
                    planned_cut += int(current_fps[cut_layer][2] / 2)
                    current_fps[cut_layer][1] /= 2
                    current_fps[cut_layer][2] = current_fps[cut_layer][
                        2] - int(current_fps[cut_layer][2] / 2)
                else:
                    break
                if cut_target <= planned_cut:
                    break
            frame_interview(current_fps, cut_target, delete_frame_index)

        # delete first screenshot if it is too old
        # there is a limitation in frame_interview that first screenshot will never be deleted
        if len(screenshot) > 1:
            if screenshot[0][1] < this_screenshot_time - max_fps[-1][
                    0] and lock_length == 0:
                delete_frame_index.add(0)

        # delete frame
        if delete_frame_index:
            with lock:  # check and delete must be atomic to avoid deleting frames when it is used by main thread
                if min(delete_frame_index) >= lock_length:
                    screenshot[:] = [
                        x for i, x in enumerate(screenshot)
                        if i not in delete_frame_index
                    ]

        # get highest current fps
        highest_fps = 0
        for i in range(len(current_fps)):
            if current_fps[i][1] > highest_fps:
                highest_fps = current_fps[i][1]
        # low fps mode if cpu is full
        cpu = psutil.cpu_percent(interval=0)
        if cpu > 95:
            high_cpu_seconds += 1 / highest_fps
        else:
            high_cpu_seconds -= 2 / highest_fps
            high_cpu_seconds = min(max(high_cpu_seconds, 0), 10)
        if high_cpu_seconds > 5:
            highest_fps = min(2, highest_fps)
            print('cpu is ' + str(cpu))  # test test need delete

        if hotkey_mode == 2 or not round_audio_analysis_start_time_done.is_set():
            highest_fps = min(1, highest_fps)

        lowest_frame_interval = 1000 / highest_fps

        if screenshot_thread_stop.is_set():  # check if stop event from config
            return

        # decide time of next screenshot time
        # to save resource, screenshot frequency will not be faster than current hight fps
        # to avoid rounding issue in future calculation, next screenshot time is based on multiple of frame interval
        t = time.time() * 1000
        next_screenshot_time = this_screenshot_time + (int(
            (t - this_screenshot_time) /
            lowest_frame_interval) + 1) * lowest_frame_interval
        sleep_time = (next_screenshot_time - t) / 1000
        # print((t-this_screenshot_time)/1000)  # test, show how long it takes
        # print('len of screenshot ' + str(len(screenshot)))
        # print(current_fps)
        this_screenshot_time = next_screenshot_time

        time.sleep(sleep_time)


class Bridge(QObject):
    click_snip = pyqtSignal()
    anki_new_note_done = pyqtSignal(float, str, str)


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


def screenshot_qimg_rgb(sct, mon):
    with lock:
        img = sct.grab(mon)

    width = img.width
    height = img.height
    qimg = QImage(img.bgra, width, height, width * 4, QImage.Format_ARGB32)

    return qimg.convertToFormat(QImage.Format_RGB888), width, height


def prune_play_log():
    # drop plays whose end is older than the audio buffer window
    cutoff = time.time() - BUFFER_SECONDS
    play_log[:] = [(s, e) for (s, e) in list(play_log) if e >= cutoff]


# --- raw-input structs: virtual cursor for games that lock the mouse ---
# such games re-center the cursor every frame (SetCursorPos), poisoning
# cursor POSITIONS, but relative WM_INPUT deltas keep flowing untouched
WM_INPUT = 0x00FF
RIDEV_INPUTSINK = 0x00000100
RIDEV_REMOVE = 0x00000001
RID_INPUT = 0x10000003
RIM_TYPEMOUSE = 0
MOUSE_MOVE_ABSOLUTE = 0x0001
RI_MOUSE_LEFT_BUTTON_DOWN = 0x0001
RI_MOUSE_LEFT_BUTTON_UP = 0x0002


class RAWINPUTDEVICE(Structure):
    _fields_ = [('usUsagePage', wintypes.USHORT), ('usUsage', wintypes.USHORT),
                ('dwFlags', wintypes.DWORD), ('hwndTarget', c_void_p)]


class RAWINPUTHEADER(Structure):
    _fields_ = [('dwType', wintypes.DWORD), ('dwSize', wintypes.DWORD),
                ('hDevice', c_void_p), ('wParam', c_void_p)]


class RAWMOUSE(Structure):
    _fields_ = [('usFlags', wintypes.USHORT),
                ('_pad', wintypes.USHORT),          # align union to 4 bytes
                ('usButtonFlags', wintypes.USHORT),
                ('usButtonData', wintypes.USHORT),
                ('ulRawButtons', wintypes.ULONG),
                ('lLastX', wintypes.LONG), ('lLastY', wintypes.LONG),
                ('ulExtraInformation', wintypes.ULONG)]


class RAWINPUT(Structure):
    _fields_ = [('header', RAWINPUTHEADER), ('mouse', RAWMOUSE)]


class Snip(QWidget):

    def __init__(self):
        super().__init__(
            None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)

        self.start_pos = None
        self.end_pos = None
        self.dragging = False
        self.last_slider_time_ms = -1

        self._vmode = False       # virtual-cursor mode (mouse-locking game)
        self._raw_on = False
        self._vpos = QPoint(0, 0)

        self.audio_start_time = 0
        self.audio_end_time = 0
        self.audio = None

        self.sct = mss()
        self.mon = self.sct.monitors[config['monitor_index']]  # test
        self.setGeometry(self.mon["left"], self.mon["top"], self.mon["width"],
                         self.mon["height"])

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
        self.slider.setGeometry(pad, pad, slider_w - pad * 2,
                                slider_h - pad * 2)

        self.slider.show()
        self.slider.setCursor(Qt.ArrowCursor)
        self.slider.valueChanged.connect(self.on_slider_changed)
        self.slider_container.setObjectName("slider_container")
        self.slider_container.setStyleSheet(
            "#slider_container{border:2px solid transparent;}#slider_container:hover{border:2px solid white;}"
        )
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
            self.hint_label.setStyleSheet(
                f"color: rgba(255,255,255,180); background: transparent; font-size: {font_size}px;"
            )
            fm = self.hint_label.fontMetrics()
            font_h = fm.height() + fm.leading()
            label_y = slider_h + (hint_h - font_h) // 2
            self.hint_label.setGeometry(0, label_y, slider_w, font_h)
            self.hint_label.show()

    def _reset_scroll_speed(self):
        """Reset step multiplier when scrolling stops."""
        self._scroll_step = 1

    def on_slider_changed(self, value):
        self.on_slider_changed_task(value)
        self.update()

    def on_slider_changed_task(self, value):
        self.background = screenshot[value][0]
        self.snip_time = screenshot[value][1] / 1000

    def _fix_slider_hover(self):
        pos = self.slider_container.mapFromGlobal(QCursor.pos())
        if self.slider_container.rect().contains(pos):
            self.slider_container.setAttribute(Qt.WA_UnderMouse, True)

    def start(self):
        global lock_length, screenshot_users, hide_on_click, _spell_index_thread
        check_processing(round_display)
        if config['anki_combine_dup']:
            # refresh the note index for THIS round; anki add/merge joins
            # this thread first (a stale index degrades to a plain add)
            _spell_index_thread = threading.Thread(
                target=rebuild_spell_index, kwargs={'wait_prev': True},
                daemon=True)
            _spell_index_thread.start()
        screenshot_login()
        screenshot[lock_length - 1][0], _, _, = screenshot_qimg_rgb(
            self.sct, self.mon)
        screenshot[lock_length - 1][1] = time.time() * 1000

        hide_on_click = True

        self.setUpdatesEnabled(False)
        self.slider.blockSignals(True)
        if not window.isVisible():
            self.last_slider_time_ms = -1
        if self.last_slider_time_ms == -1:
            start_snip_index = lock_length - 1
        else:
            for i in range(lock_length - 1, -1, -1):
                if screenshot[i][1] < self.last_slider_time_ms:
                    break
                else:
                    start_snip_index = i
            if not start_snip_index:
                start_snip_index = lock_length - 1
        self.slider.setRange(0, lock_length - 1)
        start_snip_index = lock_length - 1  # test
        self.slider.setValue(start_snip_index)  # test. need to use moving average
        self.slider.blockSignals(False)
        self.on_slider_changed_task(start_snip_index)
        self.setUpdatesEnabled(True)
        self.update()
        show_and_exclude_from_capture(self)
        #self.activateWindow()
        self.audio = None
        prune_play_log()
        self._raw_input_begin()

    def eventFilter(self, obj, event):

        if obj == self.slider:
            if event.type() == QEvent.MouseButtonPress and event.button(
            ) == Qt.LeftButton:
                opt = QStyleOptionSlider()
                self.slider.initStyleOption(opt)
                handle_rect = self.slider.style().subControlRect(
                    QStyle.CC_Slider, opt, QStyle.SC_SliderHandle, self.slider)
                # Click on handle -> let Qt handle drag normally
                if handle_rect.contains(event.pos()):
                    return False
                # Click on track -> jump to position
                x = event.pos().x()
                ratio = x / self.slider.width()
                value = self.slider.minimum() + ratio * (
                    self.slider.maximum() - self.slider.minimum())
                self.slider.setValue(round(value))
                return True

        if obj == self.slider_container:
            if event.type() == QEvent.MouseButtonPress:
                if event.button(
                ) == Qt.LeftButton and not self.slider.geometry().contains(
                        event.pos()):
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

        if self._vmode:
            vp = self._vpos
            kind = getattr(self, '_vcursor_kind', 'cross')
            if kind == 'arrow':
                # windows-style pointer, tip at the virtual position
                pts = QPolygon([QPoint(vp.x() + dx, vp.y() + dy)
                                for dx, dy in ((0, 0), (0, 17), (4, 13),
                                               (7, 20), (10, 19), (7, 12),
                                               (12, 12))])
                p.setPen(QPen(QColor(0, 0, 0), 1))
                p.setBrush(QColor(255, 255, 255))
                p.drawPolygon(pts)
                p.setBrush(Qt.NoBrush)
            else:
                arm = 14 if kind == 'move' else 12
                p.setPen(QPen(QColor(0, 0, 0), 3))
                p.drawLine(vp.x() - arm, vp.y(), vp.x() + arm, vp.y())
                p.drawLine(vp.x(), vp.y() - arm, vp.x(), vp.y() + arm)
                p.setPen(QPen(QColor(255, 255, 255), 1))
                p.drawLine(vp.x() - arm, vp.y(), vp.x() + arm, vp.y())
                p.drawLine(vp.x(), vp.y() - arm, vp.x(), vp.y() + arm)
                if kind == 'move':
                    # four arrowheads -> the size-all "move" cursor
                    p.setPen(QPen(QColor(0, 0, 0), 1))
                    p.setBrush(QColor(255, 255, 255))
                    for head in (((-arm, 0), (-arm + 6, -4), (-arm + 6, 4)),
                                 ((arm, 0), (arm - 6, -4), (arm - 6, 4)),
                                 ((0, -arm), (-4, -arm + 6), (4, -arm + 6)),
                                 ((0, arm), (-4, arm - 6), (4, arm - 6))):
                        p.drawPolygon(QPolygon(
                            [QPoint(vp.x() + dx, vp.y() + dy)
                             for dx, dy in head]))
                    p.setBrush(Qt.NoBrush)

    def cancel_drag(self): 
        self.start_pos = None
        self.end_pos = None
        self.dragging = False 
        self.update()
        window.show 

    def close_snip(self, success):
        global hotkey_mode, _snip_open_close_time, lock_length
        _snip_open_close_time = time.time()
        self._raw_input_end()
        self.hide()
        self.last_slider_time_ms = screenshot[self.slider.value()][1]
        self._slider_gen = getattr(self, '_slider_gen', 0) + 1
        gen = getattr(self, '_slider_gen', 0)
        #QTimer.singleShot(3000, lambda: setattr(self, 'last_slider_time_ms', -1) if getattr(self, '_slider_gen', 0) == gen else None)
        self.start_pos = None
        self.end_pos = None
        self.dragging = False
        hotkey_mode = 1
        self._scroll_step = 1
        if not success:
            screenshot_logout()
            show_and_exclude_from_capture(window)

    # ---- raw-input virtual cursor ----
    def _raw_input_begin(self):
        # virtual cursor engages only when a game is detected yanking the
        # cursor back; normal desktop keeps the accelerated native cursor
        self._vmode = False
        p = self.mapFromGlobal(QCursor.pos())
        self._vpos = QPoint(min(max(p.x(), 0), self.width() - 1),
                            min(max(p.y(), 0), self.height() - 1))
        self._raw_sum_x = 0
        self._raw_sum_y = 0
        self._raw_start = QCursor.pos()
        rid = RAWINPUTDEVICE(1, 2, RIDEV_INPUTSINK, int(self.winId()))
        self._raw_on = bool(windll.user32.RegisterRawInputDevices(
            byref(rid), 1, sizeof(RAWINPUTDEVICE)))

    def _raw_input_end(self):
        if self._raw_on:
            rid = RAWINPUTDEVICE(1, 2, RIDEV_REMOVE, None)
            windll.user32.RegisterRawInputDevices(byref(rid), 1,
                                                  sizeof(RAWINPUTDEVICE))
            self._raw_on = False
        if self._vmode:
            self._vmode = False
            self.setCursor(Qt.CrossCursor)
            self.panel.setAttribute(Qt.WA_TransparentForMouseEvents, False)
            self.slider.setSliderDown(False)
            self._vslider_drag = False
            self._vpanel_drag = False
            if getattr(self, '_vhover', False):
                self._vhover = False
                self.slider_container.setAttribute(Qt.WA_UnderMouse, False)
                self.slider_container.update()

    def nativeEvent(self, eventType, message):
        if self._raw_on and eventType == b'windows_generic_MSG':
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_INPUT:
                self._on_raw_input(msg.lParam)
        return False, 0

    def _on_raw_input(self, lparam):
        ri = RAWINPUT()
        size = wintypes.UINT(sizeof(RAWINPUT))
        if windll.user32.GetRawInputData(c_void_p(lparam), RID_INPUT,
                                         byref(ri), byref(size),
                                         sizeof(RAWINPUTHEADER)) <= 0:
            return
        if ri.header.dwType != RIM_TYPEMOUSE:
            return
        m = ri.mouse
        if not (m.usFlags & MOUSE_MOVE_ABSOLUTE) and (m.lLastX or m.lLastY):
            self._vmouse_move(m.lLastX, m.lLastY)
        if m.usButtonFlags & RI_MOUSE_LEFT_BUTTON_DOWN:
            self._vmouse_press()
        if m.usButtonFlags & RI_MOUSE_LEFT_BUTTON_UP:
            self._vmouse_release()

    def _vmouse_move(self, dx, dy):
        if not self._vmode:
            # lock detection by NET displacement: swipe one direction and
            # a free cursor travels along with the raw deltas, while a
            # game-locked cursor is yanked back every frame and its net
            # movement stays near zero no matter how far the mouse went
            p = QCursor.pos()
            g = self.geometry()
            if (p.x() - g.left() < 5 or g.right() - p.x() < 5 or
                    p.y() - g.top() < 5 or g.bottom() - p.y() < 5):
                # pinned by a screen edge: looks like a lock, is not one
                self._raw_sum_x = self._raw_sum_y = 0
                self._raw_start = p
                return
            self._raw_sum_x += dx
            self._raw_sum_y += dy
            raw_net = abs(self._raw_sum_x) + abs(self._raw_sum_y)
            if raw_net >= 100:
                # locked = tiny fraction of raw AND under the absolute
                # bound of one frame's excursion; the cap protects against
                # low-gain (high-DPI) desktop mice on longer windows
                if (p - self._raw_start).manhattanLength() < min(
                        raw_net * 0.2, 25):
                    print('snip: virtual cursor engaged')  # test
                    self._vmode = True
                    self._vslider_drag = False
                    self._vpanel_drag = False
                    self._vhover = False
                    self._vpos = self.mapFromGlobal(p)
                    self.setCursor(Qt.BlankCursor)
                    self.panel.setAttribute(
                        Qt.WA_TransparentForMouseEvents, True)
                    self.update()
                else:
                    self._raw_sum_x = self._raw_sum_y = 0
                    self._raw_start = p
            return
        old = QPoint(self._vpos)
        nx = min(max(self._vpos.x() + dx, 0), self.width() - 1)
        ny = min(max(self._vpos.y() + dy, 0), self.height() - 1)
        self._vpos = QPoint(nx, ny)
        if getattr(self, '_vslider_drag', False):
            self._vslider_set_from_x(self._vpos.x())
        elif getattr(self, '_vpanel_drag', False):
            self.panel.move(self._vpanel_origin +
                            (self._vpos - self._vpanel_start))
        elif self.dragging and self.start_pos is not None:
            old_rect = QRect(self.start_pos, self.end_pos).normalized()
            self.end_pos = QPoint(self._vpos)
            new_rect = QRect(self.start_pos, self.end_pos).normalized()
            dirty = old_rect.united(new_rect).adjusted(-4, -4, 4, 4)
            self.update(dirty)
        # cursor shape mirrors the real-cursor rules: arrow on the
        # slider, size-all on the empty panel, crosshair elsewhere
        sl_rect = QRect(self.slider.mapTo(self, QPoint(0, 0)),
                        self.slider.size())
        if sl_rect.contains(self._vpos):
            self._vcursor_kind = 'arrow'
        elif self.panel.geometry().contains(self._vpos):
            self._vcursor_kind = 'move'
        else:
            self._vcursor_kind = 'cross'
        # hover feedback: same WA_UnderMouse trick as _fix_slider_hover
        over = self.slider_container.rect().contains(
            self.slider_container.mapFrom(self, self._vpos))
        if over != getattr(self, '_vhover', False):
            self._vhover = over
            self.slider_container.setAttribute(Qt.WA_UnderMouse, over)
            self.slider_container.update()
        self.update(QRect(old, old).adjusted(-24, -24, 28, 28))
        self.update(QRect(self._vpos, self._vpos).adjusted(-24, -24, 28, 28))

    def _vslider_set_from_x(self, x):
        # map a virtual-cursor x (overlay coords) onto the slider value
        left = self.slider.mapTo(self, QPoint(0, 0)).x()
        ratio = (x - left) / max(1, self.slider.width())
        ratio = min(max(ratio, 0.0), 1.0)
        value = self.slider.minimum() + ratio * (
            self.slider.maximum() - self.slider.minimum())
        self.slider.setValue(round(value))

    def _vmouse_press(self):
        if not self._vmode:
            return
        if self.panel.geometry().contains(self._vpos):
            sl_rect = QRect(self.slider.mapTo(self, QPoint(0, 0)),
                            self.slider.size())
            if sl_rect.contains(self._vpos):
                # on the slider: press shows the pressed handle, holding
                # and moving drags the value
                self._vslider_drag = True
                self.slider.setSliderDown(True)
                self._vslider_set_from_x(self._vpos.x())
            else:
                # on the empty panel area: drag moves the panel, same as
                # the real-cursor path in eventFilter
                self._vpanel_drag = True
                self._vpanel_start = QPoint(self._vpos)
                self._vpanel_origin = self.panel.pos()
            return
        self.start_pos = QPoint(self._vpos)
        self.end_pos = QPoint(self._vpos)
        self.dragging = True
        self.update()

    def _vmouse_release(self):
        if not self._vmode:
            return
        if getattr(self, '_vslider_drag', False):
            self._vslider_drag = False
            self.slider.setSliderDown(False)
            return
        if getattr(self, '_vpanel_drag', False):
            self._vpanel_drag = False
            return
        if not self.dragging:
            return
        self.dragging = False
        self._do_snip(QPoint(self._vpos))

    # ---- qt mouse events (real cursor; ignored in virtual mode) ----
    def mousePressEvent(self, event):
        if self._vmode:
            return
        if event.button() == Qt.LeftButton:
            self.start_pos = event.pos()
            self.end_pos = event.pos()
            self.dragging = True
            self.update()

    def mouseMoveEvent(self, event):
        if self._vmode:
            return
        if self.start_pos is None or not self.dragging:
            return

        old_rect = QRect(self.start_pos, self.end_pos).normalized()
        self.end_pos = event.pos()
        new_rect = QRect(self.start_pos, self.end_pos).normalized()
        dirty = old_rect.united(new_rect).adjusted(-4, -4, 4, 4)
        self.update(dirty)

    def mouseReleaseEvent(self, event):
        if self._vmode:
            return
        if event.button() == Qt.LeftButton and self.start_pos:
            self._do_snip(event.pos())

    def _do_snip(self, pos):
        # freeze the rubber band at the release point BEFORE waiting:
        # check_processing pumps the event loop, and without this the
        # rect keeps chasing the mouse during the wait
        self.end_pos = pos
        self.dragging = False
        self.update()
        check_processing(round_anki_audio_sent)
        rect = QRect(self.start_pos, self.end_pos).normalized()
        cropped = self.background.copy(rect)
        click_time = time.time()
        audio_bytes, audio_start_time, audio_end_time = recorder.capture_last(
            self.snip_time, click_time)  # test need move to thread
        self.close_snip(True)
        print('lock_length ' + str(lock_length - 1) + ' slider value ' +
              str(self.slider.value()))  # text
        if config['playback_hint_left'] > 0:
            if lock_length - 1 > self.slider.value(
            ):  # means slider is used by user
                n = config['playback_hint_left'] - 1
                update_config('playback_hint_left', n)
                if n <= 0:
                    self.hint_label.deleteLater()
        run_ocr_and_display(
            ocr, on_error, cropped, self.background, self.slider.value(),
            rect, audio_bytes, audio_start_time,
            audio_end_time)  # test need better thread arrangement


def run_ocr_and_display(ocr, on_error, image, qimg_full, snip_index, rect,
                        audio_bytes, audio_start_time, audio_end_time):
    round_reset()
    ocr_result = run_ocr(image, ocr, on_error, 2)

    if ocr_result:
        # if ocr successful, go search dictionary
        word = ocr_result[0][0]
        print(word)  # test
        word_info = {}
        search_dict_thread = threading.Thread(target=lambda: word_info.update(
            search_dict(word)))  # test need to consider no result
        search_dict_thread.start()

        start_pos = rect.topLeft()
        points = [
            start_pos +
            QPoint(int(ocr_result[0][1][0]), int(ocr_result[0][1][1])),
            start_pos +
            QPoint(int(ocr_result[0][1][2]), int(ocr_result[0][1][3])),
            start_pos +
            QPoint(int(ocr_result[0][1][4]), int(ocr_result[0][1][5])),
            start_pos +
            QPoint(int(ocr_result[0][1][6]), int(ocr_result[0][1][7])),
        ]  # test need to adapt to partial screen shoot
        points = quad_to_rect(points)
        pixmap = QPixmap.fromImage(qimg_full)
        window.setUpdatesEnabled(False)
        window_change_picture(pixmap)
        window.word.setText(word)
        search_dict_thread.join()
        # merge round: the EXISTING note is what the user sees - its
        # (possibly hand-edited) text wins over the fresh dict lookup;
        # this round only contributes a new capture
        merge_target = None
        if config['anki_combine_dup']:
            if _spell_index_thread is not None:
                # index snapshot must be in before the decision; timing
                # out degrades this round to a plain add
                _spell_index_thread.join(timeout=5)
            merge_target = _spell_index.get(
                norm_spell(word_info.get('spell') or ''))
            if merge_target:
                r = invoke('notesInfo', notes=[int(merge_target)])
                if r and not r.get('error') and r.get('result') \
                        and r['result'][0].get('fields'):
                    f = r['result'][0]['fields']
                    word_info['spell'] = f['spell']['value']
                    word_info['pron'] = f['pron']['value']
                    word_info['excerpt'] = f['excerpt']['value']
                    word_info['fuzzy'] = f['fuzzy']['value']
                    # the page count is known NOW: show the nav at once;
                    # flipping blocks until the round finalizes the note
                    window.show_page_signal.emit(
                        None, 0, len(parse_captures(f)) + 1)
                else:
                    merge_target = None    # unreadable -> plain add
            print('path: merge into ' + str(merge_target)
                  if merge_target else 'path: new note')
        if word_info['spell'] != '':
            window_display_word(word_info['spell'], word_info['pron'],
                                word_info['excerpt'], word_info['fuzzy'], None,
                                False, True)
            #window.setMaximumSize(16777215, 16777215)
            refresh_window(False)
            show_and_exclude_from_capture(window)
            if window.isMinimized():
                window.showNormal()
                window.raise_()
            round_display.set()
            threading.Thread(target=after_display,
                             args=(word_info, word, points, audio_bytes,
                                   snip_index, audio_start_time,
                                   audio_end_time, rect, qimg_full,
                                   merge_target),
                             daemon=True).start()
        else:  # test maybe delete, won't happen
            window_display_word_blank()
            refresh_window(False)
            show_and_exclude_from_capture(window)
            if window.isMinimized():
                window.showNormal()
                window.raise_()
            print('search dict fail for ' + word)
            screenshot_logout()
            round_finish_all()
    else:
        screenshot_logout()
        round_finish_all()
        window._toast = Toast(ui('no_ocr_result'), duration=2000)


def resize_window_height():
    content_width = window.width() - 20  # subtract left+right margins (10+10)

    h = 0
    # title bar
    h += window.findChild(DraggableTitleBar).sizeHint().height()
    # search row
    h += window.word.sizeHint().height()
    # labels
    for box in [window.label_spell, window.label_pron]:
        box.setVisible(True)
        h += box.sizeHint().height()
    ex = window.label_excerpt
    ex.setVisible(True)
    doc = ex.document()
    doc.setTextWidth(content_width)
    eh = int(math.ceil(doc.size().height())) + 8
    ex.setFixedHeight(eh)
    h += eh
    # fuzzy box: sized like excerpt, hidden entirely when empty
    fz = window.label_fuzzy
    if fz.toPlainText().strip():
        fz.setVisible(True)
        doc = fz.document()
        doc.setTextWidth(content_width)
        fh = int(math.ceil(doc.size().height())) + 8
        fz.setFixedHeight(fh)
        h += fh
    else:
        fz.setVisible(False)

    # screenshot
    if window.label_screenshot.pixmap():
        h += window.label_screenshot.sizeHint().height()
    if getattr(window, 'page_nav', None) and window.page_nav.isVisible():
        h += window.page_nav.sizeHint().height()

    window.setMinimumHeight(0)
    window.resize(window.width(), h)


def after_display(word_info, word, points, audio_bytes, snip_index,
                  audio_start_time, audio_end_time, rect, qimg_full,
                  merge_target=None):
    # create new note in anki
    word_info['word'] = word
    window._qt_caps = None
    _qt_caps_event.clear()
    word_info['position'] = '[' + str(points[0].x()) + ',' + str(
        points[0].y()) + '],[' + str(points[1].x()) + ',' + str(
            points[1].y()) + '],[' + str(points[2].x()) + ',' + str(
                points[2].y()) + '],[' + str(points[3].x()) + ',' + str(
                    points[3].y()) + ']'
    anki_new_note_time_stamp = time.time()
    anki_new_note_thread = threading.Thread(target=anki_new_note,args=(word_info,qimg_full,anki_new_note_time_stamp,merge_target),daemon=True)
    anki_new_note_thread.start()
    if len(audio_bytes) > 0:
        threading.Thread(target=process_audio,args=(audio_bytes,audio_start_time, points, snip_index, audio_end_time, rect, word, anki_new_note_time_stamp,anki_new_note_thread,word_info.get('spell') or word),daemon=True,).start()
    else:
        anki_new_note_thread.join()
        qt_note_pages_ready(anki_new_note_time_stamp)
        screenshot_logout()
        round_finish_all()


def process_audio(audio_bytes,audio_start_time,points,snip_index,audio_end_time,rect,word,anki_new_note_time_stamp,anki_new_note_thread,spell=''):

    folder_path = os.path.join(
        os.path.expanduser("~"), "Downloads", "acard",
        time.strftime("%Y%m%d_%H%M%S",
                        time.localtime(audio_start_time)))  #test need delete
    
    os.makedirs(folder_path, exist_ok=True)  #test need delete

    snip_hog, subtitle_sentences, snip_index_in_sentences, rect_small, rect_small_expanded = detect_subtitle_prepare(points, snip_index, audio_start_time, audio_end_time, rect)
    
    snip_strip = screenshot[snip_index][0].copy(rect_small)  # test need delete: grab before logout, saved in debug tail
    snip_strip_time = screenshot[snip_index][1] / 1000  # test need delete
    
    ambiguous_diff_max = 0.15
    detect_subtitle_start(snip_hog,snip_index_in_sentences,snip_index,subtitle_sentences,rect_small,rect_small_expanded,ambiguous_diff_max,folder_path)
    
    frame_duration_ms = 20

    rms, rms_moving_average = detect_audio(audio_bytes, frame_duration_ms)
    print(f"audio_bytes length: {len(audio_bytes)/recorder.BYTES_PER_SEC:.3f}s, rms frames: {len(rms)}")
    audio_wav = pcm_to_wav_bytes(audio_bytes)
    window.end_byte = None       # end of THIS capture is not known yet
    window.audio_wav = audio_wav

    start_byte, start_frame = analyze_audio_start(audio_bytes, audio_start_time, rms, rms_moving_average,
                  frame_duration_ms, snip_index_in_sentences,
                  subtitle_sentences, ambiguous_diff_max)
    round_audio_analysis_start_time_done.set()

    detect_subtitle_end(snip_hog,snip_index_in_sentences,snip_index,subtitle_sentences,rect_small,rect_small_expanded,ambiguous_diff_max,folder_path)
    screenshot_logout()
    end_byte, end_frame = analyze_audio_end(audio_bytes, audio_start_time, rms, rms_moving_average,
                frame_duration_ms, snip_index_in_sentences,
                subtitle_sentences, ambiguous_diff_max,start_frame)

    audio_bytes_after_trim, play_start_time, play_end_time = analyze_audio_trim(frame_duration_ms, rms, rms_moving_average, start_byte, start_frame, end_byte, end_frame, audio_bytes)

    audio_wav_after_trim = pcm_to_wav_bytes(audio_bytes_after_trim)

    # the note id is published by the qt main thread (anki_new_note_after)
    # AFTER the add/merge rpc chain finishes; merge rounds make extra rpc
    # calls, and a short audio analysis can finish before them, so
    # matching without waiting silently drops the audio
    round_anki_id_generated.wait(timeout=5)
    anki_id_processed = None
    anki_last_new_note_snapshot = anki_last_new_note  # avoid anki_last_new_note changed during matching
    if anki_new_note_time_stamp == anki_last_new_note_snapshot[0]:
        anki_id_processed = int(anki_last_new_note_snapshot[1])
    if anki_id_processed is None:
        print('process_audio: note id not published for this round, '
              'audio skipped')

    if anki_id_processed:
        with lock:
            if window.anki_id:
                if anki_id_processed == int(window.anki_id):
                    print(f"[WRITE process_audio] id={anki_id_processed} start={play_start_time:.3f} end={play_end_time:.3f} wavlen={len(audio_wav_after_trim) if audio_wav_after_trim else 0}")  # debug

        fields = {}
        if audio_wav_after_trim:
            audio_mp3 = wav_to_mp3(audio_wav_after_trim)
            # L0 naming: same stem as the jpg (pairing key) + play range
            # in microseconds; range field kept for the desktop reader
            audio_name = anki_upload_media(
                audio_mp3,
                anki_l0_stem(word, anki_new_note_time_stamp)
                + f'_r{round(float(play_start_time) * 1e6)}'
                + f'-{round(float(play_end_time) * 1e6)}.mp3')
            if not audio_name or audio_name.get('error') \
                    or not audio_name.get('result'):
                print('process_audio: mp3 upload FAILED:',
                      audio_name and audio_name.get('error'))
            else:
                # img tag: a sound tag would autoplay and get auto-deleted
                new_tag = f'<img src="{audio_name["result"]}">'
                # prepend to whatever the note already holds: empty for a
                # fresh note, previous captures for a merge target
                old_audio = ''
                old_shot = ''
                r = invoke('notesInfo', notes=[int(anki_id_processed)])
                if r and not r.get('error') and r.get('result') \
                        and r['result'][0].get('fields'):
                    old_audio = r['result'][0]['fields']['audio']['value']
                    old_shot = r['result'][0]['fields'][
                        'screenshot']['value']
                else:
                    print('process_audio: old audio read FAILED:',
                          r and r.get('error'))
                fields['audio'] = new_tag + old_audio
        r = invoke("updateNoteFields",
                note={
                    "id": anki_id_processed,
                    "fields": fields
                })
        if not r or r.get('error'):
            print('process_audio: updateNoteFields FAILED:',
                  r and r.get('error'))
        else:
            print('process_audio: audio field written ('
                  + str(fields.get('audio', '').count('<img')) + ' tags)')
            if fields.get('audio'):
                # the round's note (fresh or merge target) is final now:
                # let the window know its pages; badge shows for >=2 and
                # clicking the image sequences through all of them
                window._qt_caps = parse_captures({
                    'screenshot': {'value': old_shot},
                    'audio': {'value': fields['audio']},
                })
                window.show_page_signal.emit(
                    None, 0, len(window._qt_caps))
                _qt_caps_event.set()
                qt_preload_pages()
    
    anki_new_note_thread.join()
    round_finish_all()
        
    # test need delete
    import csv
    snip_strip.save(
        os.path.join(folder_path, f"{snip_strip_time:.3f}-snip.png"))
    with open(os.path.join(folder_path, "sentences.csv"), "w",
              newline="") as f:
        csv.writer(f).writerows(
            [["diff_snip", "diff_last", "frame_time", "ocr_same", "ocr_type"]
             ] + list(subtitle_sentences))

    try:
        # WAV, not mp3: sample-exact seeking, zero encoder delay, so the
        # '@..s' positions line up exactly with the byte offsets
        with open(os.path.join(folder_path, "audio.wav"), "wb") as f:
            f.write(pcm_to_wav_bytes(audio_bytes))
    except OSError as e:
        # excel's mci player may still hold the previous file open
        print('debug audio.wav write skipped:', e)
    SENTENCE_COLS = 5  # number of columns in sentences.csv
    with open(os.path.join(folder_path, 'sentences.csv'),
                'r',
                encoding='utf-8',
                newline='') as f:
        rows = list(csv.reader(f))
    for i in range(max(len(rows), len(rms))):
        if i >= len(rows): rows.append([''] * SENTENCE_COLS)
        rows[i] += [
            f'{rms[i]:.6f}' if i < len(rms) else '',
            f'{rms_moving_average[i]:.6f}'
            if i < len(rms_moving_average) else ''
        ]
    # column H row0: the snipped word (matches <time>-snip.png).
    # column I: folder, audio start, frame duration, then the twelve
    # stage results of play START/END detection; '@..s' = position
    # inside this folder's audio.mp3
    while len(rows[0]) < SENTENCE_COLS + 4:
        rows[0].append('')
    while len(rows[1]) < SENTENCE_COLS + 4:
        rows[1].append('')
    rows[0][SENTENCE_COLS + 2] = word
    # H row2: the word's box (x,y,w,h) RELATIVE to <time>-snip.png
    # (= rect_small), directly usable as a template crop box
    _wx = [p.x() for p in points]
    _wy = [p.y() for p in points]
    rows[1][SENTENCE_COLS + 2] = (
        f'{min(_wx) - rect_small.x()},{min(_wy) - rect_small.y()},'
        f'{max(_wx) - min(_wx)},{max(_wy) - min(_wy)}')
    rows[0][SENTENCE_COLS + 3] = folder_path
    rows[1][SENTENCE_COLS + 3] = f'{audio_start_time:.3f}'
    bps = recorder.BYTES_PER_SEC
    fdur = frame_duration_ms / 1000
    step_vals = [f'frame_duration_ms={frame_duration_ms}']
    start_labels = [
        'subtitle_start_time', 'subtitle_start_frame',
        'subtitle_start_frame_to_middle',
        'subtitle_start_frame_to_middle_to_side',
        'subtitle_start_frame_to_middle_to_side_after_blank_frame',
        'start_byte']
    end_labels = [
        'subtitle_end_time', 'subtitle_end_frame',
        'subtitle_end_frame_to_middle',
        'subtitle_end_frame_to_middle_to_side',
        'subtitle_end_frame_to_middle_to_side_after_blank_frame',
        'end_byte']
    for lbls, fn in ((start_labels, analyze_audio_start),
                     (end_labels, analyze_audio_end)):
        for lbl, v in zip(lbls, getattr(fn, '_dbg', [])):
            if lbl.endswith('_time'):
                t = v - audio_start_time
            elif lbl.endswith('_byte'):
                t = v / bps
            else:
                t = v * fdur
            step_vals.append(f'{lbl}={v} @{t:.3f}s')
    for i, val in enumerate(step_vals):
        while len(rows) <= i + 2:
            rows.append([''] * (SENTENCE_COLS + 4))
        while len(rows[i + 2]) < SENTENCE_COLS + 4:
            rows[i + 2].append('')
        rows[i + 2][SENTENCE_COLS + 3] = str(val)
    with open(os.path.join(folder_path, 'sentences.csv'),
                'w',
                encoding='utf-8-sig',
                newline='') as f:
        csv.writer(f).writerows(rows)


class Toast(QWidget):

    def __init__(self, message, duration=2000):
        super().__init__(
            None,
            Qt.ToolTip | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        label = QLabel(message, self)
        label.setStyleSheet(
            "background: rgba(40,40,40,220); color: white; border-radius: 6px; padding: 6px 12px; font-family: 'Microsoft YaHei'; font-size: 11px;"
        )
        label.adjustSize()
        self.resize(label.size())
        self.move(QCursor.pos() + QPoint(16, 16))
        self.show()
        QTimer.singleShot(duration, self.close)

    def dismiss(self):
        self.close()


def run_ocr(image, ocr, on_error, directional):
    bits = image.bits()
    bits.setsize(image.byteCount())

    mat = dll.cvMatFromRGB888(int(bits), image.width(), image.height(),
                              image.bytesPerLine())
    if not mat:
        raise RuntimeError('cvMatFromRGB888 failed')

    ocr_result = []

    @DetectCallback
    def on_detect(x1, y1, x2, y2, x3, y3, x4, y4, text):
        ocr_result.append(
            (text.decode('utf-8', 'ignore'), (x1, y1, x2, y2, x3, y3, x4, y4)))

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


def quad_to_rect(points, threshold=0.15, force=False):
    p0, p1, p2, p3 = points

    width = ((p1 - p0).x()**2 + (p1 - p0).y()**2)**0.5
    height = ((p3 - p0).x()**2 + (p3 - p0).y()**2)**0.5

    top_dy = abs(p1.y() - p0.y())
    bot_dy = abs(p2.y() - p3.y())
    left_dx = abs(p3.x() - p0.x())
    right_dx = abs(p2.x() - p1.x())

    if force or (top_dy / height < threshold and bot_dy / height < threshold
                 and left_dx / width < threshold
                 and right_dx / width < threshold):
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
    return QRect(round(x1 + margin), round(y1 + margin),
                 round(x2 - x1 - margin * 2), round(y2 - y1 - margin * 2))


def detect_subtitle_prepare(points, snip_index, audio_start_time, audio_end_time, rect):
    # this is because rect will be expanded vertically for further ocr
    # if no adjustment here, the ocr is more likely to become vertical
    rect_small = quad_to_smaller_rect(points)

    sentences = []
    snip_hog = compute_hog(screenshot[snip_index][0], rect_small)
    zncc_prepare_template(screenshot[snip_index][0], rect_small)

    snip_index_in_sentences = 0  # test not sure why sometimes 'snip_index_in_sentences' where it is not associated with a value without this initialize
    for i in range(lock_length):
        this_frame_time = screenshot[i][1] / 1000
        if audio_start_time <= this_frame_time and this_frame_time <= audio_end_time:
            if i == snip_index:
                snip_index_in_sentences = len(sentences)
            sentences.append([
                -1, -1, this_frame_time, -1, ''
            ])  # (diff_snip,diff_last,time,ocr_same) test need delete last

    # expand rect_small
    expand = rect_small.height() * 5
    rect_small_expanded = rect_small.adjusted(0, -expand, 0, expand)
    screen_h = screenshot[snip_index][0].height()
    if rect_small_expanded.top() < 0:
        rect_small_expanded.setTop(0)
    if rect_small_expanded.bottom() > screen_h - 1:
        rect_small_expanded.setBottom(screen_h - 1)
        
    return snip_hog, sentences, snip_index_in_sentences, rect_small, rect_small_expanded


def detect_subtitle_start(snip_hog,snip_index_in_sentences,snip_index,subtitle_sentences,rect_last_zncc,rect_expanded,ambiguous_diff_max,folder_path):
    # loop left to find start
    last_hog = snip_hog
    ocr_budget_ambiguous = 3
    ocr_budget_move = 2
    diff_frame_draft_total = 0
    for i in range(snip_index_in_sentences - 1, -1, -1):
        ocr_budget_ambiguous, ocr_budget_move, rect_last_zncc, last_hog, diff_frame_draft_total = sentences_one_compare(
            i, snip_index_in_sentences, snip_index, subtitle_sentences, rect_last_zncc,
            rect_expanded, ocr_budget_ambiguous, snip_hog,
            ocr_budget_move, last_hog, diff_frame_draft_total,ambiguous_diff_max,
            folder_path)
        screenshot[i - snip_index_in_sentences + snip_index][0].copy(
            rect_last_zncc
        ).save(
            os.path.join(
                folder_path,
                f"{screenshot[i - snip_index_in_sentences + snip_index][1]/1000:.3f}.png"
            ))  #test need delete
        

def detect_subtitle_end(snip_hog,snip_index_in_sentences,snip_index,subtitle_sentences,rect_last_zncc,rect_small_expanded,ambiguous_diff_max,folder_path):
    global lock_length, screenshot_users
    # loop left to find end
    last_hog = snip_hog
    ocr_budget_ambiguous = 3
    ocr_budget_move = 2
    diff_frame_draft_total = 0
    for i in range(snip_index_in_sentences + 1, len(subtitle_sentences)):
        ocr_budget_ambiguous, ocr_budget_move, rect_last_zncc, last_hog, diff_frame_draft_total = sentences_one_compare(
            i, snip_index_in_sentences, snip_index, subtitle_sentences, rect_last_zncc,
            rect_small_expanded, ocr_budget_ambiguous, snip_hog,
            ocr_budget_move, last_hog, diff_frame_draft_total, ambiguous_diff_max,
            folder_path)
        screenshot[i - snip_index_in_sentences + snip_index][0].copy(
            rect_last_zncc
        ).save(
            os.path.join(
                folder_path,
                f"{screenshot[i - snip_index_in_sentences + snip_index][1]/1000:.3f}.png"
            ))  #test need delete


def sentences_one_compare(i, snip_index_in_sentences, snip_index, subtitle_sentences,
                          rect_last_zncc, rect_small_expanded,
                          ocr_budget_ambiguous, snip_hog, ocr_budget_move,
                          last_hog, diff_frame_draft_total,
                          ambiguous_diff_max,folder_path):
    ambiguous_diff_min = 0.04

    k = i - snip_index_in_sentences + snip_index
    this_hog = compute_hog(screenshot[k][0], rect_last_zncc)
    diff_snip = float(np.linalg.norm(this_hog - snip_hog))
    subtitle_sentences[i][0] = diff_snip
    diff_last = float(np.linalg.norm(this_hog - last_hog))
    subtitle_sentences[i][1] = diff_last
    if diff_last > ambiguous_diff_min:
        if ambiguous_diff_min < diff_snip and diff_snip < ambiguous_diff_max and ocr_budget_ambiguous > 0:
            ocr_budget_ambiguous -= 1
            subtitle_sentences[i][4] = 1
            rect_last_zncc, this_hog = sentences_one_compare_zncc(
                i, k, rect_last_zncc, subtitle_sentences, rect_last_zncc,
                this_hog, folder_path)
        if diff_snip > ambiguous_diff_min and ocr_budget_move > 0 and subtitle_sentences[
                i][3] != 1:
            ocr_budget_move -= 1
            subtitle_sentences[i][4] = 2
            rect_last_zncc, this_hog = sentences_one_compare_zncc(
                i, k, rect_small_expanded, subtitle_sentences, rect_last_zncc,
                this_hog, folder_path)

    if subtitle_sentences[i][3] == 0 or (subtitle_sentences[i][3] == -1
                                and subtitle_sentences[i][0] > ambiguous_diff_max
                                and subtitle_sentences[i][1] > ambiguous_diff_max):
        diff_frame_draft_total += 1
    if diff_frame_draft_total >= 2:  # avoid unnecessary detect
        ocr_budget_ambiguous = 0
    return ocr_budget_ambiguous, ocr_budget_move, rect_last_zncc, this_hog, diff_frame_draft_total


# ==== ZNCC subtitle probe =================================================
# Replaces the OCR probe: the word's own pixels, cropped from the snip
# frame, are matched against later frames. One rect only - a match is
# always the template's size, so rect_small is the single source of truth.
ZNCC_THRESHOLD = 0.6      # score at or above this means "the word is here"
_zncc_tmpl = None         # template for the current detection round


def _zncc_next_pow2(n):
    p = 1
    while p < n:
        p *= 2
    return p


def qimage_to_gray(qimg_full, rect):
    """Crop -> float64 grayscale. QImage pads rows, so the buffer must be
    reshaped by bytesPerLine and only then sliced down to the real width."""
    cropped = qimg_full.copy(rect).convertToFormat(QImage.Format_Grayscale8)
    h, w = cropped.height(), cropped.width()
    if h <= 0 or w <= 0:
        return None
    ptr = cropped.bits()
    ptr.setsize(cropped.byteCount())
    arr = np.frombuffer(memoryview(ptr).tobytes(), dtype=np.uint8)
    arr = arr.reshape((h, cropped.bytesPerLine()))
    return arr[:, :w].astype(np.float64)


def zncc_prepare_template(qimg_full, rect_small):
    """Call once per detection round, on the snip frame. Zero-mean the crop
    now so every later frame only pays for the correlation."""
    global _zncc_tmpl
    _zncc_tmpl = None
    t = qimage_to_gray(qimg_full, rect_small)
    if t is None or t.size == 0:
        return
    t = t - t.mean()
    norm = float(np.sqrt((t * t).sum()))
    if norm == 0:          # flat crop: no text to match on
        return
    _zncc_tmpl = {'t': t, 'h': t.shape[0], 'w': t.shape[1], 'norm': norm}


def zncc_find(qimg_full, rect_image):
    """Best ZNCC of this round's template inside rect_image. OpenCV naming:
    the template is _zncc_tmpl, the image is the crop taken here.
    Returns (score, QPoint top-left in FULL-frame coords), or (-1.0, None)
    when it cannot be scored at all."""
    if _zncc_tmpl is None:
        return -1.0, None
    image = qimage_to_gray(qimg_full, rect_image)
    if image is None:
        return -1.0, None
    H, W = image.shape
    h, w = _zncc_tmpl['h'], _zncc_tmpl['w']
    if h > H or w > W:
        return -1.0, None
    n = float(h * w)
    fh = _zncc_next_pow2(H + h - 1)
    fw = _zncc_next_pow2(W + w - 1)
    # correlation via FFT: flip the template to turn convolution into it
    corr = np.fft.irfft2(
        np.fft.rfft2(image, (fh, fw))
        * np.fft.rfft2(_zncc_tmpl['t'][::-1, ::-1], (fh, fw)),
        (fh, fw))[h - 1:H, w - 1:W]
    # integral images give every window's sum and sum-of-squares in O(1)
    ii = np.pad(np.cumsum(np.cumsum(image, 0), 1), ((1, 0), (1, 0)))
    ii2 = np.pad(np.cumsum(np.cumsum(image * image, 0), 1), ((1, 0), (1, 0)))
    s = ii[h:, w:] - ii[:-h, w:] - ii[h:, :-w] + ii[:-h, :-w]
    s2 = ii2[h:, w:] - ii2[:-h, w:] - ii2[h:, :-w] + ii2[:-h, :-w]
    var = s2 - s * s / n
    valid = var > n * 0.5           # flat windows cannot contain text
    ncc = np.where(valid,
                   corr / (np.sqrt(np.maximum(var, 1e-9)) * _zncc_tmpl['norm']),
                   -1.0)
    ncc = np.clip(ncc, -1.0, 1.0)
    idx = int(np.argmax(ncc))
    y, x = divmod(idx, ncc.shape[1])
    return float(ncc[y, x]), QPoint(rect_image.left() + x,
                                    rect_image.top() + y)


def sentences_one_compare_zncc(i, k, rect_image, subtitle_sentences, rect_match, this_hog, folder_path):
    # ZNCC roles: the template is _zncc_tmpl, cropped once from the snip frame.
    # rect_image is the area searched in this frame - the word's own box for an
    # ambiguous probe, the expanded strip for a move probe. rect_match is where
    # the word sits now; only a successful move probe relocates it.
    score, top_left = zncc_find(screenshot[k][0], rect_image)
    screenshot[k][0].copy(rect_image).save(
        os.path.join(
            folder_path,
            f"{screenshot[k][1]/1000:.3f}-{subtitle_sentences[i][4]}.png")
    )  # need delete
    if top_left is None:        # unscorable: abstain, same as a failed OCR
        return rect_match, this_hog
    if score >= ZNCC_THRESHOLD:
        subtitle_sentences[i][3] = 1
        if subtitle_sentences[i][4] == 2:   # move probe: adopt the new spot
            rect_match = QRect(top_left.x(), top_left.y(),
                               _zncc_tmpl['w'], _zncc_tmpl['h'])
            this_hog = compute_hog(screenshot[k][0], rect_match)
    else:
        subtitle_sentences[i][3] = 0
    return rect_match, this_hog


def sentences_one_compare_ocr(i, k, rect_to_ocr, direction, subtitle_sentences, word,
                              rect_expanded, rect_last_ocr, rect_small,
                              this_hog, folder_path):
    img = screenshot[k][0].copy(rect_to_ocr)
    ocr_result = run_ocr(img, ocr, on_error, direction)
    img.save(
        os.path.join(folder_path,
                     f"{screenshot[k][1]/1000:.3f}-{subtitle_sentences[i][4]}.png")
    )  # need delete
    if ocr_result:
        matched = find_match_in_ocr_result(ocr_result, word)
        if matched:
            subtitle_sentences[i][3] = 1
            if subtitle_sentences[i][4] == 2:
                coords = matched[1]
                offset = rect_expanded.topLeft()
                points = [
                    offset + QPoint(int(coords[0]), int(coords[1])),
                    offset + QPoint(int(coords[2]), int(coords[3])),
                    offset + QPoint(int(coords[4]), int(coords[5])),
                    offset + QPoint(int(coords[6]), int(coords[7])),
                ]
                rect_list = quad_to_rect(points, force=True)
                rect_last_ocr = QRect(rect_list[0], rect_list[2])
                rect_small = quad_to_smaller_rect(points)
            this_hog = compute_hog(screenshot[k][0], rect_small)
        else:
            subtitle_sentences[i][3] = 0
        #print(f'{i}_rect_small.jpg: {ocr_result}')
    return rect_last_ocr, rect_small, this_hog


def find_match_in_ocr_result(ocr_result, word):
    # exact match first
    matched = next((r for r in ocr_result if r[0] == word), None)
    if matched:
        return matched

    # determine minimum match length based on language
    is_cjk = any('\u3000' <= c <= '\u9fff' or '\u4e00' <= c <= '\u9fff'
                 or '\u3040' <= c <= '\u30ff' for c in word)
    min_len = 2 if is_cjk else 4

    # partial match from longest to shortest
    for n in range(len(word) - 1, min_len - 1, -1):
        for candidate in [word[:n], word[-n:]]:
            matched = next(
                (r for r in ocr_result
                 if r[0] and (candidate in r[0] or r[0] in candidate)), None)
            if matched:
                return matched

    return None


def compute_hog(qimg_full, rect_small):
    cropped = qimg_full.copy(rect_small).convertToFormat(
        QImage.Format_Grayscale8)
    ptr = cropped.bits()
    ptr.setsize(cropped.byteCount())
    arr = np.array(ptr, dtype=np.float32).reshape(
        (rect_small.height(), cropped.bytesPerLine()))
    np_img = arr[:, :rect_small.width()]

    gx = np.diff(np_img, axis=1, append=np_img[:, -1:])
    gy = np.diff(np_img, axis=0, append=np_img[-1:, :])
    mag = np.sqrt(gx**2 + gy**2)
    ang = np.arctan2(gy, gx) * 180 / np.pi % 180
    hist, _ = np.histogram(ang, bins=8, range=(0, 180), weights=mag)
    return hist / (hist.sum() + 1e-8)


def window_display_word(spell, pron, excerpt, fuzzy, pixmap, change_picture, btn_enabled):
    # QApplication.focusWidget() is None while our window is inactive
    # (game in foreground), so ask the window for its focus child instead
    fw = window.focusWidget()
    if fw is not None:
        fw.clearFocus()
    if change_picture:
        window_change_picture(pixmap)
    window.label_spell.setText(spell.strip())
    window.label_pron.setText(pron.strip())
    window.label_excerpt.setHtml(excerpt.strip().removesuffix('<div><br></div>'))
    window.label_fuzzy.setHtml((fuzzy or '').strip())
    set_btn_status(btn_enabled)
    set_result_editable(btn_enabled)   # not-found -> read-only
    toggle_to_main()
    resize_window_height()
    update_save_btn_state()


def window_change_picture(pixmap):
    if hasattr(window, 'page_nav'):
        window.page_nav.hide()
    if pixmap:
        margin = window.layout().contentsMargins()
        label_width = window.width() - margin.left() - margin.right()
        scaled_pixmap = pixmap.scaled(label_width, pixmap.height(),
                                      Qt.KeepAspectRatio,
                                      Qt.SmoothTransformation)
        window.label_screenshot.setPixmap(scaled_pixmap)
    else:
        window.label_screenshot.clear()
    sync_pic_del_btn()


def pic_image_rect():
    """Where the pixmap actually sits inside the label. The label is left
    aligned and never scales a picture narrower than itself up, so this is
    NOT the widget's own rect."""
    lab = getattr(window, 'label_screenshot', None)
    pm = lab.pixmap() if lab is not None else None
    if pm is None or pm.isNull():
        return None
    return QRect(0, max(0, (lab.height() - pm.height()) // 2),
                 pm.width(), pm.height())


def sync_pic_del_btn(pos=None):
    """Show the delete cross only while the pointer is over the image, and
    park it on the image's own top-right corner. pos is in label
    coordinates; omit it to read the pointer's current position."""
    btn = getattr(window, 'pic_del_btn', None)
    if btn is None:
        return
    area = pic_image_rect()
    # nothing to delete before this round's note exists
    if area is None or not getattr(window, '_qt_caps', None):
        btn.hide()
        return
    if pos is None:
        pos = window.label_screenshot.mapFromGlobal(QCursor.pos())
    if not area.contains(pos):
        btn.hide()
        return
    btn.move(max(0, area.right() - btn.width() - 3), area.top() + 3)
    btn.show()
    btn.raise_()


def delete_current_capture():
    """Drop the displayed capture (image plus its audio) from the window
    and remember its file names. Anki is only touched on the next save."""
    global _play_session, _qt_seq_gen
    caps = getattr(window, '_qt_caps', None) or []
    idx = getattr(window, '_qt_page', 0)
    if not caps or idx >= len(caps):
        return
    cap = caps[idx]
    # cut the audio only when the capture being removed is the one
    # sounding, with the same graceful fade as deleting a whole note
    if _play_session is not None and (
            getattr(_play_session, 'src_cap', None) is cap
            or (len(caps) == 1
                and getattr(_play_session, 'src_wav', None)
                is getattr(window, 'audio_wav', None))):
        _play_session.set_end(STOP_NOW)
        _qt_seq_gen += 1              # the sequence was on this very page
    pending = getattr(window, '_qt_pending_del', None)
    if pending is None:
        pending = window._qt_pending_del = []
    for fn in (cap.get('img'), cap.get('mp3')):
        if fn and fn not in pending:
            pending.append(fn)
    # a sequence already running holds its own list object, so flag the
    # shared dict instead: it then skips this page and plays on
    cap['_deleted'] = True
    window._qt_caps = [c for c in caps if not c.get('_deleted')]
    n = len(window._qt_caps)
    window._qt_page = min(idx, n - 1) if n else 0
    update_save_btn_state()
    if not n:                          # a text-only note is legitimate
        window.audio_wav = None
        window.start_byte = window.end_byte = 0
        window_change_picture(None)
        window.show_page_signal.emit(None, 0, 0)
        resize_window_height()
        return

    def load(cs=window._qt_caps, i=window._qt_page):
        # the survivor is not necessarily the note's FIRST capture, the
        # only one get_and_display loaded, so refresh the single-page
        # playback state from it as well
        c = cs[i]
        if c.get('_jpg') is None and c['img']:
            c['_jpg'] = anki_download_media(c['img'])
        if c.get('_wav') is None and c['mp3']:
            mp3 = anki_download_media(c['mp3'])
            c['_wav'] = mp3_to_wav(mp3) if mp3 else None
        window.audio_wav = c.get('_wav')
        window.start_byte, window.end_byte = (
            _range_to_bytes(c['_wav'], c['range']) if c.get('_wav')
            else (0, 0))
        window.show_page_signal.emit(c.get('_jpg'), i, len(cs))

    threading.Thread(target=load, daemon=True).start()


def window_display_word_blank():
    window.anki_id = None
    window_display_word('', '', '', '', '', True, False)


anki_last_new_note = (None,None)  # 0 = time stamp 1 = anki_id
def anki_l0_stem(word, ts):
    # L0 media stem: sanitized word (max 18 chars) + 13-digit ms timestamp.
    # MUST be byte-identical between the jpg and mp3 of one capture: the
    # card template pairs files by everything before the LAST underscore.
    w = re.sub(r'<[^>]+>', '', word)      # hand-edited spells carry html
    w = re.sub(r'[\\/:*?"<>|_\s]', '', w)[:18] or 'word'
    return f'{w}_{int(ts * 1000)}'


def anki_l0_quad(position):
    # position field '[x1,y1],[x2,y2],[x3,y3],[x4,y4]' -> 'x1-y1-...-y4'
    # (8 dash-separated non-negative ints; all zeros = no quad)
    pts = re.findall(r'\[\s*(-?\d+)\s*,\s*(-?\d+)\s*\]', position or '')
    if len(pts) != 4:
        return '-'.join(['0'] * 8)
    return '-'.join(str(max(0, int(v))) for xy in pts for v in xy)


def _merge_bump_schedule(cards):
    # Pure Anki RPC whose result nobody downstream reads, so keep it off
    # the merge path: anki_new_note's thread is joined by process_audio,
    # and every rpc left in that path delays the audio round.
    threading.Thread(target=_merge_bump_schedule_sync,
                     args=(list(cards),), daemon=True).start()


def _merge_bump_schedule_sync(cards):
    # a merged note has fresh material and should come up soon. Cards
    # already in review: pulled to tomorrow with their interval untouched,
    # so a word grown to a 30-day interval keeps that curve instead of
    # restarting from scratch. Cards already due sooner than that are left
    # alone - rescheduling those would push them further out and add a
    # pointless manual entry to the revlog. Cards still new: stay new (the
    # daily new-card limit keeps applying) but move to the head of the
    # queue so they are the first new word served.
    # invoke() returns the whole AnkiConnect envelope {'result':..,'error':..},
    # and iterating that dict yields its key strings, not the cards
    r = invoke('cardsInfo', cards=cards)
    info = (r or {}).get('result') or []
    if not info:
        return
    review = [c['cardId'] for c in info if c.get('type') in (2, 3)]
    fresh = [c['cardId'] for c in info if c.get('type') in (0, 1)]
    if review:
        # prop:due counts whole days from today, so >1 means "later than
        # tomorrow". Letting Anki do the date maths beats deriving it from
        # the raw due field, whose unit differs per card type.
        q = 'cid:%s prop:due>1' % ','.join(str(c) for c in review)
        f = invoke('findCards', query=q)
        far = (f or {}).get('result')
        if far is None:          # query failed: keep the old behaviour
            print('merge: prop:due query failed, rescheduling all')
            far = review
        if far:
            invoke('setDueDate', cards=far, days='1')  # no "!": keeps ivl
    if not fresh:
        return
    try:
        found = invoke('findCards', query=f'deck:{DECK_NAME} is:new')
        others = invoke('cardsInfo', cards=(found or {}).get('result') or [])
        lowest = min([c['due'] for c in (others or {}).get('result') or []]
                     or [1])
    except Exception:
        lowest = 1
    for cid in fresh:
        try:
            # newValues must be an int here, a string raises
            invoke('setSpecificValueOfCard', card=cid, keys=['due'],
                   newValues=[lowest - 1], warning_check=True)
        except Exception as e:
            print('merge: reposition failed:', e)


def anki_merge_into(target_id, fields):
    # merge-by-spell: prepend this capture's screenshot to an existing
    # note; text fields stay untouched. The audio thread appends its mp3
    # to the same note later (it follows anki_last_new_note). Returns
    # False when the target cannot be read/updated -> caller adds a new
    # note instead
    r = invoke('notesInfo', notes=[int(target_id)])
    if not r or r.get('error') or not r.get('result') \
            or not r['result'][0].get('fields'):
        return False
    old = r['result'][0]['fields']
    cards = r['result'][0].get('cards') or []
    upd = {
        'screenshot': fields.get('screenshot', '')
                      + old['screenshot']['value'],
    }
    r = invoke('updateNoteFields',
               note={'id': int(target_id), 'fields': upd})
    if not r or r.get('error'):
        print('merge: updateNoteFields failed:', r and r.get('error'))
        return False
    if cards:
        _merge_bump_schedule(cards)
    print(f"merged '{fields.get('spell', '')}' into note {target_id}")
    return True


def anki_new_note(fields, qimg_full, anki_new_note_time_stamp,
                  merge_target=None):
    global anki_check_needed
    anki_check_needed = True
    anki_check_deck_and_model(False)
    if qimg_full:
        buf = QBuffer()
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        qimg_full.save(buf, "JPEG", int(config['jpeg_quality']))
        img_bytes = buf.data().data()
        # L0 naming: quad rides in the filename; the template reads it
        # from there (position field kept only for the desktop reader)
        screenshot_name = anki_upload_media(
            img_bytes,
            anki_l0_stem(fields['word'], anki_new_note_time_stamp)
            + '_p' + anki_l0_quad(fields.get('position', '')) + '.jpg')
        if screenshot_name:
            fields['screenshot'] = f'<img src="{screenshot_name["result"]}">'
    fields.pop('position', None)   # the quad lives in the filename now
    if merge_target and fields.get('screenshot'):
        if anki_merge_into(merge_target, fields):
            # the existing note becomes this round's "new note": the
            # audio thread, history and current-card logic all follow it
            bridge.anki_new_note_done.emit(anki_new_note_time_stamp,
                                           str(merge_target),
                                           fields['word'])
            return
        # unreadable target falls through to a plain add (per spec)
    if fields.get('excerpt'):
        fields['excerpt'] += '<div><br></div>'
    # word is not a field any more: it rides in the media filenames
    _word = fields.pop('word', '')
    result = invoke("addNote",
                    note={
                        "deckName": DECK_NAME,
                        "modelName": MODEL_NAME,
                        "fields": fields,
                        "options": {"allowDuplicate": True}
                    })
    if result:
        if result['error']:
            print(result['error'])
        else:
            bridge.anki_new_note_done.emit(anki_new_note_time_stamp,str(result['result']),
                                           _word)


def anki_new_note_after(anki_new_note_time_stamp,anki_id, word):
    global anki_last_new_note
    anki_last_new_note = (anki_new_note_time_stamp,anki_id)
    # a merged target may already sit in history: move it to the front
    for _it in anki_list:
        if str(_it[0]) == str(anki_id):
            anki_list.remove(_it)
            break
    anki_list.insert(0, [anki_id, word])
    if len(anki_list) > 20:
        anki_list.pop()
    window.anki_id = anki_id
    set_save_baseline()
    round_anki_id_generated.set()
    threading.Thread(target=anki_sync, daemon=True).start()


def anki_upload_media(media_byte, filename):
    filename = re.sub(r'[\\/:*?"<>|]', "", filename)
    filename = filename.lstrip(" .")
    b64 = base64.b64encode(media_byte).decode("utf-8")
    return invoke("storeMediaFile", filename=filename, data=b64)


def anki_download_media(filename):
    result = invoke("retrieveMediaFile", filename=filename)
    if result["result"] is False:
        return None
    b64 = result["result"]
    data = base64.b64decode(b64)
    return data


def anki_get_and_display(anki_id, anki_check):
    global anki_check_needed
    anki_check_needed = anki_check
    result = invoke('notesInfo', notes=[int(anki_id)])
    # test need to consider when note deleted in anki
    fields = result['result'][0]['fields']
    pixmap = QPixmap()
    pixmap.loadFromData(
        anki_download_media(fields['screenshot']['value'].split('"')[1]))
    window_display_word(fields['spell']['value'], fields['pron']['value'],
                        fields['excerpt']['value'], fields['fuzzy']['value'],
                        pixmap, True, True)
    window.word.setText('')   # word is not stored any more

    # paint the refreshed word now; audio download below may take a while
    QApplication.processEvents(QEventLoop.ExcludeUserInputEvents)

    audio_field = fields['audio']['value']  # e.g. '<img src="xxx.mp3">'
    m = re.search(r'src="([^"]+)"', audio_field)
    if m:
        mp3_bytes = anki_download_media(m.group(1))
        window.audio_wav = mp3_to_wav(mp3_bytes) if mp3_bytes else None
        # play range: L0 filename first (_r{us}-{us}); legacy field as
        # fallback; last resort = play everything
        rng = re.search(r'_r(\d+)-(\d+)\.[^.]+$', m.group(1))
        if rng and int(rng.group(2)) > int(rng.group(1)):
            start_sec = int(rng.group(1)) / 1e6
            end_sec = int(rng.group(2)) / 1e6
        else:
            try:
                start_sec, end_sec = map(
                    float, fields['range']['value'].split(','))
            except (ValueError, KeyError):
                start_sec, end_sec = 0.0, 3600.0
        # Anki persists seconds; runtime works in PCM bytes. Convert with
        # the DECODED wav's own format (mp3 output may differ from capture)
        if window.audio_wav:
            with wave.open(io.BytesIO(window.audio_wav), 'rb') as wf:
                bps = wf.getframerate() * wf.getnchannels() * wf.getsampwidth()
                fb = wf.getnchannels() * wf.getsampwidth()
            window.start_byte = int(start_sec * bps) // fb * fb
            window.end_byte = int(end_sec * bps) // fb * fb
        else:
            window.start_byte = window.end_byte = 0
        print(f"[WRITE get_and_display] id={anki_id} range={start_sec:.3f}-{end_sec:.3f} bytes={window.start_byte}-{window.end_byte} wavlen={len(window.audio_wav) if window.audio_wav else 0}")  # debug
    else:
        window.audio_wav = None
    window._qt_caps = parse_captures(fields)
    window.show_page_signal.emit(None, 0, len(window._qt_caps))
    _qt_caps_event.set()
    qt_preload_pages()
    window.anki_id = anki_id
    set_save_baseline()


def anki_delete_note():  # test need more detailed delete
    global anki_check_needed, _qt_seq_gen
    _qt_seq_gen += 1     # cancel any running page sequence
    # stop audio only if what is playing IS the note being deleted;
    # a session still playing an EARLIER capture keeps going
    if _play_session is not None and getattr(
            _play_session, 'src_wav', None) is window.audio_wav:
        _play_session.set_end(STOP_NOW)   # fade out audio of the note being deleted
    window.delete_btn.setChecked(True)
    check_processing(round_anki_id_generated)
    window.delete_btn.setChecked(False)
    anki_check_needed = True
    if window.anki_id:  # test need to consider blank
        if config['anki_combine_dup']:
            # a note holding several captures needs an explicit yes
            r = invoke('notesInfo', notes=[int(window.anki_id)])
            if r and not r.get('error') and r.get('result') \
                    and r['result'][0].get('fields'):
                if r['result'][0]['fields']['screenshot'][
                        'value'].count('<img') >= 2:
                    if not ask_front(ui('delete_dup')):
                        return
            spell_index_forget(window.anki_id)
        threading.Thread(target=invoke,
                         args=("deleteNotes", ),
                         kwargs={
                             "notes": [int(window.anki_id)]
                         },
                         daemon=True).start()
        for i in range(len(anki_list)):
            if str(anki_list[i][0]) == str(window.anki_id):
                anki_list.remove(anki_list[i])
                break
        # display the older card in list
        if anki_list:
            if i == len(
                    anki_list
            ):  # display the newer card if deleted card is the oldest one
                i -= 1
            anki_get_and_display(anki_list[i][0], False)
        else:
            window.word.setText('')
            window_display_word_blank()


# Window show states / commands (for GetWindowPlacement / SetWindowPlacement)
SW_SHOWNORMAL = 1
SW_SHOWMINIMIZED = 2
SW_SHOWMAXIMIZED = 3
SW_SHOWNOACTIVATE = 4    # show in normal state without activating (no focus steal)
SW_SHOWMINNOACTIVE = 7   # minimize without activating
SW_RESTORE = 9
class WINDOWPLACEMENT(Structure):
    _fields_ = [
        ("length", wintypes.UINT),
        ("flags", wintypes.UINT),
        ("showCmd", wintypes.UINT),
        ("ptMinPosition", wintypes.POINT),
        ("ptMaxPosition", wintypes.POINT),
        ("rcNormalPosition", wintypes.RECT),
    ]
anki_pending_note = 0
def anki_sync():
    global anki_sync_running, anki_pending_note

    # my original plan is to sync anki for every single new note
    # but anki community told me it will put too much load on server
    # so the strategy is, for new users, it will sync every single note until it reach a certain number, then only sync multiple notes together
    if config['anki_new_note_left'] > 0:
        update_config('anki_new_note_left', config['anki_new_note_left'] - 1)
    else:
        anki_pending_note += 1
        if anki_pending_note < config['anki_sync_note']:
            return
        else:
            anki_pending_note = 0

    if not anki_sync_running:
        anki_sync_running = True

        # anki will show a status of 'sync complete' after sync
        # i don't want user keep seeing this
        # the only solution i found is to move anki outside window and then move back
        anki_hwnd = user32.FindWindowW(None, None)
        while anki_hwnd:
            buf = create_unicode_buffer(256)
            user32.GetWindowTextW(anki_hwnd, buf, 256)
            if buf.value.endswith(
                    '- Anki'):  # test need better way to capture anki window
                break
            anki_hwnd = user32.GetWindow(anki_hwnd, 2)  # GW_HWNDNEXT
        else:
            anki_hwnd = None

        # Save the full original placement (state + normal size/pos) so we can
        # restore the exact same state (maximized/minimized/normal) after sync.
        orig_wp = WINDOWPLACEMENT()
        orig_wp.length = sizeof(WINDOWPLACEMENT)
        user32.GetWindowPlacement(anki_hwnd, byref(orig_wp))

        # Restore to normal (no focus steal), then move off-screen for sync.
        move_wp = WINDOWPLACEMENT()
        move_wp.length = sizeof(WINDOWPLACEMENT)
        user32.GetWindowPlacement(anki_hwnd, byref(move_wp))
        w = move_wp.rcNormalPosition.right - move_wp.rcNormalPosition.left
        h = move_wp.rcNormalPosition.bottom - move_wp.rcNormalPosition.top
        # First call: restore to normal state (no focus steal).
        move_wp.showCmd = SW_SHOWNOACTIVATE
        user32.SetWindowPlacement(anki_hwnd, byref(move_wp))

        # Now it is in normal state, move it off-screen with MoveWindow.
        user32.MoveWindow(anki_hwnd, -10000, -10000, w, h, False)

        #time.sleep(1)
        invoke("sync")
        time.sleep(10)

        # Restore original size/position, but use no-activate show commands
        # so a non-topmost window is not briefly raised (which caused a flash).
        restore_cmd_map = {
            SW_SHOWMINIMIZED: SW_SHOWMINNOACTIVE,
            SW_SHOWMAXIMIZED: SW_SHOWMAXIMIZED,  # no no-activate variant exists
            SW_SHOWNORMAL: SW_SHOWNOACTIVATE,
        }
        orig_wp.showCmd = restore_cmd_map.get(orig_wp.showCmd,
                                              SW_SHOWNOACTIVATE)
        user32.SetWindowPlacement(anki_hwnd, byref(orig_wp))

        anki_sync_running = False


def invoke(action, **params):
    global anki_check_needed
    # check if anki is open
    if not anki_connect_is_running():
        anki_path = config['anki_path']
        if anki_check_needed:
            anki_check_needed = False
            open_anki(anki_path)
        if not config['anki_connect_successful']:
            window.show_msg_signal.emit(ui('install_anki_connect'))
            return
        else:  # Poll for AnkiConnect
            deadline = time.time() + 15
            while time.time() < deadline:
                if anki_connect_is_running():
                    break
                time.sleep(0.5)
            else:
                window.show_msg_signal.emit(ui('no_anki_connection'))
                return
    return requests.post(ANKI_URL,
                         json={
                             "action": action,
                             "params": params,
                             "version": 6
                         }).json()


def anki_connect_is_running():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        is_running = (s.connect_ex((ANKI_HOST, ANKI_PORT)) == 0)
        if is_running and not config['anki_connect_successful']:
            update_config('anki_connect_successful', True)
        return is_running


def anki_merge_note_into(target_id, src_id):
    # search-merge: move ALL captures (img+mp3 tags) of note src_id to
    # the FRONT of an existing note; text fields stay untouched. Returns
    # False when either note cannot be read or the update fails
    r = invoke('notesInfo', notes=[int(src_id), int(target_id)])
    if not r or r.get('error') or not r.get('result') \
            or len(r['result']) < 2 \
            or not r['result'][0].get('fields') \
            or not r['result'][1].get('fields'):
        return False
    src = r['result'][0]['fields']
    tgt = r['result'][1]['fields']
    cards = r['result'][1].get('cards') or []
    upd = {
        'screenshot': src['screenshot']['value'] + tgt['screenshot']['value'],
        'audio': src['audio']['value'] + tgt['audio']['value'],
    }
    r = invoke('updateNoteFields',
               note={'id': int(target_id), 'fields': upd})
    if not r or r.get('error'):
        return False
    if cards:
        _merge_bump_schedule(cards)
    return True


def ask_front(text, yes_no=True):
    global hide_on_click
    # message box forced above other windows: the main window is
    # no-activate, so a plain exec_ can open behind the game
    box = QMessageBox()
    box.setWindowTitle(ui('messagebox_title'))
    box.setText(text)
    box.setStandardButtons(
        (QMessageBox.Yes | QMessageBox.No) if yes_no else QMessageBox.Ok)
    box.setWindowFlags(box.windowFlags() | Qt.WindowStaysOnTopHint)
    show_and_exclude_from_capture(box, no_activate=False)
    box.raise_()
    box.activateWindow()
    try:
        windll.user32.SetForegroundWindow(int(box.winId()))
    except Exception:
        pass
    tmp = hide_on_click
    hide_on_click = False
    ans = box.exec_()
    hide_on_click = tmp
    return ans == QMessageBox.Yes


def maybe_merge_on_save():
    # saving while the spell belongs to ANOTHER existing note: offer to
    # move this note's captures there and drop this note. Returns True
    # when merged (the normal text save is skipped: this note is gone
    # and the target's text stays untouched)
    if not config['anki_combine_dup'] or not window.anki_id:
        return False
    target = _spell_index.get(norm_spell(window.label_spell.text()))
    if not target or str(target) == str(window.anki_id):
        return False
    if not ask_front(ui('search_dup')):
        return False
    src_id = int(window.anki_id)
    if not anki_merge_note_into(target, src_id):
        ask_front(ui('search_dup_add_fail'), yes_no=False)
        return False
    r = invoke('deleteNotes', notes=[src_id])
    if not r or r.get('error'):
        print('save merge: deleteNotes failed:', r and r.get('error'))
    spell_index_forget(src_id)
    # the target becomes the current note, on top of the history
    for _it in list(anki_list):
        if str(_it[0]) in (str(src_id), str(target)):
            anki_list.remove(_it)
    anki_list.insert(0, [str(target), window.word.text()])
    window.anki_id = str(target)
    set_save_baseline()
    anki_get_and_display(window.anki_id, False)
    print(f'save merge: note {src_id} moved into {target}')
    threading.Thread(target=anki_sync, daemon=True).start()
    return True


def refresh_word():
    check_processing(round_anki_audio_sent)
    round_reset()
    word = window.word.text()
    if word:
        word_info = search_dict(word)
        window_display_word(word_info['spell'], word_info['pron'],
                            word_info['excerpt'], word_info['fuzzy'], None,
                            False, True)
    round_finish_all()


def apply_pending_deletions():
    """Commit the crosses clicked on the image: strip exactly those files
    from the note's media fields.

    Subtractive on purpose. Rebuilding these fields from _qt_caps would
    wipe a capture that anki_merge_into or process_audio prepended while
    this window was open - process_audio writes its mp3 only after the
    subtitle scan and the encode, several seconds into the round, and the
    window's snapshot is not refreshed until after that.

    Returns False when the write failed, so the caller can bail out and
    leave the save armed for a retry.
    """
    pending = getattr(window, '_qt_pending_del', None)
    if not pending:
        return True
    r = invoke('notesInfo', notes=[int(window.anki_id)])
    res = (r or {}).get('result') or []
    live = res[0].get('fields') if res else None
    if not live:
        print('save: notesInfo failed, media left untouched')
        return False
    upd = {}
    for name in ('screenshot', 'audio'):
        val = live[name]['value']
        for fn in pending:
            val = re.sub(r'<img[^>]*src="%s"[^>]*>' % re.escape(fn), '', val)
        upd[name] = val
    r = invoke('updateNoteFields',
               note={'id': int(window.anki_id), 'fields': upd})
    if not r or r.get('error'):
        print('save: media update failed:', r and r.get('error'))
        return False
    window._qt_pending_del = []
    print('save: removed %d media file(s)' % len(pending))
    return True


def save_word_qt_to_anki():
    global hide_on_click
    hide_on_click = True
    if not window.anki_id:          # nothing to update if no note shown
        return
    # saving ends the edit: drop focus so no box stays in edit mode
    fw = window.focusWidget()
    if fw is not None:
        fw.clearFocus()
    # deletions land FIRST so a merge below carries only the survivors:
    # anki_merge_note_into re-reads this note, it never sees _qt_caps
    if not apply_pending_deletions():
        return                  # write failed: leave save armed for a retry
    if maybe_merge_on_save():
        return
    word = window.word.text()
    word_info = {
        'spell': window.label_spell.text(),
        'pron': window.label_pron.text(),
        'excerpt': window.label_excerpt.toHtml(),
        'fuzzy': window.label_fuzzy.toHtml() if window.label_fuzzy.toPlainText().strip() else '',
    }

    invoke("updateNoteFields",
            note={
                "id": int(window.anki_id),
                "fields": word_info
            })
    for i in range(len(anki_list)):
        if str(anki_list[i][0]) == str(window.anki_id):
            if word:          # empty box = recalled note, keep old label
                anki_list[i][1] = word
            break
    set_save_baseline()             # content == saved now -> grey out save
    round_finish_all()
    resize_window_height()
    threading.Thread(target=anki_sync, daemon=True).start()


def refresh_history_menu():
    global hide_on_click
    hide_on_click = False   # user opened history: they need the UI
    toggle_to_main()
    window.history_menu.clear()
    check_processing(round_anki_id_generated)
    hwnd = int(window.history_menu.winId())
    user32.SetWindowDisplayAffinity(hwnd, 0)
    user32.SetWindowDisplayAffinity(hwnd, 0x00000011)
    if anki_list:
        window.history_menu.setStyleSheet(
            "QMenu::item:selected { background-color: #444; color: white; }")
        for anki_id, word in anki_list:
            action = window.history_menu.addAction(word)
            action.triggered.connect(
                partial(anki_get_and_display, anki_id, True))
    else:
        # nothing to recall: grey the placeholder with the same colour the
        # disabled save / search / delete buttons use
        window.history_menu.setStyleSheet("QMenu::item { color: grey; }")
        window.history_menu.addAction(ui('blank'))


def on_click_snip():
    global hotkey_mode, _snip_open_close_time
    hotkey_mode = 2
    _snip_open_close_time = time.time()
    bridge.click_snip.emit()


LOOKUP_ORDER = {
    # primary first; fallbacks limited to the FROM language, then English
    ('日本語', '日本語'): ('daijirin', 'jmdict'),
    ('日本語', '中文'): ('moji', 'daijirin', 'jmdict'),
    ('日本語', 'English'): ('jmdict', 'daijirin'),
    ('中文', '日本語'): ('shogakukan', 'xiandai', 'hanying'),
    ('中文', '中文'): ('xiandai', 'hanying'),
    ('中文', 'English'): ('hanying', 'xiandai'),
    ('English', '日本語'): ('genius', 'oxford_en'),
    ('English', '中文'): ('oxford_zh', 'oxford_en'),
    ('English', 'English'): ('oxford_en',),
}
SRC_LANG_CODE = {'日本語': 'ja', '中文': 'zh', 'English': 'en'}


def get_english_base_forms(word):
    """Rule-based English inflection reversal, most likely first.
    Irregular forms (ate, mice...) resolve via build-time aliases instead."""
    cands = [word]
    w = word.lower()

    def add(x):
        if len(x) >= 2 and x not in cands:
            cands.append(x)
    if w.endswith('ies') and len(w) > 4:
        add(word[:-3] + 'y')
    if w.endswith('es') and len(w) > 3:
        add(word[:-2])
        add(word[:-1])
    elif w.endswith('s') and len(w) > 3 and not w.endswith('ss'):
        add(word[:-1])
    if w.endswith('ied') and len(w) > 4:
        add(word[:-3] + 'y')
    if w.endswith('ed') and len(w) > 3:
        add(word[:-2])
        add(word[:-1])
        if len(w) > 4 and w[-3] == w[-4]:
            add(word[:-3])          # stopped -> stop
    if w.endswith('ing') and len(w) > 4:
        add(word[:-3])
        add(word[:-3] + 'e')        # making -> make
        if len(w) > 5 and w[-4] == w[-5]:
            add(word[:-4])          # running -> run
    if w.endswith('ier') and len(w) > 4:
        add(word[:-3] + 'y')        # easier -> easy
    if w.endswith('iest') and len(w) > 5:
        add(word[:-4] + 'y')
    if w.endswith('er') and len(w) > 3:
        add(word[:-2])
        add(word[:-1])
    if w.endswith('est') and len(w) > 4:
        add(word[:-3])
        add(word[:-2])
    return cands


def _norm_key(s):
    """Match build_dict.py key normalization: NFKC + strip all whitespace."""
    if not s:
        return ''
    s = unicodedata.normalize('NFKC', s)
    return re.sub(r'\s+', '', s)


def _key_rows(c, dic, w):
    return c.execute(
        "SELECT e.spell, e.pron, e.excerpt, k.key FROM keys k "
        "JOIN entries e ON e.id = k.entry_id "
        "WHERE k.dict = ? AND k.key = ? ORDER BY k.rowid",
        (dic, w)).fetchall()


def _lookup_one(c, dic, lang, w):
    # precedence: case-exact key > alias > case-insensitive key
    rows = _key_rows(c, dic, w)
    for r in rows:
        if r['key'] == w:
            return r
    first = None
    for a in c.execute(
            "SELECT target FROM aliases WHERE lang = ? AND alias = ?",
            (lang, w)).fetchall():
        trows = _key_rows(c, dic, a['target'])
        hit = None
        for r in trows:
            if r['key'] == a['target']:
                hit = r
                break
        if hit is None and trows:
            hit = trows[0]
        if hit is not None:
            if first is None:
                first = hit
            if hit['excerpt']:  # first alias target with content wins
                return hit
    if first is not None and first['excerpt']:
        return first
    if rows:
        return rows[0]
    return first
# OCR confusion table: SEEN char -> plausible TRUE chars, grouped by the
# language the TRUE char belongs to; only the src language's group is
# active. One-way entries are deliberate ('<' never lives inside a word).
# Applied to the RAW ocr string BEFORE _norm_key (NFKC would fold
# fullwidth forms and hide some SEEN keys).
OCR_CONFUSION = {
    'ja': {
        '力': ['カ'], 'カ': ['力'],
        '口': ['ロ'], 'ロ': ['口'],
        '工': ['エ'], 'エ': ['工', 'ェ'],
        '夕': ['タ'], 'タ': ['夕'],
        '二': ['ニ'], 'ニ': ['二'],
        '八': ['ハ'], 'ハ': ['八'],
        '卜': ['ト'], 'ト': ['卜'],
        '才': ['オ'], 'オ': ['才', 'ォ'],
        'つ': ['っ'], 'っ': ['つ'],
        'や': ['ゃ'], 'ゃ': ['や'],
        'ゆ': ['ゅ'], 'ゅ': ['ゆ'],
        'よ': ['ょ'], 'ょ': ['よ'],
        'ッ': ['ツ'],
        'ヨ': ['ョ'], 'ョ': ['ヨ'],
        'ヤ': ['ャ'], 'ャ': ['ヤ'],
        'ユ': ['ュ'], 'ュ': ['ユ'],
        'ア': ['ァ'], 'ァ': ['ア'],
        'イ': ['ィ'], 'ィ': ['イ'],
        'ウ': ['ゥ'], 'ゥ': ['ウ'],
        'ェ': ['エ'],
        'ォ': ['オ'],
        '千': ['チ'], 'チ': ['千'],
        '一': ['ー'], 'ー': ['一'],
        'ソ': ['ン'], 'ン': ['ソ'],
        'シ': ['ツ'], 'ツ': ['シ', 'ッ'],
        'へ': ['ヘ'], 'ヘ': ['へ'],
        'り': ['リ'], 'リ': ['り'],
        # dakuten vs handakuten (two dots vs small circle, blurry at
        # subtitle size); the he/be/pe family also keeps its hira/kata
        # twin-shape candidates, merged into one list
        'べ': ['ベ', 'ぺ'], 'ベ': ['べ', 'ペ'],
        'ぺ': ['ペ', 'べ'], 'ペ': ['ぺ', 'ベ'],
        'ば': ['ぱ'], 'ぱ': ['ば'],
        'び': ['ぴ'], 'ぴ': ['び'],
        'ぶ': ['ぷ'], 'ぷ': ['ぶ'],
        'ぼ': ['ぽ'], 'ぽ': ['ぼ'],
        'バ': ['パ'], 'パ': ['バ'],
        'ビ': ['ピ'], 'ピ': ['ビ'],
        'ブ': ['プ'], 'プ': ['ブ'],
        'ボ': ['ポ'], 'ポ': ['ボ'],
        'つ': ['っ'], 'っ': ['つ'],
        'ヨ': ['ョ'], 'ョ': ['ヨ'],
        'や': ['ゃ'], 'ゃ': ['や'],
        'ゆ': ['ゅ'], 'ゅ': ['ゆ'],
        'よ': ['ょ'], 'ょ': ['よ'],
        'ッ': ['ツ'],
        '元': ['え'],
        '＜': ['く'], '<': ['く'],
        '5': ['ら'],
        '-': ['ー'], '－': ['ー'], '～': ['ー'],
    },
    'zh': {
        'カ': ['力'], 'ロ': ['口'], 'エ': ['工'], 'タ': ['夕'],
        'ニ': ['二'], 'ハ': ['八'], 'ト': ['卜'], 'オ': ['才'],
        'チ': ['千'], 'ー': ['一'],
        '己': ['已'], '已': ['己', '巳'],
        '未': ['末'], '末': ['未'],
        '土': ['士'], '士': ['土'],
        '曰': ['日'],
        '人': ['入'], '入': ['人'],
        '夭': ['天'],
        '0': ['〇'], 'O': ['〇'],
    },
    'en': {
        '0': ['o', 'O'], '1': ['l', 'i'], '5': ['s', 'S'],
        '8': ['B'], '6': ['b'], '|': ['l', 'I'],
        'l': ['I'], 'I': ['l'],
    },
}


def gen_ocr_variants(word, lang, cap=100):
    """Confusion variants of a raw OCR word, BFS by substitution count:
    all 1-swap variants first, then 2-swap... capped. Returns a list of
    (variant, n_substitutions); the original word is not included."""
    table = OCR_CONFUSION.get(lang)
    if not table:
        return []
    slots = [(i, table[ch]) for i, ch in enumerate(word) if ch in table]
    if not slots:
        return []
    out = []
    seen = {word}
    frontier = [word]
    for depth in range(1, len(slots) + 1):
        nxt = []
        for base in frontier:
            for i, alts in slots:
                if base[i] != word[i]:
                    continue          # slot already swapped in this base
                for alt in alts:
                    v = base[:i] + alt + base[i + 1:]
                    if v in seen:
                        continue
                    seen.add(v)
                    nxt.append(v)
                    out.append((v, depth))
                    if len(out) >= cap:
                        return out
        frontier = nxt
        if not frontier:
            break
    return out


_HAN_RE = re.compile(r'[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]')
_KANA_RE = re.compile(r'[\u3041-\u309f\u30a1-\u30ff\uff66-\uff9f]')


def _min_cand_len(s):
    """Shortest a truncation is allowed to be, decided by the characters it
    actually contains rather than by the configured source language. Han is
    the most permissive, kana next, anything else last; a mixed candidate
    takes the loosest floor any of its characters grants."""
    if _HAN_RE.search(s):
        return 1
    if _KANA_RE.search(s):
        return 2
    return 3


def search_dict(word):
    result = {
        "spell": word,
        "pron": "",
        "excerpt": "",
        "fuzzy": "",
    }
    word = re.sub(
        r'^[^\w぀-ヿ一-鿿]+|[^\w぀-ヿ一-鿿]+$',
        '', word)  # remove potential wrong sign from ocr
    src = config.get('src_lang', SRC_LANGS[0])
    dst = config.get('dst_lang', DST_LANGS[0])
    order = LOOKUP_ORDER.get((src, dst))
    if not order:
        return result
    _conn_dict_ready.wait()
    try:
        c = _conn_dict.cursor()
        lang = SRC_LANG_CODE[src]

        trunc_forms = []

        def _add_truncs(s, variant=None):
            """Prefix truncations of s, longest first. Each is kept only if
            it clears the floor its own characters set, so a lone kanji is
            fair game while a lone kana is not."""
            for i in range(len(s) - 1, 0, -1):
                cand = s[:i]
                if i < _min_cand_len(cand):
                    continue
                trunc_forms.append(cand)
                if variant:
                    alt = variant(cand)
                    if alt != cand:
                        trunc_forms.append(alt)

        if src == '日本語':
            candidates = get_base_forms(word, with_trunc=False)
            hira = kata_to_hira(word)
            if hira != word:
                candidates += get_base_forms(hira, with_trunc=False)
            # honorific お/ご, dropped only when a kanji follows it. The
            # kanji test is what keeps おとこ and おかしい from being
            # mangled into とこ and かしい. Listed before the truncations
            # because it is far likelier to be the word actually wanted.
            if len(word) > 1 and word[0] in 'おごオゴ' and _HAN_RE.match(word[1]):
                bare = word[1:]
                if len(bare) >= _min_cand_len(bare):
                    trunc_forms.append(bare)
                _add_truncs(bare, kata_to_hira)
            # prefix truncations are NOT high matches: they may only
            # rescue the primary dict, never pull in another language
            _add_truncs(word, kata_to_hira)
        elif src == '中文':
            if not _trad_map:
                _load_trad_map(_conn_dict)
            candidates = [word, _to_simp(word)]
            _add_truncs(word, _to_simp)
        else:
            candidates = get_english_base_forms(word)
        cands = []
        for w in candidates:
            n = _norm_key(w)
            if n and n not in cands:
                cands.append(n)
        truncs = []
        for w in trunc_forms:
            n = _norm_key(w)
            if n and n not in cands and n not in truncs:
                truncs.append(n)

        # OCR-confusion variants: lookalike chars swapped in the raw word.
        # Lower trust than cands: content-bearing exact hits only, tried
        # only after every cand missed. Each variant reuses the normal
        # transform pipeline (conjugation / kana / simp).
        raw_variants = gen_ocr_variants(word, lang)
        ocr_cands = []
        fuzzy_variant_keys = []   # single-swap, >=3 chars: may join fuzzy
        for v, n_subs in raw_variants:
            if lang == 'ja':
                vforms = get_base_forms(v, with_trunc=False)
                vh = kata_to_hira(v)
                if vh != v:
                    vforms += get_base_forms(vh, with_trunc=False)
            elif lang == 'zh':
                vforms = [v, _to_simp(v)]
            else:
                vforms = get_english_base_forms(v)
            for w in vforms:
                n = _norm_key(w)
                if n and n not in cands and n not in ocr_cands:
                    ocr_cands.append(n)
            if n_subs == 1 and len(v) >= 3:
                n = _norm_key(v)
                if n and n not in fuzzy_variant_keys:
                    fuzzy_variant_keys.append(n)

        print(cands)

        # main hit: primary dict first, then the allowed fallbacks. Only
        # high matches (exact after conjugation/kana/alias transforms) can
        # pull in another language; empty hits never block the chain.
        row = None
        empty_hit = None
        for dic in order:
            for w in cands:
                r = _lookup_one(c, dic, lang, w)
                if r is None:
                    continue
                if r['excerpt']:
                    row = r
                    break
                if empty_hit is None:
                    empty_hit = r
            if row:
                break
        if row is None and ocr_cands:
            # tier 2: OCR-variant exact hits. Full dict chain (may cross
            # language), but only hits WITH content count - a guessed
            # word never blocks the chain with an empty entry
            for dic in order:
                for w in ocr_cands:
                    r = _lookup_one(c, dic, lang, w)
                    if r is not None and r['excerpt']:
                        row = r
                        break
                if row:
                    break
        if row is None:
            # partial-match rescue: truncated prefixes, PRIMARY dict only,
            # content-bearing hits only
            for w in truncs:
                r = _lookup_one(c, order[0], lang, w)
                if r is not None and r['excerpt']:
                    row = r
                    break
        if row is None:
            row = empty_hit
        if row:
            result["spell"] = row["spell"]
            result["pron"] = row["pron"] or ""
            result["excerpt"] = row["excerpt"] or ""
        else:
            # final miss: dump everything we tried, to grow the table
            print('search_dict MISS:', word,
                  '| variants tried:', [v for v, _ in raw_variants])

        # fuzzy: prefix matches from the PRIMARY dict only, so the fuzzy
        # area stays in the configured language
        fuzzy_entries = []
        seen = {result["spell"]} if row else set()
        # jmdict files 子供 / 子ども / 小供 as separate entries carrying
        # identical text, so dedupe on the body as well as the headword
        seen_text = {result["excerpt"]} if row else set()

        def _take_fuzzy(r):
            if r["spell"] in seen or not r["excerpt"]:
                return
            if r["excerpt"] in seen_text:
                return
            seen.add(r["spell"])
            seen_text.add(r["excerpt"])
            fuzzy_entries.append(r)

        # same-key siblings come first: はし is 端 AND 橋 AND 箸 AND 嘴 in
        # one dict, but only the first became the main hit and the prefix
        # expansion below skips the key itself, so they would vanish
        for w in cands:
            siblings = c.execute(
                "SELECT e.spell, e.pron, e.excerpt FROM keys k "
                "JOIN entries e ON e.id = k.entry_id "
                "WHERE k.dict = ? AND k.key = ? "
                "GROUP BY e.id ORDER BY MIN(k.rowid)",
                (order[0], w)).fetchall()
            for r in siblings:
                _take_fuzzy(r)
            if siblings:
                break

        for w in cands + fuzzy_variant_keys + truncs:
            frows = c.execute(
                "SELECT e.spell, e.pron, e.excerpt FROM keys k "
                "JOIN entries e ON e.id = k.entry_id "
                "WHERE k.dict = ? AND k.key LIKE ? AND k.key != ? "
                "GROUP BY e.id ORDER BY MIN(k.rowid) LIMIT 8",
                (order[0], w + '%', w)).fetchall()
            for r in frows:
                _take_fuzzy(r)
            if len(fuzzy_entries) >= 4:
                break

        # promote first fuzzy to main only if nothing was found at all
        if not row and fuzzy_entries:
            r0 = fuzzy_entries.pop(0)
            result["spell"] = r0["spell"]
            result["pron"] = r0["pron"] or ""
            result["excerpt"] = r0["excerpt"] or ""

        blocks = []
        for r in fuzzy_entries[:3]:
            header = f'{r["spell"]}　{r["pron"]}'.strip()
            blocks.append(f'{header}<br>{r["excerpt"]}')
        result["fuzzy"] = "<br><br>".join(blocks)

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"dict search fail: {e}")

    return result


def get_base_forms(word, with_trunc=True):
    """
    Return candidate base forms to try, most likely first.
    Rule-based Japanese conjugation reversal, no external dependencies.
    with_trunc=False: only conjugation/kana transforms ("high match"),
    no prefix truncations.
    """
    candidates = [word]

    # --- Special cases: suru / kuru ---
    suru_map = {
        'した': 'する',
        'して': 'する',
        'しない': 'する',
        'します': 'する',
        'すれば': 'する',
        'しよう': 'する',
    }
    kuru_map = {
        'きた': 'くる',
        'きて': 'くる',
        'こない': 'くる',
        'きます': 'くる',
        'くれば': 'くる',
        'きよう': 'くる',
        '来た': 'くる',
        '来て': 'くる',
        '来ない': 'くる',
    }
    if word in suru_map: candidates.append(suru_map[word])
    if word in kuru_map: candidates.append(kuru_map[word])

    # Compound suru: 勉強した → 勉強する, 勉強
    m = re.match(r'^(.+)(した|して|しない|します|しよう)$', word)
    if m:
        candidates += [m.group(1) + 'する', m.group(1)]

    # ている / ていた / ていない → ichidan stem + る
    m = re.match(r'^(.+)て(?:いる|いた|いない)$', word)
    if m and not m.group(1).endswith('っ'):
        candidates.append(m.group(1) + 'る')

    # っている / っていた → godan stem + う/る/つ
    m = re.match(r'^(.+)って(?:いる|いた|いない)$', word)
    if m:
        stem = m.group(1)
        candidates += [stem + 'う', stem + 'る', stem + 'つ']

    # --- I-adjective (before godan to avoid かった misfire) ---
    iadj_rules = [
        (r'^(.+)くなかった$', r'\1い'),
        (r'^(.+)くない$', r'\1い'),
        (r'^(.+)くて$', r'\1い'),
        (r'^(.+)かった$', r'\1い'),
        (r'^(.+)ければ$', r'\1い'),
        (r'^(.+)く$', r'\1い'),
    ]
    for pat, repl in iadj_rules:
        if re.match(pat, word):
            candidates.append(re.sub(pat, repl, word))

    # Potential/passive negative: られない → ichidan base
    m = re.match(r'^(.+)られない$', word)
    if m and not m.group(1).endswith('っ'):
        candidates.append(m.group(1) + 'る')

    # --- Na-adjective forms ---
    nadj_rules = [
        (r'^(.+)じゃなかった$', r'\1'),
        (r'^(.+)ではない$', r'\1'),
        (r'^(.+)でなかった$', r'\1'),
        (r'^(.+)じゃない$', r'\1'),
        (r'^(.+)だった$', r'\1'),
        (r'^(.+)じゃ$', r'\1'),
        (r'^(.+)だ$', r'\1'),
    ]
    for pat, repl in nadj_rules:
        if re.match(pat, word):
            candidates.append(re.sub(pat, repl, word))

    # --- Ichidan (一段): both e-stem and i-stem ---
    _IC = 'えけせてねめれげべぺいきしちにみりぎじびぴ'
    ichidan_rules = [
        (rf'^(.*[{_IC}])て$', r'\1る'),
        (rf'^(.*[{_IC}])た$', r'\1る'),
        (rf'^(.*[{_IC}])ない$', r'\1る'),
        (rf'^(.*[{_IC}])ます$', r'\1る'),
        (rf'^(.*[{_IC}])られ', r'\1る'),
        (rf'^(.*[{_IC}])させ', r'\1る'),
        (rf'^(.*[{_IC}])よう$', r'\1る'),
        (rf'^(.*[{_IC}])れば$', r'\1る'),
        (rf'^(.*[{_IC}])ろ$', r'\1る'),  # imperative: 食べろ → 食べる
        (rf'^(.*[{_IC}])よ$', r'\1る'),  # formal imperative: 食べよ → 食べる
        (rf'^(.*[{_IC}])$', r'\1る'),    # bare stem: 食べ → 食べる
    ]
    for pat, repl in ichidan_rules:
        if re.match(pat, word):
            candidates.append(re.sub(pat, repl, word))

    # --- Godan (五段) ---
    godan_rules = [
        # Te/ta form (音便)
        (r'^(.+)って$', ['つ', 'う', 'る']),
        (r'^(.+)った$', ['つ', 'う', 'る']),
        (r'^(.+)いて$', ['く']),
        (r'^(.+)いた$', ['く']),
        (r'^(.+)いで$', ['ぐ']),
        (r'^(.+)いだ$', ['ぐ']),
        (r'^(.+)して$', ['す']),
        (r'^(.+)した$', ['す']),
        (r'^(.+)んで$', ['ぬ', 'ぶ', 'む']),
        (r'^(.+)んだ$', ['ぬ', 'ぶ', 'む']),
        # Negative (nai form)
        (r'^(.+)らない$', ['る']),
        (r'^(.+)かない$', ['く']),
        (r'^(.+)がない$', ['ぐ']),
        (r'^(.+)さない$', ['す']),
        (r'^(.+)たない$', ['つ']),
        (r'^(.+)ばない$', ['ぶ']),
        (r'^(.+)まない$', ['む']),
        (r'^(.+)わない$', ['う']),
        (r'^(.+)なない$', ['ぬ']),
        # Masu form
        (r'^(.+)ります$', ['る']),
        (r'^(.+)きます$', ['く']),
        (r'^(.+)ぎます$', ['ぐ']),
        (r'^(.+)します$', ['す']),
        (r'^(.+)ちます$', ['つ']),
        (r'^(.+)びます$', ['ぶ']),
        (r'^(.+)みます$', ['む']),
        (r'^(.+)います$', ['う']),
        (r'^(.+)にます$', ['ぬ']),
        # Bare masu-stem / 連用形 (noun-ized): 録り → 録る, 書き → 書く
        (r'^(.+)り$', ['る']),
        (r'^(.+)き$', ['く']),
        (r'^(.+)ぎ$', ['ぐ']),
        (r'^(.+)し$', ['す']),
        (r'^(.+)ち$', ['つ']),
        (r'^(.+)び$', ['ぶ']),
        (r'^(.+)み$', ['む']),
        (r'^(.+)い$', ['う']),
        (r'^(.+)に$', ['ぬ']),
        # Volitional (ou form)
        (r'^(.+)こう$', ['く']),
        (r'^(.+)ごう$', ['ぐ']),
        (r'^(.+)そう$', ['す']),
        (r'^(.+)とう$', ['つ']),
        (r'^(.+)のう$', ['ぬ']),
        (r'^(.+)ぼう$', ['ぶ']),
        (r'^(.+)もう$', ['む']),
        (r'^(.+)ろう$', ['る']),
        (r'^(.+)おう$', ['う']),
        # Conditional (ba form)
        (r'^(.+)けば$', ['く']),
        (r'^(.+)げば$', ['ぐ']),
        (r'^(.+)せば$', ['す']),
        (r'^(.+)てば$', ['つ']),
        (r'^(.+)ねば$', ['ぬ']),
        (r'^(.+)べば$', ['ぶ']),
        (r'^(.+)めば$', ['む']),
        (r'^(.+)えば$', ['う']),
        # Potential (eru form)
        (r'^(.+)ける$', ['く']),
        (r'^(.+)げる$', ['ぐ']),
        (r'^(.+)せる$', ['す']),
        (r'^(.+)てる$', ['つ']),
        (r'^(.+)ねる$', ['ぬ']),
        (r'^(.+)べる$', ['ぶ']),
        (r'^(.+)める$', ['む']),
        (r'^(.+)える$', ['う']),
        # Passive (areru form)
        (r'^(.+)かれる$', ['く']),
        (r'^(.+)がれる$', ['ぐ']),
        (r'^(.+)される$', ['す']),
        (r'^(.+)たれる$', ['つ']),
        (r'^(.+)なれる$', ['ぬ']),
        (r'^(.+)ばれる$', ['ぶ']),
        (r'^(.+)まれる$', ['む']),
        (r'^(.+)われる$', ['う']),
        (r'^(.+)られる$', ['る']),
        # Causative (aseru form)
        (r'^(.+)かせる$', ['く']),
        (r'^(.+)がせる$', ['ぐ']),
        (r'^(.+)させる$', ['す']),
        (r'^(.+)たせる$', ['つ']),
        (r'^(.+)なせる$', ['ぬ']),
        (r'^(.+)ばせる$', ['ぶ']),
        (r'^(.+)ませる$', ['む']),
        (r'^(.+)わせる$', ['う']),
        (r'^(.+)らせる$', ['る']),
        # Imperative (e form)
        (r'^(.+)け$', ['く']),
        (r'^(.+)げ$', ['ぐ']),
        (r'^(.+)せ$', ['す']),
        (r'^(.+)て$', ['つ']),
        (r'^(.+)ね$', ['ぬ']),
        (r'^(.+)べ$', ['ぶ']),
        (r'^(.+)め$', ['む']),
        (r'^(.+)れ$', ['る']),
        (r'^(.+)え$', ['う']),
    ]
    for pat, suffixes in godan_rules:
        m = re.match(pat, word)
        if m:
            stem = m.group(1)
            for s in suffixes:
                candidates.append(stem + s)

    # Add prefix truncation candidates, min length 2 (longest first)
    if with_trunc:
        for i in range(len(word) - 1, 1, -1):
            candidates.append(word[:i])

    # Katakana -> hiragana fallback (mimetic words stored in hiragana)
    # Apply to word and to every candidate already collected, as a last resort.
    hira_extra = []
    for cand in candidates:
        hira = "".join(
            chr(ord(ch) - 0x60) if 0x30A1 <= ord(ch) <= 0x30F6 else ch
            for ch in cand
        )
        if hira != cand:
            hira_extra.append(hira)
    candidates += hira_extra
    
    # Deduplicate, preserve order
    seen = set()
    result = []
    for c in candidates:
        if c and c not in seen:
            seen.add(c)
            result.append(c)
    return result


def kata_to_hira(s):
    """Convert full-width katakana to hiragana. Long-vowel mark stays."""
    return "".join(
        chr(ord(ch) - 0x60) if 0x30A1 <= ord(ch) <= 0x30F6 else ch
        for ch in s
    )


_trad_map = {}


def _load_trad_map(conn):
    global _trad_map
    rows = conn.execute("SELECT trad, simp FROM trad_map").fetchall()
    _trad_map = {r["trad"]: r["simp"] for r in rows}


def _to_simp(word):
    """Convert traditional Chinese characters to simplified using char map."""
    return ''.join(_trad_map.get(c, c) for c in word)


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
    "Ichidan verb - zuru verb (alternative form of -jiru verbs)":
    "Ichidan-zuru",
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
    "Nidan verb (lower class) with 'u' ending and 'we' conjugation (archaic)":
    "Nidan-l-we",
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


def search_moji_api(word, result):
    global last_moji_search_time
    last_moji_search_time = time.time()
    done_event_fuzzy = threading.Event()
    done_event_exact = threading.Event()
    for _ in range(3):
        threading.Thread(target=search_mojidict_fuzzy,
                         args=(word, result, done_event_fuzzy),
                         daemon=True).start()
        threading.Thread(target=search_mojidict_exact,
                         args=(word, result, done_event_exact),
                         daemon=True).start()
    done_event_fuzzy.wait(timeout=6)
    done_event_exact.wait(timeout=6)
    return result


def search_mojidict_fuzzy(word, result, done_event_fuzzy):
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
            "_ClientVersion":
            "js3.4.1",
            "_ApplicationId":
            "E62VyFVLMiW7kvbtVq3p",
            "g_os":
            "PCWeb",
            "g_ver":
            "v4.8.8.20240829",
            "_InstallationId":
            dummy_uuid,
        }

        response = session.post(
            "https://api.mojidict.com/parse/functions/union-api",
            json=data,
            timeout=5)

        fuzzy_result = ''
        response_json = response.json(
        )["result"]["results"]["search-all"]["result"]["word"]["searchResult"]
        k = min(len(response_json), 3)  # only take top 3 results
        for i in range(k):
            fuzzy_result += response_json[i].get("title", "") or ''
            fuzzy_result += "<br>"
            fuzzy_result += response_json[i].get("excerpt", "") or ''
            fuzzy_result += "<br><br>"

        result["fuzzy"] = fuzzy_result.strip().removesuffix("<br><br>")
        print('fuzzy ' + str(time.time() - t))
    except Exception as e:
        print("moji fuzzy fail")
    done_event_fuzzy.set()


def search_mojidict_exact(word, result, done_event_exact):
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
            timeout=5)
        response_json = response.json()["result"]["result"]

        word_info = response_json["word"][0]
        result["spell"] = word_info.get("spell", "") or ''
        result["pron"] = word_info.get("pron", "") or ''
        #result["accent"] = word_info.get("accent","")  or ''
        #result["romaji"] = word_info.get("romaji","")  or ''
        result["excerpt"] = word_info.get("excerpt", "") or ''
        print('exact ' + str(time.time() - t))
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
            self._drag_pos = event.globalPos() - window.frameGeometry(
            ).topLeft()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self._drag_pos is not None:
            window.move(event.globalPos() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None


SRC_LANGS = ["日本語", "中文", "English"]
DST_LANGS = ["日本語", "中文", "English"]


def widget_selected_text(widget):
    if isinstance(widget, QLineEdit):
        return widget.selectedText()
    if isinstance(widget, QTextEdit):
        return widget.textCursor().selectedText()
    return ''


def clear_widget_selection(widget):
    if isinstance(widget, QLineEdit):
        widget.deselect()
    elif isinstance(widget, QTextEdit):
        cursor = widget.textCursor()
        cursor.clearSelection()
        widget.setTextCursor(cursor)


def setup_editable_result_box(widget, all_boxes):
    base_cls = type(widget)
    orig_press = widget.mousePressEvent

    def press(event, w=widget, op=orig_press):
        global hide_on_click
        if not w.isReadOnly():
            # user started editing: they need the UI, disarm auto-hide
            hide_on_click = False
            # temporarily allow activation so editing works (window is no-activate)
            hwnd = int(window.winId())
            ex_style = windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE,
                                         ex_style & ~WS_EX_NOACTIVATE)
            windll.user32.SetForegroundWindow(hwnd)
        for other in all_boxes:
            if other is not w:
                clear_widget_selection(other)
        op(event)
        if not w.isReadOnly():
            w.setFocus()

    widget.mousePressEvent = press

    def focus_out(event, w=widget, cls=base_cls):
        hwnd = int(window.winId())
        ex_style = windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE,
                                     ex_style | WS_EX_NOACTIVATE)
        cls.focusOutEvent(w, event)

    widget.focusOutEvent = focus_out


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

    title_widget.setContextMenuPolicy(Qt.CustomContextMenu)
    title_widget.customContextMenuRequested.connect(
        lambda pos: show_title_menu(title_widget.mapToGlobal(pos)))


    btn_style = "QToolButton { border: none; color: white; } QToolButton:hover { background-color: #444; } QToolButton:checked { background-color: #666; }"
    close_style = "QToolButton { border: none; color: white; } QToolButton:hover { background-color: #e81123; }"

    window.label_title = QLabel("ACard", title_widget)
    window.label_title.setFont(QFont("Microsoft YaHei", font_size_title))
    window.label_title.setStyleSheet("color: #ffffff;")
    title_bar.addWidget(window.label_title)
    title_bar.addStretch()

    window.settings_btn = QToolButton(title_widget)
    window.settings_btn.setText('⚙')
    window.settings_btn.setFont(QFont('Segoe UI Symbol', font_size_btn))
    window.settings_btn.setStyleSheet(btn_style)
    window.settings_btn.clicked.connect(toggle_settings)
    window.settings_btn.setCheckable(True)
    title_bar.addWidget(window.settings_btn)

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

    window.close_btn = QToolButton(title_widget)
    window.close_btn.setText('🗕')
    window.close_btn.setFont(QFont('Segoe MDL2 Assets', font_size_btn))
    window.close_btn.clicked.connect(window.hide)
    window.close_btn.setStyleSheet(btn_style)
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
    window.word.customContextMenuRequested.connect(
        lambda pos: show_custom_context_menu(window.word, pos, font_size_small
                                             ))
    row.addWidget(window.word)

    orig_word_press = window.word.mousePressEvent

    def word_press(event):
        global hide_on_click
        # temporarily allow activation so word input works
        hwnd = int(window.winId())
        ex_style = windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE,
                                     ex_style & ~WS_EX_NOACTIVATE)
        windll.user32.SetForegroundWindow(hwnd)
        # same rule as the result boxes: entering this one drops the
        # selection everywhere else. The group is assembled further down
        # in this function, so read it off window at click time.
        for other in getattr(window, '_selection_group', ()):
            if other is not window.word:
                clear_widget_selection(other)
        orig_word_press(event)
        window.word.setFocus()
        hide_on_click = False  # user clicked on word input, disarm auto-hide

    window.word.mousePressEvent = word_press

    def word_focus_out(event):
        # restore no-activate to prevent stealing focus from game
        hwnd = int(window.winId())
        ex_style = windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE,
                                     ex_style | WS_EX_NOACTIVATE)
        QLineEdit.focusOutEvent(window.word, event)

    window.word.focusOutEvent = word_focus_out

    window.search_btn = QToolButton(window)
    window.search_btn.setText('🔍')
    window.search_btn.setFont(QFont('Segoe UI Symbol', font_size_btn))
    window.search_btn.clicked.connect(refresh_word)
    window.word.returnPressed.connect(window.search_btn.animateClick)
    row.addWidget(window.search_btn)

    window.save_btn = QToolButton(window)
    window.save_btn.setText('💾')
    window.save_btn.setFont(QFont('Segoe UI Symbol', font_size_btn))
    window.save_btn.clicked.connect(save_word_qt_to_anki)
    row.addWidget(window.save_btn)

    window.delete_btn = QToolButton(window)
    window.delete_btn.setText('✖')
    window.delete_btn.setFont(QFont('Segoe UI Symbol', font_size_btn))
    window.delete_btn.clicked.connect(anki_delete_note)
    window.delete_btn.setCheckable(True)
    row.addWidget(window.delete_btn)

    set_btn_status(False)

    sel_style = "selection-background-color: #3399ff; selection-color: white;"

    window.label_spell = QLineEdit("", central)
    window.label_spell.setAlignment(Qt.AlignHCenter)
    window.label_spell.setFrame(False)
    window.label_spell.setStyleSheet(
        "QLineEdit { background: transparent; border: 1px solid transparent; border-radius: 4px; padding: 1px; " + sel_style + " }"
        "QLineEdit:focus { background: #ffffff; border: 1px solid #3399ff; }")
    font = QFont("Microsoft YaHei", font_size_large)
    font.setBold(True)
    window.label_spell.setFont(font)
    main_layout.addWidget(window.label_spell)

    window.label_pron = QLineEdit("", central)
    window.label_pron.setAlignment(Qt.AlignHCenter)
    window.label_pron.setFrame(False)
    window.label_pron.setStyleSheet(
        "QLineEdit { background: transparent; border: 1px solid transparent; border-radius: 4px; padding: 1px; " + sel_style + " }"
        "QLineEdit:focus { background: #ffffff; border: 1px solid #3399ff; }")
    font = QFont("Microsoft YaHei", font_size_small)
    font.setBold(False)
    window.label_pron.setFont(font)
    main_layout.addWidget(window.label_pron)

    window.label_excerpt = QTextEdit(central)
    window.label_excerpt.setAcceptRichText(False)   # paste as plain text: keep newlines, drop bold/size
    window.label_excerpt.setAlignment(Qt.AlignLeft)
    window.label_excerpt.setFrameStyle(QTextEdit.NoFrame)
    window.label_excerpt.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    window.label_excerpt.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    window.label_excerpt.document().setDocumentMargin(0)
    window.label_excerpt.setStyleSheet(
        "QTextEdit { background: transparent; border: 1px solid transparent; border-radius: 4px; " + sel_style + " }"
        "QTextEdit:focus { background: #ffffff; border: 1px solid #3399ff; }")
    font = QFont("Microsoft YaHei", font_size_small)
    font.setBold(False)
    window.label_excerpt.setFont(font)
    main_layout.addWidget(window.label_excerpt)
    window.label_excerpt.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)

    window.label_fuzzy = QTextEdit(central)
    window.label_fuzzy.setAcceptRichText(False)   # paste as plain text, same as excerpt
    window.label_fuzzy.setFrameStyle(QTextEdit.NoFrame)
    window.label_fuzzy.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    window.label_fuzzy.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    window.label_fuzzy.document().setDocumentMargin(0)
    window.label_fuzzy.setStyleSheet(_FUZZY_STYLE_RO)
    window.label_fuzzy.setFont(QFont("Microsoft YaHei", font_size_small))
    main_layout.addWidget(window.label_fuzzy)
    window.label_fuzzy.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)

    #window.label_pron.setVisible(False)
    #window.label_excerpt.setVisible(False)

    class _SelectAllOnFocus(QObject):
        # right-clicking (or tabbing into) a result box selects its whole
        # content; a plain left-click just places the cursor. selectAll is
        # deferred one tick: the cursor placement that follows the event
        # would undo an immediate selection
        def eventFilter(self, obj, event):
            # Qt grants click-focus BEFORE delivering the press, so
            # hasFocus() cannot tell "entering" from "already inside".
            # FocusIn(mouse) arms a one-shot flag instead; the press that
            # caused it consumes it: right button selects all, left does
            # nothing
            if event.type() == QEvent.FocusIn:
                if event.reason() == Qt.MouseFocusReason:
                    # armed for exactly one tick: only the press belonging
                    # to this same click can consume it. hasFocus() is NOT
                    # usable here - in this no-activate window it flips
                    # with window activation, not with box entry
                    obj._ap_entered = True
                    QTimer.singleShot(0, lambda o=obj: setattr(
                        o, '_ap_entered', False))
                elif event.reason() in (Qt.TabFocusReason,
                                        Qt.BacktabFocusReason):
                    # QLineEdit drops its own selection on focus out but
                    # QTextEdit keeps it, so tabbing away from excerpt or
                    # fuzzy would leave two boxes looking selected
                    for other in getattr(window, '_selection_group', ()):
                        if other is not obj:
                            clear_widget_selection(other)
                    QTimer.singleShot(0, obj.selectAll)
            elif event.type() == QEvent.MouseButtonPress:
                if event.button() == Qt.RightButton and \
                        getattr(obj, '_ap_entered', False):
                    QTimer.singleShot(0, obj.selectAll)
                obj._ap_entered = False
            return False

    window._select_all_filter = _SelectAllOnFocus(window)  # keep a live ref

    result_boxes = [window.label_spell, window.label_pron, window.label_excerpt, window.label_fuzzy]
    # the search box joins the result boxes' selection group: entering any
    # one of them drops whatever was selected in the others
    window._selection_group = result_boxes + [window.word]
    for box in result_boxes:
        box.setContextMenuPolicy(Qt.CustomContextMenu)
        box.customContextMenuRequested.connect(
            lambda pos, w=box: show_custom_context_menu(w, pos, font_size_small))
        setup_editable_result_box(box, window._selection_group)
        box.installEventFilter(window._select_all_filter)
        if isinstance(box, QTextEdit):
            # Tab moves to the next field instead of typing a tab. The Qt
            # default swallows it, and since entering a box selects all of
            # it, that tab would replace everything the user had selected.
            box.setTabChangesFocus(True)
    # the word box behaves like the result boxes: a right-click that
    # ENTERS it selects everything, a left-click just places the cursor
    window.word.installEventFilter(window._select_all_filter)


    # save lights up whenever any field changes (search result or manual edit)
    window.word.textChanged.connect(update_save_btn_state)
    window.label_spell.textChanged.connect(update_save_btn_state)
    window.label_pron.textChanged.connect(update_save_btn_state)
    window.label_excerpt.textChanged.connect(update_save_btn_state)
    window.label_fuzzy.textChanged.connect(update_save_btn_state)


    window.label_screenshot = QLabel("", central)
    main_layout.addWidget(window.label_screenshot)
    window.label_screenshot.mousePressEvent = play_audio

    # delete-capture cross. Parented to the image label, so a click on it
    # never reaches the label's play handler underneath.
    cross = max(18, int(bar_height * 0.62))
    window.pic_del_btn = QToolButton(window.label_screenshot)
    window.pic_del_btn.setText('✕')
    window.pic_del_btn.setCursor(Qt.PointingHandCursor)
    window.pic_del_btn.setFixedSize(cross, cross)
    window.pic_del_btn.setStyleSheet(
        'QToolButton { background: rgba(0, 0, 0, 150); color: white;'
        ' border: none; border-radius: 3px; font-size: %dpx; }'
        'QToolButton:hover { background: rgba(200, 40, 40, 220); }'
        % max(10, int(cross * 0.55)))
    window.pic_del_btn.clicked.connect(delete_current_capture)
    window.pic_del_btn.hide()
    window.label_screenshot.setMouseTracking(True)

    def _pic_enter(event):
        sync_pic_del_btn()
        QLabel.enterEvent(window.label_screenshot, event)

    def _pic_move(event):
        sync_pic_del_btn(event.pos())
        QLabel.mouseMoveEvent(window.label_screenshot, event)

    def _pic_leave(event):
        # moving onto the cross (a child widget) also sends Leave to the
        # label; reading the live pointer position sorts that out, since
        # the cross sits inside the image area
        sync_pic_del_btn()
        QLabel.leaveEvent(window.label_screenshot, event)

    window.label_screenshot.enterEvent = _pic_enter
    window.label_screenshot.mouseMoveEvent = _pic_move
    window.label_screenshot.leaveEvent = _pic_leave
    # page nav under the image: only visible for multi-capture notes
    window.page_nav = QWidget(central)
    _nav_lay = QHBoxLayout(window.page_nav)
    _nav_lay.setContentsMargins(0, 2, 0, 2)
    _nav_lay.setSpacing(18)
    _nav_lay.addStretch(1)
    window.page_prev_btn = QToolButton(window.page_nav)
    window.page_prev_btn.setText('◀')
    window.page_prev_btn.setFont(QFont('Segoe UI Symbol', int(font_size_btn/2)))
    window.page_prev_btn.setAutoRaise(True)
    window.page_prev_btn.clicked.connect(lambda: qt_play_pages(-1, False))
    _nav_lay.addWidget(window.page_prev_btn)
    window.page_nav_label = QLabel('1/1', window.page_nav)
    window.page_nav_label.setFont(QFont('Segoe UI Symbol', int(font_size_btn/2)))
    _nav_lay.addWidget(window.page_nav_label)
    window.page_next_btn = QToolButton(window.page_nav)
    window.page_next_btn.setText('▶')
    window.page_next_btn.setFont(QFont('Segoe UI Symbol', int(font_size_btn/2)))
    window.page_next_btn.setAutoRaise(True)
    window.page_next_btn.clicked.connect(lambda: qt_play_pages(1, False))
    _nav_lay.addWidget(window.page_next_btn)
    _nav_lay.addStretch(1)
    main_layout.addWidget(window.page_nav)
    window.page_nav.hide()

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
    window.src_lang.setCurrentIndex(
        SRC_LANGS.index(config.get('src_lang', SRC_LANGS[0])))
    lang_row.addWidget(window.src_lang)
    window.src_lang.setFont(font_settings)
    window.src_lang.currentIndexChanged.connect(on_src_lang_changed)

    arrow = QLabel("→")
    arrow.setAlignment(Qt.AlignCenter)
    lang_row.addWidget(arrow)
    arrow.setFont(font_settings)

    window.dst_lang = QComboBox()
    window.dst_lang.addItems(DST_LANGS)
    window.dst_lang.setCurrentIndex(
        DST_LANGS.index(config.get('dst_lang', DST_LANGS[0])))
    lang_row.addWidget(window.dst_lang)
    window.dst_lang.setFont(font_settings)
    window.dst_lang.currentIndexChanged.connect(on_dst_lang_changed)

    settings_layout.addLayout(lang_row)

    window.screen_combo = QComboBox()
    window.screen_combo.setFont(font_settings)
    for i, mon in enumerate(snip.sct.monitors[1:],
                            1):  # skip monitors[0] (virtual desktop)
        window.screen_combo.addItem(
            f"{ui('monitor')} {i}  {mon['width']}x{mon['height']}")
    window.screen_combo.setCurrentIndex(config['monitor_index'] -
                                        1)  # monitors[1] = index 0 in combo
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

    anki_row = QHBoxLayout()
    anki_label = QLabel(ui('select_anki'))
    anki_label.setFont(font_settings)
    window.anki_path_btn = QPushButton(
        config.get('anki_path') or ui('select_anki'))
    window.anki_path_btn.setFont(font_settings)

    window.anki_path_btn.clicked.connect(on_pick_anki)
    anki_row.addWidget(anki_label)
    anki_row.addWidget(window.anki_path_btn)
    settings_layout.addLayout(anki_row)

    if config.get('anki_path'):

        def elide_initial():
            metrics = window.anki_path_btn.fontMetrics()
            elided = metrics.elidedText(config['anki_path'], Qt.ElideMiddle,
                                        window.anki_path_btn.width() - 10)
            window.anki_path_btn.setText(elided)

        QTimer.singleShot(0, elide_initial)

    donate_row = QHBoxLayout()
    donate_label = QLabel(ui('donate'))
    donate_label.setFont(font_settings)
    donate_row.addWidget(donate_label)

    import webbrowser
    afdian_btn = QPushButton(ui('afadian'))
    afdian_btn.setFont(font_settings)
    afdian_btn.clicked.connect(lambda: webbrowser.open('https://afdian.com/a/ACard'))
    donate_row.addWidget(afdian_btn)

    patreon_btn = QPushButton(ui('patreon'))
    patreon_btn.setFont(font_settings)
    patreon_btn.clicked.connect(lambda: webbrowser.open('https://www.patreon.com/cw/qazzzlyt/membership'))
    donate_row.addWidget(patreon_btn)

    settings_layout.addLayout(donate_row)

    # align the left label column so all controls start at the same x
    label_col = [lang_label, screen_label, hotkey_label, anki_label, donate_label]
    col_w = max(l.sizeHint().width() for l in label_col)
    for l in label_col:
        l.setFixedWidth(col_w)

    # compact right column: one uniform width for every row's control
    # area, sized to the widest natural content so nothing gets cut
    spacing = lang_row.spacing()
    if spacing < 0:
        spacing = 6
    right_w = max(
        window.src_lang.sizeHint().width() + arrow.sizeHint().width()
        + window.dst_lang.sizeHint().width() + 2 * spacing,
        window.screen_combo.sizeHint().width(),
        window.hotkey_btn.sizeHint().width(),
        afdian_btn.sizeHint().width() + patreon_btn.sizeHint().width() + spacing,
    )
    right_w = int(right_w * 1.4)   # widen the control column (tune the factor)
    half = (right_w - arrow.sizeHint().width() - 2 * spacing) // 2
    window.src_lang.setFixedWidth(half)
    window.dst_lang.setFixedWidth(half)
    window.screen_combo.setFixedWidth(right_w)
    window.hotkey_btn.setFixedWidth(right_w)
    window.anki_path_btn.setFixedWidth(right_w)
    dhalf = (right_w - spacing) // 2
    afdian_btn.setFixedWidth(dhalf)
    patreon_btn.setFixedWidth(dhalf)
    for row in (lang_row, screen_row, hotkey_row, anki_row, donate_row):
        row.insertStretch(1)   # spring after the label: controls hug the right edge


_RESULT_STYLE_RO = {
    QLineEdit: "QLineEdit { background: transparent; border: 1px solid transparent; border-radius: 4px; padding: 1px; selection-background-color: #3399ff; selection-color: white; }",
    QTextEdit: "QTextEdit { background: transparent; border: 1px solid transparent; border-radius: 4px; selection-background-color: #3399ff; selection-color: white; }",
}
_RESULT_STYLE_EDIT = {
    QLineEdit: _RESULT_STYLE_RO[QLineEdit] + "QLineEdit:focus { background: #ffffff; border: 1px solid #3399ff; }",
    QTextEdit: _RESULT_STYLE_RO[QTextEdit] + "QTextEdit:focus { background: #ffffff; border: 1px solid #3399ff; }",
}


# fuzzy box keeps its separator line and own text color in both states
_FUZZY_STYLE_RO = "QTextEdit { background: transparent; border: none; margin-top: 4px; color: #333333; selection-background-color: #3399ff; selection-color: white; }"
_FUZZY_STYLE_EDIT = _FUZZY_STYLE_RO + "QTextEdit:focus { background: #ffffff; border: 1px solid #3399ff; border-radius: 4px; }"


def set_result_editable(editable):
    # spell/pron/excerpt/fuzzy are editable only when a real note is shown;
    # read-only mode keeps text selectable but shows no focus highlight
    styles = _RESULT_STYLE_EDIT if editable else _RESULT_STYLE_RO
    for box in (window.label_spell, window.label_pron, window.label_excerpt):
        box.setReadOnly(not editable)
        box.setStyleSheet(styles[type(box)])
    window.label_fuzzy.setReadOnly(not editable)
    window.label_fuzzy.setStyleSheet(_FUZZY_STYLE_EDIT if editable else _FUZZY_STYLE_RO)


def current_fields():
    # word is not stored in anki any more, so editing it must not light
    # up the save button
    return {
        'spell': window.label_spell.text(),
        'pron': window.label_pron.text(),
        'excerpt': window.label_excerpt.toHtml(),
        'fuzzy': window.label_fuzzy.toHtml() if window.label_fuzzy.toPlainText().strip() else '',
    }


def set_save_baseline():
    # snapshot current content as "saved"; call on load / create / after save
    window._saved_fields = current_fields()
    window._qt_pending_del = []      # deletions are either committed or gone
    update_save_btn_state()


def update_save_btn_state(*_):
    # light up save only when there is a note AND content differs from the snapshot
    changed = (window.anki_id is not None
               and (getattr(window, '_saved_fields', None) != current_fields()
                    or bool(getattr(window, '_qt_pending_del', None))))
    window.save_btn.setEnabled(changed)
    window.save_btn.setStyleSheet('' if changed else 'color: grey;')


def set_btn_status(enabled):
    if enabled:
        window.search_btn.setStyleSheet('')
        window.search_btn.setEnabled(True)
        window.delete_btn.setStyleSheet('')
        window.delete_btn.setEnabled(True)
    else:
        window.search_btn.setStyleSheet('color: grey;')
        window.search_btn.setEnabled(False)
        window.delete_btn.setStyleSheet('color: grey;')
        window.delete_btn.setEnabled(False)


def on_pick_anki():
    path = pick_anki_exe()
    show_and_exclude_from_capture(window)
    if path:
        metrics = window.anki_path_btn.fontMetrics()
        elided = metrics.elidedText(path, Qt.ElideMiddle,
                                    window.anki_path_btn.width() - 10)
        window.anki_path_btn.setText(elided)


play_log = []  # (start_time, end_time) wall-clock of each playback

# ---- decoupled start/end playback, integrated 2026-07-04 -------------------
# Contract: play(start) may begin before END is known; set_end() feeds END
# later from any thread. d >= F -> per-sample ramp landing exactly on the END
# sample; d < F (incl. END already passed / STOP_NOW) -> full forward fade,
# may overshoot END, never hard-cuts. F is loudness-adaptive (50..300 ms).
CHUNK_FRAMES = 4096        # also the END poll granularity (~93 ms @ 44.1k)
PROBE_SEC = 0.10           # loudness probe window for fade sizing
FADE_MIN_SEC = 0.05
FADE_MAX_SEC = 0.30
FADE_REF_RMS = 2000.0      # int16 RMS that maps to the longest fade
STOP_NOW = -1.0            # set_end(STOP_NOW): stop gracefully asap

_play_session = None       # current AudioPlayback, replaced on each play


class AudioPlayback:

    def __init__(self, wav_bytes):
        with wave.open(io.BytesIO(wav_bytes), 'rb') as wf:
            self.rate = wf.getframerate()
            self.channels = wf.getnchannels()
            self.sampwidth = wf.getsampwidth()
            pcm = wf.readframes(wf.getnframes())
        dtype = np.int16 if self.sampwidth == 2 else np.int32
        self.frames = np.frombuffer(pcm, dtype=dtype).reshape(-1, self.channels)
        self.total = self.frames.shape[0]
        self._end_frame = None     # frames, or -1 = stop now, or None = unknown
        self.frame_bytes = self.sampwidth * self.channels
        self._stop = threading.Event()
        self._thread = None

    def set_end(self, end_sec):
        """end_sec: seconds from clip start, or STOP_NOW."""
        if end_sec is not None and end_sec == STOP_NOW:
            self._end_frame = -1
        else:
            self._end_frame = int(end_sec * self.rate)

    def set_end_bytes(self, end_byte):
        """end_byte: PCM byte offset from clip start (frame-aligned here)."""
        self._end_frame = int(end_byte) // self.frame_bytes

    def stop_now(self):
        self._end_frame = -1

    def abort(self):
        # hard stop, only for "a new playback replaces this one"
        self._stop.set()

    def _rms(self, a, b):
        a = max(0, min(int(a), self.total - 1))
        b = max(a + 1, min(int(b), self.total))
        seg = self.frames[a:b].astype(np.float32)
        return float(np.sqrt(np.mean(seg * seg)))

    def _fade_frames(self, probe_a, probe_b):
        ratio = min(max(self._rms(probe_a, probe_b) / FADE_REF_RMS, 0.0), 1.0)
        sec = FADE_MIN_SEC + (FADE_MAX_SEC - FADE_MIN_SEC) * ratio
        return max(1, int(self.rate * sec))

    def _gain_at(self, pos, target):
        # current landing gain at pos, for click-free forward handoff
        end_f, F = target
        return float(min(max((end_f - pos) / F, 0.0), 1.0))

    def _gen(self, start_frame):
        """Yield gain-applied byte chunks until the stop rule fires."""
        probe = int(self.rate * PROBE_SEC)
        pos = start_frame
        fade_in = min(self._fade_frames(pos, pos + probe),
                      max(1, (self.total - pos) // 2))
        target = None    # (end_frame, F) landing target
        forward = None   # (ramp_start, F, g0) terminal forward fade
        eof_target = (self.total,
                      self._fade_frames(self.total - probe, self.total))
        while pos < self.total and not self._stop.is_set():
            if forward is None:
                end = self._end_frame
                if end is not None and end < 0:  # stop now
                    forward = (pos, self._fade_frames(pos, pos + probe),
                               self._gain_at(pos, target or eof_target))
                elif end is not None:
                    end_f = min(end, self.total)
                    if target is None or target[0] != end_f:
                        F = self._fade_frames(end_f - probe, end_f)
                        if end_f - pos >= F:
                            target = (end_f, F)
                        else:
                            forward = (pos,
                                       self._fade_frames(pos, pos + probe),
                                       self._gain_at(pos, target or eof_target))
            if forward is not None:
                ramp_start, F, g0 = forward
                ramp_end = ramp_start + F
                if ramp_end <= pos:
                    break
                n = min(CHUNK_FRAMES, self.total - pos, ramp_end - pos)
                idx = np.arange(pos, pos + n)
                g = g0 * np.clip((ramp_end - idx) / F, 0.0, 1.0)
                stop_after = pos + n >= ramp_end
            else:
                end_f, F = target if target is not None else eof_target
                n = min(CHUNK_FRAMES, end_f - pos)
                if n <= 0:
                    break
                idx = np.arange(pos, pos + n)
                g = np.ones(n, dtype=np.float64)
                m = idx >= end_f - F
                if m.any():
                    g[m] = (end_f - idx[m]) / F
                stop_after = pos + n >= end_f
            m = idx < start_frame + fade_in
            if m.any():
                g[m] = g[m] * ((idx[m] - start_frame) / fade_in)
            chunk = self.frames[pos:pos + n].astype(np.float32) * g[:, None]
            yield chunk.astype(self.frames.dtype).tobytes()
            pos += n
            if stop_after:
                break

    def play(self, start_sec):
        self._play_from(max(0, min(int(start_sec * self.rate), self.total - 1)))

    def play_bytes(self, start_byte):
        f = int(start_byte) // self.frame_bytes
        self._play_from(max(0, min(f, self.total - 1)))

    def _play_from(self, start_frame):
        self._stop.clear()

        def worker():
            p = pyaudio.PyAudio()
            # try default output device, fall back to first available
            output_device_index = None
            try:
                p.get_default_output_device_info()
            except OSError:
                for i in range(p.get_device_count()):
                    info = p.get_device_info_by_index(i)
                    if info.get('maxOutputChannels', 0) > 0:
                        output_device_index = i
                        break
                if output_device_index is None:
                    p.terminate()
                    return  # no output device at all, silently abort
            stream = p.open(format=p.get_format_from_width(self.sampwidth),
                            channels=self.channels, rate=self.rate,
                            output=True,
                            output_device_index=output_device_index)
            play_start = time.time()
            for data in self._gen(start_frame):
                if self._stop.is_set():
                    break
                stream.write(data)
            stream.stop_stream()
            stream.close()
            p.terminate()
            play_log.append((play_start, time.time()))

        self._thread = threading.Thread(target=worker, daemon=True)
        self._thread.start()


_qt_seq_gen = 0      # bumped to cancel a running page sequence
_qt_caps_event = threading.Event()   # set when _qt_caps is final


def parse_captures(fields):
    # pair jpg/mp3 by the stem before the LAST underscore (same rule as
    # the card template); play range comes from the _r{us}-{us} suffix
    caps, by_stem = [], {}

    def stem(fn):
        b = re.sub(r'\.[^.]+$', '', fn)
        i = b.rfind('_')
        return fn if i < 0 else b[:i]

    for fn in re.findall(r'src="([^"]+)"', fields['screenshot']['value']):
        s = stem(fn)
        if s not in by_stem:
            by_stem[s] = {'img': None, 'mp3': None, 'range': None}
            caps.append(by_stem[s])
        by_stem[s]['img'] = fn
    for fn in re.findall(r'src="([^"]+)"', fields['audio']['value']):
        s = stem(fn)
        if s not in by_stem:
            by_stem[s] = {'img': None, 'mp3': None, 'range': None}
            caps.append(by_stem[s])
        by_stem[s]['mp3'] = fn
        m = re.search(r'_r(\d+)-(\d+)\.[^.]+$', fn)
        if m and int(m.group(2)) > int(m.group(1)):
            by_stem[s]['range'] = (int(m.group(1)) / 1e6,
                                   int(m.group(2)) / 1e6)
    # legacy single pair whose names never match: collapse into one
    if len(caps) == 2 and caps[0]['mp3'] is None and caps[1]['img'] is None:
        caps = [{'img': caps[0]['img'], 'mp3': caps[1]['mp3'],
                 'range': caps[1]['range']}]
    return caps


def _range_to_bytes(wav, rng):
    with wave.open(io.BytesIO(wav), 'rb') as wf:
        bps = wf.getframerate() * wf.getnchannels() * wf.getsampwidth()
        fb = wf.getnchannels() * wf.getsampwidth()
    if not rng:
        return 0, None
    return int(rng[0] * bps) // fb * fb, int(rng[1] * bps) // fb * fb


def qt_preload_pages():
    # decode every page's media in the background as soon as the caps
    # are known, so flips and the sequence start instantly
    caps = getattr(window, '_qt_caps', None)
    if not caps or len(caps) < 2:
        return

    def worker(cs=caps):
        for c in cs:
            if getattr(window, '_qt_caps', None) is not cs:
                return               # a newer round took over
            if c.get('_jpg') is None and c['img']:
                c['_jpg'] = anki_download_media(c['img'])
            if not c.get('_wav_tried') and c['mp3']:
                c['_wav_tried'] = True
                mp3 = anki_download_media(c['mp3'])
                c['_wav'] = mp3_to_wav(mp3) if mp3 else None
                if c['_wav'] is None:
                    print('preload: audio unavailable for ' + str(c['mp3']))

    threading.Thread(target=worker, daemon=True).start()


def qt_note_pages_ready(ts):
    # no-audio round tail: once the note id is published, parse the
    # note's captures so the nav reflects the merged state
    round_anki_id_generated.wait(timeout=15)
    snap = anki_last_new_note
    if ts != snap[0]:
        return
    r = invoke('notesInfo', notes=[int(snap[1])])
    if r and not r.get('error') and r.get('result') \
            and r['result'][0].get('fields'):
        window._qt_caps = parse_captures(r['result'][0]['fields'])
        window.show_page_signal.emit(None, 0, len(window._qt_caps))
        _qt_caps_event.set()
        qt_preload_pages()


def qt_play_pages(delta, auto_advance):
    # unified page navigation. Jump to (current page + delta) and play
    # it; with auto_advance, continue around ALL pages (hard cuts) and
    # come home silently. Manual arrows use auto_advance=False: play the
    # landed page only (mirrors the card template's rules)
    global _qt_seq_gen
    _qt_seq_gen += 1
    gen = _qt_seq_gen
    if not _qt_caps_event.is_set() and delta:
        # this round has not finished analyzing its audio yet: the arrow
        # stays visibly pressed until the flip can actually happen
        (window.page_prev_btn if delta < 0
         else window.page_next_btn).setDown(True)

    def worker():
        global _play_session
        # a merge round shows the nav before the note is finalized:
        # block here until the caps are ready, then flip
        if not _qt_caps_event.wait(timeout=20):
            window.nav_reset_signal.emit()
            return
        caps = getattr(window, '_qt_caps', None)
        if not caps or len(caps) < 2:
            window.nav_reset_signal.emit()
            return
        if gen != _qt_seq_gen:
            window.nav_reset_signal.emit()
            return
        n = len(caps)
        start = (getattr(window, '_qt_page', 0) + delta) % n
        steps = list(range(n)) + [None] if auto_advance else [0]
        cur = None
        for k in steps:
            if cur is not None and cur._thread is not None:
                cur._thread.join(timeout=120)
                cur = None
            if gen != _qt_seq_gen:
                return
            idx = start if k is None else (start + k) % n
            c = caps[idx]
            if c.get('_deleted'):
                continue        # removed mid-sequence: skip it, play on
            jpg = c.get('_jpg')
            if jpg is None and c['img']:
                jpg = anki_download_media(c['img'])
            if gen != _qt_seq_gen:
                return
            window.show_page_signal.emit(jpg, idx, n)
            if k is None:
                return              # home: image only, stay silent
            wav = c.get('_wav')
            if wav is None and c['mp3']:
                mp3 = anki_download_media(c['mp3'])
                wav = mp3_to_wav(mp3) if mp3 else None
            if not wav:
                time.sleep(1.0)     # audio-less page holds one second
                continue
            sb, eb = _range_to_bytes(wav, c['range'])
            if gen != _qt_seq_gen:
                return
            if _play_session is not None:
                _play_session.abort()
            s = AudioPlayback(wav)
            s.src_wav = wav
            s.src_cap = c       # lets a delete tell whether THIS page sounds
            _play_session = s
            s.play_bytes(sb)
            if eb is not None:
                s.set_end_bytes(eb)
            cur = s

    threading.Thread(target=worker, daemon=True).start()


def play_audio(event):
    # clicking the screenshot must not leave a result box in edit mode;
    # window.focusWidget() also works while the window is inactive
    fw = window.focusWidget()
    if fw is not None:
        fw.clearFocus()
    check_processing(round_audio_analysis_start_time_done)

    caps = getattr(window, '_qt_caps', None)
    if caps and len(caps) >= 2:
        # multi-page note: play only the page on display (no auto-advance)
        qt_play_pages(0, False)
        return

    global _play_session
    if not hasattr(window, 'audio_wav') or not window.audio_wav:
        return
    if window.end_byte is not None and window.end_byte <= window.start_byte:
        return
    print(f"[READ play_audio] start_byte={window.start_byte} end_byte={window.end_byte} anki_id={window.anki_id}")  # debug
    if _play_session is not None:
        _play_session.abort()
    _play_session = AudioPlayback(window.audio_wav)
    _play_session.src_wav = window.audio_wav   # tag: which buffer this session plays
    _play_session.play_bytes(window.start_byte)
    if window.end_byte is not None:
        _play_session.set_end_bytes(window.end_byte)
    # else: END still being analyzed; analyze_audio_end pushes it live



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
    96: 'Num0',
    97: 'Num1',
    98: 'Num2',
    99: 'Num3',
    100: 'Num4',
    101: 'Num5',
    102: 'Num6',
    103: 'Num7',
    104: 'Num8',
    105: 'Num9',
    110: 'Num.',
    111: 'Num/',
    106: 'Num*',
    109: 'Num-',
    107: 'Num+',
}


def hotkey_to_str(hk_list):
    hk = hk_list[0] if hk_list else {}
    if hk['type'] == 'mouse':
        btn = hk['button']
        if btn in ('middle', 'right'):
            display = btn.capitalize()
        else:
            display = btn.upper()  # x1 -> X1, x2 -> X2
        return f"Mouse {display}"
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
            display_key = raw_key.upper() if len(
                raw_key) == 1 else raw_key.capitalize()
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
    if hotkey_mode == 0:  # currently capturing, cancel
        on_hotkey_captured()
        return
    hotkey_mode = 0
    window.hotkey_btn.setChecked(True)
    window.hotkey_btn.setText('...')


def on_hotkey_captured():
    global hotkey_mode
    hotkey_mode = 1
    window.hotkey_btn.setChecked(False)
    window.hotkey_btn.setText(hotkey_to_str(config['hotkey']))


google_reachable = False


def check_google_reachable():
    global google_reachable
    try:
        urlopen(Request("https://www.google.com/generate_204",
                        headers={"User-Agent": "Mozilla/5.0"}),
                timeout=5)
        google_reachable = True
    except Exception:
        google_reachable = False


def open_default_search(term):
    global hide_on_click
    hide_on_click = False
    term = term.strip()

    # append a "meaning" keyword based on the source language for better web results
    src = config.get('src_lang', SRC_LANGS[0])
    suffix = {'日本語': '意味', '中文': '意思', 'English': 'meaning'}.get(src, '')
    if term and suffix:
        term = term + ' ' + suffix

    import webbrowser

    from urllib.parse import quote_plus
    if google_reachable:
        url = "https://www.google.com/search?q=" + quote_plus(term)
    else:
        url = "https://www.bing.com/search?q=.com/s?wd=" + quote_plus(term)
    webbrowser.open(url)


def show_custom_context_menu(widget, pos, font_size):
    menu = QMenu(widget)
    menu.setFont(QFont("Microsoft YaHei", font_size))
    menu.setStyleSheet(
        "QMenu::item:selected { background-color: #444; color: white; }"
        "QMenu::item:disabled { color: #bbb; }")

    cut = menu.addAction(ui('cut'))
    copy = menu.addAction(ui('copy'))
    paste = menu.addAction(ui('paste'))
    menu.addSeparator()
    undo = menu.addAction(ui('undo'))
    redo = menu.addAction(ui('redo')) 
    menu.addSeparator()
    search = menu.addAction(ui('search'))

    cut.triggered.connect(widget.cut)
    copy.triggered.connect(widget.copy)
    paste.triggered.connect(widget.paste)
    undo.triggered.connect(widget.undo)
    redo.triggered.connect(widget.redo)
    selected = widget_selected_text(widget)
    search.triggered.connect(lambda: open_default_search(selected))

    read_only = widget.isReadOnly()
    if isinstance(widget, QTextEdit):
        undo_avail = widget.document().isUndoAvailable()
        redo_avail = widget.document().isRedoAvailable()
    else:
        undo_avail = widget.isUndoAvailable()
        redo_avail = widget.isRedoAvailable()
    has_sel = bool(selected)
    cut.setEnabled(has_sel and not read_only)
    copy.setEnabled(has_sel)
    paste.setEnabled(bool(QApplication.clipboard().text()) and not read_only)
    undo.setEnabled(undo_avail and not read_only)
    redo.setEnabled(redo_avail and not read_only)
    search.setEnabled(has_sel)


    menu.exec_(widget.mapToGlobal(pos))


def show_copy_context_menu(widget, pos, font_size):
    selected = widget.selectedText()
    if not selected:
        return
    menu = QMenu(widget)
    menu.setFont(QFont("Microsoft YaHei", font_size))
    menu.setStyleSheet(
        "QMenu::item:selected { background-color: #444; color: white; }")
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
    global screenshot, screenshot_thread_handle, hotkey_mode
    hotkey_mode = -1
    screenshot_thread_stop.set()

    snip.close()
    bridge.click_snip.disconnect()

    screenshot_thread_handle.join()

    screenshot = []
    screenshot_thread_stop.clear()
    screenshot_thread_handle = threading.Thread(target=screenshot_thread,
                                                daemon=True)
    screenshot_thread_handle.start()

    window.reinit_snip_signal.emit()


def _reinit_snip_main_thread():
    global snip, hotkey_mode
    snip = Snip()
    time.sleep(
        0.5
    )  # test if click too fast after change monitor, error will happen in paintEvent. need better logic here
    hotkey_mode = 1
    bridge.click_snip.connect(snip.start)
    window.close_snip_signal.connect(snip.close_snip)
    window.cancel_drag_signal.connect(snip.cancel_drag)


def toggle_settings():
    global hide_on_click
    hide_on_click = False   # user opened settings: they need the UI
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

    def re_elide():
        # re-fit the anki path to the button's current width
        path = config.get('anki_path')
        if path:
            metrics = window.anki_path_btn.fontMetrics()
            window.anki_path_btn.setText(
                metrics.elidedText(path, Qt.ElideMiddle,
                                   window.anki_path_btn.width() - 10))

    QTimer.singleShot(0, re_elide)   # after the page is laid out


def check_processing(event):
    for i in range(100):
        if event.is_set():
            break
        else:
            QApplication.processEvents()
            time.sleep(0.05)
            window._toast = Toast(ui('processing'), duration=2000)
    else:
        print('time out in waiting for processing')  # test need more detail
    if hasattr(window, '_toast') and window._toast:
        window._toast.dismiss()
        window._toast = None


def pcm_to_wav_bytes(pcm_data, rate=44100, channels=2, bits=16):
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(bits // 8)
        wf.setframerate(rate)
        wf.writeframes(pcm_data)
    return buf.getvalue()


def detect_audio(audio_bytes, frame_duration_ms):
    rate = recorder.RATE
    channels = recorder.CHANNELS

    dtype_map = {8: np.int8, 16: np.int16, 32: np.int32}
    pcm_np = np.frombuffer(audio_bytes, dtype=dtype_map[recorder.BITS])

    sample_per_frame = int(rate * frame_duration_ms / 1000)
    n_frame = len(pcm_np) // (sample_per_frame * channels)

    frame = pcm_np[:n_frame * sample_per_frame * channels].reshape(
        n_frame, sample_per_frame, channels)
    frame = frame.astype(np.float32)
    max_val = 2**(recorder.BITS - 1)
    rms = np.sqrt(
        np.einsum('ijk,ijk->i', frame, frame) /
        (frame.shape[1] * frame.shape[2])) / max_val

    segment = 150
    cumsum = np.cumsum(np.pad(rms, segment // 2, mode='edge'))
    rms_moving_average = (cumsum[segment:] - cumsum[:-segment]) / segment

    return rms, rms_moving_average


def analyze_audio_start(audio_bytes, audio_start_time, rms, rms_moving_average,
                  frame_duration_ms, snip_index_in_sentences,
                  subtitle_sentences, ambiguous_diff_max):
    subtitle_start_time = 0
    # get start and end from subtitle
    subtitle_diff_left = 1
    subtitle_diff_triggered = False

    for i in range(snip_index_in_sentences, -1, -1):
        if subtitle_sentences[i][3] == -1:
            if subtitle_sentences[i][0] < ambiguous_diff_max or (
                    subtitle_sentences[i][1] < ambiguous_diff_max
                    and not subtitle_diff_triggered):
                matched = True
            else:
                matched = False
        elif subtitle_sentences[i][3] == 0:
            matched = False
        elif subtitle_sentences[i][3] == 1:
            matched = True
        if matched:
            subtitle_start_time = subtitle_sentences[i][2]
        else:
            subtitle_diff_left -= 1
            subtitle_diff_triggered = True
            if subtitle_diff_left <= 0:
                break
    
    for i in range(len(play_log)):
        s = play_log[i][0]
        e = play_log[i][1]
        if s < subtitle_start_time and subtitle_start_time < e:
            subtitle_start_time = e

    subtitle_start_frame = time_to_audio_frame(audio_start_time,
                                               frame_duration_ms, len(rms),
                                               subtitle_start_time)

    # shift start to middle to find first letter
    one_letter_audio_ms = 100
    letter_audio_frame_target = one_letter_audio_ms // frame_duration_ms
    letter_audio_frame_now = 0
    for i in range(subtitle_start_frame, len(rms)):
        if rms[i] > 0.005:
            letter_audio_frame_now += 1
        else:
            letter_audio_frame_now -= 2
            letter_audio_frame_now = max(letter_audio_frame_now, 0)
        if letter_audio_frame_now >= letter_audio_frame_target:
            subtitle_start_frame_to_middle = i
            break
    else:
        subtitle_start_frame_to_middle = subtitle_start_frame

    # shift start to side to find blank
    blank_audio_ms_start = 200
    blank_frame_target_start = blank_audio_ms_start // frame_duration_ms
    blank_frame_now = 0
    for i in range(subtitle_start_frame_to_middle, -1, -1):
        if rms[i] < 0.01 or rms[i] < rms_moving_average[i]:
            blank_frame_now += 1
        else:
            blank_frame_now -= 2
            blank_frame_now = max(blank_frame_now, 0)
        if blank_frame_now >= blank_frame_target_start:
            subtitle_start_frame_to_middle_to_side = i
            break
    else:
        subtitle_start_frame_to_middle_to_side = 0

    subtitle_start_frame_to_middle_to_side_after_blank_frame, search_ms = check_blank_frame(subtitle_start_frame_to_middle_to_side,-200,rms,rms_moving_average,frame_duration_ms,0)
    start_byte_frame = int(subtitle_start_frame_to_middle_to_side_after_blank_frame *
                           frame_duration_ms * recorder.BYTES_PER_SEC / 1000)
    start_byte = snap_to_min_energy(audio_bytes, start_byte_frame,
                                        recorder.BYTES_PER_SAMPLE,
                                        recorder.BYTES_PER_SEC, search_ms)
    
    analyze_audio_start._dbg = [
        subtitle_start_time, subtitle_start_frame,
        subtitle_start_frame_to_middle, subtitle_start_frame_to_middle_to_side,
        subtitle_start_frame_to_middle_to_side_after_blank_frame,
        start_byte]  # test need delete
    
    window.start_byte = start_byte

    return start_byte, subtitle_start_frame_to_middle_to_side_after_blank_frame


def analyze_audio_end(audio_bytes, audio_start_time, rms, rms_moving_average,
                  frame_duration_ms, snip_index_in_sentences,
                  subtitle_sentences,ambiguous_diff_max,start_frame):
    subtitle_end_time = 0
    subtitle_diff_left = 1
    subtitle_diff_triggered = False

    for i in range(snip_index_in_sentences, len(subtitle_sentences)):
        if subtitle_sentences[i][3] == -1:
            if subtitle_sentences[i][0] < ambiguous_diff_max or (
                    subtitle_sentences[i][1] < ambiguous_diff_max
                    and not subtitle_diff_triggered):
                matched = True
            else:
                matched = False
        elif subtitle_sentences[i][3] == 0:
            matched = False
        elif subtitle_sentences[i][3] == 1:
            matched = True
        if matched:
            subtitle_end_time = subtitle_sentences[i][2]
        else:
            subtitle_diff_left -= 1
            subtitle_diff_triggered = True
            if subtitle_diff_left <= 0:
                break
    
    # start_frame is an RMS frame index; play_log stores wall-clock times.
    # Convert before comparing (frame i starts at audio_start_time + i*20ms)
    start_time = audio_start_time + start_frame * frame_duration_ms / 1000
    for i in range(len(play_log)):
        s = play_log[i][0]
        if start_time < s and s < subtitle_end_time:
            subtitle_end_time = s
            
    subtitle_end_frame = time_to_audio_frame(audio_start_time,
                                            frame_duration_ms, len(rms),
                                            subtitle_end_time)

    # shift end to middle to find first letter
    one_letter_audio_ms = 100
    letter_audio_frame_target = one_letter_audio_ms // frame_duration_ms
    letter_audio_frame_now = 0
    for i in range(subtitle_end_frame, -1, -1):
        if rms[i] > 0.005:
            letter_audio_frame_now += 1
        else:
            letter_audio_frame_now -= 2
            letter_audio_frame_now = max(letter_audio_frame_now, 0)
        if letter_audio_frame_now >= letter_audio_frame_target:
            subtitle_end_frame_to_middle = i
            break
    else:
        subtitle_end_frame_to_middle = subtitle_end_frame

    # shift end to side to find blank
    blank_audio_ms_end = 150
    blank_frame_target_end = blank_audio_ms_end // frame_duration_ms
    blank_frame_now = 0
    for i in range(subtitle_end_frame_to_middle, len(rms)):
        if rms[i] < 0.01 or rms[i] < rms_moving_average[i]:
            blank_frame_now += 1
        else:
            blank_frame_now -= 2
            blank_frame_now = max(blank_frame_now, 0)
        if blank_frame_now >= blank_frame_target_end:
            subtitle_end_frame_to_middle_to_side = i
            break
    else:
        subtitle_end_frame_to_middle_to_side = len(rms) - 1


    subtitle_end_frame_to_middle_to_side_after_blank_frame, search_ms = check_blank_frame(subtitle_end_frame_to_middle_to_side,200,rms,rms_moving_average,frame_duration_ms,0)
    subtitle_end_frame_to_middle_to_side_after_blank_frame = max(subtitle_end_frame_to_middle_to_side_after_blank_frame,start_frame)

    end_bytes_frame = int(subtitle_end_frame_to_middle_to_side_after_blank_frame *
                         frame_duration_ms * recorder.BYTES_PER_SEC / 1000)
    end_byte = snap_to_min_energy(audio_bytes, end_bytes_frame ,
                                        recorder.BYTES_PER_SAMPLE,
                                        recorder.BYTES_PER_SEC, search_ms)
    
    # test need delete
    analyze_audio_end._dbg = [
        subtitle_end_time, subtitle_end_frame,
        subtitle_end_frame_to_middle, subtitle_end_frame_to_middle_to_side,
        subtitle_end_frame_to_middle_to_side_after_blank_frame,
        end_byte]  # test need delete
    window.end_byte = end_byte
    # deliver END to the live session if it is playing THIS capture

    if _play_session is not None and getattr(_play_session, 'src_wav', None) is window.audio_wav:
        _play_session.set_end_bytes(end_byte)

    return end_byte, subtitle_end_frame_to_middle_to_side_after_blank_frame
    # check if abnormal number
    #if subtitle_start_frame_to_right > subtitle_end_frame_to_left:
        #subtitle_start_frame_to_right = subtitle_start_frame
        #subtitle_end_frame_to_left = subtitle_end_frame


def analyze_audio_trim(frame_duration_ms, rms, rms_moving_average, start_byte, start_frame, end_byte, end_frame, audio_bytes):

    # trim a bigger range compared to play time
    min_gap_ms = 80
    min_gap_frame = int(min_gap_ms / frame_duration_ms)

    min_gap_frame_left = min_gap_frame
    trim_start_frame = -1
    trim_time_target_before_play_start = 3.5
    trim_start_frame_total = int(trim_time_target_before_play_start * 1000 /
                                frame_duration_ms)
    trim_start_frame_left = trim_start_frame_total
    for i in range(start_frame, -1, -1):
        if rms[i] > 0.015:
            min_gap_frame_left = min_gap_frame
        else:
            min_gap_frame_left -= 1
        if min_gap_frame_left < 0:
            trim_start_frame_left -= 1
            overshoot = abs(i - start_frame) - trim_start_frame_total
            if overshoot > 0:
                # Decay faster the further we overshoot the target window
                trim_start_frame_left -= 3 + overshoot // 10
        if trim_start_frame_left <= 0:
            trim_start_frame = i
            break

    min_gap_frame_left = min_gap_frame
    trim_end_frame = -1
    trim_time_target_after_play_end = 3
    trim_end_frame_total = int(trim_time_target_after_play_end * 1000 /
                              frame_duration_ms)
    trim_end_frame_left = trim_end_frame_total
    for i in range(end_frame, len(rms)):
        if rms[i] > 0.015:
            min_gap_frame_left = min_gap_frame
        else:
            min_gap_frame_left -= 1
        if min_gap_frame_left < 0:
            trim_end_frame_left -= 1
            if abs(i - end_frame) > trim_end_frame_total:
                trim_end_frame_left -= 2
        if trim_end_frame_left <= 0:
            trim_end_frame = i
            break

    if trim_start_frame == -1:
        trim_start_bytes = start_byte
    else:
        trim_start_frame, search_ms = check_blank_frame(trim_start_frame,-2000,rms,rms_moving_average,frame_duration_ms,0.01)
        trim_start_frame = min(trim_start_frame, start_frame)
        trim_start_bytes = int(trim_start_frame * frame_duration_ms *
                               recorder.BYTES_PER_SEC / 1000)
        trim_start_bytes = snap_to_min_energy(audio_bytes, trim_start_bytes,
                                              recorder.BYTES_PER_SAMPLE,
                                              recorder.BYTES_PER_SEC, search_ms)

    if trim_end_frame == -1:
        trim_end_bytes = end_byte
    else:
        trim_end_frame, search_ms = check_blank_frame(trim_end_frame,1000,rms,rms_moving_average,frame_duration_ms,0.01)
        trim_end_frame = max(trim_end_frame,end_frame)
        trim_end_bytes = int(trim_end_frame * frame_duration_ms *
                             recorder.BYTES_PER_SEC / 1000)
        trim_end_bytes = snap_to_min_energy(audio_bytes, trim_end_bytes,
                                            recorder.BYTES_PER_SAMPLE,
                                            recorder.BYTES_PER_SEC, search_ms)

    if trim_start_bytes == trim_end_bytes:
        trim_start_bytes = 0
        trim_end_bytes = len(audio_bytes) - 1

    play_start_bytes_remove_blank = start_byte - trim_start_bytes
    play_end_bytes_remove_blank = end_byte - trim_start_bytes

    play_end_bytes_remove_blank = min(play_end_bytes_remove_blank,trim_end_bytes - trim_start_bytes)
    
    play_start_time = max(play_start_bytes_remove_blank / recorder.BYTES_PER_SEC, 0)
    play_end_time = max(play_end_bytes_remove_blank / recorder.BYTES_PER_SEC, 0)

    return audio_bytes[
        trim_start_bytes:
        trim_end_bytes], play_start_time, play_end_time

def analyze_audio(audio_bytes, audio_start_time, rms, rms_moving_average,
                  frame_duration_ms, snip_index_in_sentences,
                  subtitle_sentences):
    return
    subtitle_start_time = 0
    subtitle_end_time = 0

    # get start and end from subtitle
    subtitle_diff_min = 0.04
    subtitle_diff_ideal = 0.15

    subtitle_start_quality = 0
    subtitle_diff_left = 1
    subtitle_diff_triggered = False
    for i in range(snip_index_in_sentences, -1, -1):
        if subtitle_sentences[i][3] == -1:
            if subtitle_sentences[i][0] < subtitle_diff_ideal or (
                    subtitle_sentences[i][1] < subtitle_diff_ideal
                    and not subtitle_diff_triggered):
                matched = True
            else:
                matched = False
        elif subtitle_sentences[i][3] == 0:
            matched = False
        elif subtitle_sentences[i][3] == 1:
            matched = True
        if matched:
            subtitle_start_time = subtitle_sentences[i][2]
        else:
            subtitle_diff_left -= 1
            subtitle_diff_triggered = True
            if subtitle_diff_left <= 0:
                subtitle_start_quality = min(
                    (subtitle_sentences[i][0] - subtitle_diff_min) /
                    (subtitle_diff_ideal - subtitle_diff_min), 1)
                break

    subtitle_end_quality = 0
    subtitle_diff_left = 1
    subtitle_diff_triggered = False
    for i in range(snip_index_in_sentences, len(subtitle_sentences)):
        if subtitle_sentences[i][3] == -1:
            if subtitle_sentences[i][0] < subtitle_diff_ideal or (
                    subtitle_sentences[i][1] < subtitle_diff_ideal
                    and not subtitle_diff_triggered):
                matched = True
            else:
                matched = False
        elif subtitle_sentences[i][3] == 0:
            matched = False
        elif subtitle_sentences[i][3] == 1:
            matched = True
        if matched:
            subtitle_end_time = subtitle_sentences[i][2]
        else:
            subtitle_diff_left -= 1
            subtitle_diff_triggered = True
            if subtitle_diff_left <= 0:
                subtitle_end_quality = min(
                    (subtitle_sentences[i][0] - subtitle_diff_min) /
                    (subtitle_diff_ideal - subtitle_diff_min), 1)
                break

    for i in range(len(play_log)):
        s = play_log[i][0]
        e = play_log[i][1]
        if e < subtitle_start_time or subtitle_end_time < s:
            pass
        elif s < subtitle_start_time and subtitle_end_time < e:
            subtitle_end_time = subtitle_start_time
        elif s < subtitle_start_time and e < subtitle_end_time:
            subtitle_start_time = e
        elif subtitle_start_time < s and subtitle_end_time < e:
            subtitle_end_time = s
        elif subtitle_start_time < s and e < subtitle_end_time:
            seg_a = s - subtitle_start_time
            seg_b = subtitle_end_time - e
            if seg_a * 2 < seg_b:  # normally take before, if too short, take after
                subtitle_start_time = e
            else:
                subtitle_end_time = s

    print(f"audio_start_time={audio_start_time:.3f}")
    print(f"subtitle_start_time={subtitle_start_time:.3f}")
    print(f"subtitle_end_time={subtitle_end_time:.3f}")
    print(f"len(rms)={len(rms)}")
    print(
        f"rms covers until={audio_start_time + len(rms) * frame_duration_ms / 1000:.3f}"
    )

    # change to frame
    length_rms = len(rms)
    subtitle_start_frame = time_to_audio_frame(audio_start_time,
                                               frame_duration_ms, length_rms,
                                               subtitle_start_time)
    subtitle_end_frame = time_to_audio_frame(audio_start_time,
                                             frame_duration_ms, length_rms,
                                             subtitle_end_time)

    # shift start and end to middle to find first letter
    one_letter_audio_ms = 100
    letter_audio_frame_target = one_letter_audio_ms // frame_duration_ms
    letter_audio_frame_now = 0
    for i in range(subtitle_start_frame, len(rms)):
        if rms[i] > 0.005:
            letter_audio_frame_now += 1
        else:
            letter_audio_frame_now -= 2
            letter_audio_frame_now = max(letter_audio_frame_now, 0)
        if letter_audio_frame_now >= letter_audio_frame_target:
            subtitle_start_frame_to_right = i
            break
    else:
        subtitle_start_frame_to_right = subtitle_start_frame
    letter_audio_frame_now = 0
    for i in range(subtitle_end_frame, -1, -1):
        if rms[i] > 0.005:
            letter_audio_frame_now += 1
        else:
            letter_audio_frame_now -= 2
            letter_audio_frame_now = max(letter_audio_frame_now, 0)
        if letter_audio_frame_now >= letter_audio_frame_target:
            subtitle_end_frame_to_left = i
            break
    else:
        subtitle_end_frame_to_left = subtitle_end_frame

    # check if abnormal number
    if subtitle_start_frame_to_right > subtitle_end_frame_to_left:
        subtitle_start_frame_to_right = subtitle_start_frame
        subtitle_end_frame_to_left = subtitle_end_frame

    # shift start and end to side to find blank
    blank_audio_ms_start = 200 - subtitle_start_quality * 100
    blank_frame_target_start = blank_audio_ms_start // frame_duration_ms
    blank_frame_now = 0
    for i in range(subtitle_start_frame_to_right, -1, -1):
        if rms[i] < 0.01 or rms[i] < rms_moving_average[i]:
            blank_frame_now += 1
        else:
            blank_frame_now -= 2
            blank_frame_now = max(blank_frame_now, 0)
        if blank_frame_now >= blank_frame_target_start:
            subtitle_start_frame_to_right_to_left = i
            break
    else:
        subtitle_start_frame_to_right_to_left = 0
    blank_audio_ms_end = 200 - subtitle_end_quality * 100
    blank_frame_target_end = blank_audio_ms_end // frame_duration_ms
    blank_frame_now = 0
    for i in range(subtitle_end_frame_to_left, len(rms)):
        if rms[i] < 0.01 or rms[i] < rms_moving_average[i]:
            blank_frame_now += 1
        else:
            blank_frame_now -= 2
            blank_frame_now = max(blank_frame_now, 0)
        if blank_frame_now >= blank_frame_target_end:
            subtitle_end_frame_to_left_to_right = i
            break
    else:
        subtitle_end_frame_to_left_to_right = len(rms) - 1

    # test need delete
    debug_frames = (
        subtitle_start_time,
        subtitle_end_time,
        subtitle_start_frame,
        subtitle_end_frame,
        subtitle_start_frame_to_right,
        subtitle_end_frame_to_left,
        subtitle_start_frame_to_right_to_left,
        subtitle_end_frame_to_left_to_right,
    )

    subtitle_start_frame_to_right_to_left, search_ms = check_blank_frame(subtitle_start_frame_to_right_to_left,-200,rms,rms_moving_average,frame_duration_ms,0)
    play_start_bytes = int(subtitle_start_frame_to_right_to_left *
                           frame_duration_ms * recorder.BYTES_PER_SEC / 1000)
    play_start_bytes = snap_to_min_energy(audio_bytes, play_start_bytes,
                                        recorder.BYTES_PER_SAMPLE,
                                        recorder.BYTES_PER_SEC, search_ms)

    subtitle_end_frame_to_left_to_right, search_ms = check_blank_frame(subtitle_end_frame_to_left_to_right,400,rms,rms_moving_average,frame_duration_ms,0)
    play_end_bytes = int(subtitle_end_frame_to_left_to_right *
                         frame_duration_ms * recorder.BYTES_PER_SEC / 1000)
    play_end_bytes = snap_to_min_energy(audio_bytes, play_end_bytes,
                                        recorder.BYTES_PER_SAMPLE,
                                        recorder.BYTES_PER_SEC, search_ms)

    # trim a bigger range compared to play time
    min_gap_ms = 80
    min_gap_frame = int(min_gap_ms / frame_duration_ms)

    min_gap_frame_left = min_gap_frame
    trim_start_frame = -1
    trim_time_target_before_play_start = 3.5
    trim_start_frame_total = int(trim_time_target_before_play_start * 1000 /
                                frame_duration_ms)
    trim_start_frame_left = trim_start_frame_total
    for i in range(subtitle_start_frame_to_right_to_left, -1, -1):
        if rms[i] > 0.015:
            min_gap_frame_left = min_gap_frame
        else:
            min_gap_frame_left -= 1
        if min_gap_frame_left < 0:
            trim_start_frame_left -= 1
            overshoot = abs(i - subtitle_start_frame_to_right_to_left) - trim_start_frame_total
            if overshoot > 0:
                # Decay faster the further we overshoot the target window
                trim_start_frame_left -= 3 + overshoot // 10
        if trim_start_frame_left <= 0:
            trim_start_frame = i
            break

    min_gap_frame_left = min_gap_frame
    trim_end_frame = -1
    trim_time_target_after_play_end = 3
    trim_end_frame_total = int(trim_time_target_after_play_end * 1000 /
                              frame_duration_ms)
    trim_end_frame_left = trim_end_frame_total
    for i in range(subtitle_end_frame_to_left_to_right, len(rms)):
        if rms[i] > 0.015:
            min_gap_frame_left = min_gap_frame
        else:
            min_gap_frame_left -= 1
        if min_gap_frame_left < 0:
            trim_end_frame_left -= 1
            if abs(i - subtitle_end_frame_to_left_to_right) > trim_end_frame_total:
                trim_end_frame_left -= 2
        if trim_end_frame_left <= 0:
            trim_end_frame = i
            break

    if trim_start_frame == -1:
        trim_start_bytes = play_start_bytes
    else:
        trim_start_frame, search_ms = check_blank_frame(trim_start_frame,-2000,rms,rms_moving_average,frame_duration_ms,0.01)
        trim_start_frame = min(trim_start_frame, subtitle_start_frame_to_right_to_left)
        trim_start_bytes = int(trim_start_frame * frame_duration_ms *
                               recorder.BYTES_PER_SEC / 1000)
        trim_start_bytes = snap_to_min_energy(audio_bytes, trim_start_bytes,
                                              recorder.BYTES_PER_SAMPLE,
                                              recorder.BYTES_PER_SEC, search_ms)

    if trim_end_frame == -1:
        trim_end_bytes = play_end_bytes
    else:
        trim_end_frame, search_ms = check_blank_frame(trim_end_frame,1000,rms,rms_moving_average,frame_duration_ms,0.01)
        trim_end_frame = max(trim_end_frame,subtitle_end_frame_to_left_to_right)
        trim_end_bytes = int(trim_end_frame * frame_duration_ms *
                             recorder.BYTES_PER_SEC / 1000)
        trim_end_bytes = snap_to_min_energy(audio_bytes, trim_end_bytes,
                                            recorder.BYTES_PER_SAMPLE,
                                            recorder.BYTES_PER_SEC, search_ms)

    if trim_start_bytes == trim_end_bytes:
        trim_start_bytes = 0
        trim_end_bytes = len(audio_bytes) - 1

    play_start_bytes_remove_blank = play_start_bytes - trim_start_bytes
    play_end_bytes_remove_blank = play_end_bytes - trim_start_bytes

    play_end_bytes_remove_blank = min(play_end_bytes_remove_blank,trim_end_bytes - trim_start_bytes)
    
    play_start_time = max(play_start_bytes_remove_blank / recorder.BYTES_PER_SEC, 0)
    play_end_time = max(play_end_bytes_remove_blank / recorder.BYTES_PER_SEC, 0)

    return audio_bytes[
        trim_start_bytes:
        trim_end_bytes], play_start_time, play_end_time, debug_frames


def check_blank_frame(raw_frame,raw_search_ms,rms,rms_moving_average,frame_duration_ms,threshold):
    outer_bound = -1
    inner_bound = -1
    if raw_search_ms > 0:
        for i in range(len(rms)-1, -1, -1):
            if rms[i] != 0 and rms_moving_average[i] > threshold:
                outer_bound = i
                break
        if outer_bound == -1:
            outer_bound = len(rms)-1
            inner_bound = raw_frame
        else:
            for i in range(min(outer_bound,raw_frame), -1, -1):
                if rms[i] != 0 and rms_moving_average[i] > threshold:
                    inner_bound = i
                    break
            if inner_bound == -1:
                inner_bound = raw_frame
        search_ms = min((outer_bound-inner_bound+1)*frame_duration_ms,raw_search_ms)
    elif raw_search_ms < 0:
        for i in range(len(rms)):
            if rms[i] != 0 and rms_moving_average[i] > threshold:
                outer_bound = i
                break
        if outer_bound == -1:
            outer_bound = 0
            inner_bound = raw_frame
        else:
            for i in range(max(outer_bound,raw_frame),len(rms)):
                if rms[i] != 0 and rms_moving_average[i] > threshold:
                    inner_bound = i
                    break
            if inner_bound == -1:
                inner_bound = raw_frame
        search_ms = max((outer_bound-inner_bound-1)*frame_duration_ms,raw_search_ms)
    # print(f"{raw_frame=}, {inner_bound=}, {search_ms=}, {outer_bound=}")
    return inner_bound, search_ms


def snap_to_min_energy(audio_bytes,
                       target_byte,
                       bytes_per_sample,
                       bytes_per_sec,
                       search_ms,
                       window_ms=30):
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

    samples = np.frombuffer(audio_bytes[region_lo:region_hi],
                            dtype=np.int16).astype(np.int64)
    # collapse interleaved channel values into per-FRAME energy, so every
    # index below lives in sample-frame units (bytes_per_sample bytes).
    # indexing the raw int16 array with frame indices halved every
    # measured position and doubled the returned displacement
    spf = bytes_per_sample // 2          # int16 values per frame
    n_frames = len(samples) // spf
    frame_sq = (samples[:n_frames * spf] *
                samples[:n_frames * spf]).reshape(n_frames, spf).sum(axis=1)

    # Cumulative sum of squares -> any window's energy in O(1).
    # int64 is required: int16^2 accumulated over the region can overflow int32.
    cumsum_sq = np.concatenate(([0], np.cumsum(frame_sq)))

    half_n = half_window_bytes // bytes_per_sample

    # Candidate frame range, clamped so the window never goes out of bounds.
    cand_lo = max(half_n, (search_lo_byte - region_lo) // bytes_per_sample)
    cand_hi = min(
        n_frames - half_n,
        (search_hi_byte - region_lo) // bytes_per_sample + 1)
    if cand_hi <= cand_lo:
        return aligned_target

    # Vectorized energy for every candidate at once.
    energies = (cumsum_sq[cand_lo + half_n:cand_hi + half_n] -
                cumsum_sq[cand_lo - half_n:cand_hi - half_n])
    best_idx = cand_lo + int(np.argmin(energies))

    return region_lo + best_idx * bytes_per_sample


def time_to_audio_frame(audio_start_time, frame_duration_ms, length_rms,
                        target_time):
    i = int((target_time - audio_start_time) * 1000 // frame_duration_ms)
    i = min(max(i, 0), length_rms - 1)
    return i


def wav_to_mp3(wav_bytes, kbps=64):
    result = []

    def cb(ptr, size):
        result.append(ptr[:size])

    _bass_code_cast(_bass_code_cast_CB(cb), wav_bytes, len(wav_bytes), b'mp3',
                    kbps, 0)
    return b''.join(result)


class BASS_CHANNELINFO(Structure):
    _fields_ = [
        ('freq', c_ulong),
        ('chans', c_ulong),
        ('flags', c_ulong),
        ('ctype', c_ulong),
        ('origres', c_ulong),
        ('plugin', c_ulong),
        ('sample', c_ulong),
        ('filename', c_char_p),
    ]

_bass = WinDLL(os.path.join(BASE, 'bass.dll'))
_bass.BASS_StreamCreateFile.restype = c_ulong
_bass.BASS_StreamCreateFile.argtypes = [c_bool, c_char_p, c_uint64, c_uint64, c_ulong]
_bass.BASS_ChannelGetData.restype = c_ulong
_bass.BASS_ChannelGetData.argtypes = [c_ulong, c_char_p, c_ulong]
_bass.BASS_ChannelIsActive.restype = c_ulong
_bass.BASS_ChannelIsActive.argtypes = [c_ulong]
_bass.BASS_StreamFree.restype = c_bool
_bass.BASS_StreamFree.argtypes = [c_ulong]
_bass.BASS_ChannelGetInfo.restype = c_bool
_bass.BASS_ChannelGetInfo.argtypes = [c_ulong, POINTER(BASS_CHANNELINFO)]
_bass.BASS_ErrorGetCode.restype = c_int
_bass.BASS_Init.restype = c_bool
_bass.BASS_Init.argtypes = [c_int, c_ulong, c_ulong, c_void_p, c_void_p]
_bass.BASS_SetDevice.restype = c_bool
_bass.BASS_SetDevice.argtypes = [c_ulong]
BASS_STREAM_DECODE = 0x200000


def _bass_bind_thread():
    # BASS holds its device setting PER THREAD, so a fresh worker thread
    # cannot even create a decode-only stream until it binds one. Device
    # 0 is the "no sound" device: decoding only, no audio hardware, so it
    # never interferes with the pyaudio playback path
    if not _bass.BASS_SetDevice(0):
        _bass.BASS_Init(0, 44100, 0, None, None)   # ALREADY = harmless
        _bass.BASS_SetDevice(0)

def mp3_to_wav(mp3_bytes):
    stream = _bass.BASS_StreamCreateFile(True, mp3_bytes, 0, len(mp3_bytes), BASS_STREAM_DECODE)
    if not stream and _bass.BASS_ErrorGetCode() == 8:   # BASS_ERROR_INIT
        _bass_bind_thread()
        stream = _bass.BASS_StreamCreateFile(
            True, mp3_bytes, 0, len(mp3_bytes), BASS_STREAM_DECODE)
    if not stream:
        # BASS error codes are per-thread: read it right here. 8=INIT,
        # 41=FILEFORM, 44=CODEC, 2=FILEOPEN, 6=FORMAT, 46=BUSY
        print('BASS_StreamCreateFile failed: err=%s len=%s head=%r thread=%s'
              % (_bass.BASS_ErrorGetCode(),
                 len(mp3_bytes) if mp3_bytes else 0,
                 (mp3_bytes or b'')[:4],
                 threading.current_thread().name))
        return None
    info = BASS_CHANNELINFO()
    _bass.BASS_ChannelGetInfo(stream, byref(info))
    print(f'mp3_to_wav: freq={info.freq}, chans={info.chans}')
    chunks = []
    buf = (c_char * 0x10000)()
    while True:
        n = _bass.BASS_ChannelGetData(stream, buf, 0x10000)
        if n == 0xFFFFFFFF:
            break
        if n > 0:
            chunks.append(buf.raw[:n])
    _bass.BASS_StreamFree(stream)
    pcm = b''.join(chunks)
    print(f'mp3_to_wav: pcm={len(pcm)} bytes, wav duration={len(pcm)/(info.freq*info.chans*2):.3f}s')
    return pcm_to_wav_bytes(pcm, rate=info.freq, channels=info.chans)


def anki_create_deck():
    if DECK_NAME not in (invoke("deckNames") or {}).get("result", []):
        invoke("createDeck", deck=config['anki_deck_name'])
    else:
        update_config('anki_deck_ok', True)


def anki_create_model():
    ANKI_MODEL_VERSION = 2
    FRONT_TEMPLATE = r"""<div id="spellText" style="font-size: min(48px, 8vh)">{{spell}}</div>
<script>
   // A lone space inside spell is stray (OCR, hand edits). A run of two
   // or more is deliberate, so leave those alone. Walk text nodes only:
   // the field can carry html, and touching innerHTML would eat spaces
   // inside tags. fromCharCode(160) instead of an escape, since
   // backslashes do not survive the trip through Python and AnkiConnect.
   (function () {
       var SP = new RegExp('[ ' + String.fromCharCode(160) + ']+', 'g');
       function strip(node) {
           for (var n = node.firstChild; n; n = n.nextSibling) {
               if (n.nodeType === 3) {
                   n.nodeValue = n.nodeValue.replace(SP, function (m) {
                       return m.length === 1 ? '' : m;
                   });
               } else if (n.nodeType === 1) {
                   strip(n);
               }
           }
       }
       var el = document.getElementById('spellText');
       if (el) strip(el);
   })();
</script>
<script>
   // Purpose of this script: (1) stop ongoing audio from previous card (2) clean up memory from previous card (3) preload back side because it is heavy
   
   function fadeStop(obj, ms) {
       if (!obj) return; 
       if (obj.gain) {
           var now = obj.ctx.currentTime;
           // A card can be answered while its clip is still playing. Fading
           // a flat 600 ms would then keep sounding past the end of the
           // range the user selected, so never fade for longer than what is
           // actually left of it (the Back template publishes the bounds).
           if (obj.endT != null && obj.webStart != null) {
               var leftMs = (obj.endT
                   - (obj.webOffset + (now - obj.webStart))) * 1000;
               if (leftMs < ms) ms = Math.max(0, leftMs);
           }
           obj.gain.gain.cancelScheduledValues(now);
           obj.gain.gain.setValueAtTime(obj.gain.gain.value, now);
           if (ms < 20) {           // nothing left worth curving
               obj.gain.gain.setValueAtTime(0, now);
               try { obj.node.stop(); } catch (e) {}
               return;
           }
   
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
           window._apSeqArm = null;
           window._apSeqNext = null;
           window._apReloadAudio = null;
           window._apRenderImage = null;
       } catch (e) {}
       // Invalidate every pending callback (timers/rAF/promise chains)
       // left behind by previous cards: they compare their captured
       // generation against this counter and bail out when stale.
       window.top._apGen = (window.top._apGen || 0) + 1;
   
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
   
           // play range rides in the mp3 filename: _r{start_us}-{end_us}
           var playTime = null;
           var rawPT = fname.match(/_r(\d+)-(\d+)\.[^.]+$/);
           if (rawPT && +rawPT[2] > +rawPT[1]) {
               playTime = [+rawPT[1] / 1e6, +rawPT[2] / 1e6];
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
                   return createImageBitmap(blob).then(function (bm) {
                       return { bm: bm, blob: blob };
                   });
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
                   bitmapPromise.then(function (res) {
                       entry.bitmap = res.bm;
                       entry.blob = res.blob;   // kept: re-decode source after iOS purges the bitmap
                   });
               }
               })
               .catch(function () {
               try {
                   ac.close();
               } catch (e) {}
               });
   }, 0);
</script>"""
    BACK_TEMPLATE = r"""<script>
/* ============================================================
   TUNABLES - every adjustable number of the card lives here.
   Edit a value, rebuild, push. Sizes/colours/fonts are in the
   styling tab (CSS), grouped under :root at its top.
   This block must stay FIRST: the scripts below read it while
   they run, and a browser executes script blocks in order.
   ============================================================ */
window._apCfg = {
    /* ---- image frame ---- */
    landscapeHeightRatio: 0.35, /* landscape: max img height = screen.width  * this */
    portraitHeightRatio: 0.5,   /* portrait:  max img height = screen.height * this */
    resizeDebounceMs: 150,      /* quiet time after a resize before reflowing */
    resizeSettleMs: 300,        /* second reflow, for late layout settling */

    /* ---- page transitions ---- */
    wipeMs: 300,                /* wipe sweep / home-return crossfade */
    wipeCleanupMs: 420,         /* when the frozen snapshot is dropped */
    waveFadeOutMs: 160,         /* waveform fade-out on a page change */
    waveSwapMs: 220,            /* when the next page's audio is loaded */
    silentHoldMs: 1000,         /* how long a page without audio holds */

    /* ---- audio ---- */
    minPlayS: 0.2,              /* ranges this short or shorter stay silent */
    audioFadeMaxS: 0.3,         /* longest fade at a clip edge */
    audioFadeRefVol: 0.01,      /* loudness that already needs a full fade */
    switchFadeS: 0.15,          /* fade when a page switch cuts playback */
    switchStopMs: 200,          /* when the faded-out source is stopped */
    targetPeakMobile: 0.45,     /* normalized peak, phones */
    targetPeakDesktop: 0.3,     /* normalized peak, desktop */
    maxGainMobile: 10,          /* gain ceiling, phones */
    maxGainDesktop: 3,          /* gain ceiling, desktop */

    /* ---- ios audio self-healing (rarely worth touching) ---- */
    watchdogMs: [300, 1200],    /* clock checks after playback starts */
    rebuildQuota: 4,            /* context rebuilds allowed per tap */
    warmupMs: 400,              /* clock probe after returning to the app */
    warmupTries: 5              /* probe attempts before giving up */
};
</script>
<script>
(function () {
    // fresh card: the window SURVIVES across cards (that is what makes
    // _apCache work), so per-card state frozen by the previous card must
    // be cleared here or it leaks into this one
    // bump the card generation FIRST: every delayed callback of the
    // previous card compares its captured generation and bails out
    window.top._apGen = (window.top._apGen || 0) + 1;
    window._apFrame = null;
    window._apSeqArm = null;
    window._apSeqNext = null;
    window._apSeqStop = null;
    // multi-capture parser: pair files by everything before the LAST
    // underscore; metadata rides in the names (_p quad / _r range-us)
    function stem(fn) {
        var b = fn.replace(/\.[^.]+$/, '');
        var i = b.lastIndexOf('_');
        return i < 0 ? fn : b.slice(0, i);
    }
    function srcs(html) {
        var out = [], re = /src="([^"]+)"/g, m;
        while ((m = re.exec(html))) out.push(m[1]);
        return out;
    }
    var caps = [], byStem = {};
    srcs(`{{screenshot}}`).forEach(function (fn) {
        var s = stem(fn), c = byStem[s];
        if (!c) { c = byStem[s] = { stem: s }; caps.push(c); }
        c.img = fn;
        var m = fn.match(/_p(\d+(?:-\d+){7})\.[^.]+$/);
        if (m) {
            var v = m[1].split('-').map(Number);
            if (v.some(function (x) { return x; })) {
                c.quad = [[v[0], v[1]], [v[2], v[3]],
                          [v[4], v[5]], [v[6], v[7]]];
            }
        }
    });
    srcs(`{{audio}}`).forEach(function (fn) {
        var s = stem(fn), c = byStem[s];
        if (!c) { c = byStem[s] = { stem: s }; caps.push(c); }
        c.mp3 = fn;
        var m = fn.match(/_r(\d+)-(\d+)\.[^.]+$/);
        if (m) {
            var a = +m[1] / 1e6, b = +m[2] / 1e6;
            if (b > a) c.range = [a, b];
        }
    });
    // LEGACY MERGE: old cards have one jpg and one mp3 whose names never
    // pair (and carry no _p/_r metadata) - collapse them into ONE capture
    if (caps.length === 2) {
        var io_ = caps.filter(function (c) { return c.img && !c.mp3 && !c.quad; });
        var ao_ = caps.filter(function (c) { return c.mp3 && !c.img && !c.range; });
        if (io_.length === 1 && ao_.length === 1) {
            caps = [{ stem: io_[0].stem, img: io_[0].img, mp3: ao_[0].mp3 }];
        }
    }
    var start = 0, key = 'ap-page:' + (caps.length ? caps[0].stem : '');
    try {
        var saved = parseInt(localStorage.getItem(key), 10);
        if (saved >= 0 && saved < caps.length) start = saved;
    } catch (e) {}
    window._apPageKey = key;
    window._apCaptures = caps;
    window._apCur = start;
    window._apCap = function () { return caps[window._apCur] || {}; };
})();
</script>
<div id="spellText" style="font-size: min(48px, 8vh)">{{spell}}</div>
<div style="font-size: 20px">
<span id="pron">{{pron}}</span>
<script>
   // A lone space inside spell/pron is stray (OCR, hand edits). A run of
   // two or more is deliberate, so leave those alone. Walk text nodes
   // only: these fields can carry html, and touching innerHTML would eat
   // spaces inside tags. fromCharCode(160) instead of an escape, since
   // backslashes do not survive the trip through Python and AnkiConnect.
   (function () {
       var SP = new RegExp('[ ' + String.fromCharCode(160) + ']+', 'g');
       function strip(node) {
           for (var n = node.firstChild; n; n = n.nextSibling) {
               if (n.nodeType === 3) {
                   n.nodeValue = n.nodeValue.replace(SP, function (m) {
                       return m.length === 1 ? '' : m;
                   });
               } else if (n.nodeType === 1) {
                   strip(n);
               }
           }
       }
       ['spellText', 'pron'].forEach(function (id) {
           var el = document.getElementById(id);
           if (el) strip(el);
       });
   })();
</script>
<div id="main-wrap">
   <div id="left-col">
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
         function canvasIsBlank(canvas) {
             // a purged backing store reads back all-zero (even alpha)
             try {
                 var c = canvas.getContext('2d');
                 var pts = [[0.5, 0.5], [0.25, 0.25], [0.75, 0.75], [0.25, 0.75]];
                 var sum = 0;
                 for (var i = 0; i < pts.length; i++) {
                     var d = c.getImageData(
                         Math.floor(canvas.width * pts[i][0]),
                         Math.floor(canvas.height * pts[i][1]), 1, 1).data;
                     sum += d[0] + d[1] + d[2] + d[3];
                 }
                 return sum === 0;
             } catch (e) {
                 return false;
             }
         }
         var _rebuildBusy = false;
         function rebuildWordImage() {
             // shared rebuild ladder: cached blob -> refetch media file.
             // The blob itself can die after long backgrounding (proven in
             // logs), so the network rung is mandatory.
             if (_rebuildBusy) return;
             var fname2 = window._apCap().mp3 || "";
             var cache = window.top._apCache && window.top._apCache[fname2];
             if (!cache || typeof createImageBitmap !== 'function') return;
             _rebuildBusy = true;
             function done(bm) {
                 cache.bitmap = bm;
                 _rebuildBusy = false;
                 try { renderScreenshot(); } catch (e) {}
                 if (window.top._imgDbg) {
                     window.top._imgDbg.healed = (window.top._imgDbg.healed || 0) + 1;
                 }
             }
             function refetch() {
                 var _src3 = window._apCap().img;
                 if (!_src3) { _rebuildBusy = false; return; }
                 fetch(_src3).then(function (r) { return r.blob(); })
                     .then(function (blob) {
                         cache.blob = blob;
                         return createImageBitmap(blob);
                     })
                     .then(done)
                     .catch(function () { _rebuildBusy = false; });
             }
             if (cache.blob) {
                 createImageBitmap(cache.blob).then(done, refetch);
             } else {
                 refetch();
             }
         }
         function verifyCanvasPainted(canvas, cache) {
             // iOS may have killed the cached ImageBitmap while backgrounded:
             // drawing paints nothing. Detect and rebuild.
             if (!canvas.width || !canvas.height) return;
             if (!canvasIsBlank(canvas)) return;
             rebuildWordImage();
         }
         function renderScreenshot() {
             var canvas = document.getElementById('word-img-canvas');
             var fallback = document.getElementById('word-img-fallback');
             if (!canvas) return;
             var fname = window._apCap().mp3 || "";
             var cache = window.top._apCache && window.top._apCache[fname];
             var bitmap = cache && cache.bitmap;
             if (bitmap) {
             canvas.style.display = 'block';
             fallback.style.display = 'none';
             ensureFrame(bitmap.width, bitmap.height);
             canvas.width = bitmap.width;
             canvas.height = bitmap.height;
             var ctx = canvas.getContext('2d');
             try {
                 ctx.drawImage(bitmap, 0, 0);
             } catch (e) {
                 // detached bitmap throws InvalidStateError: rebuild right away
                 setTimeout(rebuildWordImage, 0);
                 return true;
             }
             // run the purge check after the frame is presented: getImageData
             // forces a sync GPU readback and would delay the visible paint
             requestAnimationFrame(function () {
                 verifyCanvasPainted(canvas, cache);
             });
             return true;
             }
             canvas.style.display = 'none';
             fallback.style.display = 'block';
             var _curImg = window._apCap().img;
             var _fbAll = fallback.querySelectorAll('img');
             var fbImg = null;
             for (var _fi = 0; _fi < _fbAll.length; _fi++) {
                 var _im = _fbAll[_fi];
                 _im.style.width = '100%';
                 _im.style.height = '100%';
                 // beat the model CSS max-height:60vh cap - the frame box
                 // is the single size authority now
                 _im.style.maxWidth = 'none';
                 _im.style.maxHeight = 'none';
                 _im.style.objectFit = 'scale-down';
                 var _vis = !!_curImg && _im.getAttribute('src') === _curImg;
                 _im.style.display = _vis ? 'block' : 'none';
                 if (_vis) fbImg = _im;
             }
             function syncFallbackWidth() {
                 if (!fbImg || !fbImg.naturalWidth) return;
                 ensureFrame(fbImg.naturalWidth, fbImg.naturalHeight);
             }
             if (fbImg) {
             fbImg.complete ? syncFallbackWidth() : fbImg.addEventListener('load', syncFallbackWidth);
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
             var canvas = document.getElementById('word-img-canvas');
             var fallbackImg = null;
             var _fbs = wrap.querySelectorAll('#word-img-fallback img');
             for (var _bi = 0; _bi < _fbs.length; _bi++) {
                 if (_fbs[_bi].style.display !== 'none') { fallbackImg = _fbs[_bi]; break; }
             }
             var displayEl = (canvas && canvas.style.display !== 'none') ? canvas : fallbackImg;
             if (!displayEl) return;
             var natW, natH;
             if (displayEl === canvas) {
             natW = canvas.width;
             natH = canvas.height;
             } else {
             natW = fallbackImg.naturalWidth;
             natH = fallbackImg.naturalHeight;
             if (!natW) return;
             }
             var dispW = displayEl.offsetWidth;
             var dispH = displayEl.offsetHeight;
             // object-fit insets the drawn image inside the element box:
             // quad points need the content-rect scale plus offset
             var _s = Math.min(dispW / natW, dispH / natH, 1);
             var _ox = (dispW - natW * _s) / 2;
             var _oy = (dispH - natH * _s) / 2;
             var sv = document.getElementById('sv');
             sv.style.width = dispW + 'px';
             sv.style.height = dispH + 'px';
             sv.style.left = displayEl.offsetLeft + 'px';
             sv.style.top = displayEl.offsetTop + 'px';
             document.getElementById('pl').setAttribute('points',
             (window._apCap().quad || []).map(function(p) { return (_ox + p[0]*_s) + ',' + (_oy + p[1]*_s); }).join(' '));
         }
         (function initFrameBox() {
             var cv = document.getElementById('word-img-canvas');
             if (!cv || !cv.parentNode) return;
             var box = cv.parentNode;
             box.style.position = 'relative';
             box.style.overflow = 'hidden';
             box.style.marginLeft = 'auto';
             box.style.marginRight = 'auto';
             cv.style.position = 'absolute';
             cv.style.left = '0';
             cv.style.top = '0';
             cv.style.width = '100%';
             cv.style.height = '100%';
             cv.style.objectFit = 'scale-down';
             var fb = document.getElementById('word-img-fallback');
             if (fb) {
                 fb.style.position = 'absolute';
                 fb.style.left = '0';
                 fb.style.top = '0';
                 fb.style.width = '100%';
                 fb.style.height = '100%';
             }
             window._apFrameBox = box;
         })();
         function ensureFrame(natW, natH) {
             if (!window._apFrame) {
                 // only the HEIGHT is frozen (from the anchor page dims);
                 // widths stay 100% so late scrollbars / reflows can never
                 // knock the box, waveform and text out of alignment
                 var _pn = window._apFrameBox && window._apFrameBox.parentNode;
                 var w = (_pn && _pn.clientWidth > 0)
                     ? _pn.clientWidth : window.innerWidth * 0.95;
                 var h = w * natH / natW;
                 var mH = window.innerHeight < window.innerWidth
            ? screen.width * window._apCfg.landscapeHeightRatio
            : screen.height * window._apCfg.portraitHeightRatio;
                 // uncapped: width follows the column (100%) so late
                 // scrollbars can't cause overflow; height-capped: hug the
                 // image with a numeric width (always < column, so both
                 // centering mechanisms agree)
                 var fw = null;
                 if (h > mH) { h = mH; fw = h * natW / natH; }
                 window._apFrame = { h: h, w: fw, natW: natW, natH: natH };
             }
             var fr = window._apFrame;
             var _w = fr.w ? fr.w + 'px' : '100%';
             if (window._apFrameBox) {
                 window._apFrameBox.style.width = _w;
                 window._apFrameBox.style.height = fr.h + 'px';
             }
             var textWrap = document.getElementById('text-wrap');
             if (textWrap) textWrap.style.width = _w;
             var apWrap = document.querySelector('.ap-wrap');
             if (apWrap) apWrap.style.width = _w;
             if ((!textWrap || !apWrap) && (fr._rt = (fr._rt || 0) + 1) < 10) {
                 // parse-order guard: siblings below this script may not
                 // exist yet on some hosts - size them once they do
                 setTimeout(function () { ensureFrame(natW, natH); }, 0);
             }
         }
         renderScreenshot();
         drawBox();
         window._apRenderImage = function () { renderScreenshot(); drawBox(); };
         var _fbImgs = document.querySelectorAll('#word-img-fallback img');
         for (var _li = 0; _li < _fbImgs.length; _li++) {
             if (!_fbImgs[_li].complete) _fbImgs[_li].addEventListener('load', drawBox);
         }
         function updateLayout() {
             var isMobile = /iPhone|iPad|Android|HarmonyOS/i.test(navigator.userAgent);
             var isLandscape = window.innerWidth > window.innerHeight;
             document.body.classList.toggle('landscape', isMobile && isLandscape);
         }
         updateLayout();
         function reflowFrame() {
             updateLayout();
             if (window._apFrame) {
                 // recompute from the ANCHOR page dims, not the current page
                 var n = window._apFrame;
                 window._apFrame = null;
                 ensureFrame(n.natW, n.natH);
             }
             renderScreenshot();
             drawBox();
         }
         var _resizeTimer = null;
         window.addEventListener('resize', function() {
             if (_resizeTimer) clearTimeout(_resizeTimer);
             _resizeTimer = setTimeout(reflowFrame,
                 window._apCfg.resizeDebounceMs);
         });
         window.addEventListener('orientationchange', function() {
             setTimeout(reflowFrame, window._apCfg.resizeSettleMs);
         });
      </script>
      <div class="ap-wrap">
         <div class="ap-track" id="ap-track" style="touch-action:none;-webkit-user-select:none;user-select:none;-webkit-touch-callout:none;">
            <canvas id="ap-wave"></canvas>
            <div class="ap-range" id="ap-range" style="visibility:hidden"></div>
            <div class="ap-progress" id="ap-progress" style="visibility:hidden"></div>
            <div class="ap-handle ap-handle-start" id="ap-h-start" data-role="start" style="visibility:hidden;touch-action:none;-webkit-user-select:none;user-select:none;-webkit-touch-callout:none;">
               <div class="ap-handle-visual"></div>
            </div>
            <div class="ap-handle ap-handle-end" id="ap-h-end" data-role="end" style="visibility:hidden;touch-action:none;-webkit-user-select:none;user-select:none;-webkit-touch-callout:none;">
               <div class="ap-handle-visual"></div>
            </div>
            <div id="ap-zoom" style="display:none;position:absolute;pointer-events:none;z-index:10;background:#fff;border:1px solid #ccc;border-radius:6px;box-shadow:0 2px 8px rgba(0,0,0,.18);">
               <canvas id="ap-zoom-canvas" style="display:block"></canvas>
            </div>
         </div>
      </div>
   </div>
   <script>
      (function () {
          var _anyAudio = (window._apCaptures || []).some(function (c) { return c.mp3; });
          if (!_anyAudio) {
              document.querySelector(".ap-wrap").innerHTML = '';
              return;
          }
          let filename = window._apCap().mp3 || "";
          var _apSkipPlay = false;
          const track = document.getElementById("ap-track");
          const canvas = document.getElementById("ap-wave");
          const rangeEl = document.getElementById("ap-range");
          const progEl = document.getElementById("ap-progress");
          const hStart = document.getElementById("ap-h-start");
          const hEnd = document.getElementById("ap-h-end");
          const HIT_OUTER = parseFloat(getComputedStyle(track).getPropertyValue("--hit-outer")) || 0;
          let _apWidgetsShown = false;   // hidden until updateUI() places them
          const zoomEl = document.getElementById("ap-zoom");
          const zoomCanvas = document.getElementById("ap-zoom-canvas");
          function STORAGE_KEY() { return "ap-range:" + filename; }
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
                  const raw = localStorage.getItem(STORAGE_KEY());
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
                  STORAGE_KEY(),
                  JSON.stringify({
                      start: startT,
                      end: endT,
                      updated: Date.now(),
                  }),
                  );
              } catch (e) {}
          }
          let duration = 0;
          let startT = 0;
          let endT = 0;
          let audioBuffer = null;
          let audioCtx = null;
          const _apMyGen = window.top._apGen;
          let currentSource = null;
          let currentGain = null;
          let curVol = 1, curFadeOutS = 0, fadeArmed = false;
          let rebuilds = 0;   // zombie-clock rebuild quota per visit/tap
          let webStart = 0;
          let webOffset = 0;
          let rafId = null;
          let bars = null;
          let dragging = null;
          let dragRect = null;
          let lastClientX = 0;
          let downClientY = 0;
          let dragStartTime = 0;
          let globalPeak = null;
          function updateUI() {
              if (!duration) return;
              const sp = (startT / duration) * 100;
              const ep = (endT / duration) * 100;
              rangeEl.style.left = sp + "%";
              rangeEl.style.width = ep - sp + "%";
              hStart.style.left = sp + "%";
              hEnd.style.left = ep + "%";
              const trackW = track.clientWidth;
              const startAnchor = (sp / 100) * trackW;
              const endAnchor = (ep / 100) * trackW;
              hStart.style.setProperty("--hit-outer", Math.max(0, Math.min(HIT_OUTER, startAnchor)) + "px");
              hEnd.style.setProperty("--hit-outer", Math.max(0, Math.min(HIT_OUTER, trackW - endAnchor)) + "px");
              const gapPx = ((ep - sp) / 100) * trackW;
              const visualW = Math.max(0, Math.min(20, gapPx - 2));
              const startVis = hStart.querySelector(".ap-handle-visual");
              const endVis = hEnd.querySelector(".ap-handle-visual");
              if (startVis) startVis.style.width = visualW + "px";
              if (endVis) endVis.style.width = visualW + "px";
              if (!_apWidgetsShown) {
                  // first real layout: until now they all sat at left:0,
                  // bunched together on the far left while audio decoded
                  _apWidgetsShown = true;
                  hStart.style.visibility = '';
                  hEnd.style.visibility = '';
                  rangeEl.style.visibility = '';
                  progEl.style.visibility = '';
              }
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
                  let mn = 1, mx = -1;
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
          function drawWaveformFromBars(barsData) {
              const dpr = window.devicePixelRatio || 1;
              const w = track.clientWidth;
              const h = track.clientHeight;
              canvas.width = w * dpr;
              canvas.height = h * dpr;
              const ctx = canvas.getContext("2d");
              ctx.scale(dpr, dpr);
              const totalBars = barsData.length / 2;
              const mid = h / 2;
              const ratio = totalBars / w;
              const scale = 0.9;
              ctx.fillStyle = "#9bb8e6";
              for (let x = 0; x < w; x++) {
                  const idx = Math.floor(x * ratio) * 2;
                  const mn = barsData[idx];
                  const mx = barsData[idx + 1];
                  const y1 = mid + mn * mid * scale;
                  const y2 = mid + mx * mid * scale;
                  ctx.fillRect(x, y1, 1, Math.max(1, y2 - y1));
              }
          }
          function stopCurrent() {
              if (currentSource) {
                  var _src = currentSource, _g = currentGain;
                  if (window.top._audio && window.top._audio.node === _src) {
                  window.top._audio = null;
                  }
                  currentSource = null;
                  currentGain = null;
                  try { _src.onended = null; } catch (e) {}
                  // fade the outgoing source instead of chopping it: page
                  // switches crossfade; the delayed stop only stops a node,
                  // safe even if the card changes meanwhile
                  if (_g && audioCtx) {
                      try {
                          var _fn = audioCtx.currentTime;
                          _g.gain.cancelScheduledValues(_fn);
                          _g.gain.setValueAtTime(_g.gain.value, _fn);
                          _g.gain.linearRampToValueAtTime(
                              0, _fn + window._apCfg.switchFadeS);
                      } catch (e) {}
                      setTimeout(function () {
                          try { _src.stop(); } catch (e) {}
                          try { _src.disconnect(); } catch (e) {}
                      }, window._apCfg.switchStopMs);
                  } else {
                      try { _src.stop(); } catch (e) {}
                      try { _src.disconnect(); } catch (e) {}
                  }
              }
              if (rafId != null) {
                  cancelAnimationFrame(rafId);
                  rafId = null;
              }
          }
          let volCache = { s: -1, e: -1, vol: 1 };
          function computeVol() {
              // Peak normalization over the SELECTED range: one constant
              // gain per segment (no compression), pushed to just under
              // full scale (no clipping). Checks every channel.
              volCache = { s: startT, e: endT, vol: 1 };
              if (!audioBuffer) return;
              const sr = audioBuffer.sampleRate;
              const s0 = Math.max(0, Math.floor(startT * sr));
              let peak = 0;
              for (let ch = 0; ch < audioBuffer.numberOfChannels; ch++) {
                  const data = audioBuffer.getChannelData(ch);
                  const s1 = Math.min(Math.floor(endT * sr), data.length);
                  for (let i = s0; i < s1; i++) {
                      const a = Math.abs(data[i]);
                      if (a > peak) peak = a;
                  }
              }
              if (peak < 0.001) return;          // silence: leave it alone
              // per-device target peak: phones (weak speakers) get a hotter
              // level than PCs; UA-based detection, iPad included
              var isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent)
                  || (/Macintosh/.test(navigator.userAgent) && navigator.maxTouchPoints > 1);
              var targetPeak = isMobile
                  ? window._apCfg.targetPeakMobile
                  : window._apCfg.targetPeakDesktop;
              var maxGain = isMobile
                  ? window._apCfg.maxGainMobile
                  : window._apCfg.maxGainDesktop;
              volCache.vol = Math.min(targetPeak / peak, maxGain);
          }
          function rebuildAndReplay(tag) {
              if (_apMyGen !== window.top._apGen) return;
              if (rebuilds >= window._apCfg.rebuildQuota) {
                  if (window._apDbgLog) window._apDbgLog("au:giveup " + tag);
                  return;
              }
              rebuilds++;
              if (window._apDbgLog) window._apDbgLog("au:rebuild" + rebuilds + " " + tag);
              try { audioCtx.close(); } catch (e) {}
              const AC = window.AudioContext || window.webkitAudioContext;
              audioCtx = new AC();
              window.top._apAudioCtx = audioCtx;
              playRangeInternal();
          }
          function warmupClock(attempt) {
              // on return from background: verify the clock actually
              // advances; silently rebuild frozen contexts so the next
              // tap lands on a live one. Never touches a moving clock.
              attempt = attempt || 0;
              if (!audioCtx) return;
              if (audioCtx.state === "suspended" || audioCtx.state === "interrupted") {
                  try { audioCtx.resume(); } catch (e) {}
              }
              const c0 = audioCtx;
              const t0 = c0.currentTime;
              setTimeout(function () {
                  if (_apMyGen !== window.top._apGen) return;
                  if (audioCtx !== c0) return;
                  const adv = c0.currentTime - t0;
                  if (window._apDbgLog) window._apDbgLog(
                      "au:warm" + attempt + " +" + adv.toFixed(3) + " " + c0.state);
                  if (adv > 0 || attempt >= window._apCfg.warmupTries)
                      return;
                  try { c0.close(); } catch (e) {}
                  const AC = window.AudioContext || window.webkitAudioContext;
                  audioCtx = new AC();
                  window.top._apAudioCtx = audioCtx;
                  warmupClock(attempt + 1);
              }, window._apCfg.warmupMs);
          }
          function playRangeInternal() {
              stopCurrent();
              if (!audioBuffer || !audioCtx || !duration) return;
              // a range this short is a stray drag, not a clip worth
              // hearing. Stay silent, but still let a running sequence
              // move on, or it would stall on this page forever.
              if (endT - startT <= window._apCfg.minPlayS) {
                  updateProgressFromTime(startT);
                  const _silentGen = _apMyGen;
                  setTimeout(function () {
                      if (_silentGen !== window.top._apGen) return;
                      if (window._apSeqNext) window._apSeqNext();
                  }, window._apCfg.silentHoldMs);
                  return;
              }
              if (audioCtx.state === "suspended" || audioCtx.state === "interrupted") audioCtx.resume();
              if (volCache.s !== startT || volCache.e !== endT) computeVol();
              const vol = volCache.vol;
              const source = audioCtx.createBufferSource();
              const gain = audioCtx.createGain();
              source.buffer = audioBuffer;
              source.connect(gain);
              gain.connect(audioCtx.destination);
              const offset = startT;
              const playDur = Math.max(0, endT - startT);
              source.start(0, offset);
              currentSource = source;
              currentGain = gain;
              webStart = audioCtx.currentTime;
              webOffset = offset;
              // zombie-clock watchdog WITH repair: frozen currentTime on
              // a 'running' context = dead output unit. Rebuild the
              // context and replay; fresh contexts can inherit the stuck
              // session, so retries (with quota) matter.
              const zt = audioCtx.currentTime;
              const zsrc = source;
              const zctx = audioCtx;
              window._apCfg.watchdogMs.forEach(function (ms) {
                  setTimeout(function () {
                      if (_apMyGen !== window.top._apGen) return;
                      if (currentSource !== zsrc || audioCtx !== zctx) return;
                      const adv = zctx.currentTime - zt;
                      if (window._apDbgLog) window._apDbgLog(
                          "au:tick" + ms + " +" + adv.toFixed(3) + " " + zctx.state);
                      if (adv === 0) rebuildAndReplay("t" + ms);
                  }, ms);
              });
              const MAX_FADE_S = window._apCfg.audioFadeMaxS;
              const MAX_VOL = window._apCfg.audioFadeRefVol;
              const sr = audioBuffer.sampleRate;
              const data = audioBuffer.getChannelData(0);
              const fadeSamples = Math.floor(sr * MAX_FADE_S);
              const startSample = Math.floor(startT * sr);
              const endSample = Math.floor(endT * sr);
              let startSum = 0;
              for (let i = startSample; i < Math.min(startSample + fadeSamples, data.length); i++)
                  startSum += Math.abs(data[i]);
              const startVol = startSum / fadeSamples;
              const fadeInS = Math.min(startVol / MAX_VOL, 1) * MAX_FADE_S;
              let endSum = 0;
              for (let i = Math.max(0, endSample - fadeSamples); i < Math.min(endSample, data.length); i++)
                  endSum += Math.abs(data[i]);
              const endVol = endSum / fadeSamples;
              const fadeOutS = Math.min(
                  Math.min(endVol / MAX_VOL, 1) * MAX_FADE_S,
                  playDur * 0.5
              );

              const now = audioCtx.currentTime;
              if (fadeInS > 0) {
                  gain.gain.setValueAtTime(0, now);
                  gain.gain.linearRampToValueAtTime(vol, now + fadeInS);
              } else {
                  gain.gain.setValueAtTime(vol, now);
              }
              // fade-out is NOT scheduled up front any more: endT can
              // move while playing, so watchProgress decides per frame
              curVol = vol;
              curFadeOutS = fadeOutS;
              fadeArmed = false;

              // the card can be answered while this is still playing, so
              // the next card's fadeStop needs the range bounds to avoid
              // fading past them
              window.top._audio = {
                  node: source,
                  gain: gain,
                  ctx: audioCtx,
                  endT: endT,
                  webStart: webStart,
                  webOffset: webOffset,
              };
              rafId = requestAnimationFrame(watchProgress);
          }
          function watchProgress() {
              if (_apMyGen !== window.top._apGen) { rafId = null; return; }
              if (!currentSource) {
                  rafId = null;
                  return;
              }
              if (window.top._audio
                      && window.top._audio.node === currentSource) {
                  window.top._audio.endT = endT;   // handle may be dragged
              }
              const elapsed = audioCtx.currentTime - webStart;
              const t = webOffset + elapsed;
              if (t >= endT) {
                  stopCurrent();
                  updateProgressFromTime(endT);
                  if (window._apSeqNext) window._apSeqNext();
                  return;
              }
              if (currentGain && curFadeOutS > 0) {
                  const left = endT - t;
                  const g = currentGain.gain;
                  const n2 = audioCtx.currentTime;
                  if (!fadeArmed && left <= curFadeOutS) {
                      fadeArmed = true;
                      g.cancelScheduledValues(n2);
                      g.setValueAtTime(g.value, n2);
                      g.linearRampToValueAtTime(0, n2 + Math.max(0.01, left));
                  } else if (fadeArmed && left > curFadeOutS) {
                      fadeArmed = false;   // dragged further right: undo
                      g.cancelScheduledValues(n2);
                      g.setValueAtTime(g.value, n2);
                      g.linearRampToValueAtTime(curVol, n2 + 0.05);
                  }
              }
              updateProgressFromTime(t);
              rafId = requestAnimationFrame(watchProgress);
          }
          function loadAudio() {
              if (!filename) {
                  // audio-less page: keep the strip, clear the wave, hide
                  // the drag handles until a page with audio comes back
                  stopCurrent();
                  audioBuffer = null;
                  try {
                      const _cx = canvas.getContext("2d");
                      _cx.clearRect(0, 0, canvas.width, canvas.height);
                  } catch (e) {}
                  hStart.style.display = 'none';
                  hEnd.style.display = 'none';
                  rangeEl.style.display = 'none';
                  progEl.style.display = 'none';
                  return;
              }
              const AudioCtx = window.AudioContext || window.webkitAudioContext;
              if (!AudioCtx) {
                  document.querySelector(".ap-wrap").innerHTML =
                  '<div style="color:#c00">Web Audio not supported.</div>';
                  return;
              }
              if (!audioCtx) audioCtx = new AudioCtx();
              window.top._apAudioCtx = audioCtx;
              function onDecoded(decoded, prerenderedBars, prerenderedPlayTime) {
                  if (_apMyGen !== window.top._apGen) return;
                  hStart.style.display = '';
                  hEnd.style.display = '';
                  rangeEl.style.display = '';
                  progEl.style.display = '';
                  audioBuffer = decoded;
                  duration = decoded.duration;
                  bars = prerenderedBars || null;
                  let initStart = null, initEnd = null;
                  const saved = loadRange();
                  if (saved && saved.start < saved.end && saved.end <= duration + 0.01) {
                  initStart = Math.max(0, saved.start);
                  initEnd = Math.min(duration, saved.end);
                  }
                  if (initStart === null) {
                  let pt = prerenderedPlayTime;
                  if (!pt) {
                      var _cr = window._apCap().range;
                      if (_cr) pt = [_cr[0], _cr[1]];
                  }
                  if (pt && pt[1] <= duration + 0.01) {
                      initStart = Math.max(0, pt[0]);
                      initEnd = Math.min(duration, pt[1]);
                  }
                  }
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
                  if (_apSkipPlay) { _apSkipPlay = false; } else { playRangeInternal(); }
              }
              const cached = window.top._apCache && window.top._apCache[filename];
              if (cached) {
                  if (cached.buffer) {
                  onDecoded(cached.buffer, cached.bars, cached.playTime);
                  } else {
                  onDecoded(cached);
                  }
                  return;
              }
              fetch(filename)
                  .then((r) => r.arrayBuffer())
                  .then((buf) => audioCtx.decodeAudioData(buf))
                  .then(onDecoded)
                  .catch((err) => {
                  document.querySelector(".ap-wrap").innerHTML =
                      '<div style="color:#c00">Failed to load audio'+
                      '<br>Check if sync is finished</div>';
                  console.log("Audio load failed:", err);
                  });
          }
          loadAudio();
          window._apReloadAudio = function (noplay) {
              if (_apMyGen !== window.top._apGen) return;
              filename = window._apCap().mp3 || "";
              _apSkipPlay = !!noplay;
              loadAudio();
          };
          const ZOOM_W = 140, ZOOM_H = 44, ZOOM_SEC = 0.5;
          const SHOW_ZOOM = false; // zoom magnifier tog4
          function updateZoom() {
              if (!SHOW_ZOOM || !duration || !dragging) return;
              const t = dragging === 'start' ? startT : endT;
              const trackW = track.clientWidth;
              let left = (t / duration) * trackW - ZOOM_W / 2;
              left = Math.max(0, Math.min(trackW - ZOOM_W, left));
              zoomEl.style.left = left + 'px';
              zoomEl.style.top = (-ZOOM_H - 10) + 'px';
              const dpr = window.devicePixelRatio || 1;
              zoomCanvas.width = ZOOM_W * dpr;
              zoomCanvas.height = ZOOM_H * dpr;
              zoomCanvas.style.width = ZOOM_W + 'px';
              zoomCanvas.style.height = ZOOM_H + 'px';
              const ctx = zoomCanvas.getContext('2d');
              ctx.scale(dpr, dpr);
              ctx.clearRect(0, 0, ZOOM_W, ZOOM_H);
              const mid = ZOOM_H / 2, sc = 0.85;
              const tStart = t - ZOOM_SEC;
              const tEnd = t + ZOOM_SEC;
              const span = tEnd - tStart;
              ctx.fillStyle = '#9bb8e6';
              if (bars) {
                  const total = bars.length / 2;
                  for (let x = 0; x < ZOOM_W; x++) {
                      const tx = tStart + (x / ZOOM_W) * span;
                      if (tx < 0 || tx > duration) continue;
                      let bi = Math.floor((tx / duration) * total);
                      if (bi >= total) bi = total - 1;
                      const idx = bi * 2;
                      const y1 = mid + bars[idx] * mid * sc;
                      const y2 = mid + bars[idx + 1] * mid * sc;
                      ctx.fillRect(x, y1, 1, Math.max(1, y2 - y1));
                  }
              } else if (audioBuffer) {
                  const data = audioBuffer.getChannelData(0);
                  const sr = audioBuffer.sampleRate;
                  if (globalPeak === null) {
                      let gp = 0;
                      for (let i = 0; i < data.length; i++) { const v = Math.abs(data[i]); if (v > gp) gp = v; }
                      globalPeak = gp || 1;
                  }
                  const peak = globalPeak;
                  const pxDur = span / ZOOM_W;
                  for (let x = 0; x < ZOOM_W; x++) {
                      const tx = tStart + (x / ZOOM_W) * span;
                      if (tx < 0 || tx > duration) continue;
                      const a = Math.floor(tx * sr);
                      const b = Math.min(Math.floor((tx + pxDur) * sr), data.length);
                      let mn = 1, mx = -1;
                      for (let i = a; i < b; i++) { const v = data[i] / peak; if (v < mn) mn = v; if (v > mx) mx = v; }
                      if (mn > mx) continue;
                      const y1 = mid + mn * mid * sc;
                      const y2 = mid + mx * mid * sc;
                      ctx.fillRect(x, y1, 1, Math.max(1, y2 - y1));
                  }
              }
              if (dragStartTime >= tStart && dragStartTime <= tEnd) {
                  const x0 = ((dragStartTime - tStart) / span) * ZOOM_W;
                  ctx.fillStyle = 'rgba(0,0,0,0.18)';
                  ctx.fillRect(x0 - 0.5, 0, 1, ZOOM_H);
              }
              ctx.fillStyle = 'rgba(26,115,232,0.8)';
              ctx.fillRect(ZOOM_W / 2 - 0.5, 0, 1, ZOOM_H);
          }
          function getXY(e) {
              if (e.touches && e.touches.length) return { x: e.touches[0].clientX, y: e.touches[0].clientY };
              return { x: e.clientX, y: e.clientY };
          }
          function onDown(e) {
              if (window._apSeqStop) window._apSeqStop();
              dragging = e.currentTarget.dataset.role;
              dragRect = track.getBoundingClientRect();
              const p = getXY(e);
              lastClientX = p.x;
              downClientY = p.y;
              dragStartTime = dragging === 'start' ? startT : endT;
              if (e.currentTarget.setPointerCapture && e.pointerId != null) {
                  try {
                  e.currentTarget.setPointerCapture(e.pointerId);
                  } catch (err) {}
              }
              e.preventDefault();
              e.stopPropagation();
              if (SHOW_ZOOM) zoomEl.style.display = 'block';
              updateZoom();
          }
          function onMove(e) {
              if (!dragging || !duration) return;
              const p = getXY(e);
              const dx = p.x - lastClientX;
              lastClientX = p.x;
              const vDist = Math.abs(p.y - downClientY);
              const speed = Math.max(0.125, 1 - vDist / 200);
              const timeDelta = (dx / dragRect.width) * duration * speed;
              if (dragging === "start") {
                  startT = Math.max(0, Math.min(startT + timeDelta, endT - 0.05));
              } else {
                  endT = Math.min(duration, Math.max(endT + timeDelta, startT + 0.05));
              }
              updateUI();
              updateZoom();
              e.preventDefault();
          }
          function onUp() {
              if (dragging) {
                  saveRange();
                  computeVol();   // precompute loudness for the new range
              }
              dragging = null;
              dragRect = null;
              zoomEl.style.display = 'none';
              updateUI();
          }
          addTracked(hStart, "pointerdown", onDown);
          addTracked(hEnd, "pointerdown", onDown);
          addTracked(document, "pointermove", onMove);
          addTracked(document, "pointerup", onUp);
          addTracked(document, "pointercancel", onUp);
          if (window.PointerEvent) {
              var blockTouch = function (e) { e.preventDefault(); };
              addTracked(hStart, "touchstart", blockTouch, { passive: false });
              addTracked(hEnd, "touchstart", blockTouch, { passive: false });
              addTracked(document, "touchmove", function (e) {
                  if (dragging) e.preventDefault();
              }, { passive: false });
          } else {
              addTracked(hStart, "touchstart", onDown, { passive: false });
              addTracked(hEnd, "touchstart", onDown, { passive: false });
              addTracked(document, "touchmove", onMove, { passive: false });
              addTracked(document, "touchend", onUp);
          }
          window.playRange = function () {
              rebuilds = 0;   // each real tap earns a fresh repair quota
              if (window._apSeqArm) window._apSeqArm();
              if (typeof fadeStop === "function" && window.top._audio) {
                  fadeStop(window.top._audio, 200);
                  window.top._audio = null;
              }
              playRangeInternal();
          };
          function redrawAll() {
              if (_apMyGen !== window.top._apGen) return;
              if (document.visibilityState !== "visible") return;
              const cache = window.top._apCache && window.top._apCache[filename];
              // audio: iOS may leave the context stuck after lock/interruption
              try {
                  if (audioCtx && (audioCtx.state === "suspended" || audioCtx.state === "interrupted")) {
                      audioCtx.resume();
                  }
              } catch (e) {}
              // waveform: bars are plain JS data, redrawing is free
              try {
                  if (cache && cache.bars) {
                      drawWaveformFromBars(cache.bars);
                  } else if (audioBuffer) {
                      drawWaveform(audioBuffer);
                  }
              } catch (e) {}
              // image: delegate to the shared rebuild ladder (blob -> refetch)
              if (typeof rebuildWordImage === "function") {
                  rebuildWordImage();
              } else {
                  try { renderScreenshot(); } catch (e) {}
              }
          }
          function onVisible() {
              if (document.visibilityState === "visible") {
                  rebuilds = 0;
                  warmupClock();
                  setTimeout(redrawAll, 100);
                  setTimeout(redrawAll, 700);
              }
          }
          addTracked(document, "visibilitychange", onVisible);
      })();
   </script>
   <div id="text-wrap">
      {{#excerpt}}
      <div id="excerpt-text" style="font-size: 18px; text-align: left">{{excerpt}}</div>
      <script>
      var e = document.getElementById('excerpt-text');
      e.innerHTML = e.innerHTML.replace(/(<div><br><[/]div>|<br>)$/i, '');
      </script>
      {{/excerpt}} {{#excerpt}}{{#fuzzy}}<br />{{/fuzzy}}{{/excerpt}} {{#fuzzy}}
      <div style="font-size: 18px; text-align: left">{{fuzzy}}</div>
      {{/fuzzy}}
   </div>
   </div>
</div>
<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 70px; width: fit-content; margin: 14px auto">
   <span id="etymSpell" style="display: none">{{spell}}</span>
   <a
      id="dictBtn"
      href="#"
      onclick="return window._apSearch(this)"
      style="
      display: inline-block;
      text-align: center;
      padding: 12px 22px;
      background: #4f46e5;
      color: #fff;
      border-radius: 10px;
      text-decoration: none;
      font-size: 18px;
      font-family: system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
      "
      >
   Meaning
   </a>
   <a
      id="etymBtn"
      href="#"
      onclick="return window._apSearch(this)"
      style="
      display: inline-block;
      text-align: center;
      padding: 12px 22px;
      background: #4f46e5;
      color: #fff;
      border-radius: 10px;
      text-decoration: none;
      font-size: 18px;
      font-family: system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
      "
      >
   Origin
   </a>
</div>
<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; width: fit-content; margin: 0 auto">
   <button onclick="exportRanges()">Copy Audio Time</button>
   <button onclick="importRanges()">Import Audio Time</button>
</div>
<div id="apTimeField" style="display:none">{{time}}</div>
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
       // viewport units + inset pinning: percentage heights can resolve
       // against a transformed/short ancestor in Anki's webview and only
       // cover part of the screen
       div.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;width:100vw;height:100vh;background:rgba(0,0,0,0.85);z-index:9999;display:flex;flex-direction:column;align-items:center;justify-content:flex-start;box-sizing:border-box;padding:calc(env(safe-area-inset-top) + 10vh) 16px env(safe-area-inset-bottom) 16px;';
       // modal: swallow pointer events so taps cannot bubble up to Anki's
       // tap-to-answer / tap-to-flip handlers behind the overlay
       ['click', 'dblclick', 'mousedown', 'mouseup',
        'pointerdown', 'pointerup',
        'touchstart', 'touchmove', 'touchend'].forEach(function (ev) {
           div.addEventListener(ev, function (e) {
               e.stopPropagation();
               if (e.target === div && ev !== 'click') e.preventDefault();
           });
       });
   var ta = document.createElement('div');
   ta.textContent = json;
   // NOT contentEditable: keeps iOS from popping the keyboard and from
   // auto-zooming (focus on <16px editable zooms the page). Selection
   // and the copy callout work fine on plain text.
   ta.style.cssText = 'width:80%;height:3em;font-size:16px;background:white;color:black;padding:8px;overflow:auto;word-break:break-all;-webkit-user-select:text;user-select:text;';
   var label = document.createElement('div');
   label.innerHTML = '<div style="text-align:center;margin-bottom:6px">Manually sync audio time to another device</div>1. Copy below text<br>2. Click "Edit" in Anki<br>3. Paste to field "time"<br>4. Sync this device<br>5. Sync another device<br>6. On another device, open <span style="text-decoration:underline">the same note</span> and click "Import Audio Time"'
   label.style.cssText = 'color:white;margin-bottom:8px;font-size:14px;text-align:left;';
       var btn = document.createElement('button');
       btn.textContent = 'Close';
       btn.style.cssText = 'margin-top:16px;padding:8px 24px;font-size:16px;';
       btn.onclick = function() {
           div.parentNode.removeChild(div);
           window._exportShowing = false;
       };
       div.appendChild(label);
       div.appendChild(ta);
       div.appendChild(btn);
       document.documentElement.appendChild(div);   // escape any transformed body container
       setTimeout(function() {
           var range = document.createRange();
           range.selectNodeContents(ta);
           var sel = window.getSelection();
           sel.removeAllRanges();
           sel.addRange(range);
       }, 100);
   }
   function importRanges() {
       // read the field from the DOM, never as a JS string literal: a
       // newline in the field breaks the literal and kills this whole
       // script block. textContent already decodes the HTML entities.
       // fromCharCode instead of escapes: backslashes do not survive the
       // template's trip through Python and AnkiConnect intact.
       var _tf = document.getElementById('apTimeField');
       var _NB = String.fromCharCode(160);
       var _LF = String.fromCharCode(10);
       var _CR = String.fromCharCode(13);
       var json = (_tf ? _tf.textContent : '')
       .split(_NB).join(' ')
       .split(_LF).join('')
       .split(_CR).join('')
       .trim();
       if (!json) {
           alert(`field "time" is empty
   sync another device first, then open the same note`);
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
               }
           }
           alert('Import complete,  ' + count + ' records updated');
       } catch(e) {
           alert('Error: ' + e.message);
       }
   }

   window.useGoogle = true;
   async function checkConnectivity() {
     try {
       await fetch('https://www.google.com/generate_204', {
         mode: 'no-cors',
         cache: 'no-store',
         signal: AbortSignal.timeout(2000)
       });
       window.useGoogle = true;
     } catch(e) {
       window.useGoogle = false;
     }
   }
   checkConnectivity();

   // one search path for every lookup button: the button carries only its
   // keyword, the spell scrape and the engine choice live here
   window._apSearch = function (el) {
       var d = document.createElement('div');
       d.innerHTML = document.getElementById('etymSpell')
           .innerHTML.replace(/<[^>]*>/g, ' ');
       var spell = d.textContent.split(String.fromCharCode(160)).join(' ')
           .replace(/ +/g, ' ').trim();
       var base = window.useGoogle
           ? 'https://www.google.com/search?q='
           : 'https://cn.bing.com/search?q=';
       el.href = base + encodeURIComponent(spell + ' ' + (el.dataset.kw || ''));
       return true;
   };

    {
    // the CJK test runs once here and nowhere else
    const spellText = document.getElementById('etymSpell').textContent;
    const cjk = /[぀-ヿ㐀-鿿]/u.test(spellText);
    [['dictBtn', '辞典', 'Meaning'],
     ['etymBtn', '語源', 'Origin']].forEach(function (spec) {
        const b = document.getElementById(spec[0]);
        if (!b) return;
        b.textContent = cjk ? spec[1] : spec[2];
        b.dataset.kw = b.textContent;
    });
    }
</script>

<div id="dbg-panel" style="margin-top: 32px; text-align: left; font-family: monospace; font-size: 10px; line-height: 1.5; color: #999; white-space: pre-wrap; -webkit-user-select: text; user-select: text"></div>
<script>
   // --- canvas blank-after-lock probe: OBSERVE ONLY, no repair ---
   (function () {
       var W = window.top;
       if (!W._imgDbg) W._imgDbg = { log: [], blank: 0, timer: null };
       var D = W._imgDbg;
       D.fname = (window._apCap && window._apCap().mp3) || '';
       D.everPainted = false;
       D.lastState = null;
       D.freshBlankLogged = false;
       var NL = String.fromCharCode(10);

       function ts() {
           var d = new Date();
           function p(n) { return (n < 10 ? '0' : '') + n; }
           return p(d.getHours()) + ':' + p(d.getMinutes()) + ':' + p(d.getSeconds());
       }
       function render() {
           var el = document.getElementById('dbg-panel');
           if (el) el.textContent = D.log.slice(-30).join(NL);
       }
       function log(msg) {
           D.log.push(ts() + ' ' + msg);
           if (D.log.length > 60) D.log.shift();
           render();
       }
       function sample() {
           var canvas = document.getElementById('word-img-canvas');
           if (!canvas || canvas.style.display === 'none') return 'nocanvas';
           if (!canvas.width || !canvas.height) return 'nosize';
           try {
               var ctx = canvas.getContext('2d');
               var sum = 0;
               var pts = [[0.5, 0.5], [0.25, 0.25], [0.75, 0.75], [0.25, 0.75]];
               for (var i = 0; i < pts.length; i++) {
                   var d = ctx.getImageData(
                       Math.floor(canvas.width * pts[i][0]),
                       Math.floor(canvas.height * pts[i][1]), 1, 1).data;
                   sum += d[0] + d[1] + d[2] + d[3];
               }
               return sum === 0 ? 'blank' : 'painted';
           } catch (e) {
               return 'err:' + e.name;
           }
       }
       function bitmapState() {
           // liveness test on an OFFSCREEN canvas: never touches the visible one
           var cache = W._apCache && W._apCache[D.fname];
           if (!cache || !cache.bitmap) return 'bm-missing';
           try {
               var c = document.createElement('canvas');
               c.width = 8;
               c.height = 8;
               var x = c.getContext('2d');
               x.drawImage(cache.bitmap, 0, 0, 8, 8);
               var d = x.getImageData(0, 0, 8, 8).data;
               var sum = 0;
               for (var i = 0; i < d.length; i++) sum += d[i];
               return sum === 0 ? 'bm-dead' : 'bm-alive';
           } catch (e) {
               return 'bm-err:' + e.name;
           }
       }
       function probeHeal(tag) {
           var cache = W._apCache && W._apCache[D.fname];
           var canvas = document.getElementById('word-img-canvas');
           if (!cache || !canvas) return;
           try {
               if (cache.bitmap) {
                   canvas.getContext('2d').drawImage(cache.bitmap, 0, 0);
                   if (sample() === 'painted') { log(tag + ' redraw-ok'); D.lastState = 'painted'; return; }
               }
           } catch (e) {}
           if (cache.blob && typeof createImageBitmap === 'function') {
               createImageBitmap(cache.blob).then(function (bm) {
                   cache.bitmap = bm;
                   try {
                       canvas.getContext('2d').drawImage(bm, 0, 0);
                       log(tag + ' ' + (sample() === 'painted' ? 'recreate-ok' : 'recreate-blank'));
                       D.lastState = sample();
                   } catch (e) { log(tag + ' recreate-err'); }
               }, function () { log(tag + ' recreate-fail'); });
           } else {
               log(tag + ' no-blob');
           }
       }
       function check(src) {
           if (D.healed && D.healed !== D.healedSeen) {
               D.healedSeen = D.healed;
               log('img self-heal #' + D.healed);
           }
           var st = sample();
           if (st === 'painted') D.everPainted = true;
           if (st !== D.lastState) {
               var flipped = D.lastState !== null;
               D.lastState = st;
               if (st === 'blank' && D.everPainted) {
                   D.blank += 1;
                   log(src + ' BLANK #' + D.blank + ' | ' + bitmapState());
                   probeHeal('heal:');
               } else if (flipped) {
                   log(src + ' ' + st);
               }
           }
           if (st === 'blank' && !D.everPainted && !D.freshBlankLogged) {
               D.freshBlankLogged = true;
               log(src + ' render-blank | ' + bitmapState());
               probeHeal('heal:');
           }
       }

       // ---- audio-side observation (no repair) ----
       var ctx = W._apAudioCtx;
       if (ctx) {
           if (ctx.state !== 'running') log('au:ctx ' + ctx.state);
           ctx.onstatechange = function () {
               log('au:state ' + ctx.state);
           };
       } else {
           log('au:ctx none');
       }
       if (window.playRange && !window.playRange._dbgWrapped) {
           var origPlay = window.playRange;
           var wrapped = function () {
               var c = W._apAudioCtx;
               log('au:play ' + (c ? c.state : 'noctx'));
               return origPlay.apply(this, arguments);
           };
           wrapped._dbgWrapped = true;
           window.playRange = wrapped;
       }
       window._apDbgLog = log;   // probe output for the play-clock ticks
       if (D.timer) clearInterval(D.timer);
       D.timer = setInterval(function () { check('t'); }, 3000);
       if (!document._imgDbgArmed) {
           document._imgDbgArmed = true;
           var evs = ['visibilitychange', 'pageshow', 'pagehide', 'focus', 'blur', 'resume', 'freeze'];
           for (var i = 0; i < evs.length; i++) {
               (function (ev) {
                   var tgt = (ev === 'focus' || ev === 'blur') ? window : document;
                   tgt.addEventListener(ev, function () {
                       log('ev:' + ev + (ev === 'visibilitychange' ? '/' + document.visibilityState : ''));
                       check('ev');
                   });
               })(evs[i]);
           }
           log('probe armed');
       } else {
           log('card shown');
       }
       render();
   })();
</script>
<script>
(function () {
    var _apMyGen = window.top._apGen;
    var caps = window._apCaptures || [];
    if (caps.length < 2) return;
    var wrap = document.querySelector('.ap-wrap');
    if (!wrap || !wrap.parentNode) return;

    var bar = document.createElement('div');
    bar.id = 'ap-nav';
    bar.style.cssText = 'display:flex;align-items:center;' +
        'justify-content:center;gap:18px;margin:6px auto 0;' +
        'user-select:none;-webkit-user-select:none;';
    var prev = document.createElement('div');
    var label = document.createElement('div');
    var next = document.createElement('div');
    prev.textContent = '◀';
    next.textContent = '▶';
    prev.style.cssText = next.style.cssText =
        'padding:6px 16px;cursor:pointer;font-size:20px;opacity:.75;';
    label.style.cssText =
        'font-size:14px;opacity:.8;min-width:3em;text-align:center;';
    label.textContent = (window._apCur + 1) + '/' + caps.length;
    bar.appendChild(prev);
    bar.appendChild(label);
    bar.appendChild(next);
    wrap.parentNode.insertBefore(bar, wrap.nextSibling);

    var seqOn = false, seqLeft = 0, seqHome = 0, holdTimer = null;

    function _visibleImg() {
        var fb = document.getElementById('word-img-fallback');
        if (!fb) return null;
        var imgs = fb.querySelectorAll('img');
        for (var i = 0; i < imgs.length; i++) {
            if (imgs[i].style.display !== 'none') return imgs[i];
        }
        return null;
    }
    // freeze the outgoing image as an overlay, then wipe it away with a
    // clip-path sweep: forward = front moves right-to-left, backward
    // mirrored (new page is revealed underneath)
    function wipe(dir, fade) {
        var box = window._apFrameBox;
        if (!box) return;
        var cv = document.getElementById('word-img-canvas');
        var snap = null;
        if (cv && cv.style.display !== 'none' && cv.width) {
            snap = document.createElement('canvas');
            snap.width = cv.width;
            snap.height = cv.height;
            try { snap.getContext('2d').drawImage(cv, 0, 0); }
            catch (e) { snap = null; }
        }
        if (!snap) {
            var im = _visibleImg();
            if (im && im.naturalWidth) snap = im.cloneNode(false);
        }
        if (!snap) return;
        snap.style.cssText = 'position:absolute;left:0;top:0;' +
            'width:100%;height:100%;object-fit:scale-down;' +
            'display:block;z-index:5;pointer-events:none;';
        snap.style.clipPath = 'inset(0 0 0 0)';
        snap.style.webkitClipPath = 'inset(0 0 0 0)';
        var _wm = window._apCfg.wipeMs;
        snap.style.transition = fade
            ? 'opacity ' + _wm + 'ms ease'
            : 'clip-path ' + _wm + 'ms ease, -webkit-clip-path '
              + _wm + 'ms ease';
        box.appendChild(snap);
        requestAnimationFrame(function () {
            requestAnimationFrame(function () {
                if (fade) {
                    snap.style.opacity = '0';
                } else {
                    var tgt = dir >= 0 ? 'inset(0 100% 0 0)'
                                       : 'inset(0 0 0 100%)';
                    snap.style.clipPath = tgt;
                    snap.style.webkitClipPath = tgt;
                }
            });
        });
        setTimeout(function () {
            if (snap.parentNode) snap.parentNode.removeChild(snap);
        }, window._apCfg.wipeCleanupMs);
    }
    function fadeWave(fn) {
        if (!wrap) { if (fn) fn(); return; }
        wrap.style.transition =
            'opacity ' + window._apCfg.waveFadeOutMs + 'ms';
        wrap.style.opacity = '0';
        setTimeout(function () {
            if (_apMyGen !== window.top._apGen) return;
            if (fn) fn();
            wrap.style.opacity = '1';
        }, window._apCfg.waveSwapMs);
    }
    function maybeTimerAdvance() {
        if (holdTimer) { clearTimeout(holdTimer); holdTimer = null; }
        if (!seqOn) return;
        if (!window._apCap().mp3) {
            holdTimer = setTimeout(function () {
                if (_apMyGen !== window.top._apGen) return;
                if (window._apSeqNext) window._apSeqNext();
            }, window._apCfg.silentHoldMs);
        }
    }
    function show(idx, opts) {
        opts = opts || {};
        var n = caps.length;
        idx = ((idx % n) + n) % n;
        wipe(opts.dir >= 0 ? 1 : -1, !!opts.fade);
        window._apCur = idx;
        label.textContent = (idx + 1) + '/' + n;
        if (window._apRenderImage) window._apRenderImage();
        fadeWave(function () {
            if (window._apReloadAudio) window._apReloadAudio(!!opts.noplay);
        });
        if (!opts.auto) {
            try {
                localStorage.setItem(window._apPageKey, String(idx));
            } catch (e) {}
        }
        maybeTimerAdvance();
    }
    function go(d) {
        seqOn = false;
        if (holdTimer) { clearTimeout(holdTimer); holdTimer = null; }
        show(window._apCur + d, { dir: d });
    }
    prev.onclick = function () { go(-1); };
    next.onclick = function () { go(1); };

    // sequence: play every page once starting from the current (anchor)
    // page, wrapping around, then come home silently
    window._apSeqArm = function () {
        if (_apMyGen !== window.top._apGen) return;
        seqOn = true;
        seqLeft = caps.length - 1;
        seqHome = window._apCur;
    };
    window._apSeqNext = function () {
        if (_apMyGen !== window.top._apGen) return;
        if (!seqOn) return;
        if (seqLeft > 0) {
            seqLeft--;
            show(window._apCur + 1, { auto: true, dir: 1 });
        } else {
            seqOn = false;
            show(seqHome, { auto: true, dir: 1, noplay: true, fade: true });
        }
    };
    // dragging a range handle = manual intervention: let the current page
    // finish but do not auto-advance afterwards
    window._apSeqStop = function () {
        if (_apMyGen !== window.top._apGen) return;
        seqOn = false;
        if (holdTimer) { clearTimeout(holdTimer); holdTimer = null; }
    };
    // card shown = the sequence starts from the anchor page
    window._apSeqArm();
    maybeTimerAdvance();
})();
</script>"""
    CSS = r"""img {
  max-width: 100%;
  height: auto;
}

#left-col {
  align-items: center;
}

#text-wrap {
  width: fit-content;
  margin: 0 auto;
}

#main-wrap {
  display: flex;
  flex-direction: column;
}

#left-col {
  display: flex;
  flex-direction: column;
}

#text-wrap {
  margin: 0 auto;
}

body.landscape #main-wrap {
  flex-direction: row;
  align-items: flex-start;
  gap: 16px;
}

body.landscape #text-wrap {
  flex: 1;
  text-align: left;
  margin: 0;
}

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
  background: #f5f5f5;
  border-radius: 6px;
  touch-action: none;

  /* ---- handle geometry: tune these, everything below derives from them ---- */
  --vis-w: 20px;     /* visible bracket width (the display box) */
  --hit-up: 20px;    /* hit area extends this far above the display box */
  --hit-down: 20px;  /* hit area extends this far below the display box */
  --hit-outer: 50px;  /* hit area past the bracket line (anchored side) */
  --hit-inner: 5px; /* hit area past the bracket's open side */
}

#ap-wave {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  display: block;
  border-radius: 6px;
}

.ap-range {
  position: absolute;
  top: 0;
  bottom: 0;
  background: rgba(26, 115, 232, 0.18);
  pointer-events: none;
  border-radius: 4px;
}

/* Outer handle = invisible hit area, all sizes derived from the variables above */
.ap-handle {
  position: absolute;
  top: calc(-1 * var(--hit-up));
  width: calc(var(--vis-w) + var(--hit-outer) + var(--hit-inner));
  height: calc(100% + var(--hit-up) + var(--hit-down));
  cursor: ew-resize;
  z-index: 2;
  background: transparent;
  touch-action: none;
}

/* Inner visual = the actual visible bracket (display box), snapped to track height */
.ap-handle-visual {
  position: absolute;
  top: var(--hit-up);
  bottom: var(--hit-down);
  width: var(--vis-w);
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
  background: #1a73e8;
}

/* Bottom bar of the bracket */
.ap-handle-visual::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 1px;
  background: #1a73e8;
}

/* Start handle: vertical line on the LEFT, anchored to time point */
.ap-handle-start {
  transform: translateX(calc(-1 * var(--hit-outer)));
}

.ap-handle-start .ap-handle-visual {
  left: var(--hit-outer);
  border-left: 1px solid #1a73e8;
}

/* End handle: vertical line on the RIGHT, anchored to time point */
.ap-handle-end {
  transform: translateX(calc(-1 * (var(--vis-w) + var(--hit-inner))));
}

.ap-handle-end .ap-handle-visual {
  right: var(--hit-outer);
  border-right: 1px solid #1a73e8;
}

/* Active state: thicker top and bottom bars only */
.ap-handle:active .ap-handle-visual::before,
.ap-handle:active .ap-handle-visual::after {
  height: 2px;
}

.ap-handle-start:active .ap-handle-visual {
  border-left: 1px solid #0b57c4;
}

.ap-handle-end:active .ap-handle-visual {
  border-right: 1px solid #0b57c4;
}"""
    FRONT_TEMPLATE = FRONT_TEMPLATE.strip('\n')
    BACK_TEMPLATE = BACK_TEMPLATE.strip('\n')
    CSS = CSS.strip('\n')

    if ui_index == 1:
        SYNC_UI = (
            ('field "time" is empty', 'time字段为空'),
            ('sync another device first, then open the same note',
             '先同步另一设备，再打开同一词条'),
            ('Import complete, ', '导入完成，更新了'),
            ('records updated', '条记录'),
            ('Error: ', '解析失败：'),
            ('<div style="text-align:center;margin-bottom:6px">Manually sync audio time to another device</div>1. Copy below text<br>2. Click "Edit" in Anki<br>3. Paste to field "time"<br>4. Sync this device<br>5. Sync another device<br>6. On another device, open <span style="text-decoration:underline">the same note</span> and click "Import Audio Time"',
             '<div style="text-align:center;margin-bottom:6px">手动复制音频时间到另一设备</div>1.复制以下文本<br>2.点击Anki的"编辑"<br>3.找到"time"字段并黏贴<br>4.同步本设备<br>5.同步另一设备<br>6.在另一设备打开 <span style="text-decoration:underline">同一词条</span> 并点击"导入音频时间"'
             ),
            ('Copy Audio Time', '复制音频时间'),
            ('Import Audio Time', '导入音频时间'),
            ('Close', '关闭'),
            ('Failed to load:', '音频获取失败'),
            ('Check if sync is finished', '检查同步是否完成'),
        )

        for en, zh in SYNC_UI:
            BACK_TEMPLATE = BACK_TEMPLATE.replace(en, zh)

    need_update_config = False

    MODEL_FIELDS = [
        "spell",
        "pron",
        "excerpt",
        "fuzzy",
        "screenshot",
        "audio",
        "time",
    ]
    if MODEL_NAME not in (invoke("modelNames") or {}).get("result", []):
        invoke("createModel",
               modelName=MODEL_NAME,
               inOrderFields=MODEL_FIELDS,
               css=CSS,
               isCloze=False,
               cardTemplates=[{
                   "Name": MODEL_NAME,
                   "Front": FRONT_TEMPLATE,
                   "Back": BACK_TEMPLATE,
               }])
        need_update_config = True
    else:
        update_config('anki_model_ok', True)
        # check if any missing fields and add
        fields_in_anki = invoke("modelFieldNames", modelName=MODEL_NAME)
        if fields_in_anki and fields_in_anki.get("result"):
            existing = fields_in_anki["result"]
            for field in MODEL_FIELDS:
                if field not in existing:
                    invoke("modelFieldAdd",
                           modelName=MODEL_NAME,
                           fieldName=field)
        # check model version. however, before overwrite old model, check if it user modified it manually
        # if yes, assume user need the modified model so will not update newer model to anki
        if config['anki_model_version_and_hash'][0] < ANKI_MODEL_VERSION:
            model_hash = anki_current_model_hash()
            if model_hash == config['anki_model_version_and_hash'][
                    1] or config['anki_model_version_and_hash'][0] == 0:
                invoke("updateModelTemplates",
                       model={
                           "name": MODEL_NAME,
                           "templates": {
                               MODEL_NAME: {
                                   "Front": FRONT_TEMPLATE,
                                   "Back": BACK_TEMPLATE,
                               }
                           }
                       })
                invoke("updateModelStyling",
                       model={
                           "name": MODEL_NAME,
                           "css": CSS
                       })
                need_update_config = True

    if need_update_config:
        model_hash = anki_current_model_hash()
        update_config('anki_model_version_and_hash',
                      [ANKI_MODEL_VERSION, model_hash])

    # Mirror the shipped templates next to config.json (debug/backup copy)
    time.sleep(15)
    try:
        from platformdirs import user_config_dir
        tpl_dir = user_config_dir('ACard', appauthor=False)
        for name, text in (("FRONT_TEMPLATE.html", FRONT_TEMPLATE),
                           ("BACK_TEMPLATE.html", BACK_TEMPLATE),
                           ("CSS.css", CSS)):
            with open(os.path.join(tpl_dir, name), 'w', encoding='utf-8') as f:
                f.write(text)
    except OSError:
        pass


def anki_check_deck_and_model(intial_run):
    if intial_run:
        anki_thread.join()
    if not config['anki_deck_ok'] or intial_run:
        threading.Thread(target=anki_create_deck, daemon=True).start()
    if not config['anki_model_ok'] or intial_run:
        threading.Thread(target=anki_create_model, daemon=True).start()


def anki_current_model_hash():
    model_data = str(invoke("modelTemplates", modelName=MODEL_NAME)) + str(
        invoke("modelStyling", modelName=MODEL_NAME)) + str(
            invoke("modelFieldNames", modelName=MODEL_NAME))
    model_data.replace(' ', '').replace('\n',
                                        '').replace('\t',
                                                    '').replace('\r', '')
    return hashlib.md5(model_data.encode()).hexdigest()


def ttt(label=""):  # test need delete
    global _last_time
    now = time.time()
    if _last_time is not None:
        print(f"[{label}] {now - _last_time:.3f}s")
    else:
        print(f"[{label}] start")
    _last_time = now


def _record_mei_folder():
    # Record current _MEI folder name in config, keep most recent 3.
    if not getattr(sys, 'frozen', False):
        return
    current = os.path.basename(sys._MEIPASS)
    folders = config.get('mei_folder', [])
    if current in folders:
        folders.remove(current)  # move to end if already present
    folders.append(current)
    folders = folders[-3:]  # keep most recent 3
    update_config('mei_folder', folders)


def _cleanup_old_mei():
    # Delete recorded _MEI folders except the current one (residue from force-killed exits).
    if not getattr(sys, 'frozen', False):
        return
    current = os.path.basename(sys._MEIPASS)
    temp = tempfile.gettempdir()
    folders = config.get('mei_folder', [])
    remaining = []
    for name in folders:
        if name == current:
            remaining.append(name)  # keep the one in use
            continue
        path = os.path.join(temp, name)
        if os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)
        # Keep in list only if deletion failed (still exists), so we retry next time
        if os.path.isdir(path):
            remaining.append(name)
    update_config('mei_folder', remaining)


windll.kernel32.SetProcessWorkingSetSize(windll.kernel32.GetCurrentProcess(),
                                         -1, -1)
ui_index = get_ui_index()
if ui_index == 1:
    default_dst_lang = "中文"
else:
    default_dst_lang = "English"
DEFAULT_CONFIG = {
    "anki_path": "",
    "anki_connect_successful": False,
    "anki_deck_name": "ACard",
    "anki_model_name": "ACardModel",
    "anki_deck_ok": False,
    "anki_model_ok": False,
    "anki_model_version_and_hash": [0, ""],
    "anki_new_note_left": 30,
    "anki_sync_note": 20,
    "anki_combine_dup": True,
    "monitor_index": 1,
    "max_fps": [[5, 8], [10, 4], [120, 2]],
    "min_memory_gb": 0.5,
    "max_memory_percentage": 0.5,
    "max_disk_percentage": 0.5,
    "jpeg_quality": 75,
    "window_pos": None,
    "hotkey": [{
        "type": "keyboard",
        "modifiers": ["alt"],
        "key": "a"
    }],
    "playback_hint_left": 10,
    "src_lang": "日本語",
    "dst_lang": default_dst_lang,
    "tip": [
        [
            ["Snip after sentence COMPLETE","等完整句子结束之后截图"]
        ],
        [
            ["Select Borderless for games","尽量用无边框模式运行游戏"],
            ["Use scroll button to playback","用鼠标滚轮回放"]
        ]
    ],
    "mei_folder": [],
}
config_path, config = load_config()
repair_config()
_record_mei_folder()
threading.Timer(15, _cleanup_old_mei).start()
app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)


class AppEventFilter(QObject):

    def eventFilter(self, obj, event):
        if isinstance(obj, QMenu) and event.type() == QEvent.Show:
            hwnd = int(obj.winId())
            user32.SetWindowDisplayAffinity(hwnd, 0)
            user32.SetWindowDisplayAffinity(hwnd, 0x00000011)
        return False


app_event_filter = AppEventFilter()
QApplication.instance().installEventFilter(app_event_filter)
ANKI_HOST = '127.0.0.1'
ANKI_PORT = 8765
ANKI_URL = f'http://{ANKI_HOST}:{ANKI_PORT}'
DECK_NAME = config['anki_deck_name']
MODEL_NAME = config['anki_model_name']
anki_check_needed = True
anki_path = check_get_anki_path()
anki_thread = threading.Thread(target=open_anki,
                               args=(anki_path, ),
                               daemon=True)
anki_thread.start()  # test
threading.Thread(target=check_google_reachable,daemon=True).start()
check_dup()

round_display = threading.Event()
round_anki_id_generated = threading.Event()
round_audio_analysis_start_time_done = threading.Event()
round_anki_audio_sent = threading.Event()
_round_events = (round_display, round_anki_id_generated, round_audio_analysis_start_time_done, round_anki_audio_sent)

# --- merge-by-spell: index of existing notes ---------------------------
_spell_index = {}          # normalized spell -> oldest unsuspended note id
_spell_index_thread = None


def norm_spell(s):
    # merge key: strip html tags and nbsp (hand-edited notes carry both),
    # then compare exactly
    s = re.sub(r'<[^>]+>', '', s or '')
    return s.replace('\xa0', '').strip()


def rebuild_spell_index(wait_prev=False):
    # snapshot {spell: note id} of every active note in the deck. With
    # wait_prev the previous round's note must land in Anki first, so
    # re-snipping the same word sees it as a merge target
    global _spell_index
    if wait_prev:
        round_anki_id_generated.wait(timeout=5)
    t0 = time.time()
    r = invoke('findNotes',
               query=f'deck:{DECK_NAME} note:{MODEL_NAME} -is:suspended')
    if not r or r.get('error') or r.get('result') is None:
        print('spell index: findNotes failed, keeping old index')
        return
    r = invoke('notesInfo', notes=r['result'])
    if not r or r.get('error') or r.get('result') is None:
        print('spell index: notesInfo failed, keeping old index')
        return
    idx = {}
    for n in r['result']:
        s = norm_spell(n['fields']['spell']['value'])
        nid = n['noteId']
        if s and (s not in idx or nid < idx[s]):
            idx[s] = nid    # duplicate spells: oldest note wins
    _spell_index = idx
    print(f'spell index: {len(idx)} entries in {time.time() - t0:.2f}s')


def spell_index_forget(note_id):
    # a note deleted in acard: drop it from the index
    for k, v in list(_spell_index.items()):
        if str(v) == str(note_id):
            del _spell_index[k]
            break


def _spell_index_boot():
    # quiet warm-up: wait for AnkiConnect, then build the first index
    for _ in range(120):
        if anki_connect_is_running():
            rebuild_spell_index()
            return
        time.sleep(2)


if config['anki_combine_dup']:
    threading.Thread(target=_spell_index_boot, daemon=True).start()

session = None  # moji session
dummy_uuid = str(uuid.uuid4())
hotkey_mode = 1  # -1 = ignore all, 0 = config, 1 = main, 2 = in snip
keyboard_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
last_moji_search_time = 0
anki_sync_running = False
_dict_loading = False


def round_reset():
    for ev in _round_events:
        ev.clear()


def round_finish_all():
    for ev in _round_events:
        ev.set()


def _init_dict():
    global _conn_dict
    path = os.path.join(BASE, 'dict.db')
    if not os.path.exists(path):
        print(f'dict.db not found at {path}')
        return
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    _conn_dict = conn
    _conn_dict_ready.set()


def start_dict():
    # one unified dict.db serves every language pair: open it once,
    # switching languages needs no reload
    global _dict_loading
    if _conn_dict is None and not _dict_loading:
        _dict_loading = True
        threading.Thread(target=_init_dict, daemon=True).start()


start_dict()
max_fps = [row[:]
           for row in config['max_fps']]  # Copy to avoid modifying config
max_record_time = max_fps[-1][0]
AUDIO_BEFORE_SNIP_SECOND = 60  # when a snip is taken, take this seconds before the snip time as draft audio for further analysis
BUFFER_SECONDS = max_record_time + AUDIO_BEFORE_SNIP_SECOND
AUDIO_AFTER_SNIP_SECOND = 15


class LoopbackRecorder:
    DLL_PATH = os.path.join(BASE, 'LoopbackCapture.dll')

    RATE = 44100
    CHANNELS = 2
    BITS = 16

    BYTES_PER_SAMPLE = CHANNELS * (BITS // 8)
    BYTES_PER_SEC = RATE * BYTES_PER_SAMPLE

    MAX_BYTES = BYTES_PER_SEC * BUFFER_SECONDS

    utilsdll = cdll.LoadLibrary(DLL_PATH)

    AudioCallback = CFUNCTYPE(None, POINTER(c_char), c_size_t, c_longlong)

    SetAudioCallback = utilsdll.SetAudioCallback
    SetAudioCallback.argtypes = [AudioCallback]
    SetAudioCallback.restype = c_int

    StartCaptureAsync = utilsdll.StartCaptureAsync
    StartCaptureAsync.argtypes = [POINTER(c_void_p)]
    StartCaptureAsync.restype = c_int

    StopCapture = utilsdll.StopCapture
    StopCapture.argtypes = []
    StopCapture.restype = c_int

    def __init__(self):
        self.ptr = c_void_p()
        self.lock = threading.Lock()
        self.ring = deque()
        self.size = 0
        self.last_audio = b''

        self.cb = self.AudioCallback(self._on_data)
        self.SetAudioCallback(self.cb)
        self.StartCaptureAsync(pointer(self.ptr))

        threading.Timer(0.2, self.capture_last, args=(time.time(),time.time(),)).start()  # initialized capture

    def _on_data(self, ptr, sz, timestamp_ms):
        if not ptr or sz == 0:
            return
        data = string_at(ptr, sz)
        with self.lock:
            self.ring.append((data, timestamp_ms / 1000.0))
            self.size += sz
            while self.size > self.MAX_BYTES:
                old, _ = self.ring.popleft()
                self.size -= len(old)

    def capture_last(self, snip_time, click_time):
        """Extract this capture's audio window and RETURN it. No shared
        state: every snip owns its private copy, so overlapping pipelines
        can never clobber each other's audio."""
        with self.lock:
            chunks = list(self.ring)
        if not chunks:
            return b'', 0.0, 0.0

        # print(f"first chunk time: {chunks[0][1]:.3f}")
        # print(f"last chunk time:  {chunks[-1][1]:.3f}")
        # print(f"click_time:       {click_time:.3f}")
        # print(f"data_start_time:  {chunks[0][1]:.3f}")
        # print(f"snip_time-60:     {snip_time - AUDIO_BEFORE_SNIP_SECOND:.3f}")

        data = b''.join(c for c, _ in chunks)
        data_start_time = chunks[0][1]
        last_chunk_time = chunks[-1][1]
        # print(f"len(data)/BYTES_PER_SEC={len(data)/self.BYTES_PER_SEC:.3f}s")
        # print(f"last_chunk_time - data_start_time={last_chunk_time - data_start_time:.3f}s")
        audio_start_time = max(snip_time - AUDIO_BEFORE_SNIP_SECOND,
                               data_start_time)
        save_start_byte = len(data) - int(
            self.BYTES_PER_SEC * (last_chunk_time - audio_start_time))
        save_start_byte = save_start_byte - save_start_byte % self.BYTES_PER_SAMPLE
        save_start_byte = max(save_start_byte, 0)

        audio_end_time = min(snip_time + AUDIO_AFTER_SNIP_SECOND,
                             last_chunk_time)
        save_end_byte = len(data) - int(
            self.BYTES_PER_SEC * (last_chunk_time - audio_end_time))
        save_end_byte = save_end_byte - save_end_byte % self.BYTES_PER_SAMPLE
        save_end_byte = min(save_end_byte, len(data))
        save_end_byte = max(save_end_byte, 0)

        data = data[save_start_byte:save_end_byte]
        print(f'captured {len(data)} bytes')
        return data, audio_start_time, audio_end_time

    def stop(self):
        # Signal the native capture thread to stop and join it
        self.StopCapture()

recorder = LoopbackRecorder()
min_memory_gb = config['min_memory_gb']
max_memory_percentage = config['max_memory_percentage']
max_disk_percentage = config['max_disk_percentage']
convert_max_fps()
screenshot = []
anki_list = []
lock = threading.Lock()
user32 = WinDLL("user32", use_last_error=True)
screenshot_users = 0
lock_length = 0
round_finish_all()
this_screenshot_time = int(time.time()) * 1000  # initial run at whole second to reduce rounding effect
psutil.cpu_percent(interval=0)  # for cpu
high_cpu_seconds = 0
screenshot_thread_stop = threading.Event()
screenshot_thread_handle = threading.Thread(target=screenshot_thread,
                                            daemon=True)
screenshot_thread_handle.start()

# for ocr
ErrorCallback = CFUNCTYPE(None, c_char_p)
DetectCallback = CFUNCTYPE(None, c_float, c_float, c_float, c_float, c_float,
                           c_float, c_float, c_float, c_char_p)
dll.cvMatFromRGB888.argtypes = (c_void_p, c_int, c_int, c_int)
dll.cvMatFromRGB888.restype = CvMat
dll.cvMatDestroy.argtypes = (CvMat, )
dll.cvMatDestroy.restype = None
dll.OcrLoadRuntime.restype = c_bool
dll.OcrInit.argtypes = (c_wchar_p, c_wchar_p, c_wchar_p, c_int32, c_bool,
                        c_uint64, c_char_p, ErrorCallback)
dll.OcrInit.restype = OcrHandle
dll.OcrDetect.argtypes = (OcrHandle, CvMat, c_int32, DetectCallback,
                          ErrorCallback)
dll.OcrDetect.restype = None
dll.OcrDestroy.argtypes = (OcrHandle, )
dll.OcrDestroy.restype = None
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
    show_msg_signal = pyqtSignal(str)
    show_page_signal = pyqtSignal(object, int, int)
    nav_reset_signal = pyqtSignal()
    reinit_snip_signal = pyqtSignal()
    close_snip_signal = pyqtSignal(bool)  # 0 = quit, 1 = successful snip
    cancel_drag_signal = pyqtSignal()
    scroll_signal = pyqtSignal(int)
    hotkey_captured_signal = pyqtSignal()
    hide_signal = pyqtSignal()
    slider_set_signal = pyqtSignal(int)
    copy_text_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        # Debounce timer: only save after movement settles
        self._pos_save_timer = QTimer(self)
        self._pos_save_timer.setSingleShot(True)
        self._pos_save_timer.setInterval(300)
        self._pos_save_timer.timeout.connect(self._save_position)
        self._restore_done = False
        self.show_msg_signal.connect(self._show_msg)
        self.show_page_signal.connect(self._show_page)
        self.nav_reset_signal.connect(self._nav_reset)
        self.reinit_snip_signal.connect(_reinit_snip_main_thread)
        self.close_snip_signal.connect(snip.close_snip)
        self.cancel_drag_signal.connect(snip.cancel_drag)
        self.scroll_signal.connect(_snip_scroll)
        self.hide_signal.connect(self.hide)
        self.slider_set_signal.connect(lambda v: snip.slider.setValue(v))
        self.copy_text_signal.connect(
            lambda text: QApplication.clipboard().setText(text))

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

    def _save_position(
            self):  # keep same positon when application open next time
        p = self.pos()
        update_config('window_pos', [p.x(), p.y()])

    def closeEvent(self, event):
        on_quit()

    def _nav_reset(self):
        # let the arrows pop back up (round finished or timed out)
        window.page_prev_btn.setDown(False)
        window.page_next_btn.setDown(False)

    def _show_page(self, jpg_bytes, idx, total):
        self._nav_reset()
        # worker asks the gui thread to hard-cut to a page and refresh
        # the nav bar; jpg_bytes None = nav refresh only
        # read visibility BEFORE window_change_picture: that call hides
        # the nav, so reading after it always looks like a hidden->shown
        # flip and resizes on every page change - and with the nav just
        # shown its sizeHint is still stale, so the window shrinks a bit
        was = window.page_nav.isVisible()
        if jpg_bytes:
            pm = QPixmap()
            pm.loadFromData(jpg_bytes)
            window_change_picture(pm)
        window._qt_page = idx
        if total >= 2:
            window.page_nav_label.setText(f'{idx + 1}/{total}')
            window.page_nav.show()
        else:
            window.page_nav.hide()
        if window.page_nav.isVisible() != was:
            resize_window_height()

    def _show_msg(self, str):
        global anki_check_needed
        if anki_check_needed:
            anki_check_needed = False
            msg = QMessageBox()
            msg.setWindowTitle(ui('messagebox_title'))
            msg.setText(str)
            msg.setTextFormat(Qt.RichText)
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec_()


def fetch_tips():
    import urllib.request
    TIP_URL = "https://raw.githubusercontent.com/qazzzlyt/ACard/main/no%20need%20to%20download%2C%20this%20is%20source%20code%20for%20developers/tip.json"
    try:
        url = f"{TIP_URL}?t={int(time.time())}"
        with urllib.request.urlopen(url, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            if isinstance(data, list):
                update_config('tip',data)
    except Exception as e:
        print(f"fetch_tips error: {e}")


def show_tip():
    alltip = config['tip']
    if config['playback_hint_left'] != 0:
        tip = alltip[0]
    else:
        tip = alltip[1]
    window.label_spell.setText(random.choice(tip)[ui_index])
    mon = snip.sct.monitors[config['monitor_index']]
    fit_w = window.label_spell.fontMetrics().horizontalAdvance(
        window.label_spell.text()) + 40           # actual text pixel width + margins
    floor = max(360, int(mon['width'] * 0.2))      # lower bound: keep excerpt readable
    cap = int(mon['width'] * 0.5)                   # upper bound: avoid over-wide window
    window.setFixedWidth(max(floor, min(fit_w, cap)))
    resize_window_height()
    set_result_editable(False)         # tip is read-only
    update_save_btn_state()            # no note yet -> save greyed


def show_title_menu(global_pos):
    # Same quit menu as the tray icon
    menu = QMenu()
    action_quit = QAction(ui('quit'), menu)
    action_quit.triggered.connect(on_quit)
    menu.addAction(action_quit)
    menu.exec_(global_pos)


def on_quit():
    threading.Thread(target=anki_sync_on_quit, daemon=True).start()
    window._save_position()  # save window position
    tray.hide()              # remove tray icon
    recorder.stop()          # stop native audio capture thread
    _generate_exit_bat()     # generate bat: delete _MEI (and apply update if pending)
    rotate_log_if_needed()   # close log and rotate if it grew past the cap
    try:
        psutil.Process(os.getpid()).parent().kill()  # kill PyInstaller bootloader
    except Exception:
        pass
    os._exit(0)              # force immediate exit, skip native teardown


def anki_sync_on_quit():
    if not anki_sync_running:
        requests.post(ANKI_URL, json={"action": "sync","params": {},"version": 6},timeout=10).json()


def tray_show(reason):
    global hide_on_click
    if reason == QSystemTrayIcon.Trigger:
        hide_on_click = False   # manual summon: disarm auto-hide until next lookup
        window.show()


print('ver ' + __version__)
window = MainWindow()
bridge.anki_new_note_done.connect(anki_new_note_after,Qt.BlockingQueuedConnection)
window.restore_position()
window.setStyleSheet("background-color: #f0f0f0; color: #000000;")
window.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
window.setWindowOpacity(0.9)
show_and_exclude_from_capture(window)
hide_on_click = False
set_qt_layout()

show_tip()
threading.Timer(10, fetch_tips).start()
threading.Thread(target=anki_check_deck_and_model, args=(True, ),
                 daemon=True).start()
# Create tray icon
tray = QSystemTrayIcon(window)
tray.setIcon(QIcon(resource_path("icon.ico")))
tray.setToolTip("ACard")
#right-click menu
menu = QMenu()
action_quit = QAction(ui('quit'))
action_quit.triggered.connect(on_quit)
menu.addAction(action_quit)
tray.setContextMenu(menu)
tray.show()
tray.activated.connect(tray_show)
keyboard_listener.start()
time.sleep(0.3)  # test need delete
print(f"keyboard_listener alive: {keyboard_listener.is_alive()}"
      )  # test need delete
threading.Thread(target=_start_mouse_hook, daemon=True).start()
sys.exit(app.exec_())