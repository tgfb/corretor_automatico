import os
import re
import shutil
from utils.utils import log_error, log_info
from core.models.student_submission import save_students_to_json, load_students_from_json

def verification_renamed(message):
    try:
        os.makedirs("output", exist_ok=True) 
        file_path = os.path.join("output", "check_rename.txt")
        with open(file_path, "a", encoding="utf-8") as renamed_verification:
            renamed_verification.write(f"{message}\n")
    except Exception as e:
        log_error(f"Não foi possível criar ou escrever no arquivo de verificação: {str(e)}")


def rename_files_based_on_dictionary(submissions_folder, questions_dict, students, haskell=None):
    try:

        for student in students:
            student_login = student.login
            student_folder_path = os.path.join(submissions_folder, student_login)

            if os.path.isdir(student_folder_path):
                log_info(f"\nVerificando pasta do estudante: {student_folder_path}")
    
                used_questions = set()

                for filename in os.listdir(student_folder_path):
                    file_path = os.path.join(student_folder_path, filename)

                    if os.path.isfile(file_path) and not filename.startswith('.'):
                        log_info(f"Verificando arquivo: {filename}")
                        
                        for i in range(1, 5):
                            if haskell == 1:
                                expected_filename = f"q{i}_{student_login}.hs"
                            else:
                                expected_filename = f"q{i}_{student_login}.c"
                            
                            if filename == expected_filename:
                                log_info(f"O arquivo '{filename}' já está no formato correto.")
                                break  

                        else: 
                            base_filename_clean = re.sub(r"\(\d+\)", "", os.path.splitext(filename)[0].lower()) \
                                .replace("_", " ") \
                                .replace(student_login.lower(), "") \
                                .strip()

                            found_match = False  
                            for question_number, possible_names in questions_dict.items():
                                if question_number in used_questions:
                                    continue

                                for possible_name in reversed(possible_names):
                                    possible_name_clean = possible_name.lower().strip()

                                    if base_filename_clean == possible_name_clean:
                                        if haskell == 1:
                                            new_filename = f"q{question_number}_{student_login}.hs"
                                        else:
                                            new_filename = f"q{question_number}_{student_login}.c"

                                        new_file_path = os.path.join(student_folder_path, new_filename)

                                        if filename != new_filename:
                                            os.rename(file_path, new_file_path)
                                            log_info(f"Renomeando: '{filename}' para '{new_filename}' para o estudante '{student_login}'")
                                            used_questions.add(question_number) 
                                            student.update_field('formatacao', 1)
                                            student.add_comment(f"Erro de formatação de arquivo: renomeado: {filename} para {new_filename}")
                                        
                                        found_match = True
                                        break  

                                if found_match:
                                    break  
                        
                            if not found_match:
                                log_info(f"Tentando correspondência parcial para o arquivo {filename}")
                                for question_number, possible_names in questions_dict.items():
                                    if question_number in used_questions:
                                        continue
                                    
                                    for possible_name in reversed(possible_names):
                                        possible_name_clean = possible_name.lower().strip()
                                        possible_name_parts = possible_name_clean.split()
                                        log_info(f"{possible_name_parts}")

                                        if any(part in base_filename_clean for part in possible_name_parts):
                                            if haskell == 1:
                                                new_filename = f"q{question_number}_{student_login}.hs"
                                            else:
                                                new_filename = f"q{question_number}_{student_login}.c"
                                            
                                            new_file_path = os.path.join(student_folder_path, new_filename)

                                            if filename != new_filename:
                                                student.update_field('formatacao', 1)
                                                student.add_comment(f"Erro de formatação no arquivo: tentando correspondência parcial {student_login}: de {filename} para {new_filename}")
                                                verification_renamed(f"{student_login}: de {filename} para {new_filename}")
                                                os.rename(file_path, new_file_path)
                                                log_info(f"Renomeando'{filename}' para '{new_filename}' para o estudante '{student_login}'")
                                                used_questions.add(question_number) 
                                            else:
                                                log_info(f"O arquivo '{filename}' já está com o nome correto.")
                                            found_match = True
                                            break

                                    if found_match:
                                        break

                            if not found_match:
                                student.update_field('formatacao', 1)
                                student.add_comment(f"Erro de formatação no arquivo: não foi encontrado nenhum nome correspondente {student_login}: {filename}")
                                verification_renamed(f"{student_login}: {filename}")
                                log_info(f"Nenhum nome correspondente encontrado para o arquivo {filename}")

    except Exception as e:
        log_error(f"Erro em renomear arquivos baseado nos nomes do dicionario {str(e)}")

def no_c_files_in_directory(submissions_folder, students): 
    try:
        for root, dirs, files in os.walk(submissions_folder): 
            folder_name = os.path.basename(root) 
            student = next((s for s in students if s.login == folder_name), None)
            if student is None:
                continue

            for file in files:
                file_path = os.path.join(root, file)
                file_name, file_extension = os.path.splitext(file)

                if file.startswith("."):
                    log_info(f"Deletando arquivo oculto: {file_path}")
                    os.remove(file_path)
                    continue

                if file_name.lower() in ['makefile', 'main', 'main-debug']:
                    log_info(f"Deletando arquivo: {file_path}")
                    os.remove(file_path)
                    student.update_field('formatacao', 0)
                    student.add_comment(f"Erro de formatação: deletado arquivo não permitido: {file_name}")
                    continue

                if file_extension == '.C':
                    new_file_path = os.path.join(root, file_name + '.c')
                    os.rename(file_path, new_file_path)
                    student.update_field('formatacao', 0)
                    student.add_comment(f"Erro de formatação: renomeado arquivo: de {file_path} para {new_file_path}")
                
                if file_extension == '.cpp':
                            new_file_path = os.path.join(root, file_name + '.c')
                            log_info(f"Renomeando arquivo: {file_path} -> {new_file_path}")
                            os.rename(file_path, new_file_path)
                            student.update_field('formatacao', 0)
                            student.add_comment(f"Erro de formatação: renomeado arquivo: {file_path} para {new_file_path}")

                elif file_extension != '.c':
                    if '.c' in file_name:
                        base_name = file_name.split('.c')[0] 
                        new_file_path = os.path.join(root, base_name + '.c')
                        log_info(f"Renomeando arquivo: {file_path} -> {new_file_path}")
                        os.rename(file_path, new_file_path)
                        student.update_field('formatacao', 0)
                        student.add_comment(f"Erro de formatação: renomeado arquivo: {file_path} para {new_file_path}")
                    else:    
                        log_info(f"Deletando arquivo: {file_path}")
                        os.remove(file_path)
                        student.update_field('formatacao', 0)
                        student.add_comment(f"Erro de formatação: deletado arquivo inválido: {file_path}")
                    
    except Exception as e:
        log_error(f"Erro no metodo no c files no diretorio {str(e)}")

def no_hs_files_in_directory(submissions_folder, students):
    try:
        for root, dirs, files in os.walk(submissions_folder): 
            folder_name = os.path.basename(root) 
            student = next((s for s in students if s.login == folder_name), None)
            if student is None:
                continue

            for file in files:
                file_path = os.path.join(root, file)
                file_name, file_extension = os.path.splitext(file)

                if file.startswith("."):
                    log_info(f"Deletando arquivo oculto: {file_path}")
                    os.remove(file_path)
                    continue

                if file_name.lower() in ['makefile', 'main', 'main-debug']:
                    log_info(f"Deletando arquivo: {file_path}")
                    os.remove(file_path)
                    student.update_field('formatacao', 0)
                    student.add_comment(f"Erro de formatação: deletado arquivo não permitido: {file_name}")
                    continue
                
                if file_extension == '.HS':
                    new_file_path = os.path.join(root, file_name + '.hs')
                    os.rename(file_path, new_file_path)
                    student.update_field('formatacao', 0)
                    student.add_comment(f"Erro de formatação: renomeado arquivo: {file_path}")

                elif file_extension != '.hs':
                    if '.hs' in file_name:
                        base_name = file_name.split('.hs')[0] 
                        new_file_path = os.path.join(root, base_name + '.hs')
                        log_info(f"Renomeando arquivo: {file_path} -> {new_file_path}")
                        os.rename(file_path, new_file_path)
                        student.update_field('formatacao', 0)
                        student.add_comment(f"Erro de formatação: renomeado arquivo: {file_path} para {new_file_path}")                        
                    else:
                        log_info(f"Deletando arquivo: {file_path}")
                        os.remove(file_path)
                        student.update_field('formatacao', 0)
                        student.add_comment(f"Erro de formatação: deletado arquivo inválido: {file_name}")
    except Exception as e:
        log_error(f"Erro no metodo no hs files no diretorio {str(e)}")                    
                 
def rename_files(submissions_folder, list_title, questions_data, students):
    try:
        if 'HASKELL' in list_title:
            no_hs_files_in_directory(submissions_folder, students)
            rename_files_based_on_dictionary(submissions_folder, questions_data, students, 1)
            return 'haskell'
        else:
            no_c_files_in_directory(submissions_folder, students)
            rename_files_based_on_dictionary(submissions_folder, questions_data, students)
            return 'c'
    except Exception as e:
        log_error(f"Erro no método renomear arquivos {str(e)}")       

def integrate_renaming(turmas, list_title, questions_data):
    try:
        for turma_path in turmas:
            formatted_list_folder = os.path.dirname(turma_path)
            class_name = os.path.basename(turma_path).replace("zips_", "") 

            students_filename = f"students_{class_name}.json"
            students_path = os.path.join(formatted_list_folder, students_filename)
            submissions_path = os.path.join(turma_path, f"submissions_{class_name}")

            if not os.path.exists(students_path):
                log_error(f"Arquivo de alunos não encontrado: {students_path}")
                continue

            if not os.path.exists(submissions_path):
                log_error(f"Pasta de submissões não encontrada: {submissions_path}")
                continue

            students = load_students_from_json(students_path)
            rename_files(submissions_path, list_title, questions_data, students)
            save_students_to_json(students, students_path)

        log_info("Renomeação e salvamento dos dados finais concluídos com sucesso.")

    except Exception as e:
        log_error(f"Erro ao integrar renomeação no main: {e}")

