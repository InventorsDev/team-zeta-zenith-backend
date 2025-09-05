import os

EXCLUDE = {"__pycache__", ".git", ".idea", ".vscode", "venv", "env", "node_modules"}

def print_structure(start_path, indent=""):
    folder_name = os.path.basename(start_path) or start_path
    print(indent + folder_name + "/")
    for item in sorted(os.listdir(start_path)):
        if item in EXCLUDE or item.endswith(".pyc"):
            continue
        path = os.path.join(start_path, item)
        if os.path.isdir(path):
            print_structure(path, indent + "    ")
        else:
            print(indent + "    " + item)


print_structure("/Users/user/Downloads/hackathon/")
