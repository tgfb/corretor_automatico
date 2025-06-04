import os
import subprocess
from utils.utils import move_logs_to_base, get_latest_lista_folder

def check_error_log(error_log_path):
    return os.path.exists(error_log_path)

def run_script(script_name, error_log_path):
    print(f"\nExecutando {script_name}...")
    subprocess.run(["python", script_name])
    if check_error_log(error_log_path):
        print(f"\nErro detectado após {script_name}.")
        return False
    return True

def main():
    
    error_log_path = "output/error_log.txt"

    sequence = [
        "download_main.py",
        "moss_main.py",
        "beecrowd_main.py",
        "spreadsheet_main.py" 
    ]

    if os.path.exists(error_log_path):
        os.remove(error_log_path)

    for script in sequence:
        if not run_script(script, error_log_path):
            return

    print("\nTodos os scripts foram executados com sucesso.")
    base_path = get_latest_lista_folder()
    
    if not base_path:
        print("Nenhuma pasta LISTA encontrada em Downloads.")
        return
    move_logs_to_base(base_path)  

if __name__ == "__main__":
    main()
