import re
import os
import time
import json
import unicodedata
from utils.utils import log_info, log_error
import utils.utils as utils
from infrastructure.auth_google import get_gspread_client, get_sheet_title
from core.models.student_submission import StudentSubmission, save_students_to_json, load_students_from_json

def update_final_grade_for_no_submission_json(json_path):
    try:
        students = load_students_from_json(json_path)
        updated = False

        for student in students:
            entregou = int(student.entregou)
            nota_total = student.nota_total.strip() if student.nota_total else ""

            if entregou == 0:
                if nota_total not in ("0", "", None):
                    student.update_field("nota_total", "0")
                    student.add_comment("O aluno tirou 100 no beecrowd, mas a entrega no classroom foi zerada.")
                    updated = True

        if updated:
            save_students_to_json(students, json_path)
            log_info(f"Arquivo atualizado com notas zeradas e comentários: {json_path}")
        else:
            log_info(f"Nenhuma alteração necessária em {json_path}")

    except Exception as e:
        log_error(f"Erro ao processar o arquivo JSON {json_path}: {e}")


def normalize_token(s: str) -> str:
    s = unicodedata.normalize('NFD', s)
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    s = re.sub(r'[^A-Za-z0-9]+', '', s)
    return s.upper()

def extract_turma_letter(text: str) -> str:
    m = re.search(r'TURMA\s*([A-Z])', text, re.IGNORECASE)
    return m.group(1).upper() if m else ''

def title_has_turma(title: str, letter: str) -> bool:
    if not letter:
        return True  
    T = unicodedata.normalize('NFKD', title).encode('ASCII', 'ignore').decode().upper()

    return (
        re.search(rf'\bTURMA\s*{letter}\b', T) or
        re.search(rf'\bTURMA{letter}\b', T) or
        re.search(rf'_TURMA_{letter}\b', T) or
        re.search(rf'^\s*{letter}\s*[-–—]\s*', T) or
        re.search(rf'[-–—]\s*{letter}\s*[-–—]', T)
    )

def list_tokens(list_name: str):
   
    base = normalize_token(list_name)                
    tokens = {base}

    m = re.search(r'LISTA\s*0*([0-9]+)', list_name, re.IGNORECASE)
    if m:
        n = m.group(1).lstrip('0') or '0'
        tokens.add(f'LISTA{n}')                        
        tokens.add(f'LISTA{int(m.group(1)):02d}')      

    return tokens

def read_id_from_file_beecrowd(filename, list_name, classroom_name):
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            sheet_ids = [line.strip() for line in file if line.strip()]

        turma_letter = extract_turma_letter(classroom_name)  
        list_name_tokens = list_tokens(list_name)            

        for sheet_id in sheet_ids:
            sheet_title = get_sheet_title(sheet_id)
            if not sheet_title:
                log_info(f"Ignorando planilha {sheet_id}, pois não foi possível obter o título.")
                continue

            normalized_title = normalize_token(sheet_title)

            list_ok = any(token in normalized_title for token in list_name_tokens)
            turma_ok = title_has_turma(sheet_title, turma_letter)

            if not list_ok and 'LISTA' not in ''.join(list_name_tokens):
                loose = normalize_token(list_name.replace('-', ' '))
                list_ok = loose in normalized_title

            if list_ok and turma_ok:
                log_info(f"Correspondência encontrada: {sheet_title}")
                return sheet_id

        print(f"Não foi encontrado o sheet id da planilha do Beecrowd da {list_name}, da {classroom_name}.")
        return None

    except FileNotFoundError:
        log_info(f"Arquivo {filename} não encontrado.")
        return None
    except Exception as e:
        log_error(f"Erro ao ler o id da planilha do arquivo {filename}: {e}")
        return None
    
def update_grades_json(sheet_id1, student_json_path, score, classroom_name):
    try:
        client = get_gspread_client()
        worksheet1 = client.open_by_key(sheet_id1).get_worksheet(0)

        emails = [email.strip().lower() for email in worksheet1.col_values(6)[1:] if email]
        percentages = [percent.strip() for percent in worksheet1.col_values(10)[1:] if percent]

        log_info(f"\nProcurando os emails {emails}")
        print("\nAtualizando notas no JSON com base na planilha Beecrowd...\n")

        students = load_students_from_json(student_json_path)

        if isinstance(score, dict):
            score_values = {key: float(value) for key, value in score.items()}
            score_sum = float(sum(score_values.values()))
        else:
            log_info("\nPontuação não fornecida, usando 100 como base.")
            score_sum = 100

        updated_emails = []
        not_found_emails = []

        for email, percentage in zip(emails, percentages):
            if not email:
                continue

            time.sleep(1)
            match_found = False

            for student in students:
                if student.email.strip().lower() == email:
                    if percentage == "100":
                        student.update_field("nota_total", str(score_sum))
                        student.add_comment("")
                    elif percentage == "0":
                        student.update_field("nota_total", "0")
                        student.add_comment("O aluno tirou 0 no beecrowd.")
                    updated_emails.append(email)
                    match_found = True
                    break

            if not match_found and percentage in ("100", "0"):
                not_found_emails.append((email, percentage))

        save_students_to_json(students, student_json_path)

        log_info(f"\n{len(updated_emails)} alunos atualizados no JSON.")
        print(f"\n{len(updated_emails)} alunos atualizados no JSON.")

        save_not_found_emails(not_found_emails, classroom_name)

    except Exception as e:
        log_error(f"Erro ao atualizar JSON com notas do Beecrowd: {e}")

def save_not_found_emails(not_found_emails, classroom_name, filename="not_found_emails_100_or_0.txt"):
    if not_found_emails:
        
        base_folder = utils.FOLDER_PATH if utils.FOLDER_PATH else "output"
        output_folder = os.path.join(base_folder, "output") if not base_folder.endswith("output") else base_folder

        os.makedirs(output_folder, exist_ok=True)
        full_path = os.path.join(output_folder, filename)

        with open(full_path, "a", encoding="utf-8") as file:
            file.write(f"\n{classroom_name}\n")
            for email, percentage in not_found_emails:
                file.write(f"{email}\t{percentage}\n")

        print(f"\nAlguns emails não foram encontrados no JSON. Veja o arquivo {full_path}.")

def compare_emails(sheet_id_beecrowd, student_json_path, classroom_name):
    try:
        client = get_gspread_client()
        worksheet1 = client.open_by_key(sheet_id_beecrowd).get_worksheet(0)

        emails_beecrowd = set(email.strip().lower() for email in worksheet1.col_values(6)[1:] if email)

        with open(student_json_path, "r", encoding="utf-8") as f:
            students = json.load(f)

        emails_json = set(student["email"].strip().lower() for student in students if "email" in student)

        only_in_beecrowd = emails_beecrowd - emails_json
        only_in_json = emails_json - emails_beecrowd

        students_objs = load_students_from_json(student_json_path)
        updated_count = 0

        for student in students_objs:
            email_lower = (student.email or "").strip().lower()
            if email_lower in only_in_json:
                student.add_comment("Aluno não está no Beecrowd.")
                updated_count += 1

        if updated_count > 0:
            save_students_to_json(students_objs, student_json_path)

        base_folder = utils.FOLDER_PATH if utils.FOLDER_PATH else "output"
        output_folder = os.path.join(base_folder, "output") if not base_folder.endswith("output") else base_folder

        os.makedirs(output_folder, exist_ok=True)
        file_path = os.path.join(output_folder, "email_differences.txt")

        with open(file_path, "a", encoding="utf-8") as file:
            file.write(f"\nClassroom: {classroom_name}\n")
            file.write("Beecrowd\n")
            for email in sorted(only_in_beecrowd):
                file.write(f"{email}\n")

            file.write("\nClassroom \n")
            for email in sorted(only_in_json):
                file.write(f"{email}\n")

        print(f"\nArquivo '{file_path}' criado com sucesso. Nele você confere os e-mails que existem apenas em uma das plataformas.")

    except Exception as e:
        log_error(f"Erro ao comparar e-mails entre Beecrowd e JSON: {str(e)}")

def fill_scores_for_students_json(json_path, num_questions, score=None):
    try:
        students = load_students_from_json(json_path)

        score_values = {}
        if score is not None:
            for key, value in score.items():
                try:
                    score_values[key] = float(value)
                except ValueError:
                    continue
            score_sum = sum(score_values.values())
        else:
            score_sum = 100

        for student in students:
            final_score = float(student.nota_total) if student.nota_total.replace('.', '', 1).isdigit() else None

            if num_questions is not None:
                if final_score == score_sum:
                    for i in range(num_questions):
                        question_key = f'q{i+1}'
                        if student.questions.get(question_key) != 0:
                            student.update_field(question_key, score_values.get(question_key, 0))
                elif final_score == 0:
                    for i in range(num_questions):
                        student.update_field(f'q{i+1}', 0)
            else:
                if final_score == 0:
                    student.update_field('q1', 0)

        save_students_to_json(students, json_path)

    except Exception as e:
        log_error(f"Erro ao preencher pontuações no JSON: {e}")
    
