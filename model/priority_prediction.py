import logging
import pandas as pd
import numpy as np
from sklearn.preprocessing import LabelEncoder
from stable_baselines3 import PPO
import torch
import warnings
from datetime import datetime

# load central config and logging
try:
    import config_loader as cfg
    cfg.setup_logging()
    _conf = cfg.load_config()
except Exception:
    _conf = {}

logger = logging.getLogger(__name__)

CSV_PATH = _conf.get('output_path') or "final_userstory_commit_test_report_poc.csv"
MODEL_PATH = _conf.get('ppo_model_path') or "ppo_test_selection_model"

data = pd.read_csv(CSV_PATH)

# ensure relevant columns are strings so fillna('missing') won't warn
cols_to_force_str = ['file_changed', 'changed_function', 'dependent_function', 'test_case_id', 'last_status']
for c in cols_to_force_str:
    if c in data.columns:
        data[c] = data[c].astype(object).astype(str)  # force string dtype

data.replace({None: "missing", "nan": "missing", "NaN": "missing"}, inplace=True)
data.fillna("missing", inplace=True)

encoders = {}
for col in cols_to_force_str:
    if col in data.columns:
        le = LabelEncoder()
        data[col] = le.fit_transform(data[col].astype(str))
        encoders[col] = le

logger.info("📂 Loading trained PPO model...")
model = PPO.load(MODEL_PATH)
policy = model.policy
logger.info("✅ Model loaded successfully!")

try:
    n_actions = model.action_space.n
except Exception:
    n_actions = getattr(model, "env", None)
    if hasattr(n_actions, "action_space"):
        n_actions = model.env.action_space.n
    else:
        n_actions = policy.action_net.out_features if hasattr(policy, "action_net") else None

if n_actions is None:
    raise RuntimeError("Could not determine number of actions in the trained model.")

encoder_classes = encoders['test_case_id'].classes_ if 'test_case_id' in encoders else np.array([])

if len(encoder_classes) != n_actions:
    warnings.warn(
        f"Encoder classes ({len(encoder_classes)}) != model actions ({n_actions}).\n"
        "This means the encoder you rebuilt at prediction time differs from what the model saw during training.\n"
        "Prediction will proceed, but indices outside encoder range will be labelled 'UNKNOWN_<index>'.\n"
        "Recommended: save the label encoders at training time and load them here."
    )

latest = data.iloc[-1]
decoded_file_changed = encoders['file_changed'].inverse_transform([latest['file_changed']])[0] \
    if 'file_changed' in encoders else str(latest['file_changed'])
decoded_changed_function = encoders['changed_function'].inverse_transform([latest['changed_function']])[0] \
    if 'changed_function' in encoders else str(latest['changed_function'])
decoded_dependent_function = encoders['dependent_function'].inverse_transform([latest['dependent_function']])[0] \
    if 'dependent_function' in encoders else str(latest['dependent_function'])

logger.info("\n📊 Prioritizing tests for latest commit:")
logger.info("   File Changed       : %s", decoded_file_changed)
logger.info("   Changed Function   : %s", decoded_changed_function)
logger.info("   Dependent Function : %s", decoded_dependent_function)

state = np.array([
    latest['file_changed'],
    latest['changed_function'],
    latest['dependent_function']
]) / len(data)

state_tensor = torch.tensor(state, dtype=torch.float32).unsqueeze(0)

with torch.no_grad():
    dist = policy.get_distribution(state_tensor).distribution
    if hasattr(dist, "logits"):
        logits = dist.logits
        probs = torch.softmax(logits, dim=1).cpu().numpy().flatten()
    elif hasattr(dist, "probs"):
        probs = dist.probs.cpu().numpy().flatten()
    else:
        action, _ = model.predict(state, deterministic=False)
        probs = np.zeros(n_actions, dtype=float)
        probs[int(action)] = 1.0

if len(probs) != n_actions:
    if len(probs) < n_actions:
        pad = np.zeros(n_actions - len(probs), dtype=float)
        probs = np.concatenate([probs, pad])
    else:
        probs = probs[:n_actions]

if probs.sum() <= 0:
    probs = np.ones_like(probs) / len(probs)
else:
    probs = probs / probs.sum()


mapped_labels = []
for idx in range(n_actions):
    if idx < len(encoder_classes):
        mapped_labels.append(encoder_classes[idx])
    else:
        mapped_labels.append(f"UNKNOWN_{idx}")

ranking = sorted(zip(mapped_labels, probs), key=lambda x: x[1], reverse=True)


def get_reason(tc_label, file_name, func_name):
    t = str(tc_label).lower()
    if file_name.lower() in t:
        return "Same file reference"
    if func_name.lower() in t:
        return "Matches function name"
    if "missing" in (file_name.lower(), func_name.lower()):
        return "Missing metadata — fallback prediction"
    return "Model-based priority (probability score)"

logger.info("\n🧩 Ranked Test Case Priorities (top 15):")
for rank, (tc, prob) in enumerate(ranking[:15], start=1):
    reason = get_reason(tc, decoded_file_changed, decoded_changed_function)
    logger.info("%02d. %s | Score: %.4f | Reason: %s", rank, tc, prob, reason)

out_df = pd.DataFrame(ranking, columns=["Test_Case", "Priority_Score"])
out_df["Reason"] = out_df["Test_Case"].apply(lambda x: get_reason(x, decoded_file_changed, decoded_changed_function))
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
out_df.to_csv(_conf.get('priority_output_path') or f"test_case_priorities_safe_{timestamp}.csv", index=False)
logger.info("\n💾 Saved '%s'", _conf.get('priority_output_path') or f"test_case_priorities_safe_{timestamp}.csv")