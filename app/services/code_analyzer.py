import os
import re 
from core.models.student_submission import StudentSubmission, save_students_to_json, load_students_from_json
from utils.utils import log_info, log_error

def log_small_submissions(submissions_folder, num_questions, base_path):
    small_files_log = []

    output_dir = os.path.join(base_path, "output")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "small_files.txt")

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


def apply_small_files_penalties(log_path, students_json_path):
    """
    Lê 'small_files.txt' (linhas '<login> | q<i> | arquivo') e, usando
    StudentSubmission, zera a questão e adiciona comentário em cada aluno.
    Retorna o número de ocorrências aplicadas.
    """
    try:
        if not os.path.isfile(log_path):
            log_error(f"Log de arquivos pequenos não encontrado: {log_path}")
            return 0

        # 1) Carrega alunos como OBJETOS
        students = load_students_from_json(students_json_path)
        by_login = {s.login: s for s in students if getattr(s, "login", "").strip()}

        # 2) Lê e processa o log
        with open(log_path, "r", encoding="utf-8") as f:
            lines = [ln.strip() for ln in f if ln.strip()]

        applied = 0
        for ln in lines:
            if ln.startswith("Arquivos muito pequenos"):
                continue

            # Formato: "<login> | q<i> | <arquivo>"
            parts = [p.strip() for p in ln.split("|")]
            if len(parts) < 2:
                continue

            login, q_key = parts[0], parts[1]
            if not login or not re.match(r"^q\d+$", q_key):
                continue

            student = by_login.get(login)
            if not student:
                # login do log não está no JSON desta turma
                continue

            # 3) Zera a nota e adiciona comentário (via métodos da classe)
            try:
                student.update_field(q_key, 0)
            except Exception as e:
                log_error(f"Erro ao zerar {q_key} de {login}: {e}")

            try:
                msg = f"{q_key} | Erro de requisito. O aluno enviou a questão vazia ou com poucas linhas."
                student.add_comment(msg)
            except Exception as e:
                log_error(f"Erro ao adicionar comentário de {login} ({q_key}): {e}")

            applied += 1

        # 4) Salva de volta como JSON (flatten já é feito por save_students_to_json)
        save_students_to_json(students, students_json_path)
        log_info(f"Penalidades aplicadas a {applied} ocorrência(s) usando objetos StudentSubmission.")
        return applied

    except Exception as e:
        log_error(f"Falha em apply_small_files_penalties_objects: {e}")
        return 0