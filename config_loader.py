import json
import logging
import os
from typing import Any, Dict


def _default_config_path() -> str:
    # config.json lives in the project root (d:\data-learn\config.json)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')


def load_config(path: str = None) -> Dict[str, Any]:
    """Load JSON config and return a dict."""
    cfg_path = path or _default_config_path()
    if not os.path.exists(cfg_path):
        raise FileNotFoundError(f"Config file not found: {cfg_path}")
    with open(cfg_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def setup_logging(log_file: str = None, level: int = logging.INFO) -> None:
    """Configure root logger to write to the given log_file (appends)."""
    cfg = None
    try:
        cfg = load_config()
    except Exception:
        pass

    log_path = log_file or (cfg.get('log_file') if cfg else None)
    if not log_path:
        # fallback to local temp
        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'automation.log')

    os.makedirs(os.path.dirname(log_path), exist_ok=True)

    handler = logging.FileHandler(log_path, encoding='utf-8')
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s - %(message)s')
    handler.setFormatter(formatter)

    root = logging.getLogger()
    # if handlers already configured, don't double-add
    if not any(isinstance(h, logging.FileHandler) and getattr(h, 'baseFilename', None) == os.path.abspath(log_path) for h in root.handlers):
        root.addHandler(handler)

    root.setLevel(level)


if __name__ == '__main__':
    # quick test
    cfg = load_config()
    print('Loaded config keys:', list(cfg.keys()))
