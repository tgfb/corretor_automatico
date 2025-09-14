import os
import re
from typing import Set
from utils.utils import log_info, log_error
from core.models.student_submission import load_students_from_json, save_students_to_json

def humanize_q_list(question_numbers):
    if not question_numbers:
        return ""
    labels = [f"q{n}" for n in question_numbers]
    return labels[0] if len(labels) == 1 else (", ".join(labels[:-1]) + " e " + labels[-1])

def parse_penalty_logs(log_paths):
    penalty_line = re.compile(r'^([^|]+)\|\s*(q\d+)\b', re.IGNORECASE)
    
    penalized = {}

    for log_path in log_paths or []:
        if not log_path or not os.path.isfile(log_path):
            continue

        try:
            with open(log_path, "r", encoding="utf-8", errors="ignore") as handle:
                for raw_line in handle:
                    line = raw_line.strip()
                    match = penalty_line.match(line)
                    if not match:
                        continue
                    login = match.group(1).strip()
                    qkey = match.group(2).lower() 
                    try:
                        qnum = int(qkey[1:])
                    except Exception:
                        continue

                    if login and qnum > 0:
                        if login not in penalized:
                            penalized[login] = set()
                        penalized[login].add(qnum)
        except Exception as e:
            log_error(f"Falha ao ler log de penalidade '{log_path}': {e}")

    return penalized

def present_questions_in_folder(student_folder, student_login, num_questions):
   
    present = set()
    if not os.path.isdir(student_folder):
        return present

    try:
        qfile = re.compile(r'^q(\d+)_([^.\\/]+)\.', re.IGNORECASE)
        for filename in os.listdir(student_folder):
            match = qfile.match(filename)
            if not match:
                continue
            question_number = int(match.group(1))
            if 1 <= question_number <= num_questions:
                file_path = os.path.join(student_folder, filename)
                try:
                    if os.path.isfile(file_path) and os.path.getsize(file_path) > 0:
                        present.add(question_number)
                except OSError:
                    pass
    except Exception as e:
        log_error(f"Erro ao varrer pasta do aluno '{student_login}': {e}")

    return present

def question_score(student, question_number):

    try:
        return getattr(student, f"q{question_number}")
    except Exception:
        return None

def verify_and_comment_valid_questions_considering_penalties(
    final_submissions_folder,
    students_json_by_class,
    num_questions,
    penalty_logs = None,
    treat_zero_as_invalid = True
):
  
    summary = {}

    penalized_map = parse_penalty_logs(penalty_logs or [])

    try:
        for class_letter, students_json_path in students_json_by_class.items():
            students = load_students_from_json(students_json_path)
            commented_count = 0

            for student in students:
                student_login = getattr(student, "login", None) or getattr(student, "student_login", "")
                if not student_login:
                    continue

                student_folder = os.path.join(final_submissions_folder, student_login)
                present_questions = present_questions_in_folder(
                    student_folder=student_folder,
                    student_login=student_login,
                    num_questions=num_questions
                )

                penalized_for_login = penalized_map.get(student_login, set())

                zero_scored_questions: Set[int] = set()
                if treat_zero_as_invalid:
                    for qnum in range(1, num_questions + 1):
                        score_value = question_score(student, qnum)
                        try:
                            numeric_score = float(score_value) if score_value is not None else None
                        except Exception:
                            numeric_score = None
                        if numeric_score is not None and numeric_score == 0.0:
                            zero_scored_questions.add(qnum)

                valid_questions = present_questions - penalized_for_login - zero_scored_questions

                expected_set = set(range(1, num_questions + 1))

                if valid_questions != expected_set:
                    sorted_valid = sorted(valid_questions)
                    if sorted_valid:
                        message = f"Aluno só enviou a {humanize_q_list(sorted_valid)} válidas no Google Classroom."
                    else:
                        message = "Aluno não enviou nenhuma questão válida no Google Classroom."
                    try:
                        student.add_comment(message)
                        commented_count += 1
                    except Exception as e:
                        log_error(f"Falha ao adicionar comentário para {student_login}: {e}")

            try:
                save_students_to_json(students, students_json_path)
            except Exception as e:
                log_error(f"Falha ao salvar JSON da turma {class_letter}: {e}")

            summary[class_letter] = commented_count
            log_info(f"Turma {class_letter}: {commented_count} alunos comentados.")

    except Exception as e:
        log_error(f"Erro na verificação de questões válidas (com penalidades): {e}")

    return summary
