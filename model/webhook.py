import os
import time
import subprocess
from threading import Thread
from flask import Flask, request
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import re
import logging

# load config_loader from project root
try:
    import config_loader as cfg_loader
except Exception:
    cfg_loader = None


# initialize config and logging
try:
    config = cfg_loader.load_config() if cfg_loader else {}
except Exception:
    config = {}

log_file = config.get('log_file') if config else None
if cfg_loader:
    try:
        cfg_loader.setup_logging(log_file)
    except Exception:
        pass
else:
    # minimal logging fallback
    logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)



VENV_PYTHON = config.get('venv') or r"D:\project-testcase\backend\venv\Scripts\python.exe"
EXCEL_FILE = config.get('excel_file') or r"D:\project-testcase\Todo_UserStories_TestCases.xlsx"
MODEL_TRAINING_PATH = config.get('model_training_path') or r"backend/model_train.py"
priority_prediction_path = config.get('priority_prediction_path') or r"backend/priority_prediction.py"
# Path to the git_diff script (adjust if your workspace path differs)
GIT_DIFF_PATH = config.get('git_diff_path') or r"D:\data-learn\automated data\git_diff.py"
# DEPLOY_SCRIPT = r"C:\path\to\project\deploy.py"
# EXCEL_SCRIPT = r"C:\path\to\project\process_excel.py"


app = Flask(__name__)



@app.route('/')
def index():
    return "Webhook server is running.", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    logger.info("=== Webhook Received ===")

    try:
        payload = request.get_json()
        logger.info("Payload: %s", payload)

        # Try to extract user_story_id from payload. Accept explicit field or parse from commit messages.
        user_story_id = None
        if isinstance(payload, dict):
            # direct field
            user_story_id = payload.get("user_story_id") or payload.get("userStoryId")

            # If not provided, inspect git push-like payload for commits
            if not user_story_id:
                commits = payload.get("commits") or []
                for c in commits:
                    msg = c.get("message", "")
                    m = re.search(r"\b(US-\d+)\b", msg, flags=re.IGNORECASE)
                    if m:
                        user_story_id = m.group(1).upper()
                        break

        if not user_story_id:
            msg = "No user_story_id found in payload (expected 'user_story_id' or commit messages containing 'US-<number>')."
            logger.warning(msg)
            return msg, 400

        logger.info("Found user_story_id: %s", user_story_id)

        # Run git-diff report for this user story (most recent match only)
        try:
            logger.info("Running git_diff to find commits for user story...")
            subprocess.run([VENV_PYTHON, GIT_DIFF_PATH, "--user_story_id", user_story_id, "--last_only"], check=True)
        except subprocess.CalledProcessError as e:
            logger.exception("Error running git_diff: %s", e)

        # Optionally run model training after processing the git diff
        try:
            logger.info("Running deploy/train script inside venv...")
            subprocess.run([VENV_PYTHON, MODEL_TRAINING_PATH], check=True)
        except subprocess.CalledProcessError as e:
            logger.exception("Error running model training: %s", e)

        return "Webhook processed", 200
    except Exception as e:
        print("Error:", e)
        return str(e), 500


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

if __name__ == '__main__':
    Thread(target=start_excel_watchdog, daemon=True).start()

    app.run(host='0.0.0.0', port=5000)