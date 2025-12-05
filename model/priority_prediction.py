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

# ------------------------------
# HuggingFace NLP Model (FLAN-T5)
# ------------------------------
try:
    from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
    print("\n[INFO] Loading FLAN-T5 NLP model…")
    nlp_tokenizer = AutoTokenizer.from_pretrained("google/flan-t5-base")
    nlp_model = AutoModelForSeq2SeqLM.from_pretrained("google/flan-t5-base")
    print("[SUCCESS] NLP model loaded.\n")
except Exception as e:
    print(f"[WARNING] NLP model could not be loaded: {e}")
    nlp_tokenizer = None
    nlp_model = None

# ------------------------------
# Add parent directory to path
# ------------------------------
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import config_loader as cfg
    cfg.setup_logging()
    _conf = cfg.load_config()
except:
    _conf = {}

logger = logging.getLogger(__name__)

CSV_PATH = _conf.get('output_path') or "final_userstory_commit_test_report_poc.csv"
MODEL_PATH = _conf.get('ppo_model_path') or "ppo_test_selection_model"
ENCODER_PATH = MODEL_PATH + "_encoders.pkl"
TODO_PATH = _conf.get('todo_path') or "D:\\data-learn\\data\\Todo_UserStories_TestCases.xlsx"

# ------------------------------
# Load Excel Mapping (User Story -> Test Cases)
# ------------------------------
todo_mapping = {}

if os.path.exists(TODO_PATH):
    try:
        todo_df = pd.read_excel(TODO_PATH)
        todo_df.columns = todo_df.columns.str.strip().str.lower().str.replace(" ", "")

        us_col = next((c for c in todo_df.columns if "userstory" in c or "user_story" in c), None)
        tc_col = next((c for c in todo_df.columns if "testcase" in c or "test_case" in c), None)

        if us_col and tc_col:
            for _, row in todo_df.iterrows():
                us = str(row[us_col]).strip()
                tc = str(row[tc_col]).strip()
                if us.lower() != 'nan' and tc.lower() != 'nan':
                    if us not in todo_mapping:
                        todo_mapping[us] = []
                    if tc not in todo_mapping[us]:
                        todo_mapping[us].append(tc)

        logger.info("Loaded Excel US->TC mapping")

    except Exception as e:
        logger.warning(f"[WARNING] Could not load Excel mapping: {e}")

else:
    logger.warning("[WARNING] Todo Excel not found.")


# ------------------------------
# Load or Rebuild Encoders
# ------------------------------
try:
    with open(ENCODER_PATH, "rb") as f:
        encoders = pickle.load(f)
    logger.info("Encoders loaded")
except:
    logger.warning("Encoders not found, rebuilding...")
    if os.path.exists(CSV_PATH):
        df = pd.read_csv(CSV_PATH)
        encoders = {}
        for col in ["file_changed", "changed_function", "dependent_function", "test_case_id", "user_story_id", "language"]:
            if col in df.columns:
                le = LabelEncoder()
                df[col] = df[col].astype(str)
                df[col] = le.fit_transform(df[col])
                encoders[col] = le
    else:
        logger.error("CSV path for training data not found, cannot rebuild encoders.")
        encoders = {}


# ------------------------------
# Load PPO Model
# ------------------------------
try:
    model = PPO.load(MODEL_PATH, device="cpu")
    policy = model.policy
    
    try:
        n_actions = model.action_space.n
    except Exception:
        n_actions = getattr(model, "env", None)
        if hasattr(n_actions, "action_space"):
            n_actions = model.env.action_space.n
        else:
            n_actions = policy.action_net.out_features if hasattr(policy, "action_net") else None
            
    encoder_classes = encoders["test_case_id"].classes_ if "test_case_id" in encoders else []
except Exception as e:
    logger.error(f"Could not load PPO model: {e}")
    sys.exit(1)


# ------------------------------
# CLI Argument Parsing
# ------------------------------
parser = argparse.ArgumentParser()
parser.add_argument("--user_story_id", type=str, default="US-10")
parser.add_argument('--file_changed', type=str, default='unknown', help='File changed in commit')
parser.add_argument('--changed_function', type=str, default='unknown', help='Function changed in commit')
parser.add_argument('--dependent_function', type=str, default='unknown', help='Dependent function')
parser.add_argument('--git_diff_file', type=str, default=None, help='Path to git_diff output CSV (alternative to manual args)')
parser.add_argument('--output_file', type=str, default=None, help='Output CSV file for ranked test cases')

args = parser.parse_args()

# ------------------------------
# Prepare input for prediction (Git Diff Integration)
# ------------------------------
if args.git_diff_file and os.path.exists(args.git_diff_file):
    logger.info("[LOAD] Loading git_diff output from %s...", args.git_diff_file)
    try:
        diff_df = pd.read_csv(args.git_diff_file, on_bad_lines='skip', engine='python')
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
    except Exception as e:
        logger.warning("[WARNING]  Could not parse git_diff file: %s, using args", e)
        user_story_id, file_changed, changed_function, dependent_function = args.user_story_id, args.file_changed, args.changed_function, args.dependent_function
        language = 'unknown'
else:
    user_story_id, file_changed, changed_function, dependent_function = args.user_story_id, args.file_changed, args.changed_function, args.dependent_function
    language = 'unknown'

logger.info("\n[PREDICT] Predicting test cases for:")
logger.info("   User Story ID      : %s", user_story_id)
logger.info("   File Changed       : %s", file_changed)
logger.info("   Changed Function   : %s", changed_function)


# ------------------------------
# Encode Model State
# ------------------------------
def safe_encode(col, val):
    if col in encoders:
        try:
            return int(encoders[col].transform([str(val)])[0])
        except:
            return 0
    return 0

state = np.array([
    safe_encode("user_story_id", user_story_id),
    safe_encode("file_changed", file_changed),
    safe_encode("changed_function", changed_function),
    safe_encode("dependent_function", dependent_function),
    safe_encode("language", language)
], dtype=np.float32)

# Normalize state if needed (based on previous implementation)
state = state / max(1, n_actions)

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

# Handle output size mismatch
if len(probs) != n_actions:
    if len(probs) < n_actions:
        pad = np.zeros(n_actions - len(probs), dtype=float)
        probs = np.concatenate([probs, pad])
    else:
        probs = probs[:n_actions]

if len(encoder_classes) > 0:
    mapped_labels = []
    for idx in range(n_actions):
        if idx < len(encoder_classes):
            mapped_labels.append(encoder_classes[idx])
        else:
            mapped_labels.append(f"UNKNOWN_{idx}")
    
    ranking = sorted(zip(mapped_labels, probs), key=lambda x: x[1], reverse=True)
else:
    ranking = sorted(zip(range(n_actions), probs), key=lambda x: x[1], reverse=True)

max_prob = max(score for _, score in ranking) if ranking else 1.0
ranking = [(tc, round(score / max_prob, 4)) for tc, score in ranking]


# ------------------------------
# Load Training Dataset for File/Function/US Mapping (STEP 1)
# ------------------------------
tc_file_func_map = {}  # dict: TC -> list of (file, function)
tc_to_us_mapping = {}

if os.path.exists(CSV_PATH):
    train_data = pd.read_csv(CSV_PATH)
    for _, row in train_data.iterrows():
        tc = str(row.get('test_case_id', '')).strip()
        us = str(row.get('user_story_id', '')).strip()
        f  = str(row.get('file_changed', '')).strip()
        fn = str(row.get('changed_function', '')).strip()

        # US Mapping
        if tc and us and tc.lower() != 'nan' and us.lower() != 'nan':
            if tc not in tc_to_us_mapping:
                tc_to_us_mapping[tc] = set()
            tc_to_us_mapping[tc].add(us)

        if tc not in tc_file_func_map:
            tc_file_func_map[tc] = []

        # Avoid duplicates
        pair = (f if f.lower() != "nan" else "",
                fn if fn.lower() != "nan" else "")
        
        if pair not in tc_file_func_map[tc]:
            tc_file_func_map[tc].append(pair)


# ------------------------------
# NLP Reason Generation
# ------------------------------
def generate_reason(tc, user_story, files, funcs, is_direct):
    if nlp_tokenizer and nlp_model:
        prompt = fprompt = f"""
You are an AI that writes clear reasons for test-case-to-user-story mapping.

Test Case: {tc}
User Story: {user_story}
Files Changed: {files}
Functions Changed: {funcs}
Direct Mapping: {is_direct}

Write a short, clear justification like:
"TC-24 maps to US-10 because the task update logic in app.py directly implements the acceptance criteria."

Rules:
- Mention file-specific impact.
- If function list is empty, say "UI behavior" or "component update".
- Keep the explanation 1–2 sentences.
"""
        try:
            input_ids = nlp_tokenizer(prompt, return_tensors="pt").input_ids
            output_ids = nlp_model.generate(input_ids, max_length=70)
            return nlp_tokenizer.decode(output_ids[0], skip_special_tokens=True)
        except Exception:
            return "Model-based priority"
    else:
        # Fallback if NLP model not loaded
        if is_direct:
            return "Directly mapped in Excel"
        if files and files != "unknown" and files in str(tc):
            return "Same file reference"
        return "Model-based priority"


# ------------------------------
# Build Final Output (Format B) - STEP 2: Expand ranking
# ------------------------------
expanded_rows = []
directly_mapped_tcs = todo_mapping.get(user_story_id, [])

# Re-sort ranking to prioritize direct maps
direct_ranking = []
other_ranking = []
for tc, score in ranking:
    if tc in directly_mapped_tcs:
        direct_ranking.append((tc, 1.0))
    else:
        other_ranking.append((tc, score * 0.5))
final_ranking = direct_ranking + sorted(other_ranking, key=lambda x: x[1], reverse=True)


for rank, (tc, score) in enumerate(final_ranking, start=1):
    
    # If TC has mappings, create one row per file/function
    if tc in tc_file_func_map and tc_file_func_map[tc]:
        for file_changed_hist, changed_function_hist in tc_file_func_map[tc]:

            reason = generate_reason(tc, user_story_id, file_changed_hist, changed_function_hist, tc in directly_mapped_tcs)
            original_us = ", ".join(sorted(tc_to_us_mapping.get(tc, set()))) or "Unknown"

            expanded_rows.append({
                "Rank": rank,
                "Test_Case_ID": tc,
                "Priority_Score": score,
                "Original_User_Story_ID": original_us,
                "Input_User_Story_ID": user_story_id,
                "Reason": reason,
                "File_Changed": file_changed_hist,
                "Changed_Function": changed_function_hist,
                "Is_Direct_Map": tc in directly_mapped_tcs
            })
    else:
        # No mapping found, default row
        reason = generate_reason(tc, user_story_id, "unknown", "unknown", tc in directly_mapped_tcs)
        original_us = ", ".join(sorted(tc_to_us_mapping.get(tc, set()))) or "Unknown"
        
        expanded_rows.append({
            "Rank": rank,
            "Test_Case_ID": tc,
            "Priority_Score": score,
            "Original_User_Story_ID": original_us,
            "Input_User_Story_ID": user_story_id,
            "Reason": reason,
            "File_Changed": "",
            "Changed_Function": "",
            "Is_Direct_Map": tc in directly_mapped_tcs
        })


# ------------------------------
# Save Output - STEP 3
# ------------------------------
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
output_file = args.output_file or _conf.get('priority_output_path') or f"test_case_priorities_{timestamp}.csv"

out_df = pd.DataFrame(expanded_rows)
# Ensure columns order
cols = ["Rank", "Test_Case_ID", "Priority_Score", "Original_User_Story_ID", "Input_User_Story_ID", "Reason", "File_Changed", "Changed_Function", "Is_Direct_Map"]
# Filter columns that exist
cols = [c for c in cols if c in out_df.columns]
out_df = out_df[cols]

out_df.to_csv(output_file, index=False)

logger.info(f"[SAVE] Saved full NLP-enhanced results to: {output_file}")

# ------------------------------
# Save filtered results (ONLY REQUIRED)
# ------------------------------
filtered_output_file = output_file.replace(".csv", "_onlyrequired.csv")
if "_onlyrequired" not in filtered_output_file: 
    filtered_output_file = output_file + "_onlyrequired.csv"

# Filter logic: Direct Map OR Same File OR Matches Function
# Note: Now we filter based on the EXPANDED rows. 
# So if a TC has 10 rows, and 1 matches the function name, that 1 row will be kept.
# We check if the HISTORICAL file/function matches the CURRENT input file/function
filtered_df = out_df[
    (out_df["Is_Direct_Map"] == True) |
    ((out_df["File_Changed"] == file_changed) & (file_changed != 'unknown')) |
    ((out_df["Changed_Function"] == changed_function) & (changed_function != 'unknown'))
]

filtered_df.to_csv(filtered_output_file, index=False)
logger.info("[SAVE] Filtered (required only) test cases saved to: %s", filtered_output_file)
