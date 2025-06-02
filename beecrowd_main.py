import os
import re
from time import sleep
from infrastructure.auth_google import get_gspread_client
from infrastructure.spreadsheet_handler import get_google_sheet_if_exists
from core.models.list_metadata import ListMetadata
from core.models.student_submission import load_students_from_json
from infrastructure.beecrowd_handle import (
    read_id_from_file_beecrowd,
    update_grades,
    update_final_grade_for_no_submission,
    compare_emails
)
from utils.utils import log_info, log_error


def main():
    try:
        input_folder = os.path.join("Downloads")
        turmas = ["A", "B"]

        for turma in turmas:
            students_path = os.path.join(input_folder, f"students_turma{turma}.json")
            metadata_path = os.path.join(input_folder, f"metadata_turma{turma}.json")

            if not os.path.exists(students_path) or not os.path.exists(metadata_path):
                print(f"Arquivos da turma {turma} não encontrados.")
                continue

            students = load_students_from_json(students_path)
            metadata = ListMetadata.load_metadata_from_json(metadata_path)

            class_name = metadata.class_name
            list_name = metadata.list_name
            list_title = list_name.split(" - ")[0] if " - " in list_name else list_name
            num_questions = metadata.num_questions
            score = metadata.score

            sheet_id = read_id_from_file_beecrowd("input/sheet_id_beecrowd.txt", list_title, class_name)
            if sheet_id is None:
                continue

            spreadsheet, worksheet = get_google_sheet_if_exists(class_name, list_title, folder_id=None)
            if worksheet is None:
                print(f"A planilha da turma {class_name} ainda não foi criada ou a aba '{list_title}' não foi criada.")
                continue

            update_grades(sheet_id, worksheet, score, class_name)
            sleep(1)
            update_final_grade_for_no_submission(worksheet, num_questions)
            sleep(1)
            compare_emails(sheet_id, worksheet, class_name)
            print(f"\nSincronização finalizada para a turma {class_name}.\n")

    except Exception as e:
        log_error(f"Erro no fluxo principal do Beecrowd: {str(e)}")


if __name__ == "__main__":
    main()