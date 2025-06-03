import os
from utils.utils import log_info

def log_small_submissions(submissions_folder, num_questions, base_path):
    small_files_log = []

    output_dir = os.path.join(base_path, "output")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "small_files.txt")
    #output_path = os.path.join(base_path, "small_files.txt")

    for i in range(1, num_questions + 1):
        for folder in os.listdir(submissions_folder):
            folder_path = os.path.join(submissions_folder, folder)
            if os.path.isdir(folder_path):
                filename = f"q{i}_{folder}.c"
                filepath = os.path.join(folder_path, filename)
                if os.path.isfile(filepath):
                    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read().strip()
                        if len(content) < 10:
                            small_files_log.append(f"{folder} | q{i} | {filename}")

    with open(output_path, "w", encoding="utf-8") as out:
        out.write("Arquivos muito pequenos detectados:\n\n")
        for line in small_files_log:
            out.write(line + "\n")

    log_info(f"\n{len(small_files_log)} arquivos pequenos foram salvos em: {output_path}")