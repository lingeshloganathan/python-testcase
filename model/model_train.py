import logging
import os
import json
import sys
import pandas as pd
import numpy as np
from sklearn.preprocessing import LabelEncoder
import gymnasium as gym
from gymnasium import spaces
from stable_baselines3 import PPO
from pathlib import Path

# Add project root to path so config_loader can be found
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# load config and logging
_conf = {}
try:
    import config_loader as cfg
    cfg.setup_logging()
    _conf = cfg.load_config()
    logging.info("✅ Config loaded via config_loader")
except Exception as e:
    logging.warning("⚠️ config_loader import failed: %s; trying direct load", e)
    # Fallback: load config.json directly
    try:
        config_path = os.path.join(project_root, 'config.json')
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                _conf = json.load(f)
            logging.basicConfig(level=logging.INFO)
            logging.info("✅ Config loaded from %s", config_path)
    except Exception as e2:
        logging.basicConfig(level=logging.INFO)
        logging.warning("⚠️ Direct config load failed: %s", e2)

logger = logging.getLogger(__name__)

# Fallback paths if config is empty
CSV_PATH = _conf.get('output_path')
MODEL_PATH = _conf.get('ppo_model_path')

logger.info("CSV_PATH: %s", CSV_PATH)
logger.info("MODEL_PATH: %s", MODEL_PATH)

# Check if CSV exists
if not os.path.exists(CSV_PATH):
    logger.error("❌ Training CSV not found at: %s", CSV_PATH)
    logger.error("❌ Cannot train model without data. Please run report.py first to generate the training data.")
    logger.info("ℹ️ Expected paths:")
    logger.info("  - Main report: %s", CSV_PATH)
    logger.info("  - Full report: %s", CSV_PATH.replace(".csv", "_full.csv"))
    exit(1)

data = pd.read_csv(CSV_PATH)
logger.info("Loaded %d rows from %s", len(data), CSV_PATH)

encoders = {}
for col in ['file_changed', 'changed_function', 'dependent_function', 'test_case_id', 'last_status']:
    le = LabelEncoder()
    data[col] = le.fit_transform(data[col].astype(str))
    encoders[col] = le

state_cols = ['file_changed', 'changed_function', 'dependent_function']
action_col = 'test_case_id'
reward_col = data['last_status'].apply(
    lambda x: 1 if len(encoders.get('last_status', []).classes_) and x == encoders['last_status'].transform(['fail'])[0] else -0.1
)

class TestSelectionEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(self, data, state_cols, action_col, reward_col):
        super().__init__()
        self.data = data.reset_index(drop=True)
        self.state_cols = state_cols
        self.action_col = action_col
        self.reward_col = reward_col.values

        # Define action and observation spaces
        self.action_space = spaces.Discrete(len(self.data[action_col].unique()))
        self.observation_space = spaces.Box(
            low=0.0,
            high=1.0,
            shape=(len(state_cols),),
            dtype=np.float32,
        )

        self.current_index = 0

    def reset(self, seed=None, options=None):
        """Start a new episode"""
        super().reset(seed=seed)
        self.current_index = np.random.randint(0, len(self.data))
        state = self.data.loc[self.current_index, self.state_cols].values / len(self.data)
        info = {}
        return state.astype(np.float32), info

    def step(self, action):
        """Perform one action"""
        row = self.data.loc[self.current_index]
        reward = self.reward_col[self.current_index]

        terminated = True   # Episode ends naturally
        truncated = False   # Not truncated by time limit
        info = {}

        self.current_index = np.random.randint(0, len(self.data))
        next_state = self.data.loc[self.current_index, self.state_cols].values / len(self.data)

        return next_state.astype(np.float32), float(reward), terminated, truncated, info

env = TestSelectionEnv(data, state_cols, action_col, reward_col)

model = PPO("MlpPolicy", env, verbose=1, tensorboard_log="./ppo_logs")
logger.info("\n🚀 Training PPO model... please wait...")
model.learn(total_timesteps=int(_conf.get('ppo_train_steps', 10000)))
logger.info("✅ Training complete!")

def suggest_test(model, file_changed, changed_function, dependent_function):
    """Predict best test case for a given commit"""
    state = np.array([file_changed, changed_function, dependent_function]) / len(data)
    action, _ = model.predict(state, deterministic=True)
    test_case = encoders['test_case_id'].inverse_transform([action])[0]
    return test_case

logger.info("\n🎯 Example prediction:")
example = data.iloc[0]
suggested = suggest_test(
    model,
    example['file_changed'],
    example['changed_function'],
    example['dependent_function']
)
logger.info("Suggested Test Case: %s", suggested)

model.save("ppo_test_selection_model")
logger.info("\n💾 PPO model saved as '%s'", MODEL_PATH)