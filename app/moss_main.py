import os
import re
import sys
from infrastructure.moss_handler import moss_script, update_moss_results_json
from core.models.list_metadata import ListMetadata
from utils.utils import set_log_folder


def moss_main():
    try:
        if len(sys.argv) < 2:
            print("\nComo usar: python nome_do_arquivo.py 'LISTA 04'\n")
            return

        selected_folder = sys.argv[1]

        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(script_dir)
        downloads_path = os.path.join(project_root, "Downloads")
        base_path = os.path.join(downloads_path, selected_folder)
        set_log_folder(base_path)
        submissions_folder = os.path.join(base_path, "submissions")

        if not os.path.exists(submissions_folder):
            print(f"Pasta '{submissions_folder}' não encontrada.")
            return

        metadata_files = [
            name for name in os.listdir(base_path)
            if re.fullmatch(r"metadata_turma[A-Z]\.json", name, flags=re.IGNORECASE)
        ]

        if not metadata_files:
            print("Nenhum arquivo de metadados encontrado.")
            return

        metadata_path = os.path.join(base_path, metadata_files[0])
        metadata = ListMetadata.load_metadata_from_json(metadata_path)
        if metadata is None:
            print(f"Metadados inválidos em {os.path.basename(metadata_path)}.")
            return

        list_name = metadata.list_name
        num_questions = metadata.num_questions
        language = metadata.language

        print("\nRodando o MOSS...")
        moss_results = moss_script(submissions_folder, language, list_name, num_questions)

        if moss_results:
            print("\nAtualizando arquivos JSON com os resultados...")
            update_moss_results_json(base_path, moss_results, num_questions)
        else:
            print("\nNenhum resultado do MOSS para processar.")

    except Exception as e:
        print(f"Erro ao executar o MOSS: {e}")


if __name__ == "__main__":
    moss_main()

