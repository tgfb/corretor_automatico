import os
import sys
from infrastructure.spreadsheet_handler import (
    header_worksheet,
    insert_header_title,
    fill_worksheet_with_students,
    freeze_and_sort,
    get_google_sheet_if_exists,
    create_google_sheet_and_worksheet,
    apply_dynamic_formula_in_column,
    align_and_resize,
    align_middle_entire_sheet
)
from core.models.student_submission import load_students_from_json
from utils.utils import log_error, read_id_from_file, set_log_folder, get_available_turmas_from_folder
from core.models.list_metadata import ListMetadata
from services.laudo_spreadsheet import highlight_rows_by_names_from_laudo, log_laudo_names_not_found


def main():
    try:
        if len(sys.argv) < 2:
            print("\nComo usar: python nome_do_arquivo.py 'LISTA 04'\n")
            return

        selected_folder = sys.argv[1] 

        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(script_dir)  
        downloads_root = os.path.join(project_root, "Downloads")
        downloads_path = os.path.join(downloads_root, selected_folder)
        set_log_folder(downloads_path)

        if not os.path.exists(downloads_path):
            print(f"A pasta '{downloads_path}' não foi encontrada.")
            return
        
        turmas = get_available_turmas_from_folder(downloads_path) or ["A", "B"]

        folder_id = read_id_from_file(os.path.join("input", "folder_id.txt"))
        if not folder_id:
            print("Arquivo 'folder_id.txt' não encontrado ou inválido.\n")
            return
        
        audit_worksheets = []

        for turma in turmas:
            students_path = os.path.join(downloads_path, f"students_turma{turma}.json")
            metadata_path = os.path.join(downloads_path, f"metadata_turma{turma}.json")

            if not os.path.exists(students_path):
                print(f"O arquivo '{students_path}' não foi encontrado.")
                return

            if not os.path.exists(metadata_path):
                print(f"O arquivo '{metadata_path}' não foi encontrado.")
                return

            students = load_students_from_json(students_path)
            metadata = ListMetadata.load_metadata_from_json(metadata_path)

            if metadata is None:
                print(f"Metadados inválidos para turma {turma}")
                continue

            class_name = metadata.class_name
            list_title = metadata.list_name
            list_name = metadata.list_name.split(" - ")[0].strip()
            num_questions = metadata.num_questions
            score = metadata.score

            spreadsheet, worksheet = get_google_sheet_if_exists(class_name, list_name, folder_id)

            if spreadsheet is None:
                spreadsheet, worksheet = create_google_sheet_and_worksheet(class_name, list_name, folder_id)
            elif worksheet is None:
                worksheet = spreadsheet.add_worksheet(title=list_name, rows=100, cols=50)
                print(f"Aba '{list_name}' criada na planilha existente.\n")

            if worksheet is None:
                print("Não foi possível obter ou criar a planilha e aba.\n")
                return

            audit_worksheets.append(worksheet)
            existing_values = worksheet.get_all_values()         
            if len(existing_values) > 3:
                print(f"A aba '{list_name}' já está preenchida. Pulando preenchimento.")
                continue

            header_ok = header_worksheet(worksheet, class_name, list_title, num_questions, score)

            if header_ok:
                insert_header_title(worksheet, score, num_questions)
                fill_worksheet_with_students(worksheet, students, num_questions)
                apply_dynamic_formula_in_column(worksheet, num_questions)
                freeze_and_sort(worksheet)
                align_and_resize(worksheet)
                align_middle_entire_sheet(worksheet)
                highlighted_count = highlight_rows_by_names_from_laudo(worksheet)
                print(f"{highlighted_count} linhas destacadas na aba '{list_name}'.")
            else:
                log_error("Erro ao configurar cabeçalho. Dados dos alunos não foram enviados.")

        if audit_worksheets:
            log_laudo_names_not_found(audit_worksheets)   
        print("\nProcesso finalizado com sucesso.\n")

    except Exception as e:
        log_error(f"Erro no fluxo spreadsheet main: {e}")


if __name__ == "__main__":
    main()
