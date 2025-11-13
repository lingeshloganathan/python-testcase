# """
# predict_priority_userstory.py

# Given a specific UserStoryID (e.g., US-10):
#  - find its commits from GitHub/local repo
#  - extract changed functions/files
#  - find matching tests
#  - predict priorities using PPO model
#  - remove duplicates and show final DataFrame
# """

# import os
# import re
# import subprocess
# import pandas as pd
# import numpy as np
# import gymnasium as gym
# from stable_baselines3 import PPO
# from sklearn.preprocessing import MinMaxScaler

# # ====================================================
# # Configuration
# # ====================================================
# USER_STORY_ID = "US-08"  # <-- change this to your story ID
# REPO_PATH = r"D:\data-learn\python-testcase"
# MODEL_PATH = r"D:\data-learn\ppo_priority_gymnasium_model.zip"
# TEST_RESULTS_PATH = r"D:\data-learn\python-testcase\tests\results\test_results.csv"
# OUTPUT_PATH = r"D:\data-learn\python-testcase\backend\priority_userstory.csv"

# # ====================================================
# # 1️⃣ Get Commits for the given UserStoryID
# # ====================================================
# def get_commits_for_story(repo_path, story_id):
#     """Find all commits mentioning the UserStoryID."""
#     os.chdir(repo_path)
#     commits = subprocess.check_output(["git", "log", "--all", "--grep", story_id, "--pretty=%H"]).decode().splitlines()
#     if not commits:
#         raise ValueError(f"❌ No commits found for {story_id}")
#     print(f"🔍 Found {len(commits)} commits for {story_id}:")
#     for c in commits:
#         print("   ", c)
#     return commits

# def extract_changes(repo_path, commit_hash):
#     """Extract changed files and functions for a given commit."""
#     os.chdir(repo_path)
#     changed_files = subprocess.check_output(
#         ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", commit_hash]
#     ).decode().splitlines()

#     diff_text = subprocess.check_output(["git", "show", commit_hash]).decode(errors="ignore")
#     changed_functions = set(re.findall(r"def\s+(\w+)\s*\(", diff_text))

#     return changed_files, changed_functions

# commits = get_commits_for_story(REPO_PATH, USER_STORY_ID)

# changed_files_total = set()
# changed_functions_total = set()
# for c in commits:
#     f, funcs = extract_changes(REPO_PATH, c)
#     changed_files_total.update(f)
#     changed_functions_total.update(funcs)

# print(f"\n📂 Changed Files for {USER_STORY_ID}: {', '.join(changed_files_total)}")
# print(f"⚙️  Changed Functions: {', '.join(changed_functions_total)}\n")

# # ====================================================
# # 2️⃣ Load Test Results
# # ====================================================
# tests = pd.read_csv( TEST_RESULTS_PATH,
#     usecols=["Test Case ID", "Test Name", "Status", "Timestamp"],  # no Message
#     parse_dates=["Timestamp"],
#     engine="python")
# tests["Status"] = tests["Status"].str.upper().fillna("PASSED")

# # ====================================================
# # 3️⃣ Match Tests to Changed Code
# # ====================================================
# def compute_impact(row):
#     test_name = str(row.get("Test Name", "")).lower()
#     # message = str(row.get("Message", "")).lower()
#     score = 0

#     # if any(fn.lower() in test_name or fn.lower() in message for fn in changed_functions_total):
#     #     score += 5
#     if any(f.lower().split("/")[-1].replace(".py", "") in test_name for f in changed_files_total):
#         score += 3
#     if row["Status"] == "FAILED":
#         score += 4
#     # Additional factors to consider
#     if row["Status"] == "FAILED" and "critical" in test_name:
#         score += 2
#     elif row["Status"] == "FAILED" and "major" in test_name:
#         score += 1
#     return score
# def compute_impact(row):
#     test_name = str(row.get("Test Name", "")).lower()
#     # message = str(row.get("Message", "")).lower()
#     score = 0

#     # if any(fn.lower() in test_name or fn.lower() in message for fn in changed_functions_total):
#     #     score += 5
#     if any(f.lower().split("/")[-1].replace(".py", "") in test_name for f in changed_files_total):
#         score += 3
#     if row["Status"] == "FAILED":
#         score += 4
#     return score

# tests["ImpactScore"] = tests.apply(compute_impact, axis=1)
# scaler = MinMaxScaler()
# tests["ImpactScoreScaled"] = scaler.fit_transform(tests[["ImpactScore"]])

# # ====================================================
# # 4️⃣ Define PPO Environment
# # ====================================================
# class PriorityEnv(gym.Env):
#     def __init__(self, row):
#         super().__init__()
#         self.row = row
#         self.observation_space = gym.spaces.Box(low=0, high=1, shape=(4,), dtype=np.float32)
#         self.action_space = gym.spaces.Discrete(3)
#         self.scaler = MinMaxScaler()

#     def reset(self, *, seed=None, options=None):
#         super().reset(seed=seed)
#         fail = 1 if self.row["Status"] == "FAILED" else 0
#         vec = np.array([
#             self.row["ImpactScoreScaled"],
#             fail,
#             np.random.rand(),
#             np.random.rand(),
#         ], dtype=np.float32).reshape(1, -1)
#         self.scaler.fit(np.vstack([vec, np.ones((1, 4))]))
#         obs = self.scaler.transform(vec)[0]
#         return obs, {}

#     def step(self, action):
#         reward = 0.0
#         terminated, truncated = True, False
#         return np.zeros(4, dtype=np.float32), reward, terminated, truncated, {}

# # ====================================================
# # 5️⃣ Predict Priority Using PPO Model
# # ====================================================
# print(" Loading PPO model...")
# model = PPO.load(MODEL_PATH)
# # print("🚀 Loading PPO model...")
# # model = PPO.load(MODEL_PATH)

# predictions = []
# for _, row in tests.iterrows():
#     env = PriorityEnv(row)
#     obs, _ = env.reset()
#     action, _ = model.predict(obs, deterministic=True)
#     priority = {0: "Low", 1: "Medium", 2: "High"}[int(action)]
#     predictions.append(priority)

# tests["Predicted Priority"] = predictions

# # ====================================================
# # 6️⃣ Remove Duplicates (Keep Latest Unique Test ID)
# # ====================================================
# tests.sort_values("Timestamp", ascending=False, inplace=True)
# tests_unique = tests.drop_duplicates(subset=["Test Case ID"], keep="first")

# # Rank based on ImpactScore + Priority
# priority_order = {"High": 3, "Medium": 2, "Low": 1}
# tests_unique["PriorityValue"] = tests_unique["Predicted Priority"].map(priority_order)
# tests_unique["FinalScore"] = tests_unique["ImpactScoreScaled"] * 0.6 + tests_unique["PriorityValue"] * 0.4

# final_df = tests_unique.sort_values("FinalScore", ascending=False)

# # ====================================================
# # 7️⃣ Output Results
# # ====================================================
# # Add the UserStoryID column
# final_df["UserStoryID"] = USER_STORY_ID

# # Define the exact columns to output (no Message)
# out_cols = [
#     "UserStoryID",
#     "Test Case ID", "Test Name", "Status",
#     "Predicted Priority", "ImpactScore", "ImpactScoreScaled",
#     "PriorityValue", "FinalScore", "Timestamp"
# ]

# print(f"\n===== 🧠 Final Priority Table for {USER_STORY_ID} =====")
# print(final_df[out_cols])
# # Save clean CSV
# final_df[out_cols].to_csv(OUTPUT_PATH, index=False)
# print(f"\n Final priorities saved to {OUTPUT_PATH}")
# # Create a new table for the regression matrix values
# regression_matrix_df = pd.read_csv(TEST_RESULTS_PATH)
# print("\n===== Regression Matrix Table =====")
# print(regression_matrix_df)

# # Save clean CSV
# final_df[out_cols].to_csv(OUTPUT_PATH, index=False)
# print(f"\n✅ Final priorities saved to {OUTPUT_PATH}")


# ============================================
# 🎯 PPO Test Case Selection — Prediction Script (Updated for Latest Data)
# ============================================

# ============================================
# 🎯 PPO Test Case Selection — Predict Last Commit Only
# ============================================

# ============================================
# ⚙️ PPO Test Case Prioritization with Reasoning
# ============================================

# priority_prediction_ranked_safe.py
import pandas as pd
import numpy as np
from sklearn.preprocessing import LabelEncoder
from stable_baselines3 import PPO
import torch
import warnings

CSV_PATH = "final_userstory_commit_test_report_poc.csv"
MODEL_PATH = "ppo_test_selection_model"

# -------------------------
# Load CSV and clean safely
# -------------------------
data = pd.read_csv(CSV_PATH)

# ensure relevant columns are strings so fillna('missing') won't warn
cols_to_force_str = ['file_changed', 'changed_function', 'dependent_function', 'test_case_id', 'last_status']
for c in cols_to_force_str:
    if c in data.columns:
        data[c] = data[c].astype(object).astype(str)  # force string dtype

# replace missing values
data.replace({None: "missing", "nan": "missing", "NaN": "missing"}, inplace=True)
data.fillna("missing", inplace=True)

# -------------------------
# Rebuild encoders (best-effort)
# -------------------------
encoders = {}
for col in cols_to_force_str:
    if col in data.columns:
        le = LabelEncoder()
        data[col] = le.fit_transform(data[col].astype(str))
        encoders[col] = le

# -------------------------
# Load model
# -------------------------
print("📂 Loading trained PPO model...")
model = PPO.load(MODEL_PATH)
policy = model.policy
print("✅ Model loaded successfully!")

# number of actions that the model expects
try:
    n_actions = model.action_space.n
except Exception:
    # fallback: try env (if available)
    n_actions = getattr(model, "env", None)
    if hasattr(n_actions, "action_space"):
        n_actions = model.env.action_space.n
    else:
        # fallback to length of policy output if accessible
        n_actions = policy.action_net.out_features if hasattr(policy, "action_net") else None

if n_actions is None:
    raise RuntimeError("Could not determine number of actions in the trained model.")

# get classes known to the encoder used here (may differ from training)
encoder_classes = encoders['test_case_id'].classes_ if 'test_case_id' in encoders else np.array([])

if len(encoder_classes) != n_actions:
    warnings.warn(
        f"Encoder classes ({len(encoder_classes)}) != model actions ({n_actions}).\n"
        "This means the encoder you rebuilt at prediction time differs from what the model saw during training.\n"
        "Prediction will proceed, but indices outside encoder range will be labelled 'UNKNOWN_<index>'.\n"
        "Recommended: save the label encoders at training time and load them here."
    )

# -------------------------
# Prepare latest commit state
# -------------------------
latest = data.iloc[-1]
decoded_file_changed = encoders['file_changed'].inverse_transform([latest['file_changed']])[0] \
    if 'file_changed' in encoders else str(latest['file_changed'])
decoded_changed_function = encoders['changed_function'].inverse_transform([latest['changed_function']])[0] \
    if 'changed_function' in encoders else str(latest['changed_function'])
decoded_dependent_function = encoders['dependent_function'].inverse_transform([latest['dependent_function']])[0] \
    if 'dependent_function' in encoders else str(latest['dependent_function'])

print(f"\n📊 Prioritizing tests for latest commit:")
print(f"   File Changed       : {decoded_file_changed}")
print(f"   Changed Function   : {decoded_changed_function}")
print(f"   Dependent Function : {decoded_dependent_function}")

# build state exactly as training (numeric encoded values normalized by len(data))
state = np.array([
    latest['file_changed'],
    latest['changed_function'],
    latest['dependent_function']
]) / len(data)

# torch tensor for policy
state_tensor = torch.tensor(state, dtype=torch.float32).unsqueeze(0)

# -------------------------
# Get action probabilities
# -------------------------
with torch.no_grad():
    dist = policy.get_distribution(state_tensor).distribution
    # try to obtain logits or probs depending on distribution type
    if hasattr(dist, "logits"):
        logits = dist.logits
        probs = torch.softmax(logits, dim=1).cpu().numpy().flatten()
    elif hasattr(dist, "probs"):
        probs = dist.probs.cpu().numpy().flatten()
    else:
        # fallback to using model.predict_proba-like behavior via policy
        action, _ = model.predict(state, deterministic=False)
        # construct a one-hot fallback (not ideal)
        probs = np.zeros(n_actions, dtype=float)
        probs[int(action)] = 1.0

# sanity: ensure probs length == n_actions
if len(probs) != n_actions:
    # try to pad/truncate
    if len(probs) < n_actions:
        pad = np.zeros(n_actions - len(probs), dtype=float)
        probs = np.concatenate([probs, pad])
    else:
        probs = probs[:n_actions]

# normalize to sum=1 if not already
if probs.sum() <= 0:
    probs = np.ones_like(probs) / len(probs)
else:
    probs = probs / probs.sum()

# -------------------------
# Map indices -> test case labels (safe)
# -------------------------
mapped_labels = []
for idx in range(n_actions):
    if idx < len(encoder_classes):
        mapped_labels.append(encoder_classes[idx])
    else:
        mapped_labels.append(f"UNKNOWN_{idx}")

# Rank test cases
ranking = sorted(zip(mapped_labels, probs), key=lambda x: x[1], reverse=True)

# -------------------------
# Simple reason function (customize as needed)
# -------------------------
def get_reason(tc_label, file_name, func_name):
    t = str(tc_label).lower()
    if file_name.lower() in t:
        return "Same file reference"
    if func_name.lower() in t:
        return "Matches function name"
    if "missing" in (file_name.lower(), func_name.lower()):
        return "Missing metadata — fallback prediction"
    return "Model-based priority (probability score)"

# -------------------------
# Print top-ranked results
# -------------------------
print("\n🧩 Ranked Test Case Priorities (top 15):")
for rank, (tc, prob) in enumerate(ranking[:15], start=1):
    reason = get_reason(tc, decoded_file_changed, decoded_changed_function)
    print(f"{rank:02d}. {tc:<15} | Score: {prob:.4f} | Reason: {reason}")

# optional: save CSV
out_df = pd.DataFrame(ranking, columns=["Test_Case", "Priority_Score"])
out_df["Reason"] = out_df["Test_Case"].apply(lambda x: get_reason(x, decoded_file_changed, decoded_changed_function))
out_df.to_csv("test_case_priorities_safe.csv", index=False)
print("\n💾 Saved 'test_case_priorities_safe.csv'")
