import os
import re
import sys
import shutil
from googleapiclient.discovery import build
import utils.utils as utils
from core.models.student_submission import save_students_to_json
from services.file_renamer import rename_files, integrate_renaming
from infrastructure.submission_handler import download_submissions
from utils.utils import log_error, format_list_title, read_id_from_file, log_info, get_available_turma_letters
from infrastructure.auth_google import get_credentials
from infrastructure.classroom_gateway import list_classroom_data
from utils.sheet_id_handler import semester_informations, list_questions
from core.models.list_metadata import ListMetadata
from infrastructure.folders_organizer import (
    organize_extracted_files,
    move_non_zip_files,
    if_there_is_a_folder_inside,
    delete_subfolders_in_student_folders,
    remove_empty_folders
)
from services.code_analyzer import log_small_submissions, apply_small_files_penalties

def main():
    try:
        creds = get_credentials()
        classroom_service = build("classroom", "v1", credentials=creds)
        drive_service = build("drive", "v3", credentials=creds)

        sheet_id = read_id_from_file(os.path.join("input", "sheet_id.txt"))
        if not sheet_id:
            print("Arquivo 'sheet_id.txt' não encontrado.\n")
            return

        semester = semester_informations(sheet_id)
      
        desired_title = sys.argv[1].strip() if len(sys.argv) > 1 else None

        list_name = list_title = None
        list_title_a = None
        turma_folders = []
        formatted_list = None
        script_dir = os.path.dirname(os.path.abspath(__file__))
        students_paths = {}
        class_letters = get_available_turma_letters(classroom_service, semester) or ["A", "B"]

        for class_letter in class_letters:
            turma_type = f"TURMA {class_letter}"

            classroom_id, coursework_id, classroom_name, list_name, list_title = list_classroom_data(
                classroom_service,
                semester,
                turma_type=turma_type,
                saved_assignment_title=(list_title_a or desired_title)
            )

            if not classroom_id:
                print("Dados da turma não encontrados.\n")
                return

            if class_letter == class_letters[0]:
               
                list_title_a = desired_title or list_title

                list_name_ref = list_name
                formatted_list = format_list_title(list_name)
                base_path = os.path.join(script_dir, "Downloads", formatted_list)
                if os.path.exists(base_path):
                    print(f"Já existe uma pasta de download para a lista '{formatted_list}', não é possível continuar.\n")
                    return

            else:
                if list_name != list_name_ref:
                    print("As duas turmas devem usar a mesma atividade.\n")
                    return

            try:
                questions_data, num_questions, score = list_questions(sheet_id, list_name)
                if not score or not questions_data:
                    print("\nA aba da planilha precisa conter número de questões e score.")
                    return
            except Exception as e:
                print(f"Erro ao carregar dados da planilha: {e}")
                return

            formatted_class = f"turma{class_letter}"

            script_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(script_dir)
            base_path = os.path.join(project_root, "Downloads", formatted_list)
            utils.FOLDER_PATH = os.path.join(base_path, "output")
            zips_folder = os.path.join(base_path, f"zips_{formatted_class}")
            submissions_folder = os.path.join(zips_folder, f"submissions_{formatted_class}")

            os.makedirs(zips_folder, exist_ok=True)

            turma_folders.append(zips_folder)

            metadata = ListMetadata(
                class_name=classroom_name,
                list_name=list_title,
                num_questions=num_questions,
                score=score
            )

            metadata_filename = f"metadata_turma{class_letter.upper()}.json"
            metadata_path = os.path.join(base_path, metadata_filename)
            ListMetadata.save_metadata_to_json(metadata, metadata_path)

            submissions = classroom_service.courses().courseWork().studentSubmissions().list(
                courseId=classroom_id, courseWorkId=coursework_id).execute()

            print(f"\nComeçando download da turma {class_letter} ...")
            student_list = download_submissions(
                classroom_service, drive_service, submissions,
                zips_folder, classroom_id, coursework_id, num_questions
            )

            print("\nDownload completo. Arquivos salvos em:", os.path.abspath(zips_folder))

            students_filename = f"students_turma{class_letter.upper()}.json"
            students_path = os.path.join(base_path, students_filename)
            save_students_to_json(student_list, students_path)

            organize_extracted_files(zips_folder, student_list, formatted_class)
            move_non_zip_files(zips_folder, formatted_class)
            if_there_is_a_folder_inside(student_list, submissions_folder)
            delete_subfolders_in_student_folders(submissions_folder)
            remove_empty_folders(submissions_folder)
            save_students_to_json(student_list, students_path)

            print("\nProcesso de organização de pastas finalizado:", os.path.abspath(submissions_folder))

            language = rename_files(submissions_folder, list_title, questions_data, student_list)
            remove_empty_folders(submissions_folder)

            metadata_path = os.path.join(base_path, f"metadata_turma{class_letter.upper()}.json")
            ListMetadata.update_language(metadata_path, language)
            save_students_to_json(student_list, students_path)
            students_paths[class_letter] = students_path
            print("\nProcesso de verificação e renomeação finalizado.")

        integrate_renaming(turma_folders, list_title, questions_data)

        final_submissions_folder = os.path.join(project_root, "Downloads", formatted_list, "submissions")
        os.makedirs(final_submissions_folder, exist_ok=True)

        for zips_folder in turma_folders:
            class_name = os.path.basename(zips_folder).replace("zips_", "")
            src_submission_path = os.path.join(zips_folder, f"submissions_{class_name}")
            for student in os.listdir(src_submission_path):
                src_path = os.path.join(src_submission_path, student)
                dst_path = os.path.join(final_submissions_folder, student)
                shutil.move(src_path, dst_path)

            shutil.rmtree(src_submission_path)
            log_info(f"Pasta deletada: {src_submission_path}")

        print("\nSubmissões unificadas em:", final_submissions_folder)

        final_base_path = os.path.abspath(os.path.join(project_root, "Downloads", formatted_list))
        log_small_submissions(final_submissions_folder, num_questions, final_base_path)
        log_path = os.path.join(final_base_path, "output", "small_files.txt")

        for turma in students_paths:
            apply_small_files_penalties(log_path, students_paths[turma])

    except Exception as e:
        log_error(f"Erro no fluxo principal: {e}")

if __name__ == "__main__":
    main()