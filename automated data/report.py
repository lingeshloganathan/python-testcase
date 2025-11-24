# report.py  — Full version with DB insert fixed
import os, json, math, csv
import sys
from pathlib import Path

# Add project root to path so we can import model package
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import pandas as pd
from model.db_connection import get_connection

import logging

# load centralized config and logging
try:
    import config_loader as cfg
    cfg.setup_logging()
    _conf = cfg.load_config()
except Exception:
    _conf = {}

# ---------- CONFIG ----------
output_file = _conf.get('output_file')
tests_path = _conf.get('tests_path')
app_deps_path = _conf.get('app_deps_path')
todo_path = _conf.get('todo_path')
output_path = _conf.get('output_path')
if not output_file:
    logging.error("output_file is not configured. Please set output_file in config_loader or _conf.")
    sys.exit(1)
if not output_path:
    logging.error("output_path is not configured. Please set output_path in config_loader or _conf.")
    sys.exit(1)
output_status = output_path.replace(".csv", "_status.csv")

logger = logging.getLogger(__name__)



# ---------- HELPERS ----------
def read_any(path):
    _, ext = os.path.splitext(path.lower())

    # --- CSV FIX FOR BAD LINES ---
    if ext == ".csv":
        # Use python engine and handle bad rows (warn or skip)
        return pd.read_csv(
            path,
            dtype=str,
            on_bad_lines="skip"   # or "skip" to silently ignore malformed lines
        )

    elif ext in (".xls", ".xlsx"):
        return pd.read_excel(path, dtype=str)

    elif ext == ".json":
        with open(path, "r", encoding="utf8") as f:
            return json.load(f)

    else:
        raise ValueError("Unsupported file type: " + ext)

def split_funcs_cell(cell):
    if pd.isna(cell): return []
    s = str(cell).strip()
    if s.lower() in ("nan", ""): return []
    for sep in [";", "|", "/", "\\"]: s = s.replace(sep, ",")
    return [p.strip() for p in s.split(",") if p.strip() and p.lower() != "nan"]

def map_columns_lower_strip(df):
    df = df.copy()
    df.columns = df.columns.str.strip()
    return df

def map_commits(df):
    df = df.copy()
    cols = {c.lower().replace(" ", ""): c for c in df.columns}
    colmap = {}
    for key, orig in cols.items():
        if key in ('commitsha','commitid','commit','sha'):
            colmap[orig] = 'commit_sha'
        if key in ('userstoryid','user_story_id','userstory','storyid'):
            colmap[orig] = 'user_story_id'
        if 'file' in key and 'change' in key:
            colmap[orig] = 'file_changed'
        if 'function' in key:  # 👈 MATCHES ANY COLUMN WITH 'function'
            colmap[orig] = 'changed_function'
        if key in ('author','committer','developer'):
            colmap[orig] = 'author'
        if key in ('language','lang','filetype','source'):
            colmap[orig] = 'language'
    return df.rename(columns=colmap)

def map_tests(df):
    df = df.copy()
    cols = {c.lower().replace(" ", ""): c for c in df.columns}
    colmap = {}
    for key, orig in cols.items():
        if key in ('testcaseid','test_case_id','testcase','testcase_id'): colmap[orig] = 'test_case_id'
        if key in ('testname','test_name','test'): colmap[orig] = 'test_name'
        if key in ('status','result','outcome'): colmap[orig] = 'status'
        if key in ('timestamp','time','execution_date','date','run_time','executed_at'): colmap[orig] = orig
    return df.rename(columns=colmap)

def map_todo(df):
    df = df.copy()
    cols_lower = {c.lower().replace(" ", ""): c for c in df.columns}
    colmap = {}
    for key, orig in cols_lower.items():
        if key in ('userstoryid','user_story_id','userstory'): colmap[orig] = 'user_story_id'
        if key in ('testcaseid','test_case_id','testcase'): colmap[orig] = 'test_case_id'
    return df.rename(columns=colmap)

# ---------- 1) LOAD ----------
commits_df = read_any(output_file)
logger.info("Loaded %d commits from %s", len(commits_df), output_file)

# Load tests - optional, if file missing, skip test aggregation
tests_df = None
if os.path.exists(tests_path):
    try:
        tests_df = read_any(tests_path)
        logger.info("Loaded %d test records from %s", len(tests_df), tests_path)
    except Exception as e:
        logger.warning("Could not load tests from %s: %s", tests_path, e)
else:
    logger.warning("Test file not found: %s", tests_path)

# Load todo - optional, if file missing, use commits as-is
todo_df = None
if os.path.exists(todo_path):
    try:
        todo_df = read_any(todo_path)
        logger.info("Loaded %d todo mappings from %s", len(todo_df), todo_path)
    except Exception as e:
        logger.warning("Could not load todo from %s: %s", todo_path, e)
else:
    logger.warning("Todo file not found: %s", todo_path)

app_deps   = read_any(app_deps_path) if os.path.exists(app_deps_path) else {}
logger.info("Loaded app dependencies: %d keys", len(app_deps))

# ---------- 2) NORMALIZE HEADERS ----------
commits_df = map_commits(map_columns_lower_strip(commits_df))
if tests_df is not None:
    tests_df   = map_tests(map_columns_lower_strip(tests_df))
if todo_df is not None:
    todo_df    = map_todo(map_columns_lower_strip(todo_df))

logger.info("Commit cols: %s", list(commits_df.columns))
if tests_df is not None:
    logger.info("Test cols: %s", list(tests_df.columns))
if todo_df is not None:
    logger.info("Todo cols: %s", list(todo_df.columns))

# ---------- 3) EXPLODE CHANGED FUNCTIONS ----------
if 'changed_function' not in commits_df.columns:
    logger.warning("⚠ No 'changed_function' column found — using empty values.")
    commits_df['changed_function'] = None
commits_df['changed_function_list'] = commits_df['changed_function'].apply(split_funcs_cell)
commits_exploded = commits_df.explode('changed_function_list').copy()
# Keep commits even when no functions were extracted. Normalize empty lists/strings to NA
commits_exploded['changed_function_list'] = commits_exploded['changed_function_list'].replace({None: pd.NA, '': pd.NA})
commits_exploded = commits_exploded.reset_index(drop=True)

# ---------- 4) PREPARE TEST RESULTS ----------
agg_tests = None
if tests_df is not None:
    tests_df['status_norm'] = tests_df['status'].astype(str).str.lower().str.strip()
    tests_df['status_norm'] = tests_df['status_norm'].replace(
        {'passed':'pass','failed':'fail','ok':'pass','error':'fail'}
    )

    timestamp_col = next((c for c in tests_df.columns if any(k in c.lower() for k in ['time','date'])), None)
    if timestamp_col:
        tests_df[timestamp_col] = pd.to_datetime(tests_df[timestamp_col], errors='coerce')

    agg_counts = (tests_df.groupby('test_case_id', dropna=False)
                  .agg(total_no_of_Passed=('status_norm', lambda s: (s=='pass').sum()),
                       total_no_of_Failed=('status_norm', lambda s: (s=='fail').sum()))
                  .reset_index())

    def choose_test_name(group):
        vals = group['test_name'].dropna()
        if vals.empty: return pd.NA
        mode = vals.mode()
        return mode.iloc[0] if not mode.empty else vals.iloc[-1]

    # names = tests_df.groupby('test_case_id', dropna=False).apply(choose_test_name, include_groups=False).reset_index()
    # names.columns = ['test_case_id','test_name']
    # agg_tests = agg_counts.merge(names, on='test_case_id', how='left')

    names = (
    tests_df.groupby('test_case_id', dropna=False)
    .apply(lambda g: choose_test_name(g), include_groups=False)
    .reset_index(name='test_name')
)

    agg_tests = agg_counts.merge(names, on='test_case_id', how='left')

    if timestamp_col:
        last = (tests_df.sort_values(timestamp_col)
                .groupby('test_case_id', dropna=False)
                .last()
                .reset_index())
        last_small = last[['test_case_id','status_norm',timestamp_col]].rename(
            columns={'status_norm':'last_status', timestamp_col:'last_execution_date'})
        agg_tests = agg_tests.merge(last_small, on='test_case_id', how='left')
    logger.info("Aggregated %d test cases", len(agg_tests))
else:
    logger.warning("Tests not available; skipping test aggregation")

# ---------- 5) JOIN COMMITS + TODO + TESTS ----------
final = commits_exploded.copy()

if todo_df is not None and agg_tests is not None:
    mapped_todo = todo_df[['user_story_id','test_case_id']].dropna().drop_duplicates()
    joined = final.merge(mapped_todo, on='user_story_id', how='left')
    final = joined.merge(agg_tests, on='test_case_id', how='left')
    logger.info("After join with todo+tests: %d rows", len(final))
elif agg_tests is not None:
    logger.warning("Todo not available; cannot join with tests")
else:
    logger.warning("Tests not available; report will only show commits")

# ---------- 6) DEPENDENCY LOOKUP ----------
def lookup_deps_by_file(file_changed, func_name, app_deps_obj):
    # Normalize missing / pandas.NA values safely
    if pd.isna(func_name):
        return []

    # Accept either a single function name or a list of function names
    if isinstance(func_name, list):
        funcs = [f for f in func_name if (not pd.isna(f)) and str(f).strip()]
    else:
        s = str(func_name).strip()
        if s == "" or s.lower() == "nan":
            return []
        funcs = [s]

    results = []
    basename = os.path.basename(str(file_changed))
    for f in funcs:
        if not f:
            continue

        # Check file-specific mapping
        if file_changed in app_deps_obj and isinstance(app_deps_obj[file_changed], dict):
            fm = app_deps_obj[file_changed]
            if f in fm and isinstance(fm[f], list):
                results.extend(fm[f])
            elif f.lower() in fm and isinstance(fm[f.lower()], list):
                results.extend(fm[f.lower()])

        # Check by basename match
        for fk, fm in app_deps_obj.items():
            if os.path.basename(fk) == basename and isinstance(fm, dict):
                if f in fm and isinstance(fm[f], list):
                    results.extend(fm[f])
                elif f.lower() in fm and isinstance(fm[f.lower()], list):
                    results.extend(fm[f.lower()])

        # Check top-level list mapping for function name
        if f in app_deps_obj and isinstance(app_deps_obj[f], list):
            results.extend(app_deps_obj[f])
        elif f.lower() in app_deps_obj and isinstance(app_deps_obj[f.lower()], list):
            results.extend(app_deps_obj[f.lower()])

    # Deduplicate while preserving order
    return list(dict.fromkeys(results))

final['dependent_functions_list'] = final.apply(
    lambda r: lookup_deps_by_file(r.get('file_changed',''), r.get('changed_function_list',''), app_deps),
    axis=1,
    result_type='reduce'
)
final['dependent_function'] = final['dependent_functions_list'].apply(lambda L: ", ".join(L) if isinstance(L, list) and L else pd.NA)

# ---------- 7) FINALIZE ----------
desired_cols = [
 'user_story_id','commit_sha','author','file_changed','changed_function',
 'dependent_function','language','test_case_id','test_name','total_no_of_Passed',
 'total_no_of_Failed','last_status','last_execution_date'
]
for c in desired_cols:
    if c not in final.columns: final[c] = pd.NA
final['changed_function'] = final['changed_function_list']

final_df = final[desired_cols].copy()
final_df['last_execution_date'] = pd.to_datetime(final_df['last_execution_date'], errors='coerce')
final_df['last_execution_date'] = final_df['last_execution_date'].dt.strftime("%Y-%m-%d %H:%M:%S")
final_df['last_status'] = final_df['last_status'].astype(str).str.lower().replace(
    {'nan': pd.NA, 'none': pd.NA, '': pd.NA, 'passed':'pass','failed':'fail','ok':'pass','error':'fail'}
)

# Replace missing test mappings/names/status with user-friendly placeholders
final_df['test_case_id'] = final_df['test_case_id'].astype(object)
final_df['test_name'] = final_df['test_name'].astype(object)
final_df['last_status'] = final_df['last_status'].astype(object)

final_df['test_case_id'] = final_df['test_case_id'].where(pd.notnull(final_df['test_case_id']), 'No Test Mapped')
final_df['test_name'] = final_df['test_name'].where(pd.notnull(final_df['test_name']), 'No Test Name')
final_df['last_status'] = final_df['last_status'].where(pd.notnull(final_df['last_status']), 'No Execution')

# ---------- 8) SAVE ----------
# df_with_status = final_df[final_df['last_status'].notna()].copy()
df_full = final_df.copy()

# df_with_status.to_csv(output_status, index=False, encoding='utf-8', quoting=csv.QUOTE_MINIMAL)
df_full.to_csv(output_path, index=False, encoding='utf-8', quoting=csv.QUOTE_MINIMAL)

# logger.info("✅ Saved main report: %s  (%d rows)", output_path, len(df_with_status))
logger.info("✅ Saved full report: %s  (%d rows)\n", output_status, len(df_full))

def _to_native_int(v):
    if v is None: return None
    if isinstance(v, int): return v
    if isinstance(v, float):
        if math.isnan(v): return None
        return int(v)
    try:
        if isinstance(v, str) and v.strip() != "":
            return int(float(v)) if '.' in v else int(v)
    except Exception:
        return None
    return None

def insert_regression_matrix(df):
    conn = get_connection()
    if conn is None:
        logger.error("❌ Cannot insert — DB connection failed.")
        return
        return
    df2 = df.copy().where(pd.notnull(df), None)

    query = """
        INSERT INTO regression_matrix (
            user_story_id, commit_sha, author, file_changed, changed_function,
            dependent_function, test_case_id, test_name, total_no_of_Passed,
            total_no_of_Failed, last_status, last_execution_date
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (changed_function) DO UPDATE SET
            dependent_function = EXCLUDED.dependent_function,
            test_case_id = EXCLUDED.test_case_id,
            test_name = EXCLUDED.test_name,
            total_no_of_Passed = EXCLUDED.total_no_of_Passed,
            total_no_of_Failed = EXCLUDED.total_no_of_Failed,
            last_status = EXCLUDED.last_status,
            last_execution_date = EXCLUDED.last_execution_date;
    """
    cur = None
    try:
        cur = conn.cursor()
        inserted, failed = 0, 0
        for _, row in df2.iterrows():
            try:
                data = [
                    row.get('user_story_id'),
                    row.get('commit_sha'),
                    row.get('author'),
                    row.get('file_changed'),
                    row.get('changed_function'),
                    row.get('dependent_function'),
                    row.get('test_case_id'),
                    row.get('test_name'),
                    _to_native_int(row.get('total_no_of_Passed')),
                    _to_native_int(row.get('total_no_of_Failed')),
                    None if pd.isna(row.get('last_status')) else str(row.get('last_status')),
                    None if pd.isna(row.get('last_execution_date')) else str(row.get('last_execution_date'))
                ]
                cur.execute(query, data)
                inserted += 1
            except Exception as row_e:
                failed += 1
    except Exception as e:
        conn.rollback()
        logger.exception("❌ Insert aborted: %s", e)
    finally:
        if cur: cur.close()
        conn.close()

# insert_regression_matrix(df_with_status)
print(output_path)