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

try:
    import config_loader as cfg_loader
except Exception as e:
    logger_temp = logging.getLogger(__name__)
    logger_temp.warning("config_loader import failed: %s; will load config.json directly", e)
    cfg_loader = None


config = {}
log_file = None

if cfg_loader:
    try:
        config = cfg_loader.load_config() if cfg_loader else {}
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
    
    if log_file and not cfg_loader:
        try:
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                handlers=[
                    logging.FileHandler(log_file),
                    logging.StreamHandler()
                ]
            )
        except Exception:
            logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)
logger.info("Config loaded. Log file: %s", log_file)



VENV_PYTHON = config.get('venv')
MODEL_TRAINING_PATH = config.get('model_training_path') 
priority_prediction_path = config.get('priority_prediction_path') 
GIT_DIFF_PATH = config.get('git_diff_path')
DEPLOY_SCRIPT = config.get('priority_prediction_path')
report_path = config.get('report_path')
pipeline_script = config.get('pipeline_script')
EXCEL_SCRIPT = config.get('excel_file')
EXCEL_SCRIPT = os.path.normpath(EXCEL_SCRIPT)


if not VENV_PYTHON:
    VENV_PYTHON = 'python'
    logger.warning("VENV_PYTHON not configured in config.json; falling back to system 'python'")

if not GIT_DIFF_PATH:
    logger.warning("GIT_DIFF_PATH not configured in config.json")

logger.info("Webhook configuration:")
logger.info("  VENV_PYTHON: %s", VENV_PYTHON)
logger.info("  GIT_DIFF_PATH: %s", GIT_DIFF_PATH)
logger.info("  MODEL_TRAINING_PATH: %s", MODEL_TRAINING_PATH)
logger.info("  EXCEL_SCRIPT: %s", EXCEL_SCRIPT)


app = Flask(__name__)



@app.route('/')
def index():
    return "Webhook server is running.", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    logger.info("=== Webhook Received ===")

    try:
        payload = request.get_json(force=True)
        logger.info("Payload: %s", payload)
        
        if isinstance(payload, dict):
            action = payload.get("action")
            if action:
                logger.info("GitHub event action: %s", action)
            
            repo = payload.get("repository")
            if repo:
                repo_name = repo.get("full_name", "unknown")
                logger.info("Repository: %s", repo_name)
            
            commits = payload.get("commits")
            if commits:
                logger.info("Number of commits: %d", len(commits))
                for idx, commit in enumerate(commits):
                    commit_msg = commit.get("message", "")
                    commit_sha = commit.get("id", "")
                    logger.info("  Commit %d: %s - %s", idx, commit_sha[:7], commit_msg[:100])

        user_story_id = None
        if isinstance(payload, dict):
            user_story_id = payload.get("user_story_id") or payload.get("userStoryId")

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
        if not GIT_DIFF_PATH:
            logger.error("GIT_DIFF_PATH not configured; cannot run git_diff")
            return "GIT_DIFF_PATH not configured in config.json", 500
        
        try:
            logger.info("Running git_diff to find commits for user story...")
            logger.info("Using VENV_PYTHON: %s", VENV_PYTHON)
            logger.info("Using GIT_DIFF_PATH: %s", GIT_DIFF_PATH)
            subprocess.run([VENV_PYTHON, GIT_DIFF_PATH, "--user_story_id", user_story_id, "--last_only"], check=True)
        except subprocess.CalledProcessError as e:
            logger.exception("Error running git_diff: %s", e)

        # Optionally run model training after processing the git diff
        try:
            logger.info("Running deploy/train script inside venv...")
            subprocess.run([VENV_PYTHON, pipeline_script], check=True)
            subprocess.run([VENV_PYTHON, report_path], check=True)
            subprocess.run([VENV_PYTHON, priority_prediction_path], check=True)
            
            # subprocess.run([VENV_PYTHON, MODEL_TRAINING_PATH], check=True)
            # subprocess.run([VENV_PYTHON, priority_prediction_path], check=True)

        except subprocess.CalledProcessError as e:
            logger.exception("Error running model training: %s", e)

        # Run priority prediction after training
        if priority_prediction_path:
            try:
                logger.info("Running priority prediction script inside venv...")
                subprocess.run([VENV_PYTHON, priority_prediction_path], check=True)
            except subprocess.CalledProcessError as e:
                logger.exception("Error running priority prediction: %s", e)
        else:
            logger.warning("priority_prediction_path not configured; skipping priority prediction")

        return "Webhook processed", 200
    except Exception as e:
        print("Error:", e)
        return str(e), 500


class ExcelWatchHandler(FileSystemEventHandler):
   def on_any_event(self, event):
        if event.is_directory:
            return
        changed_file = os.path.normpath(event.src_path)
        if changed_file == EXCEL_SCRIPT:
            print("\n=== Excel File Updated ===")
            print("Running pipeline, report and training...")
            subprocess.run([VENV_PYTHON, pipeline_script], check=True)
            subprocess.run([VENV_PYTHON, report_path], check=True)
            subprocess.run([VENV_PYTHON, MODEL_TRAINING_PATH], check=True)
            # subprocess.run([VENV_PYTHON, EXCEL_SCRIPT], check=True)
            print("=== Excel Processing Complete ===\n")


def start_excel_watchdog():
    if not EXCEL_SCRIPT:
        logger.info("EXCEL_SCRIPT not configured; skipping Excel watchdog.")
        return

    observer = Observer()
    event_handler = ExcelWatchHandler()
    watch_path = os.path.dirname(EXCEL_SCRIPT)

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