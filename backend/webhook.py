import os
import time
import subprocess
from threading import Thread
from flask import Flask, request
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


# -------------------------------
# CONFIG
# -------------------------------
VENV_PYTHON = r"D:\project-testcase\backend\venv\Scripts\python.exe"  
# Example: r"C:\Users\Nithish\project\venv\Scripts\python.exe"

EXCEL_FILE = r"D:\project-testcase\Todo_UserStories_TestCases.xlsx"
MODEL_TRAINING_PATH = r"backend/model_train.py"
priority_prediction_path = r"backend/priority_prediction.py"
# DEPLOY_SCRIPT = r"C:\path\to\project\deploy.py"
# EXCEL_SCRIPT = r"C:\path\to\project\process_excel.py"


app = Flask(__name__)


# -------------------------------
# FLASK WEBHOOK (runs python file)
# -------------------------------
@app.route('/')
def index():
    return "Webhook server is running.", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    print("\n=== Webhook Received ===")

    try:
        payload = request.get_json()
        print("Payload:", payload)

        print("Running deploy script inside venv...")
        subprocess.run([VENV_PYTHON, MODEL_TRAINING_PATH], check=True)

        return "Webhook processed", 200
    except Exception as e:
        print("Error:", e)
        return str(e), 500


# -------------------------------
# WATCHDOG (monitors Excel file)
# -------------------------------
class ExcelWatchHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path.endswith(".xlsx"):
            print("\n=== Excel File Updated ===")
            print("Running excel processing script...")

            subprocess.run([VENV_PYTHON, EXCEL_FILE], check=True)


def start_excel_watchdog():
    observer = Observer()
    event_handler = ExcelWatchHandler()
    watch_path = os.path.dirname(EXCEL_FILE)

    observer.schedule(event_handler, watch_path, recursive=False)
    observer.start()
    print("Watching Excel file for changes...")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


# -------------------------------
# MAIN ENTRY
# -------------------------------
if __name__ == '__main__':
    # Start watchdog in background thread
    Thread(target=start_excel_watchdog, daemon=True).start()

    # Start Flask server
    app.run(host='0.0.0.0', port=5000)