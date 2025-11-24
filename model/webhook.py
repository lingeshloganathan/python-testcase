import os
import time
import subprocess
from threading import Thread
from flask import Flask, request
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import re
import logging
import json

# ---------------------------
# CONFIG LOADING
# ---------------------------

try:
    import config_loader as cfg_loader
except Exception as e:
    logger_temp = logging.getLogger(__name__)
    logger_temp.warning("config_loader import failed: %s; using config.json", e)
    cfg_loader = None

config = {}
log_file = None

if cfg_loader:
    try:
        config = cfg_loader.load_config()
        log_file = config.get('log_file')
        cfg_loader.setup_logging(log_file)
    except Exception as e:
        logging.basicConfig(level=logging.INFO)
        logging.getLogger(__name__).warning("config_loader setup failed: %s", e)
else:
    try:
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.json')
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = json.load(f)
            log_file = config.get('log_file')
    except Exception as e:
        logging.basicConfig(level=logging.INFO)
        logging.getLogger(__name__).warning("Direct config.json load failed: %s", e)
    
    if log_file:
        try:
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                handlers=[logging.FileHandler(log_file), logging.StreamHandler()]
            )
        except Exception:
            logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)
logger.info("Config loaded. Log file: %s", log_file)

# ---------------------------
# CONFIG VARIABLES
# ---------------------------

VENV_PYTHON = config.get('venv') or 'python'
MODEL_TRAINING_PATH = config.get('model_training_path')
priority_prediction_path = config.get('priority_prediction_path')
GIT_DIFF_PATH = config.get('git_diff_path')
pipeline_script = config.get('pipeline_script')
report_path = config.get('report_path')
EXCEL_SCRIPT = os.path.normpath(config.get('todo_path'))

logger.info("Webhook configuration:")
logger.info("  VENV_PYTHON: %s", VENV_PYTHON)
logger.info("  GIT_DIFF_PATH: %s", GIT_DIFF_PATH)
logger.info("  MODEL_TRAINING_PATH: %s", MODEL_TRAINING_PATH)
logger.info("  EXCEL_SCRIPT: %s", EXCEL_SCRIPT)

app = Flask(__name__)

# ---------------------------
# TRAINING FUNCTION
# ---------------------------

def run_training():
    """Run training ONLY when Excel file changes."""
    logger.info("=== Running model training (Excel trigger) ===")

    try:
        subprocess.run([VENV_PYTHON, pipeline_script], check=True)
        subprocess.run([VENV_PYTHON, report_path], check=True)
        subprocess.run([VENV_PYTHON, MODEL_TRAINING_PATH], check=True)
    except subprocess.CalledProcessError as e:
        logger.exception("Training error: %s", e)

    logger.info("=== Training Completed ===")


# ---------------------------
# PREDICTION FUNCTION
# ---------------------------

def run_prediction():
    """Run prediction when GitHub webhook triggers."""
    logger.info("=== Running Prediction (GitHub Trigger) ===")

    try:
        subprocess.run([VENV_PYTHON, pipeline_script], check=True)
        subprocess.run([VENV_PYTHON, report_path], check=True)
        # Pass git_diff output CSV to priority_prediction so it gets real commit data
        git_diff_output = config.get('output_file')
        print("Git diff output file for prediction:", git_diff_output)
        subprocess.run([VENV_PYTHON, priority_prediction_path, '--git_diff_file', git_diff_output], check=True)
    except subprocess.CalledProcessError as e:
        logger.exception("Prediction error: %s", e)

    logger.info("=== Prediction Completed ===")


# ---------------------------
# ROUTES
# ---------------------------

@app.route('/')
def index():
    return "Webhook server is running.", 200


@app.route('/webhook', methods=['POST'])
def webhook():
    logger.info("=== Webhook Received ===")

    try:
        payload = request.get_json(force=True)
        logger.info("Payload: %s", payload)

        # Extract user_story_id from payload
        user_story_id = None
        
        if isinstance(payload, dict):
            user_story_id = payload.get("user_story_id") or payload.get("userStoryId")
            
            if not user_story_id:
                for c in payload.get("commits", []):
                    msg = c.get("message", "")
                    m = re.search(r"\b(US-\d+)\b", msg, flags=re.IGNORECASE)
                    if m:
                        user_story_id = m.group(1).upper()
                        break

        if not user_story_id:
            err = "No user_story_id found in payload."
            logger.warning(err)
            return err, 400

        logger.info("Found user_story_id: %s", user_story_id)

        # Run git diff ONCE
        if GIT_DIFF_PATH:
            try:
                logger.info("Running git diff...")
                subprocess.run([VENV_PYTHON, GIT_DIFF_PATH, "--user_story_id", user_story_id, "--last_only"], check=True)
            except subprocess.CalledProcessError as e:
                logger.exception("git_diff error: %s", e)

        # Run prediction ONLY (NO TRAINING HERE)
        run_prediction()

        return "Webhook processed", 200

    except Exception as e:
        logger.exception("Webhook error: %s", e)
        return str(e), 500


# ---------------------------
# EXCEL WATCHDOG
# ---------------------------

class ExcelWatchHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if not event.is_directory:
            changed_file = os.path.normpath(event.src_path)
            if changed_file == EXCEL_SCRIPT:
                logger.info("Excel file updated: %s", changed_file)
                run_training()


def start_excel_watchdog():
    if not EXCEL_SCRIPT:
        logger.info("EXCEL_SCRIPT not configured; skipping Excel watchdog.")
        return

    observer = Observer()
    handler = ExcelWatchHandler()
    watch_path = os.path.dirname(EXCEL_SCRIPT)

    observer.schedule(handler, watch_path, recursive=False)
    observer.start()
    logger.info("Watching Excel file for changes...")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()

    observer.join()


# ---------------------------
# MAIN APP START
# ---------------------------

if __name__ == '__main__':
    Thread(target=start_excel_watchdog, daemon=True).start()
    app.run(host='0.0.0.0', port=5000)
