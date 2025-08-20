import os
import sys
from utils.utils import log_error, set_log_folder
from core.models.list_metadata import ListMetadata
from infrastructure.beecrowd_handle import (
    read_id_from_file_beecrowd,
    update_grades_json,
    update_final_grade_for_no_submission_json,
    compare_emails,
    fill_scores_for_students_json
)

def main():
    try:
        if len(sys.argv) < 2:
            print("\nComo usar: python nome_do_arquivo.py 'LISTA 04'\n")
            return

        selected_folder = sys.argv[1] 

        script_dir = os.path.dirname(os.path.abspath(__file__))
        downloads_root = os.path.join(script_dir, "Downloads")
        downloads_path = os.path.join(downloads_root, selected_folder)
        set_log_folder(downloads_path)
        
        if not os.path.exists(downloads_path):
            print(f"A pasta '{downloads_path}' não foi encontrada.")
            return
        
        turmas = ["A", "B"]

        for turma in turmas:
            students_path = os.path.join(downloads_path, f"students_turma{turma}.json")
            metadata_path = os.path.join(downloads_path, f"metadata_turma{turma}.json")

            if not os.path.exists(students_path):
                print(f"O arquivo '{students_path}' não foi encontrado.")
                continue

            if not os.path.exists(metadata_path):
                print(f"O arquivo '{metadata_path}' não foi encontrado.")
                continue

            metadata = ListMetadata.load_metadata_from_json(metadata_path)

            if metadata is None:
                print(f"Metadados inválidos para turma {turma}")
                continue

            class_name = metadata.class_name
            list_title = metadata.list_name
            num_questions = metadata.num_questions
            list_name = list_title.split(" - ")[0].strip()
            score = metadata.score


            sheet_id = read_id_from_file_beecrowd("app/input/sheet_id_beecrowd.txt", list_name, class_name)
            if sheet_id is None:
                continue

            update_grades_json(sheet_id, students_path, score, class_name)
            update_final_grade_for_no_submission_json(students_path)
            fill_scores_for_students_json(students_path, num_questions, score)
            compare_emails(sheet_id, students_path, class_name)
            print(f"\nSincronização finalizada para a turma {class_name}.\n")

    except Exception as e:
        log_error(f"Erro no fluxo principal do Beecrowd: {str(e)}")

if __name__ == "__main__":
    main()
