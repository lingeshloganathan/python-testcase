import logging
import pandas as pd
import numpy as np
from sklearn.preprocessing import LabelEncoder
from stable_baselines3 import PPO
import torch
import warnings
from datetime import datetime
import argparse
import pickle
import sys
import os

# Add parent directory to path for config_loader import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
ENCODER_PATH = MODEL_PATH + "_encoders.pkl"
TODO_PATH = _conf.get('todo_path') or "D:\\data-learn\\data\\Todo_UserStories_TestCases.xlsx"

# ===============================
# Load todo/Excel mapping (User Story -> Test Cases)
# ===============================
todo_mapping = {}
if os.path.exists(TODO_PATH):
    logger.info("📂 Loading todo mapping from %s...", TODO_PATH)
    try:
        todo_df = pd.read_excel(TODO_PATH)
        # Normalize column names
        todo_df.columns = todo_df.columns.str.strip().str.lower().str.replace(" ", "")
        
        # Find user_story_id and test_case_id columns
        us_col = next((c for c in todo_df.columns if 'userstory' in c or 'user_story' in c), None)
        tc_col = next((c for c in todo_df.columns if 'testcase' in c or 'test_case' in c), None)
        
        if us_col and tc_col:
            for _, row in todo_df.iterrows():
                us_id = str(row[us_col]).strip()
                tc_id = str(row[tc_col]).strip()
                if us_id and tc_id and us_id.lower() != 'nan':
                    if us_id not in todo_mapping:
                        todo_mapping[us_id] = []
                    if tc_id not in todo_mapping[us_id]:
                        todo_mapping[us_id].append(tc_id)
            logger.info("✅ Loaded todo mapping: %d user stories mapped", len(todo_mapping))
        else:
            logger.warning("⚠️  Could not find user_story or test_case columns in Excel")
    except Exception as e:
        logger.warning("⚠️  Could not load todo mapping: %s", e)
else:
    logger.warning("⚠️  Todo file not found: %s", TODO_PATH)

# ===============================
# Load saved encoders from training
# ===============================
logger.info("📂 Loading encoders from %s...", ENCODER_PATH)
try:
    with open(ENCODER_PATH, 'rb') as f:
        encoders = pickle.load(f)
    logger.info("✅ Encoders loaded successfully!")
except FileNotFoundError:
    logger.warning("⚠️  Encoders file not found. Rebuilding from training data...")
    data = pd.read_csv(CSV_PATH)
    cols_to_force_str = ['file_changed', 'changed_function', 'dependent_function', 'test_case_id', 'user_story_id', 'last_status', 'language']
    for c in cols_to_force_str:
        if c in data.columns:
            data[c] = data[c].astype(object).astype(str)
    
    data.replace({None: "missing", "nan": "missing", "NaN": "missing"}, inplace=True)
    data.fillna("missing", inplace=True)
    
    encoders = {}
    for col in cols_to_force_str:
        if col in data.columns:
            le = LabelEncoder()
            data[col] = le.fit_transform(data[col].astype(str))
            encoders[col] = le

logger.info("📂 Loading trained PPO model from %s...", MODEL_PATH)
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
        "This may affect prediction accuracy."
    )

# ===============================
# Parse command-line arguments
# ===============================
parser = argparse.ArgumentParser(description='Predict priority test cases for a given commit.')
parser.add_argument('--user_story_id', type=str, default='US-12', help='User story ID (e.g., US-12)')
parser.add_argument('--file_changed', type=str, default='unknown', help='File changed in commit')
parser.add_argument('--changed_function', type=str, default='unknown', help='Function changed in commit')
parser.add_argument('--dependent_function', type=str, default='unknown', help='Dependent function')
parser.add_argument('--git_diff_file', type=str, default=None, help='Path to git_diff output CSV (alternative to manual args)')
parser.add_argument('--output_file', type=str, default=None, help='Output CSV file for ranked test cases')

args = parser.parse_args()

# ===============================
# Prepare input for prediction
# ===============================
if args.git_diff_file and os.path.exists(args.git_diff_file):
    logger.info("📂 Loading git_diff output from %s...", args.git_diff_file)
    try:
        diff_df = pd.read_csv(args.git_diff_file, on_bad_lines='skip', engine='python')
    except Exception as e:
        logger.warning("⚠️  Could not parse git_diff file: %s, using args", e)
        user_story_id, file_changed, changed_function, dependent_function = args.user_story_id, args.file_changed, args.changed_function, args.dependent_function
        language = 'unknown'
    if len(diff_df) > 0:
        latest = diff_df.iloc[-1]
        user_story_id = str(latest.get('UserStoryID', latest.get('user_story_id', args.user_story_id))).strip()
        file_changed = str(latest.get('FileChanged', latest.get('file_changed', args.file_changed))).strip()
        changed_function = str(latest.get('ChangedFunctions', latest.get('changed_function', args.changed_function))).strip()
        dependent_function = str(latest.get('dependent_function', args.dependent_function)).strip()
        language = str(latest.get('language', 'unknown')).strip()
    else:
        user_story_id, file_changed, changed_function, dependent_function = args.user_story_id, args.file_changed, args.changed_function, args.dependent_function
        language = 'unknown'
else:
    user_story_id, file_changed, changed_function, dependent_function = args.user_story_id, args.file_changed, args.changed_function, args.dependent_function
    language = 'unknown'

logger.info("\n🔍 Predicting test cases for:")
logger.info("   User Story ID      : %s", user_story_id)
logger.info("   File Changed       : %s", file_changed)
logger.info("   Changed Function   : %s", changed_function)
logger.info("   Dependent Function : %s", dependent_function)

# ===============================
# Encode input for model prediction
# ===============================
# Map to encoded values (use encoder classes to test membership)
def safe_encode(col_name, value):
    if col_name in encoders:
        classes = getattr(encoders[col_name], 'classes_', None)
        try:
            # If classes_ available, use membership check
            if classes is not None and str(value) in classes:
                return int(encoders[col_name].transform([str(value)])[0])
            else:
                # fallback: try transform and catch
                return int(encoders[col_name].transform([str(value)])[0])
        except Exception:
            return 0
    return 0

encoded_us = safe_encode('user_story_id', user_story_id)
encoded_file = safe_encode('file_changed', file_changed)
encoded_func = safe_encode('changed_function', changed_function)
encoded_dep = safe_encode('dependent_function', dependent_function)
encoded_lang = safe_encode('language', language)

# include all 5 state columns to match the trained model: user_story_id, file_changed, changed_function, dependent_function, language
state = np.array([encoded_us, encoded_file, encoded_func, encoded_dep, encoded_lang], dtype=np.float32) / max(1, n_actions)

logger.info("   Encoded State      : [%.4f, %.4f, %.4f, %.4f, %.4f]", state[0], state[1], state[2], state[3], state[4])

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
# else:
    # probs = probs / probs.sum()
    # Convert scores into relative priority (highest = 1.0)

# ===============================
# Load training data to map test cases to their original user stories
# ===============================
tc_to_us_mapping = {}
if os.path.exists(CSV_PATH):
    logger.info("📂 Loading training data to find original user stories for each test case...")
    try:
        train_data = pd.read_csv(CSV_PATH)
        # Map each test case to its original user stories (there may be multiple)
        for _, row in train_data.iterrows():
            tc = str(row.get('test_case_id', '')).strip()
            us = str(row.get('user_story_id', '')).strip()
            if tc and us and tc.lower() != 'nan' and us.lower() != 'nan':
                if tc not in tc_to_us_mapping:
                    tc_to_us_mapping[tc] = set()
                tc_to_us_mapping[tc].add(us)
        logger.info("✅ Mapped %d test cases to their original user stories", len(tc_to_us_mapping))
    except Exception as e:
        logger.warning("⚠️  Could not load training data: %s", e)

# ===============================
# Map action indices to test case IDs
# ===============================
mapped_labels = []
for idx in range(n_actions):
    if idx < len(encoder_classes):
        mapped_labels.append(encoder_classes[idx])
    else:
        mapped_labels.append(f"UNKNOWN_{idx}")

ranking = sorted(zip(mapped_labels, probs), key=lambda x: x[1], reverse=True)
max_score = max(score for _, score in ranking)
ranking = [(tc, round(score / max_score, 4)) for tc, score in ranking]


# ===============================
# PRIORITIZE: Test cases directly mapped to this user story in Excel
# ===============================
directly_mapped_tcs = todo_mapping.get(user_story_id, [])
logger.info("\n📌 Test cases directly mapped to %s in Excel: %s", user_story_id, directly_mapped_tcs)

# Separate ranking into two lists: directly mapped (high priority) and others
direct_ranking = []
other_ranking = []

for tc, score in ranking:
    if tc in directly_mapped_tcs:
        # Directly mapped: boost score to 1.0 (highest priority)
        direct_ranking.append((tc, 1.0))
    else:
        # Not directly mapped: keep model score but lower priority
        other_ranking.append((tc, score * 0.5))  # Scale down non-mapped test cases

# Combine: directly mapped tests first (sorted by order in Excel), then others
final_ranking = direct_ranking + sorted(other_ranking, key=lambda x: x[1], reverse=True)

def get_reason(tc_label, file_name, func_name, is_direct_map):
    if is_direct_map:
        return "Directly mapped in Excel"
    t = str(tc_label).lower()
    if file_name.lower() != "unknown" and file_name.lower() in t:
        return "Same file reference"
    if func_name.lower() != "unknown" and func_name.lower() in t:
        return "Matches function name"
    if "unknown" in (file_name.lower(), func_name.lower()):
        return "Unknown metadata — fallback prediction"
    return "Model-based priority (high failure risk)"

logger.info("\n🧩 RANKED TEST CASES (by priority):")
logger.info("=" * 80)
for rank, (tc, prob) in enumerate(final_ranking[:30], start=1):
    is_direct = tc in directly_mapped_tcs
    reason = get_reason(tc, file_changed, changed_function, is_direct)
    original_us = ", ".join(sorted(tc_to_us_mapping.get(tc, set()))) or "Unknown"
    logger.info("%02d. %-12s | Score: %.4f | Original US: %s | Reason: %s", rank, tc, prob, original_us, reason)
logger.info("=" * 80)

# ===============================
# Save results to CSV
# ===============================
out_df = pd.DataFrame(final_ranking, columns=["Test_Case_ID", "Priority_Score"])
out_df["Rank"] = range(1, len(out_df) + 1)
# Map test case to its ORIGINAL user story (not the input user_story_id)
out_df["Original_User_Story_ID"] = out_df["Test_Case_ID"].apply(lambda tc: ", ".join(sorted(tc_to_us_mapping.get(tc, set()))) or "Unknown")
out_df["Input_User_Story_ID"] = user_story_id
out_df["File_Changed"] = file_changed
out_df["Changed_Function"] = changed_function
out_df["Is_Direct_Map"] = out_df["Test_Case_ID"].apply(lambda x: x in directly_mapped_tcs)
out_df["Reason"] = out_df.apply(lambda row: get_reason(row["Test_Case_ID"], file_changed, changed_function, row["Is_Direct_Map"]), axis=1)
out_df = out_df[["Rank", "Test_Case_ID", "Priority_Score", "Original_User_Story_ID", "Input_User_Story_ID", "Reason", "File_Changed", "Changed_Function"]]

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
output_file = args.output_file or _conf.get('priority_output_path') or f"test_case_priorities_{timestamp}.csv"
out_df.to_csv(output_file, index=False)
logger.info("\n💾 Ranked test cases saved to: %s", output_file)
logger.info("✅ Prediction complete! Top 5 test cases to run for %s:", user_story_id)
for rank, row in out_df.head(5).iterrows():
    logger.info("   %d. %s (score: %.4f) - %s", row['Rank'], row['Test_Case_ID'], row['Priority_Score'], row['Reason'])