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
    
    

def find_and_write_commits(repo_owner: str = "lingeshloganathan",
                           repo_name: str = "python-testcase",
                           output_file: str = r"D:\data-learn\automated data\userstory_commit_report.csv",
                           latest: int = 0):
    headers = {"Accept": "application/vnd.github.v3+json"}
    logging.info(f"Fetching commits for {repo_owner}/{repo_name}")

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

        # Debug: print API error messages
        if isinstance(commits, dict) and "message" in commits:
            print("GitHub API error:", commits["message"])
            break

        # stop when no more commits or an error message object is returned
        if not commits:
            break

        all_commits.extend(commits)
        page += 1
        if latest and len(all_commits) >= latest:
            break

    print(f"Total commits fetched: {len(all_commits)}")
    if all_commits and isinstance(all_commits[0], dict):
        print("Sample commit keys:", list(all_commits[0].keys()))
        print("Sample commit:", all_commits[0])

    logging.info(f"\U0001F4E6 Total commits fetched: {len(all_commits)}")

    fieldnames = ["UserStoryID", "CommitSHA", "Author", "Message", "FileChanged", "ChangedFunctions", "Language"]
    file_exists = os.path.exists(output_file)

    # Ensure the output directory exists
    output_dir = os.path.dirname(output_file)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    with open(output_file, mode="w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for commit in all_commits:
            sha = commit["sha"]
            author = commit["commit"]["author"]["name"]
            msg = commit["commit"]["message"].replace("\n", "\\n").strip()

            # Extract user story ID from commit message if present (e.g., US-123, STORY-456, etc.)
            user_story_id = ""
            match = re.search(r"\b([A-Z]+-\d+)\b", msg)
            if match:
                user_story_id = match.group(1)

            files_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/commits/{sha}"
            details = requests.get(files_url, headers=headers).json()
            files = details.get("files", [])
            print(f"Commit {sha} has {len(files)} files")
            for file in files:
                filename = file["filename"]
                patch = file.get("patch", "")
                print(f"File: {filename}, Patch exists: {bool(patch)}")
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
                    added_functions = re.findall(r"^\\+def\\s+([a-zA-Z_][a-zA-Z0-9_]*)", patch, flags=re.MULTILINE)
                elif language == 'java' and patch:
                    java_patterns = [
                        r"^\\+\\s*(public|private|protected)?\\s+(static)?\\s*(\\w+)\\s+([a-zA-Z_][a-zA-Z0-9_]*)\\s*\\(",
                        r"^\\+\\s*(\\w+)\\s+([a-zA-Z_][a-zA-Z0-9_]*)\\s*\\("
                    ]
                    for pattern in java_patterns:
                        matches = re.findall(pattern, patch, flags=re.MULTILINE)
                        for match in matches:
                            if isinstance(match, tuple):
                                func_name = match[-1]
                            else:
                                func_name = match
                            if func_name and func_name.lower() not in ('if', 'for', 'while', 'switch', 'class'):
                                added_functions.append(func_name)
                elif language in ('javascript', 'typescript') and patch:
                    js_patterns = [
                        r"^\\+\\s*(export\\s+)?(async\\s+)?function\\s+([a-zA-Z_][a-zA-Z0-9_]*)",
                        r"^\\+\\s*(export\\s+)?(const|let|var)\\s+([a-zA-Z_][a-zA-Z0-9_]*)\\s*=\\s*(async\\s*)?\\(",
                        r"^\\+\\s*([a-zA-Z_][a-zA-Z0-9_]*)\\s*\\(\\s*.*?\\s*\\)\\s*{",
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
                    csharp_patterns = [
                        r"^\\+\\s*(public|private|protected)?\\s+(static)?\\s*(\\w+)\\s+([a-zA-Z_][a-zA-Z0-9_]*)\\s*\\(",
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

                added_functions = list(dict.fromkeys(added_functions))
                joined_functions = ", ".join(added_functions) if added_functions else ""

                writer.writerow({
                    "UserStoryID": user_story_id,
                    "CommitSHA": sha,
                    "Author": author,
                    "Message": msg,
                    "FileChanged": filename,
                    "ChangedFunctions": joined_functions,
                    "Language": language
                })
    logging.info(f"\n✅ Data written/appended successfully to: {output_file}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Fetch all commits from GitHub and report files/functions added.")
    parser.add_argument("--repo_owner", default=None, help="GitHub repo owner")
    parser.add_argument("--repo_name", default=None, help="GitHub repo name")
    parser.add_argument("--output_file", default=None, help="CSV output file")
    parser.add_argument("--latest", type=int, default=0, help="If set, process the most recent N commits.")

    args = parser.parse_args(argv)

    cfg = _load_config_fallback() or {}
    repo_owner = args.repo_owner or cfg.get('repo_owner') or 'lingeshloganathan'
    repo_name = args.repo_name or cfg.get('repo_name') or 'python-testcase'
    output_file = args.output_file or cfg.get('output_file')
    print(output_file)

    find_and_write_commits(repo_owner, repo_name, output_file, args.latest)

if __name__ == '__main__':
    main()