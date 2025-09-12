import os
import re
import shutil
from datetime import datetime

FOLDER_PATH = None

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
    return list_title

def get_available_turma_letters(service, semester, course_name_filter="PIF"):

    try:
        results = service.courses().list().execute()
        courses = results.get("courses", []) or []
        letters = set()

        for c in courses:
            name = c.get("name", "") or ""
            if semester in name and course_name_filter.upper() in name.upper():
                m = re.search(r'\bTURMA\s*([A-Z])\b', name.upper())
                if m:
                    letters.add(m.group(1))

        found = sorted(letters)
        if not found:
            print(f"Nenhuma turma encontrada para {semester}.\n")
        else:
            print(f"Turmas encontradas no semestre {semester}: {', '.join(found)}")
        return found
    except Exception:
        return ["A", "B"]
    
def get_available_turmas_from_folder(downloads_path: str):

    try:
        letters = set()
        for name in os.listdir(downloads_path):
            m = re.match(r'(students|metadata)_turma([A-Z])\.json$', name, re.IGNORECASE)
            if m:
                letters.add(m.group(2).upper())
        return sorted(letters)
    except Exception:
        return []

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
    global FOLDER_PATH
    try:
        base_folder = FOLDER_PATH if FOLDER_PATH else "output"
        
        os.makedirs(base_folder, exist_ok=True)
        log_path = os.path.join(base_folder, "output_log.txt")

        with open(log_path, "a", encoding="utf-8") as file:
            file.write(f"{message}\n")
    except Exception as e:
        print(f"Erro ao escrever log: {message} - {str(e)}")

def set_log_folder(base_path):
    global FOLDER_PATH
    FOLDER_PATH = os.path.join(base_path, "output") 

def extract_turma_name(classroom_name):
    match = re.search(r'TURMA\s*[A-Z]', classroom_name)
    return match.group().replace(" ", "_") if match else classroom_name

def extract_turma_key(class_name, fallback_letter = None):
 
    if not class_name:
        return f"TURMA {fallback_letter}" if fallback_letter else None

    up_class = class_name.upper()
    m = re.search(r"\bTURMA\s+([A-Z])\b", up_class)
    if m:
        return f"TURMA {m.group(1)}"
    return f"TURMA {fallback_letter}" if fallback_letter else None

