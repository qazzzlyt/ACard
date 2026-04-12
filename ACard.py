import os
import threading
import uuid
import base64
import wave
import io
from mss import mss
import socket
import sys
import time
import psutil
import math
import json
import subprocess
import tempfile
import time
import requests
from functools import partial
from pynput import keyboard, mouse
from ctypes import *
from collections import deque
from pathlib import Path
from pynput import keyboard, mouse
import ctypes
from ctypes import wintypes
from ctypes import CDLL, CFUNCTYPE, c_bool, c_char_p, c_float, c_int, c_int32, c_uint64, c_void_p, c_wchar_p
def get_base():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))
BASE = get_base()
# load DLL first, before importing Qt
dll = CDLL(os.path.join(BASE, 'CVUtils.dll'))
if getattr(sys, 'frozen', False):
    _k32 = ctypes.WinDLL('kernel32', use_last_error=True)
    _k32.LoadLibraryW.argtypes = [ctypes.c_wchar_p]
    _k32.LoadLibraryW.restype = ctypes.c_void_p
    for _dll in ['onnxruntime.dll', 'NativeUtils.dll', 'LoopbackCapture.dll', 'bass.dll', 'bassenc.dll', 'bassenc_mp3.dll', 'bassenc_opus.dll']:
        _k32.LoadLibraryW(os.path.join(BASE, _dll))
from PyQt5.QtWidgets import QApplication, QMessageBox, QFileDialog, QMainWindow, QWidget, QMenu, QSlider, QToolTip, QLabel, QVBoxLayout, QLineEdit, QHBoxLayout, QToolButton
from PyQt5.QtCore import Qt, QRect, QEvent, QObject, pyqtSignal, QTimer, QBuffer, QIODevice, QPoint
from PyQt5.QtGui import QPainter, QColor, QPen, QPixmap, QImage, QCursor, QFont

UI_TEXT = {
    'messagebox_title': ('ACard', 'ACard'),
    'no_anki_in_config': ('Download Anki from <a href="https://apps.ankiweb.net">apps.ankiweb.net</a><br>Then select anki.exe','登录<a href="https://apps.ankiweb.net">apps.ankiweb.net</a>下载Anki<br>然后选择anki.exe'),
    'select_anki': ('Select anki.exe', '选择anki.exe'),
    'no_anki_connection': ('Click yes to Open Anki', '点击确定打开Anki'),
    'dup': ('ACard is already running', 'ACard已启动'),
    'blank': ('Blank', '无')
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
        # test need to make blank file
    return path, config
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
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump({key: value}, f, indent=4)
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
    keep_alive_thread()
def keep_alive_thread():
    global last_moji_search_time
    dummy = {}
    while True:
        if time.time() - last_moji_search_time > 590:  # not sure how long moji session will expire. in my test at 2026/03/01, longest survivor is 1192s
        # if last search was recent, do not refresh the session
        # moji search is connected via racing in this project. if too many connections at the same time, the session will fail
        # when keep alive session is running, there is a small chance that it coincides with a real search. In this case, session number will double and real session might fail
        # to lower this probability, keep alive session will not run if a real search happend recently
            last_moji_search_time = time.time()
            for _ in range(3):  # used for racing. 3 try for each moji search
                threading.Thread(target=search_mojidict_exact, args=('テスト', dummy), daemon=True).start()
                threading.Thread(target=search_mojidict_fuzzy, args=('テスト', dummy), daemon=True).start()
        time.sleep(5)
def on_press(key):
    if hotkey_mode == 1:
        try:
            if key.char == 'o' and False:  # test
                on_click_snip()
        except AttributeError:
            pass
def on_click(x, y, button, pressed):
    if hotkey_mode == 1:
        if button == mouse.Button.middle and pressed:
            on_click_snip()
class LoopbackRecorder:
    DLL_PATH = os.path.join(BASE, 'LoopbackCapture.dll')

    RATE = 44100
    CHANNELS = 2
    BITS = 16

    BYTES_PER_SEC = RATE * CHANNELS * (BITS // 8)
    BUFFER_SECONDS = 30
    SAVE_SECONDS = 10

    MAX_BYTES = BYTES_PER_SEC * BUFFER_SECONDS
    SAVE_BYTES = BYTES_PER_SEC * SAVE_SECONDS

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

    def capture_last(self):
        with self.lock:
            data = b''.join(self.ring)

        if len(data) > self.SAVE_BYTES:
            data = data[-self.SAVE_BYTES:]

        snip.audio = data
        print(f'captured {len(data)} bytes')
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
def show_and_exclude_from_capture(window):
    user32.SetWindowDisplayAffinity.argtypes = [wintypes.HWND, wintypes.DWORD]
    user32.SetWindowDisplayAffinity.restype = wintypes.BOOL
    with lock:  # need a lock to avoid screenshot between show and exclude from capture
        window.show()
        hwnd = int(window.winId())
        user32.SetWindowDisplayAffinity(hwnd, 0)  # has to reset everytime, otherwise exclude from mss will fail starting 2nd time. don't know why
        ok = user32.SetWindowDisplayAffinity(hwnd, 0x00000011)
    if not ok:
        raise ctypes.WinError(ctypes.get_last_error())
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
    mon = sct.monitors[1] # test
    while True:
        img = sct.grab(mon)  # test screenshot

        # save width and height for later use
        width = img.width
        height = img.height
        qimg = QImage(
            img.bgra,
            width,
            height,
            width * 4,
            QImage.Format_ARGB32
        )

        qimg_rgb = qimg.convertToFormat(QImage.Format_RGB888)
        del qimg
        del img

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
class Snip(QWidget):
    def __init__(self):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        
        self.start_pos = None
        self.end_pos = None
        self.dragging = False

        with mss() as sct:
            self.mon = sct.monitors[0]
        self.setGeometry(
            self.mon["left"],
            self.mon["top"],
            self.mon["width"],
            self.mon["height"]
        )

        self.mask_color = QColor(0, 0, 0, 100)
        self.border_pen = QPen(QColor(255, 0, 0), 2)

        self.setCursor(Qt.CrossCursor)

        self.slider = QSlider(Qt.Horizontal,self)

        self.slider.setPageStep(3)
        self.slider.setGeometry(50, 100, 1500, 80)
        self.slider.show()
        self.slider.setCursor(Qt.ArrowCursor)
        self.slider.valueChanged.connect(self.on_slider_changed)
        QApplication.instance().installEventFilter(self)

    def on_slider_changed(self, value):
         self.background = screenshot[value][0]
         self.update()

    def start(self):
        global lock_length
        with lock:  # make sure screenshot does not change while getting lock_length. this is extremely important
            lock_length = len(screenshot)
        self.slider.setRange(0, lock_length - 1)
        self.slider.setValue(lock_length - 1)  # test. need to use moving average
        show_and_exclude_from_capture(self)
        self.activateWindow()
        self.audio = None

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Wheel:
            # Only handle wheel events from this window or its children
            if isinstance(obj, QWidget) and obj.window() is self:
                delta = event.angleDelta().y()
                if delta > 0:
                    self.slider.setValue(self.slider.value() - self.slider.singleStep())
                elif delta < 0:
                    self.slider.setValue(self.slider.value() + self.slider.singleStep())
                return True  # Eat the wheel event
        if event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Up or event.key() == Qt.Key_PageUp:
                self.slider.setValue(self.slider.value() - self.slider.pageStep())
                return True
            elif event.key() == Qt.Key_Down or event.key() == Qt.Key_PageDown:
                self.slider.setValue(self.slider.value() + self.slider.pageStep())
                return True
            elif event.key() == Qt.Key_Home:
                self.slider.setValue(self.slider.minimum())
                return True
            elif event.key() == Qt.Key_End:
                self.slider.setValue(self.slider.maximum())
                return True
        return super().eventFilter(obj, event)

    def paintEvent(self, event):
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

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.start_pos = event.pos()
            self.end_pos = event.pos()
            self.dragging = True
            self.update()
        if event.button() == Qt.RightButton:
            if self.dragging:
                self.cancel_drag()
            else:
                self.close_snip()

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
            recorder.capture_last()  # test need move to thread
            self.close_snip()
            run_ocr_and_after(ocr, on_error, cropped, self.background, self.audio, rect.topLeft())
            # self.save_rect(rect) # test
            
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            if self.dragging:
                self.cancel_drag()
            else:
                self.close_snip()

    def cancel_drag(self):
        self.start_pos = None
        self.end_pos = None
        self.dragging = False
        self.update()
    
    def close_snip(self):
        global lock_length
        global hotkey_mode
        self.hide()
        self.start_pos = None
        self.end_pos = None
        self.dragging = False
        lock_length = 0
        hotkey_mode = 1

    def save_rect(self, rect): # test
        cropped = self.background.copy(rect)

        download_dir = Path.home() / "Downloads"
        download_dir.mkdir(parents=True, exist_ok=True)

        filename = f"snip_{time.strftime('%Y%m%d_%H%M%S')}.png"
        save_path = download_dir / filename

        cropped.save(str(save_path), "PNG")
        # print(f"Saved: {save_path}") #test
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
def run_ocr_and_after(ocr, on_error, qimg_cropped, qimg_full, audio, start_pos):
    global window
    global processing
    image  = qimg_cropped
    bits  = image.bits()
    bits.setsize(image.byteCount())

    mat = dll.cvMatFromRGB888(int(bits), image.width(), image.height(), image.bytesPerLine())
    if not mat:
        raise RuntimeError('cvMatFromRGB888 failed')

    ocr_result = []

    @DetectCallback
    def on_detect(x1, y1, x2, y2, x3, y3, x4, y4, text):
        ocr_result.append((text.decode('utf-8', 'ignore'), (x1, y1, x2, y2, x3, y3, x4, y4)))

    dll.OcrDetect(ocr, mat, 2, on_detect, on_error)
    dll.cvMatDestroy(mat)
    if ocr_result:
    # if ocr successful, go search dictionary
        word = ocr_result[0][0]
        word_info = {}
        search_dict_thread = threading.Thread(target=lambda: word_info.update(search_dict(word))) # test need to consider no result
        search_dict_thread.start()

        window_display_word_blank()
        window.word.setText(word)
        show_and_exclude_from_capture(window)
        if window.isMinimized():
            window.showNormal()
        window.raise_()
        window.repaint()
        QApplication.processEvents()
        
        points = [
            start_pos + QPoint(int(ocr_result[0][1][0]), int(ocr_result[0][1][1])),
            start_pos + QPoint(int(ocr_result[0][1][2]), int(ocr_result[0][1][3])),
            start_pos + QPoint(int(ocr_result[0][1][4]), int(ocr_result[0][1][5])),
            start_pos + QPoint(int(ocr_result[0][1][6]), int(ocr_result[0][1][7])),
        ]  # test need to adapt to partial screen shoot

        pixmap = QPixmap.fromImage(qimg_full)
        search_dict_thread.join()
        window_display_word(word_info['spell'], word_info['pron'], word_info['accent'], word_info['romaji'], word_info['excerpt'], word_info['fuzzy'],pixmap)

        # create new note in anki
        word_info['word'] = word
        word_info['word_position'] = '[' + str(points[0].x()) + ',' + str(points[0].y()) + '],[' + str(points[1].x()) + ',' + str(points[1].y()) + '],[' + str(points[2].x()) + ',' + str(points[2].y()) + '],[' + str(points[3].x()) + ',' + str(points[3].y()) + ']'
        processing = True
        audio_bytes = pcm_to_wav_bytes(audio)  #test
        threading.Thread(target=anki_new_note, args=(word_info,qimg_full,audio_bytes,), daemon = True).start()
    else:
        print('no ocr result')  # test need tool tip
        #QToolTip.showText(QCursor.pos(), "No OCR result", window, QRect(), 2000)
        #QTimer.singleShot(2000, QToolTip.hideText)
def window_display_word(spell, pron, accent, romaji, excerpt, fuzzy, pixmap):
    if pixmap:
        scaled_pixmap = pixmap.scaled(300, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation)  # test need better scale
        window.label_screenshot.setPixmap(scaled_pixmap)
    else:
        window.label_screenshot.clear()
    window.label_spell.setText(spell)
    pron = pron or ''
    accent = accent or ''
    if (pron + accent) and romaji:
        pipe = ' | '
    else:
        pipe = ''
    window.label_pron.setText(pron + accent + pipe + romaji)
    if excerpt and fuzzy: 
        lf = '\n\n'
    else:
        lf = ''
    window.label_excerpt.setText(excerpt + lf + fuzzy)
def window_display_word_blank():
    window_display_word('','','','','','','')
    window.anki_id = 0
def anki_new_note(fields,qimg_full,audio):
    screenshot_name = upload_image_to_anki(qimg_full, fields['word'] + str(time.time()) + '.png')
    fields['screenshot'] = f'<img src="{screenshot_name['result']}">'
    audio_name = upload_audio_to_anki(audio, fields['word'] + str(time.time()) + '.wav')
    fields['audio'] =  audio_name['result']
    result = invoke("addNote", note={
        "deckName": "test",
        "modelName": "testm",
        "fields": fields,
        "options": {"allowDuplicate": True}
    })
    if result['error']:
        print('anki create new error')
    else:
        bridge.anki_new_note_done.emit(str(result['result']),fields['word'])
def anki_new_note_after(anki_id,word):
    global processing
    anki_list.insert(0,(anki_id,word))
    window.anki_id = anki_id
    processing = False
def anki_delete_note():  # test need more detailed delete
    check_processing()
    invoke("deleteNotes", notes = [int(window.anki_id)])
    for i in range(len(anki_list)):
        if str(anki_list[i][0]) == str(window.anki_id):
            anki_list.remove(anki_list[i])
            break
    # display next card in list
    if anki_list:
        if i == len(anki_list):
            i -= 1
        anki_get_and_display(anki_list[i][0])
    else:
        window_display_word_blank()
def on_click_snip():
    global hotkey_mode
    hotkey_mode = 2
    bridge.click_snip.emit()
def search_dict(word):
    result = {
        "spell": "",
        "pron": "",
        "accent": "",
        "romaji": "",
        "excerpt": "",
        "fuzzy": ""
    }
    return search_moji(word,result)
def search_moji(word,result):
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
            fuzzy_result += response_json[i].get("title", "")
            fuzzy_result += "\n"
            fuzzy_result += response_json[i].get("excerpt", "")
            fuzzy_result += "\n\n"

        result["fuzzy"] = fuzzy_result
    except Exception as e:
        print("moji fuzzy fail")
    done_event_fuzzy.set()
def search_mojidict_exact(word,result,done_event_exact):
    
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
        result["spell"] = word_info.get("spell","")
        result["pron"] = word_info.get("pron","")
        result["accent"] = word_info.get("accent","")
        result["romaji"] = word_info.get("romaji","")
        result["excerpt"] = word_info.get("excerpt","")
    except Exception as e:
        print("moji exact fail")
    done_event_exact.set()
def set_qt_layout():
    # test also need warm up
    central = QWidget()
    window.setCentralWidget(central)

    layout = QVBoxLayout(central)
    layout.setContentsMargins(10, 0, 10, 0)
    layout.setSpacing(0)
    layout.setAlignment(Qt.AlignTop)

    window.word = QLineEdit(central)
    window.word.setFixedHeight(32)

    window.search_btn = QToolButton(window)
    window.search_btn.setText('📥')
    window.search_btn.setFont(QFont('Segoe UI Symbol', 16))
    window.search_btn.setFixedHeight(32)

    window.delete_btn = QToolButton(window)
    window.delete_btn.setText('🗑︎')
    window.delete_btn.setFont(QFont('Segoe UI Symbol', 16))
    window.delete_btn.setFixedHeight(32)
    window.delete_btn.clicked.connect(anki_delete_note)
    
    window.history_btn = QToolButton(window)
    window.history_btn.setText('🕘')
    window.history_btn.setFont(QFont('Segoe UI Symbol', 16))
    window.history_btn.setFixedHeight(32)
    window.history_menu = QMenu(window)
    window.history_menu.aboutToShow.connect(refresh_history_menu)
    window.history_btn.setMenu(window.history_menu)
    window.history_btn.setPopupMode(QToolButton.InstantPopup)

    row = QHBoxLayout()
    row.addWidget(window.word)
    row.addWidget(window.search_btn)
    row.addWidget(window.delete_btn)
    row.addWidget(window.history_btn)

    window.label_spell = QLabel("", central)
    window.label_spell.setAlignment(Qt.AlignHCenter)
    window.label_spell.setTextInteractionFlags(Qt.TextSelectableByMouse)
    window.label_spell.setStyleSheet("QLabel {selection-background-color: #3399ff;selection-color: white;}")
    font = QFont("Microsoft YaHei", 20)
    font.setBold(True)
    window.label_spell.setFont(font)

    window.label_pron = QLabel("", central)
    window.label_pron.setAlignment(Qt.AlignHCenter)
    window.label_pron.setTextInteractionFlags(Qt.TextSelectableByMouse)
    window.label_pron.setStyleSheet("QLabel {selection-background-color: #3399ff;selection-color: white;}")
    font = QFont("Microsoft YaHei", 10)
    font.setBold(False)
    window.label_pron.setFont(font)

    window.label_excerpt = QLabel("", central)
    window.label_excerpt.setAlignment(Qt.AlignLeft | Qt.AlignTop)
    window.label_excerpt.setTextInteractionFlags(Qt.TextSelectableByMouse)
    window.label_excerpt.setStyleSheet("QLabel {selection-background-color: #3399ff;selection-color: white;}")
    window.label_excerpt.setWordWrap(True)
    font = QFont("Microsoft YaHei", 10)
    font.setBold(False)
    window.label_excerpt.setFont(font)

    window.label_screenshot = QLabel("", central)

    layout.addLayout(row)
    layout.addWidget(window.label_spell)
    layout.addWidget(window.label_pron)
    layout.addWidget(window.label_excerpt)
    layout.addWidget(window.label_screenshot)
def refresh_history_menu():
    window.history_menu.clear()
    check_processing()
    if anki_list:
        for anki_id, word in anki_list:
            action = window.history_menu.addAction(word)
            action.triggered.connect(partial(anki_get_and_display, anki_id))
    else:
        window.history_menu.addAction(ui('blank'))
def anki_get_and_display(anki_id):
    result = invoke('notesInfo', notes=[int(anki_id)])
    fields = result['result'][0]['fields']
    pixmap = QPixmap()
    pixmap.loadFromData(download_image_from_anki(fields['screenshot']['value'].split('"')[1]))
    window_display_word(fields['spell']['value'], fields['pron']['value'], fields['accent']['value'], fields['romaji']['value'], fields['excerpt']['value'], fields['fuzzy']['value'],pixmap)
    window.word.setText(fields['word']['value'])
    window.anki_id = anki_id
def invoke(action, **params):
    # check if anki is open
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        if s.connect_ex((ANKI_HOST, ANKI_PORT)) != 0:  # test test test need more detail to process anki open
            anki_path = config['anki_path']
            if anki_path:
                open_anki(anki_path)
            msg = QMessageBox()
            msg.setWindowTitle(ui('messagebox_title'))
            msg.setText(ui('no_anki_connection'))
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec_()
    return requests.post(ANKI_URL, json={"action": action, "params": params, "version": 6}).json()
def check_processing():
    for i in range(100):
        if processing:
            time.sleep(0.05)
        else:
            break
    else:
        print('time out in waiting for processing')  # test need more detail
def upload_image_to_anki(qimg, filename):
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    qimg.save(buf, "PNG")
    b64 = base64.b64encode(buf.data().data()).decode("utf-8")
    return invoke("storeMediaFile", filename=filename, data=b64)   
def download_image_from_anki(filename):
    result = invoke("retrieveMediaFile", filename=filename)
    if result["result"] is False:
        return None
    b64 = result["result"]
    data = base64.b64decode(b64)
    return data
def upload_audio_to_anki(audio_bytes, filename):
    b64 = base64.b64encode(audio_bytes).decode("utf-8")
    return invoke("storeMediaFile", filename=filename, data=b64)
def pcm_to_wav_bytes(pcm_data, rate=44100, channels=2, bits=16):
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(bits // 8)
        wf.setframerate(rate)
        wf.writeframes(pcm_data)
    return buf.getvalue()

ui_index = get_ui_index()
ui_index = 1  # test, show Chinese ui
config_path, config = load_config()
app = QApplication(sys.argv)
anki_path = check_get_anki_path()
anki_thread = threading.Thread(target=open_anki, args=(anki_path,), daemon = True)
#anki_thread.start()  # test
check_dup()
processing = False  # global variable to check if some thread is in processing
session = None # moji session
dummy_uuid = str(uuid.uuid4())
hotkey_mode = 1  # 0 = config, 1 = main, 2 = in snip
keyboard_listener = keyboard.Listener(on_press=on_press)
keyboard_listener.start()
mouse_listener = mouse.Listener(on_click=on_click)
mouse_listener.start()
recorder = LoopbackRecorder()
last_moji_search_time = 0
moji_thread = threading.Thread(target=moji_session, daemon = True)  # test change to a thread to include warm up qt image: _dummy = QPixmap(1, 1).toImage().convertToFormat(QImage.Format_RGB888)
moji_thread.start()
max_fps = config['max_fps']
min_memory_gb = config['min_memory_gb']
max_memory_percentage = config['max_memory_percentage']
convert_max_fps()
screenshot = []
anki_list = []
ANKI_HOST = '127.0.0.1'
ANKI_PORT = 8765
ANKI_URL = f'http://{ANKI_HOST}:{ANKI_PORT}'
lock = threading.Lock()
user32 = ctypes.WinDLL("user32", use_last_error=True)
lock_length = 0
this_screenshot_time = int(time.time()) * 1000  # initial run at whole second to reduce rounding effect
threading.Thread(target=screenshot_thread,daemon=True).start()

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

window = QMainWindow()
bridge.anki_new_note_done.connect(anki_new_note_after)

show_and_exclude_from_capture(window)
set_qt_layout()
window.label_spell.setText(ui('messagebox_title'))  # test
sys.exit(app.exec_())