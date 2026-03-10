import os
import threading
paddle_model = None # global
# thread_model = threading.Thread(target=create_paddle_model)
# thread_model.start() #test

from PyQt5.QtWidgets import QApplication, QMessageBox,  QFileDialog
from PyQt5.QtCore import Qt
import sys
import json
import subprocess
import time

UI_TEXT = {
    'no_anki_in_config': ('Download Anki from <a href="https://apps.ankiweb.net">apps.ankiweb.net</a><br>Then select anki.exe','登录<a href="https://apps.ankiweb.net">apps.ankiweb.net</a>下载Anki<br>然后选择anki.exe'),
    'select_anki': ('Select anki.exe', '选择 anki.exe'),
}
def create_paddle_model():
    global paddle_model
    os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK'] = 'True'
    from paddlex import create_model
    paddle_model = create_model(model_name='PP-OCRv5_mobile_rec')

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
        lang = locale.getdefaultlocale()[0]
        if 'zh' in lang.lower():
            return 1
    except:
        pass
    return 0

def update_config(key, value):
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump({key: value}, f, indent=4)

def ui(key):
    return UI_TEXT[key][ui_index]

def open_anki():
    # check if anki_path is in config
    if config['anki_path'] == '':
        msg = QMessageBox()
        msg.setWindowTitle("ACard")
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

            file_path, _ = QFileDialog.getOpenFileName(
                None,
                ui('select_anki'),
                default_dir,
                ''
                '*.exe;;*.lnk'
            )
            if not file_path:
                return
            else:
                update_config('anki_path', file_path)
        if result == QMessageBox.Cancel:
            return
    else:
        file_path = config['anki_path']
    # open anki
    proc = subprocess.Popen([file_path])
    # test need to (1) check if anki is opened (2) install anki connect automatically (3)) hide anki





ui_index = get_ui_index()
ui_index = 1  # test, show Chinese ui
config_path, config = load_config()
app = QApplication(sys.argv)
open_anki()
# test