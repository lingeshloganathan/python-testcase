import argparse
import requests
import re
import csv
import os
import sys
import logging

# Try to import the project's config_loader; be tolerant when running as a standalone script
try:
    import config_loader as _cfg
except Exception:
    _cfg = None

import sys, os

# Add project root to path: d:/data-learn/
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(PROJECT_ROOT)



def _load_config_fallback():
    # Prefer config_loader if available, otherwise attempt dynamic import
    if _cfg:
        try:
            return _cfg.load_config()
        except Exception:
            pass
    try:
        import importlib
        cfg_mod = importlib.import_module('config_loader')
        return cfg_mod.load_config()
    except Exception:
        return {}
    
    

def find_and_write_commits(user_story_id: str,
                           repo_owner: str = "lingeshloganathan",
                           repo_name: str = "python-testcase",
                           output_file: str = r"D:\data-learn\automated data\userstory_commit_report.csv",
                           last_only: bool = False,
                           latest: int = 0):
    headers = {"Accept": "application/vnd.github.v3+json"}
    logging.info(f"Searching commits for {user_story_id} in {repo_owner}/{repo_name}")

    all_commits = []
    page = 1
    while True:
        url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/commits"
        print(url)
        params = {"per_page": 100, "page": page}
        response = requests.get(url, headers=headers, params=params)

        try:
            commits = response.json()
        except Exception as e:
            print("Error decoding JSON from GitHub response:", e)
            break

        # stop when no more commits or an error message object is returned
        if not commits or (isinstance(commits, dict) and commits.get("message")):
            break

        all_commits.extend(commits)
        page += 1
        # If caller only requested a limited number of recent commits, stop when we have enough
        if latest and len(all_commits) >= latest:
            break

    logging.info(f"📦 Total commits fetched: {len(all_commits)}")

    fieldnames = ["UserStoryID", "CommitSHA", "Author", "Message", "FileChanged", "ChangedFunctions", "Language"]
    file_exists = os.path.exists(output_file)

    # Ensure the output directory exists
    output_dir = os.path.dirname(output_file)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    with open(output_file, mode="a", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()

        matched_any = False
        for commit in all_commits:
            msg = commit["commit"]["message"]
            # If latest mode is enabled, process unconditionally (we'll still honor last_only later)
            if latest:
                match_us = True
            else:
                match_us = bool(re.match(rf"^{re.escape(user_story_id)}\b[:\s-]?", msg.strip(), re.IGNORECASE))

            if match_us:
                matched_any = True
                sha = commit["sha"]
                author = commit["commit"]["author"]["name"]
                clean_msg = msg.replace("\n", "\\n").strip()

                logging.info(f"Commit: {sha} Author: {author} Message: {clean_msg[:120]}...")

                files_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/commits/{sha}"
                details = requests.get(files_url, headers=headers).json()
                files = details.get("files", [])

                for file in files:
                    filename = file["filename"]
                    patch = file.get("patch", "")
                    # detect language from file extension (basic)
                    _, ext = os.path.splitext(filename.lower())
                    ext_map = {
                        '.py': 'python', '.js': 'javascript', '.ts': 'typescript',
                        '.java': 'java', '.cs': 'csharp', '.go': 'go', '.php': 'php',
                        '.cpp': 'cpp', '.c': 'c', '.h': 'c', '.jsx': 'javascript', '.tsx': 'typescript'
                    }
                    language = ext_map.get(ext, 'unknown')

                    # Extract added function names based on language
                    added_functions = []
                    
                    if language == 'python' and patch:
                        # Python: def function_name(
                        added_functions = re.findall(r"^\+def\s+([a-zA-Z_][a-zA-Z0-9_]*)", patch, flags=re.MULTILINE)
                    
                    elif language == 'java' and patch:
                        # Java: public/private/protected void/String/etc functionName(
                        java_patterns = [
                            r"^\+\s*(public|private|protected)?\s+(static)?\s*(\w+)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(",
                            r"^\+\s*(\w+)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\("
                        ]
                        for pattern in java_patterns:
                            matches = re.findall(pattern, patch, flags=re.MULTILINE)
                            for match in matches:
                                if isinstance(match, tuple):
                                    func_name = match[-1]  # Last group is always the function name
                                else:
                                    func_name = match
                                if func_name and func_name.lower() not in ('if', 'for', 'while', 'switch', 'class'):
                                    added_functions.append(func_name)
                    
                    elif language in ('javascript', 'typescript') and patch:
                        # JavaScript/TypeScript patterns:
                        # function name(), const name = (), export function name()
                        js_patterns = [
                            r"^\+\s*(export\s+)?(async\s+)?function\s+([a-zA-Z_][a-zA-Z0-9_]*)",  # function declaration
                            r"^\+\s*(export\s+)?(const|let|var)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(async\s*)?\(",  # const func = ()
                            r"^\+\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\(\s*.*?\s*\)\s*{",  # arrow function or method
                        ]
                        for pattern in js_patterns:
                            matches = re.findall(pattern, patch, flags=re.MULTILINE)
                            for match in matches:
                                if isinstance(match, tuple):
                                    func_name = [m for m in match if m and not m in ('export', 'async', 'const', 'let', 'var')][-1]
                                else:
                                    func_name = match
                                if func_name and func_name.lower() not in ('if', 'for', 'while', 'switch', 'class'):
                                    added_functions.append(func_name)
                    
                    elif language == 'csharp' and patch:
                        # C#: public/private void/string FunctionName()
                        csharp_patterns = [
                            r"^\+\s*(public|private|protected)?\s+(static)?\s*(\w+)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(",
                        ]
                        for pattern in csharp_patterns:
                            matches = re.findall(pattern, patch, flags=re.MULTILINE)
                            for match in matches:
                                if isinstance(match, tuple):
                                    func_name = match[-1]
                                else:
                                    func_name = match
                                if func_name:
                                    added_functions.append(func_name)

                    # Remove duplicates while preserving order
                    added_functions = list(dict.fromkeys(added_functions))

                    joined_functions = ", ".join(added_functions) if added_functions else ""

                    writer.writerow({
                        "UserStoryID": user_story_id,
                        "CommitSHA": sha,
                        "Author": author,
                        "Message": clean_msg,
                        "FileChanged": filename,
                        "ChangedFunctions": joined_functions,
                        "Language": language
                    })

                # if only the most recent match is desired, stop after first match
                if last_only:
                    break

        # If latest mode is enabled, and we only wanted N recent commits, we can stop after writing
        if latest:
            # We processed up to `latest` commits (we collected that many). Inform and return.
            logging.info(f"Processed latest {min(latest, len(all_commits))} commits for {repo_owner}/{repo_name}")
            return

        if not matched_any:
            logging.info(f"No commits found matching user story id: {user_story_id}")

    logging.info(f"\n✅ Data written/appended successfully to: {output_file}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Fetch commits from GitHub and report files/functions added for a user story id")
    parser.add_argument("--user_story_id", required=False, help="User story id to search for (e.g. US-12)")
    # keep these None by default so we can fill from config
    parser.add_argument("--repo_owner", default=None, help="GitHub repo owner")
    parser.add_argument("--repo_name", default=None, help="GitHub repo name")
    parser.add_argument("--output_file", default=None, help="CSV output file")
    parser.add_argument("--last_only", action="store_true", help="Only write the most recent matching commit")
    parser.add_argument("--latest", type=int, default=0, help="If set, process the most recent N commits (no user_story filter)")

    args = parser.parse_args(argv)

    # Ensure --user_story_id is required only if --latest is not specified
    if not args.latest and not args.user_story_id:
        parser.error("--user_story_id is required unless --latest is specified.")

    cfg = _load_config_fallback() or {}
    # configure logging
    try:
        # try to setup logging via config_loader
        try:
            import config_loader as cl
            cl.setup_logging(cfg.get('log_file'))
        except Exception:
            # fallback to our earlier package import
            try:
                _cfg.setup_logging(cfg.get('log_file'))
            except Exception:
                pass
    except Exception:
        pass

    repo_owner = args.repo_owner or cfg.get('repo_owner') or 'lingeshloganathan'
    repo_name = args.repo_name or cfg.get('repo_name') or 'python-testcase'
    output_file = args.output_file or cfg.get('output_file') 
    print(output_file)

    find_and_write_commits(args.user_story_id, repo_owner, repo_name, output_file, args.last_only, args.latest)


if __name__ == '__main__':
    main()