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
logger.info("Loaded %d rows from %s (including ALL rows, even with empty last_status)", len(data), CSV_PATH)

# Fill missing values
data['total_no_of_Passed'] = pd.to_numeric(data['total_no_of_Passed'], errors='coerce').fillna(0)
data['total_no_of_Failed'] = pd.to_numeric(data['total_no_of_Failed'], errors='coerce').fillna(0)
data['last_status'] = data['last_status'].fillna('unknown')
# ensure language column exists (added by git_diff)
if 'language' not in data.columns:
    data['language'] = 'unknown'
else:
    data['language'] = data['language'].fillna('unknown')

# Create encoders for categorical columns
encoders = {}
for col in ['file_changed', 'changed_function', 'dependent_function', 'test_case_id', 'user_story_id', 'last_status', 'language']:
    le = LabelEncoder()
    data[col] = le.fit_transform(data[col].astype(str))
    encoders[col] = le

state_cols = ['user_story_id', 'file_changed', 'changed_function', 'dependent_function', 'language']
action_col = 'test_case_id'

# Reward: prioritize tests with failures (high failure rate gets high reward)
def compute_reward(row):
    passed = row['total_no_of_Passed'] if not pd.isna(row['total_no_of_Passed']) else 0
    failed = row['total_no_of_Failed'] if not pd.isna(row['total_no_of_Failed']) else 0
    
    # Higher reward for failures and tests with high failure rate
    if failed > 0:
        failure_rate = failed / (passed + failed) if (passed + failed) > 0 else 0
        return 1.0 + (failure_rate * 0.5)  # 1.0 to 1.5 based on failure rate
    elif passed > 0:
        return 0.2  # Low reward for passing tests
    else:
        return 0.1  # Very low reward for untested cases

reward_col = data.apply(compute_reward, axis=1)
logger.info("Reward distribution: min=%.2f, max=%.2f, mean=%.2f", reward_col.min(), reward_col.max(), reward_col.mean())

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

model.save(MODEL_PATH)
logger.info("\n✅ PPO model saved to %s", MODEL_PATH)

# ===============================
# Save encoders for later use in priority_prediction
# ===============================
import pickle
encoder_path = MODEL_PATH + "_encoders.pkl"
with open(encoder_path, 'wb') as f:
    pickle.dump(encoders, f)
logger.info("✅ Encoders saved to %s", encoder_path)

# ===============================
# Sample predictions on training data
# ===============================
logger.info("\n🎯 Sample predictions on training data:")
for idx in range(min(5, len(data))):
    row = data.iloc[idx]
    state = row[state_cols].values.astype(np.float32) / len(data)
    action, _ = model.predict(state, deterministic=True)
    test_id = encoders['test_case_id'].inverse_transform([int(action)])[0]
    reward = reward_col.iloc[idx]
    file_name = encoders['file_changed'].inverse_transform([int(row['file_changed'])])[0]
    logger.info("  Sample %d: File=%s | Predicted Test=%s | Reward=%.2f", idx, file_name, test_id, reward)