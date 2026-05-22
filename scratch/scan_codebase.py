import ast
import os


def scan_file(file_path):
    with open(file_path, encoding="utf-8") as f:
        content = f.read()

    try:
        tree = ast.parse(content, filename=file_path)
    except SyntaxError as e:
        return {"error": f"Syntax Error: {e}"}

    file_doc = ast.get_docstring(tree)
    classes = []
    functions = []

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            class_doc = ast.get_docstring(node)
            methods = []
            for item in node.body:
                if isinstance(item, (ast.AsyncFunctionDef, ast.FunctionDef)):
                    method_doc = ast.get_docstring(item)
                    args = [arg.arg for arg in item.args.args]
                    methods.append(
                        {"name": item.name, "args": args, "docstring": method_doc}
                    )
            classes.append(
                {"name": node.name, "docstring": class_doc, "methods": methods}
            )
        elif isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            func_doc = ast.get_docstring(node)
            args = [arg.arg for arg in node.args.args]
            functions.append({"name": node.name, "args": args, "docstring": func_doc})

    return {"docstring": file_doc, "classes": classes, "functions": functions}


def scan_dir(directory):
    results = {}
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".py") and not file.startswith("__"):
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, directory)
                results[rel_path] = scan_file(full_path)
    return results


if __name__ == "__main__":
    src_dir = "src/bb_paxdata"
    res = scan_dir(src_dir)

    # Save output to a text file
    with open("scratch/scan_results.txt", "w", encoding="utf-8") as f:
        for path, info in sorted(res.items()):
            f.write(f"=== FILE: {path} ===\n")
            if "error" in info:
                f.write(f"Error: {info['error']}\n\n")
                continue
            if info["docstring"]:
                f.write(f"Docstring: {info['docstring']}\n")
            if info["classes"]:
                f.write("Classes:\n")
                for cls in info["classes"]:
                    f.write(f"  - Class: {cls['name']}\n")
                    if cls["docstring"]:
                        f.write(f"    Doc: {cls['docstring']}\n")
                    if cls["methods"]:
                        f.write("    Methods:\n")
                        for m in cls["methods"]:
                            f.write(f"      * {m['name']}({', '.join(m['args'])})\n")
                            if m["docstring"]:
                                f.write(f"        Doc: {m['docstring']}\n")
            if info["functions"]:
                f.write("Functions:\n")
                for fn in info["functions"]:
                    f.write(f"  - {fn['name']}({', '.join(fn['args'])})\n")
                    if fn["docstring"]:
                        f.write(f"    Doc: {fn['docstring']}\n")
            f.write("\n")
    print("Scanned successfully and saved to scratch/scan_results.txt")
