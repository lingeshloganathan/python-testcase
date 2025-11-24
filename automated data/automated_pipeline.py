import os
import json
import csv
import logging
import sys
from tree_sitter import Language, Parser

# === FIX: Add project root FIRST so we can import config_loader ===
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# load centralized config and logging
print(PROJECT_ROOT)
config_loader = None
_conf = {}
try:
    import config_loader
    config_loader.setup_logging()
    _conf = config_loader.load_config()
    logging.info("✅ Config loaded via config_loader")
except Exception as e:
    logging.warning("⚠️ Config loading failed: %s; using fallback", e)
    # Fallback: load config.json directly
    try:
        config_path = os.path.join(PROJECT_ROOT, 'config.json')
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                _conf = json.load(f)
            logging.basicConfig(level=logging.INFO)
            logging.info("✅ Config loaded from %s", config_path)
    except Exception as e2:
        logging.basicConfig(level=logging.INFO)
        logging.warning("⚠️ Fallback config load also failed: %s", e2)
        _conf = {}

# === CONFIGURATION ===
PROJECT_PATH = _conf.get('app_deps') 
app_deps = _conf.get('project_path')
print("Using app_deps:", app_deps)


logger = logging.getLogger(__name__)

# Validate app_deps
if not app_deps:
    logger.error("❌ app_deps not configured in config.json. Cannot proceed.")
    exit(1)

logger.info("🔍 Using app_deps: %s", app_deps)

# === OUTPUT PATHS ===
if os.path.isfile(app_deps):
    base_name = "app"
    OUTPUT_JSON = os.path.join(PROJECT_PATH, base_name + "_dependencies.json")
    OUTPUT_CSV = os.path.join(PROJECT_PATH, base_name + "_dependencies.csv")
    print(OUTPUT_JSON)
else:
    OUTPUT_JSON = os.path.join(PROJECT_PATH, "app_dependencies.json")
    OUTPUT_CSV = os.path.join(PROJECT_PATH, "app_dependencies.csv")
    print(OUTPUT_JSON)

# === LANGUAGE DETECTION ===
LANGUAGE_MAP = {
    '.py': 'python',
    '.java': 'java',
    '.js': 'javascript',
    '.ts': 'typescript',
    '.tsx': 'typescript',
    '.jsx': 'javascript',
    '.cs': 'csharp',
    '.go': 'go',
    '.php': 'php',
    '.cpp': 'cpp',
    '.cc': 'cpp',
    '.cxx': 'cpp',
    '.c': 'c',
}

# === LANGUAGE PARSERS ===
PARSERS = {}

def get_parser(language):
    """Lazy-load Tree-sitter parser for given language."""
    if language in PARSERS:
        return PARSERS[language]
    
    try:
        lang = None
        if language == 'python':
            import tree_sitter_python as ts_lang
            lang = Language(ts_lang.language())
        elif language == 'java':
            import tree_sitter_java as ts_lang
            lang = Language(ts_lang.language())
        elif language == 'javascript':
            import tree_sitter_javascript as ts_lang
            lang = Language(ts_lang.language())
        elif language == 'typescript':
            import tree_sitter_typescript as ts_lang
            # TypeScript has language_typescript function
            lang = Language(ts_lang.language_typescript())
        elif language == 'csharp':
            import tree_sitter_c_sharp as ts_lang
            lang = Language(ts_lang.language())
        elif language == 'go':
            import tree_sitter_go as ts_lang
            lang = Language(ts_lang.language())
        elif language == 'php':
            import tree_sitter_php as ts_lang
            # PHP has language_php function
            lang = Language(ts_lang.language_php())
        elif language == 'cpp':
            import tree_sitter_cpp as ts_lang
            lang = Language(ts_lang.language())
        elif language == 'c':
            import tree_sitter_c as ts_lang
            lang = Language(ts_lang.language())
        else:
            logger.warning("⚠️ Unsupported language: %s", language)
            return None
        
        if lang is None:
            logger.warning("⚠️ Failed to load language for: %s", language)
            return None
            
        parser = Parser(lang)
        PARSERS[language] = parser
        logger.info("✅ Loaded parser for %s", language)
        return parser
    except (ImportError, AttributeError) as e:
        logger.warning("⚠️ Tree-sitter parser not available for %s: %s", language, e)
        return None



def get_node_text(node, code_bytes):
    """Extract text content for any Tree-sitter node."""
    return code_bytes[node.start_byte:node.end_byte].decode("utf8", errors="ignore")


def extract_dependencies_generic(node, code_bytes, language, seen=None):
    """
    Recursively find all unique function call dependencies for any language.
    - Deduplicates repeated calls
    - Preserves order of first occurrence
    """
    if seen is None:
        seen = set()
    deps = []
    
    # Function call node types vary by language
    call_node_types = {
        'python': 'call',
        'java': 'method_invocation',
        'javascript': 'call_expression',
        'typescript': 'call_expression',
        'csharp': 'invocation_expression',
        'go': 'call_expression',
        'php': 'object_creation_expression',  # or method call
        'cpp': 'call_expression',
        'c': 'call_expression',
    }
    
    call_type = call_node_types.get(language, 'call')
    
    if node.type == call_type:
        try:
            # Extract function name based on language specifics
            func_name = None
            if language == 'python':
                func_node = node.child_by_field_name("function")
                if func_node:
                    func_name = get_node_text(func_node, code_bytes).strip()
            elif language == 'java':
                # method_invocation: object.method()
                for child in node.children:
                    if child.type == 'identifier':
                        func_name = get_node_text(child, code_bytes).strip()
                        break
            elif language in ('javascript', 'typescript', 'cpp', 'c', 'go'):
                # call_expression: func()
                func_node = node.child_by_field_name("function")
                if func_node:
                    func_name = get_node_text(func_node, code_bytes).strip()
            elif language == 'csharp':
                # invocation_expression
                for child in node.children:
                    if child.type in ('identifier', 'member_access_expression'):
                        func_name = get_node_text(child, code_bytes).strip()
                        break
            
            if func_name and func_name not in seen:
                seen.add(func_name)
                deps.append(func_name)
        except Exception as e:
            logger.warning("⚠️ Error extracting call in %s: %s", language, e)
    
    # Recursively process children
    for child in node.children:
        deps.extend(extract_dependencies_generic(child, code_bytes, language, seen))
    
    return deps


def find_function_defs_generic(node, code_bytes, language):
    """
    Recursively find all function/method definitions for any language.
    Returns list of (function_name, node) tuples.
    """
    functions = []
    
    # Function definition node types vary by language
    def_node_types = {
        'python': 'function_definition',
        'java': 'method_declaration',
        'javascript': 'function_declaration',
        'typescript': 'function_declaration',
        'csharp': 'method_declaration',
        'go': 'function_declaration',
        'php': 'function_declaration',
        'cpp': 'function_definition',
        'c': 'function_definition',
    }
    
    def_type = def_node_types.get(language, 'function_definition')
    
    if node.type == def_type:
        try:
            func_name = None
            if language in ('python', 'javascript', 'typescript', 'go', 'php'):
                name_node = node.child_by_field_name("name")
                if name_node:
                    func_name = get_node_text(name_node, code_bytes).strip()
            elif language == 'java':
                # method_declaration: modifiers type name params body
                for child in node.children:
                    if child.type == 'identifier':
                        func_name = get_node_text(child, code_bytes).strip()
                        break
            elif language == 'csharp':
                # method_declaration
                for child in node.children:
                    if child.type == 'identifier':
                        func_name = get_node_text(child, code_bytes).strip()
                        break
            elif language in ('cpp', 'c'):
                # function_definition: decl body
                decl = node.child_by_field_name("declarator")
                if decl:
                    func_name = get_node_text(decl, code_bytes).strip()
                    # Remove type prefixes and trailing ( for C/C++
                    if '(' in func_name:
                        func_name = func_name[:func_name.index('(')].strip()
            
            if func_name:
                functions.append((func_name, node))
        except Exception as e:
            logger.warning("⚠️ Error extracting function def in %s: %s", language, e)
    
    # Recursively process children
    for child in node.children:
        functions.extend(find_function_defs_generic(child, code_bytes, language))
    
    return functions


def build_dependency_graph_generic(code, language):
    """
    Build dependency graph for code in any supported language.
    Returns dict: {function_name: [dependencies]}
    """
    parser = get_parser(language)
    if not parser:
        logger.warning("⚠️ Parser unavailable for %s; skipping", language)
        return {}
    
    try:
        code_bytes = bytes(code, "utf8")
        tree = parser.parse(code_bytes)
        root = tree.root_node
        graph = {}
        
        for func_name, func_node in find_function_defs_generic(root, code_bytes, language):
            deps = extract_dependencies_generic(func_node, code_bytes, language)
            graph[func_name] = deps
        
        return graph
    except Exception as e:
        logger.exception("⚠️ Error building dependency graph for %s: %s", language, e)
        return {}


def scan_files_by_language(base_path, exclude_dirs=None):
    """Recursively scan for source files by supported extensions."""
    if exclude_dirs is None:
        exclude_dirs = {
            "venv",
            "__pycache__",
            ".git",
            ".github",
            ".vscode",
            "node_modules",
            "env",
            "dist",
            "build",
            "target",
            "bin",
            "obj",
        }

    source_files = {}
    for root, dirs, files in os.walk(base_path):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in LANGUAGE_MAP:
                lang = LANGUAGE_MAP[ext]
                if lang not in source_files:
                    source_files[lang] = []
                source_files[lang].append(os.path.join(root, file))
    return source_files


# === MAIN ===
if __name__ == "__main__":
    logger.info("🔍 Scanning path: %s", app_deps)

    all_dependencies = {}

    # Case 1: Single file
    if os.path.isfile(app_deps):
        logger.info("📄 Detected single file mode.")
        ext = os.path.splitext(app_deps)[1].lower()
        if ext not in LANGUAGE_MAP:
            logger.error("❌ Unsupported file extension: %s", ext)
            exit(1)
        language = LANGUAGE_MAP[ext]
        files_by_lang = {language: [app_deps]}

    # Case 2: Folder
    elif os.path.isdir(app_deps):
        logger.info("📁 Detected folder mode — scanning recursively...")
        files_by_lang = scan_files_by_language(app_deps)
        total_files = sum(len(f) for f in files_by_lang.values())
        logger.info("✅ Found %d source files across %d language(s): %s", 
                    total_files, len(files_by_lang), ', '.join(files_by_lang.keys()))

    else:
        logger.error("❌ Invalid path. Please provide a valid file or folder.")
        exit(1)

    processed = 0
    skipped = 0
    
    # Process files by language
    for language, file_list in sorted(files_by_lang.items()):
        logger.info("\n🔄 Processing %d %s file(s)...", len(file_list), language.upper())
        
        for file_path in file_list:
            try:
                with open(file_path, "r", encoding="utf8", errors="ignore") as f:
                    code = f.read()
                
                deps = build_dependency_graph_generic(code, language)
                all_dependencies[file_path] = deps or {}
                processed += 1
                
                if processed % 10 == 0:
                    logger.info("⏳ Processed %d file(s)...", processed)
                    
            except Exception as e:
                logger.warning("⚠️ Skipping %s: %s", file_path, e)
                skipped += 1

    # === SAVE RESULTS ===
    logger.info("\n✅ Finished scanning %d file(s) (%d skipped).", processed, skipped)
    logger.info("✅ Files with dependencies found: %d", sum(bool(v) for v in all_dependencies.values()))

    if not all_dependencies:
        logger.warning("⚠️ No dependencies detected.")
        exit(0)

    # Save JSON
    with open(OUTPUT_JSON, "w", encoding="utf8") as jf:
        json.dump(all_dependencies, jf, indent=2, ensure_ascii=False)
    logger.info("📦 Saved JSON → %s", OUTPUT_JSON)

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
    logger.info("📊 Saved CSV → %s", OUTPUT_CSV)

    # === PRINT SAMPLE OUTPUT ===
    logger.info("\n📘 Sample Output:")
    for i, (fname, funcs) in enumerate(all_dependencies.items()):
        logger.info("\n📄 %s", fname)
        if funcs:
            for func, calls in list(funcs.items())[:5]:  # limit to first 5 functions
                logger.info("  └─ %s: %s", func, calls[:3])  # limit to first 3 calls
        else:
            logger.info("  ⚠️ No functions or dependencies found.")
        if i >= 2:  # limit display to 3 files
            break
