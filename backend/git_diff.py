import requests
import re
import csv
import os

repo_owner = "lingeshloganathan"
repo_name = "python-testcase"

# storyid=["US-01","US-02","US-03","US-04","US-05","US-06","US-07","US-08","US-09","US-10"]

# for id in storyid:
#     print(id)
user_story_id = "US-12"

# Optional: authentication for private repos
# GITHUB_TOKEN = "ghp_your_generated_token_here"
# headers = {
#     "Authorization": f"token {GITHUB_TOKEN}",
#     "Accept": "application/vnd.github.v3+json"
# }
headers = {"Accept": "application/vnd.github.v3+json"}

# === Fetch ALL commits (pagination handling) ===
all_commits = []
page = 1
while True:
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/commits"
    print(url)
    params = {"per_page": 100, "page": page}
    response = requests.get(url, headers=headers, params=params)
    commits = response.json()

    # Break when no more pages
    if not commits or isinstance(commits, dict) and commits.get("message"):
        break

    all_commits.extend(commits)
    page += 1

print(f"📦 Total commits fetched: {len(all_commits)}")

# === CSV setup ===
output_file = r"D:\data-learn\python-testcase\backend\userstory_commit_report.csv"
fieldnames = ["UserStoryID", "CommitSHA", "Author", "Message", "FileChanged", "ChangedFunctions"]

file_exists = os.path.exists(output_file)
with open(output_file, mode="a", newline="", encoding="utf-8") as csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    if not file_exists:
        writer.writeheader()

    # === Process commits ===
    for commit in all_commits:
        msg = commit["commit"]["message"]
        # Match only if commit starts with this US-ID (not just contains)
        if re.match(rf"^{user_story_id}\b[:\s-]?", msg.strip(), re.IGNORECASE):
            sha = commit["sha"]
            author = commit["commit"]["author"]["name"]
            clean_msg = msg.replace("\n", "\\n").strip()  # remove newlines and strip

            print(f"\n🔹 Commit: {sha}")
            print(f"👤 Author: {author}")
            print(f"💬 Message: {clean_msg[:120]}...")

            # Get file change details
            files_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/commits/{sha}"
            details = requests.get(files_url, headers=headers).json()
            files = details.get("files", [])

            for file in files:
                filename = file["filename"]
                patch = file.get("patch", "")

                added_functions = re.findall(r"^\+def\s+([a-zA-Z_][a-zA-Z0-9_]*)", patch, flags=re.MULTILINE)
                joined_functions = ", ".join(added_functions) if added_functions else ""

                # === Write to CSV ===
                writer.writerow({
                    "UserStoryID": user_story_id,
                    "CommitSHA": sha,
                    "Author": author,
                    "Message": clean_msg,
                    "FileChanged": filename,
                    "ChangedFunctions": joined_functions
                })

print(f"\n✅ Data written/appended successfully to: {output_file}")