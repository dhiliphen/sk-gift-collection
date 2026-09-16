import sys
import os
import threading
import time
import webbrowser

# Resolve base directory — sys._MEIPASS when bundled, project root otherwise
if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS
    DB_DIR = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'SKGiftCollection')
    os.makedirs(DB_DIR, exist_ok=True)
    DB_PATH = os.path.join(DB_DIR, 'inventory.db')
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DB_PATH = os.path.join(BASE_DIR, 'inventory.db')

os.environ['BASE_DIR'] = BASE_DIR
os.environ['DB_PATH'] = DB_PATH

import uvicorn

def open_browser():
    time.sleep(2)
    webbrowser.open('http://127.0.0.1:8000')

threading.Thread(target=open_browser, daemon=True).start()

uvicorn.run('main:app', host='127.0.0.1', port=8000)
