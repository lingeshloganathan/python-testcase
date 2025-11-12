import os
import json
import csv
from tree_sitter import Language, Parser
import tree_sitter_python as tspython

# === CONFIGURATION ===
PROJECT_PATH = r"D:\data-learn\python-testcase\backend\app.py" 

# === OUTPUT PATHS ===
if os.path.isfile(PROJECT_PATH):
    base_name = os.path.splitext(PROJECT_PATH)[0]
    OUTPUT_JSON = base_name + "_dependencies.json"
    OUTPUT_CSV = base_name + "_dependencies.csv"
else:
    OUTPUT_JSON = os.path.join(PROJECT_PATH, "function_dependencies.json")
    OUTPUT_CSV = os.path.join(PROJECT_PATH, "function_dependencies.csv")


PY_LANGUAGE = Language(tspython.language())
parser = Parser(PY_LANGUAGE)



def get_node_text(node, code_bytes):
    """Extract text content for any Tree-sitter node."""
    return code_bytes[node.start_byte:node.end_byte].decode("utf8")


def extract_dependencies(node, code_bytes, seen=None):
    """
    Recursively find all unique function call dependencies inside a node.
    - Deduplicates repeated calls
    - Preserves order of first occurrence
    """
    if seen is None:
        seen = set()
    deps = []
    if node.type == "call":
        func_node = node.child_by_field_name("function")
        if func_node:
            func_name = get_node_text(func_node, code_bytes)
            if func_name not in seen:
                seen.add(func_name)
                deps.append(func_name)
    for child in node.children:
        deps.extend(extract_dependencies(child, code_bytes, seen))
    return deps


def find_function_defs(node, code_bytes):
    functions = []
    if node.type == "function_definition":
        name_node = node.child_by_field_name("name")
        if name_node:
            func_name = get_node_text(name_node, code_bytes)
            functions.append((func_name, node))
    for child in node.children:
        functions.extend(find_function_defs(child, code_bytes))
    return functions


def build_dependency_graph(code):
    code_bytes = bytes(code, "utf8")
    tree = parser.parse(code_bytes)
    root = tree.root_node
    graph = {}
    for func_name, func_node in find_function_defs(root, code_bytes):
        deps = extract_dependencies(func_node, code_bytes)
        graph[func_name] = deps
    return graph


def scan_python_files(base_path, exclude_dirs=None):
    """Recursively scan for .py files, skipping unwanted directories."""
    if exclude_dirs is None:
        exclude_dirs = {
            "venv",
            "__pycache__",
            ".git",
            ".github",
            ".vscode",
            "node_modules",
            "env",
        }

    py_files = []
    for root, dirs, files in os.walk(base_path):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for file in files:
            if file.endswith(".py"):
                py_files.append(os.path.join(root, file))
    return py_files


# === MAIN ===
if __name__ == "__main__":
    print(f"🔍 Scanning path: {PROJECT_PATH}\n")

    all_dependencies = {}

    # Case 1: Single file
    if os.path.isfile(PROJECT_PATH):
        print("📄 Detected single file mode.\n")
        py_files = [PROJECT_PATH]

    # Case 2: Folder
    elif os.path.isdir(PROJECT_PATH):
        print("📁 Detected folder mode — scanning recursively...\n")
        py_files = scan_python_files(PROJECT_PATH)
        print(f"✅ Found {len(py_files)} Python files.\n")

    else:
        print("❌ Invalid path. Please provide a valid file or folder.")
        exit(1)

    processed = 0
    for file_path in py_files:
        try:
            with open(file_path, "r", encoding="utf8") as f:
                code = f.read()
            deps = build_dependency_graph(code)
            all_dependencies[file_path] = deps or {}
            processed += 1
            if processed % 10 == 0:
                print(f"⏳ Processed {processed}/{len(py_files)} files...")
        except Exception as e:
            print(f"⚠️ Skipping {file_path}: {e}")

    # === SAVE RESULTS ===
    print(f"\n✅ Finished scanning {processed} file(s).")
    print(f"✅ Files with dependencies found: {sum(bool(v) for v in all_dependencies.values())}\n")

    if not all_dependencies:
        print("⚠️ No dependencies detected.")
        exit(0)

    # Save JSON
    with open(OUTPUT_JSON, "w", encoding="utf8") as jf:
        json.dump(all_dependencies, jf, indent=2, ensure_ascii=False)
    print(f"📦 Saved JSON → {OUTPUT_JSON}")

    # Save CSV
    with open(OUTPUT_CSV, "w", newline="", encoding="utf8") as cf:
        writer = csv.writer(cf)
        writer.writerow(["File", "Function", "Dependencies"])
        for file, funcs in all_dependencies.items():
            if funcs:
                for func_name, deps in funcs.items():
                    writer.writerow([file, func_name, ", ".join(deps)])
            else:
                writer.writerow([file, "(no functions)", ""])
    print(f"📊 Saved CSV → {OUTPUT_CSV}")

    # === PRINT SAMPLE OUTPUT ===
    print("\n📘 Sample Output:")
    for i, (fname, funcs) in enumerate(all_dependencies.items()):
        print(f"\n📄 {fname}")
        if funcs:
            for func, calls in funcs.items():
                print(f"  └─ {func}: {calls}")
        else:
            print("  ⚠️ No functions or dependencies found.")
        if i >= 2:  # limit display
            break
