import os
import shutil
import zipfile
import rarfile
from utils.utils import log_info, log_error
from core.models.student_submission import StudentSubmission

def is_real_zip(file_path):
    try:
        with zipfile.ZipFile(file_path, 'r') as zip_ref:
            return zip_ref.testzip() is None
    except Exception as e:
        log_error(f"Erro ao verificar se é um zip: {str(e)}")
        return False

def extract_zip(student_login, zip_file_path, extraction_path, student_obj):
    try:
        if not is_real_zip(zip_file_path):
            log_info(f"O arquivo {zip_file_path} não é um .zip válido.")
            student_obj.update_field('entregou', 0)
            student_obj.add_comment(f"O arquivo {zip_file_path} não é um .zip válido.")
            return

        with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
            zip_ref.extractall(extraction_path)

        macosx_path = os.path.join(extraction_path, '__MACOSX')
        if os.path.exists(macosx_path):
            log_info(f"Removendo pasta __MACOSX de {extraction_path}")
            shutil.rmtree(macosx_path)
            student_obj.add_comment("Deletado pasta __MACOSX")

    except Exception as e:
        log_error(f"Erro ao extrair o zip: {str(e)}") 

def extract_rar(student_login, rar_file_path, extraction_path, student_obj):
    try:
        try:
            with rarfile.RarFile(rar_file_path, 'r') as rar_ref:
                rar_ref.extractall(extraction_path)
        except rarfile.Error as e:
            log_info(f"Erro ao usar rarfile: {e}")
            log_info(f"Tentando extrair com unar...")

        macosx_path = os.path.join(extraction_path, '__MACOSX')
        if os.path.exists(macosx_path):
            log_info(f"Removendo pasta __MACOSX de {extraction_path}")
            shutil.rmtree(macosx_path)
            student_obj.add_comment("Deletado pasta __MACOSX")

    except Exception as e:
        log_error(f"Erro ao extrair o rar: {str(e)}")

def move_file(source, destination):
    try:
        try:
            shutil.move(source, destination)
        except shutil.Error as e:
            log_info(f"Erro ao mover arquivo: {e}")
    except Exception as e:
        log_error(f"Erro ao mover o arquivo {str(e)}")  

def create_folder_if_not_exists(folder_path):
    try:
        if not os.path.exists(folder_path):
                os.makedirs(folder_path)
    except Exception as e:
        log_error(f"Erro em criar a pasta se não existir a pasta {str(e)}")       

def rename_directory_if_needed(directory_path, expected_name, student_obj):
    try:
        if os.path.isdir(directory_path):
            current_name = os.path.basename(directory_path)
            if current_name != expected_name:
                new_directory_path = os.path.join(os.path.dirname(directory_path), expected_name)
                os.rename(directory_path, new_directory_path)
                log_info(f"Pasta renomeada de {current_name} para {expected_name}")
                if current_name.lower() != expected_name:
                    student_obj.update_field('formatacao', 0)
                    student_obj.add_comment(f"Erro de formatação de pasta: pasta renomeada de {current_name} para {expected_name}.")
                return new_directory_path
        return directory_path
    except Exception as e:
        log_error(f"Erro ao renomear o diretório se necessário: {str(e)}")

def organize_extracted_files(download_folder, students, class_name):
    try:
        submissions_folder = os.path.join(download_folder, f"submissions_{class_name}")
        os.makedirs(submissions_folder, exist_ok=True)

        for student in students:
            student_login = student.login
            zip_path = os.path.join(download_folder, f"{student_login}.zip")
            rar_path = os.path.join(download_folder, f"{student_login}.rar")
            extraction_path = os.path.join(submissions_folder, student_login)
            create_folder_if_not_exists(extraction_path)

            try:
                if os.path.exists(zip_path):
                    extract_zip(student_login, zip_path, extraction_path, student)
                elif os.path.exists(rar_path):
                    extract_rar(student_login, rar_path, extraction_path, student)
                else:
                    continue
            except (zipfile.BadZipFile, rarfile.Error) as e:
                log_info(f"Erro ao extrair o arquivo de {student_login}: {e}")
                student.update_field('entregou', 0)
                student.update_field('formatacao', 0)
                student.add_comment("Erro de submissão: compactação com erro")
                continue

            extracted_items = os.listdir(extraction_path)
            if not extracted_items:
                student.update_field('entregou', 0)
                student.update_field('formatacao', 0)
                student.add_comment("Erro de submissão: zip vazio")
                continue

            if len(extracted_items) == 1 and os.path.isdir(os.path.join(extraction_path, extracted_items[0])):
                extracted_folder = os.path.join(extraction_path, extracted_items[0])
                rename_directory_if_needed(extracted_folder, student_login, student)

            for extracted_item in os.listdir(extraction_path):
                extracted_item_path = os.path.join(extraction_path, extracted_item)

                if os.path.exists(extracted_item_path) and os.path.isfile(extracted_item_path):
                    if extracted_item.endswith('.zip'):
                        student.update_field('formatacao', 0)
                        student.add_comment("Erro de formatação de pasta: zip dentro do zip.")
                        try:
                            extract_zip(student_login, extracted_item_path, extraction_path, student)
                            os.remove(extracted_item_path)
                        except zipfile.BadZipFile:
                            log_info(f"Erro ao extrair zip: {extracted_item_path}")
                    elif extracted_item.endswith('.rar'):
                        student.update_field('formatacao', 0)
                        student.add_comment("Erro de formatação de pasta: rar dentro do rar.")
                        try:
                            extract_rar(student_login, extracted_item_path, extraction_path, student)
                            os.remove(extracted_item_path)
                        except rarfile.Error:
                            log_info(f"Erro ao extrair rar: {extracted_item_path}")

            extracted_items = os.listdir(extraction_path)
            log_info(f"\nArquivos extraídos de {student_login}: {extracted_items}")
            for_not_executed = True
            if len(extracted_items) == 1:
                extracted_path = os.path.join(extraction_path, extracted_items[0])

                if os.path.isdir(extracted_path):
                    extracted_folder = extracted_path

                    if extracted_items[0] == student_login:
                        log_info(f"A pasta extraída {extracted_items[0]} já tem o nome correto. Movendo arquivos para {extraction_path}.")

                        for file in os.listdir(extracted_folder):
                            for_not_executed = False
                            source_file_path = os.path.join(extracted_folder, file)
                            destination_file_path = os.path.join(extraction_path, file)

                            if os.path.exists(source_file_path):
                                log_info(f"Movendo arquivo: {source_file_path} -> {destination_file_path}")
                                move_file(source_file_path, destination_file_path)
                            else:
                                log_info(f"Arquivo não encontrado: {source_file_path}")

                        if not os.listdir(extracted_folder):
                            shutil.rmtree(extracted_folder)
                            log_info(f"Pasta extra deletada: {extracted_folder}")
                            if for_not_executed:
                                student.update_field('entregou', 0)
                                student.update_field('formatacao', 0)
                                student.add_comment("Não tem arquivos dentro da pasta: pasta deletada.")
                        else:
                            log_info(f"Pasta extra {extracted_folder} ainda contém arquivos e não será deletada.")
                    else:
                        log_info(f"A pasta extraída {extracted_items[0]} é diferente do nome esperado {student_login}")
                        student.update_field('formatacao', 0)
                        student.add_comment(f"Erro de formatação de pasta: a pasta extraída {extracted_items[0]} é diferente do nome esperado {student_login}.")

                        for file in os.listdir(extracted_folder):
                            source_file_path = os.path.join(extracted_folder, file)
                            destination_file_path = os.path.join(extraction_path, file)

                            if os.path.exists(source_file_path):
                                log_info(f"Movendo arquivo: {source_file_path} -> {destination_file_path}")
                                move_file(source_file_path, destination_file_path)
                            else:
                                log_info(f"Arquivo não encontrado: {source_file_path}")

                        shutil.rmtree(extracted_folder)
                        log_info(f"Pasta deletada: {extracted_folder}")
                else:
                    log_info(f"Erro de formatação: {student_login} enviou arquivos soltos sem pasta.")
                    student.update_field('formatacao', 0)
                    student.add_comment("Erro de formatação de pasta: enviou sem pasta")
    except Exception as e:
        log_error(f"Erro ao organizar arquivos extraídos: {str(e)}")

def if_there_is_a_folder_inside(students, submissions_folder):
    try:
        def move_files_to_inicial_folder(first_folder, folder_name, student):
            if os.path.basename(first_folder).startswith('.'):
                return

            items = os.listdir(first_folder)
            
            subfolders = [item for item in items if os.path.isdir(os.path.join(first_folder, item)) and not item.startswith('.')]
            
            if subfolders:
                for subfolder in subfolders:
                    subfolder_path = os.path.join(first_folder, subfolder)

                    if subfolder in ['output', '.vscode']:
                        student.update_field('formatacao', 0)
                        student.add_comment(f"Erro de formatação de pasta: output ou .vscode")
                    else:
                        student.update_field('formatacao', 0)
                        student.add_comment(f"Erro de formatação de pasta: subpastas como {subfolder} foram movidas.")
                    
                    move_files_to_inicial_folder(subfolder_path, folder_name, student)
            
            files = [item for item in items if os.path.isfile(os.path.join(first_folder, item)) and not item.startswith('.')]
            for file in files:
                file_path = os.path.join(first_folder, file)
                destination = os.path.join(submissions_folder, os.path.basename(first_folder), file)

                if not os.path.exists(os.path.dirname(destination)):
                    os.makedirs(os.path.dirname(destination))

                shutil.move(file_path, destination)
            
            if first_folder != submissions_folder and not os.listdir(first_folder):
                os.rmdir(first_folder)

        for student in students:
            folder_name = student.login
            folder_path = os.path.join(submissions_folder, folder_name)
            if os.path.isdir(folder_path) and not folder_name.startswith('.'):
                move_files_to_inicial_folder(folder_path, folder_name, student)

    except Exception as e:
        log_error(f"Erro se existe uma pasta dentro da pasta: {str(e)}")

def delete_subfolders_in_student_folders(submissions_folder):
    try:
        for student_folder in os.listdir(submissions_folder):
            student_folder_path = os.path.join(submissions_folder, student_folder)

            if os.path.isdir(student_folder_path): 
                for item in os.listdir(student_folder_path):
                    item_path = os.path.join(student_folder_path, item)

                    if os.path.isdir(item_path): 
                        shutil.rmtree(item_path)
    except Exception as e:
        log_error(f"Erro ao deletar pastas dentro das pastas dos estudantes: {str(e)}")

def move_non_zip_files(download_folder, class_name):
    try:
        submissions_folder = os.path.join(download_folder, f"submissions_{class_name}")
        for item in os.listdir(download_folder):
            item_path = os.path.join(download_folder, item)
            if os.path.isdir(item_path) and item != f"submissions_{class_name}":
                destination_folder = os.path.join(submissions_folder, item)
                if not os.path.exists(destination_folder):
                    os.rename(item_path, destination_folder)
    except Exception as e:
        log_error(f"Erro ao mover arquivos que não estavam zipados: {str(e)}")

def remove_empty_folders(submissions_folder):
    try:
        for student_folder in os.listdir(submissions_folder):
            folder_path = os.path.join(submissions_folder, student_folder)
            if os.path.isdir(folder_path) and not os.listdir(folder_path):
                os.rmdir(folder_path)
    except Exception as e:
        log_error(f"Erro ao remover pastas vazias: {str(e)}")
