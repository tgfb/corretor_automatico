import os
import re
import shutil
from datetime import datetime

def read_id_from_file(filename):
    try:
        with open(filename, 'r') as file:
            return file.read().strip()
    except FileNotFoundError:
        return None
    except Exception as e:
        log_error(f"Erro ao ler '{filename}': {e}")
        return None

def format_list_title(list_title):
    match = re.search(r'LISTA\s*(\d+)', list_title.upper())
    if match:
        return f"LISTA {match.group(1).zfill(2)}"
    return "lista"

def extract_prefix(email):
    try:
        return email.split('@')[0]
    except Exception as e:
        log_error(f"Erro ao extrair prefixo do e-mail: {e}")
        return ""

def calculate_delay(due_date_str, submission_date_str):
    try:
        due_date = datetime.strptime(due_date_str, "%Y-%m-%dT%H:%M:%S.%fZ")
        submission_date = datetime.strptime(submission_date_str, "%Y-%m-%dT%H:%M:%S.%fZ")
        delay = submission_date - due_date
        return delay.days + 1 if delay.total_seconds() > 0 else 0
    except Exception as e:
        log_error(f"Erro ao calcular atraso: {e}")
        return 0

def get_due_date(classroom_service, classroom_id, coursework_id):
    try:
        coursework = classroom_service.courses().courseWork().get(
            courseId=classroom_id, id=coursework_id).execute()
        due_date = coursework.get('dueDate')
        due_time = coursework.get('dueTime')

        if due_date:
            year = due_date['year']
            month = due_date['month']
            day = due_date['day']
            hours = due_time.get('hours', 2) if due_time else 2
            minutes = due_time.get('minutes', 59) if due_time else 59
            seconds = due_time.get('seconds', 59) if due_time else 59

            return f"{year}-{month:02d}-{day:02d}T{hours:02d}:{minutes:02d}:{seconds:02d}.000Z"
        return None
    except Exception as e:
        log_error(f"Erro ao obter data de entrega: {e}")
        return None

def get_submission_timestamp(submission, student_id):
    try:
        for history_entry in submission.get('submissionHistory', []):
            state_history = history_entry.get('stateHistory', {})
            if state_history.get('state') == 'TURNED_IN' and state_history.get('actorUserId') == student_id:
                return state_history.get('stateTimestamp')
        return None
    except Exception as e:
        log_error(f"Erro ao obter timestamp da submissão: {e}")
        return None

def log_error(message):
    try:
        os.makedirs("output", exist_ok=True)
        log_path = os.path.join("output", "error_log.txt")
        
        with open(log_path, "a", encoding="utf-8") as file:
            file.write(f"{message}\n")
    except Exception:
        pass

def log_info(message):
    try:
        os.makedirs("output", exist_ok=True)
        log_path = os.path.join("output", "output_log.txt")

        with open(log_path, "a", encoding="utf-8") as file:
            file.write(f"{message}\n")
    except Exception:
        log_error(f"Erro ao escrever log de info: {message}")

def move_logs_to_base(base_path):
    try:
        src_output_dir = "output"
        dest_output_dir = os.path.join(base_path, "output")
        os.makedirs(dest_output_dir, exist_ok=True)

        for log_filename in ["output_log.txt", "check_rename.txt"]:
            src_file = os.path.join(src_output_dir, log_filename)
            if os.path.exists(src_file):
                shutil.move(src_file, os.path.join(dest_output_dir, log_filename))

        if os.path.exists(src_output_dir) and not os.listdir(src_output_dir):
            os.rmdir(src_output_dir)

    except Exception as e:
        print(f"Erro ao mover os arquivos de log: {e}")
