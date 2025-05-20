import os
from googleapiclient.discovery import build
from infrastructure.auth_google import get_credentials, get_gspread_client
from infrastructure.spreadsheet_handler import (create_or_get_google_sheet_in_folder, header_worksheet, insert_header_title, freeze_and_sort, fill_worksheet_with_students)
from core.models.student_submission import load_students_from_txt
from utils.utils import log_error, log_info, read_id_from_file
from core.models.list_metadata import load_metadata_from_json

def main():
    try:

        downloads_path = os.path.join(os.path.dirname(__file__), "Downloads")
        turmas = ["A", "B"]

        for turma in turmas:
            students_path = os.path.join(downloads_path, f"students_turma{turma}.json")
            metadata_path = os.path.join(downloads_path, f"metadata_turma{turma}.json")

            if not os.path.exists(downloads_path):
                print("A pasta 'Downloads' não foi encontrada.")
                return

            folder_id = read_id_from_file(os.path.join("input", "folder_id.txt"))
            if not folder_id:
                print("Arquivo 'folder_id.txt' não encontrado ou inválido.\n")
                return

            creds = get_credentials()
            classroom_service = build("classroom", "v1", credentials=creds)
            drive_service = build("drive", "v3", credentials=creds)

            for turma in turmas:
                students_path = os.path.join(downloads_path, f"students_turma{turma}.json")
                metadata_path = os.path.join(downloads_path, f"metadata_turma{turma}.json")

                if not os.path.exists(students_path):
                    print(f"O arquivo 'Downloads/students_turma{turma}' não foi encontrado.")
                    return
            
                if not os.path.exists(metadata_path):
                    print(f"O arquivo 'Downloads/metadata_turma{turma}' não foi encontrado.")
                    return
                
                students = load_students_from_txt(students_path)
                metadata = load_metadata_from_json(metadata_path)

                if metadata is None:
                    print(f"Metadados inválidos para turma {turma}")
                    continue
        
                list_title = metadata.list_name
                list_name = metadata.list_name.split(" - ")[0] if " - " in metadata.list_name else metadata.list_name
                num_questions = metadata.num_questions
                score = metadata.score
            
                worksheet = create_or_get_google_sheet_in_folder(list_title, list_name, folder_id)
                if worksheet is None:
                    print("Não foi possíve; obter planilha\n")
                    continue
                
                header_worksheet(worksheet, num_questions, score)

                for student in students:
                    worksheet.append_rows([student.to_list(num_questions)])

                freeze_and_sort(worksheet)
                insert_header_title(worksheet,list_title, list_title)
                print("\nProcesso finalizado com sucesso.\n")

    except Exception as e:
        log_error(f"Erro no fluxo spreadsheet main: {e}")

if __name__ == "__main__":
    main()