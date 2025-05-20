import os
from infrastructure.moss_handler import moss_script, update_moss_results_json
from core.models.list_metadata import load_metadata_from_json
from utils.utils import log_info

def moss_main():
    try:
        script_dir = os.path.dirname(os.path.abspath(_file_))
        formatted_list = input("Digite o nome da lista formatada (ex: lista01, lista02...): ").strip()
        base_path = os.path.join(script_dir, "..", "Downloads", formatted_list)
        submissions_folder = os.path.join(base_path, "submissions")

        if not os.path.exists(submissions_folder):
            print(f"Pasta '{submissions_folder}' não encontrada.")
            return

        metadata_a_path = os.path.join(base_path, "metadata_turmaA.json")
        metadata_b_path = os.path.join(base_path, "metadata_turmaB.json")

        if not os.path.exists(metadata_a_path) and not os.path.exists(metadata_b_path):
            print("Nenhum arquivo de metadados encontrado.")
            return

        if os.path.exists(metadata_a_path):
            metadata = load_metadata_from_json(metadata_a_path)
        else:
            metadata = load_metadata_from_json(metadata_b_path)

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

if _name_ == "_main_":
    moss_main()