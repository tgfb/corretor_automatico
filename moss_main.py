import os
from infrastructure.moss_handler import moss_script, update_moss_results_json
from core.models.list_metadata import ListMetadata

def moss_main():
    try:

        script_dir = os.path.dirname(os.path.abspath(__file__))
        downloads_path = os.path.join(script_dir, "Downloads")

        folders = [f for f in os.listdir(downloads_path) if os.path.isdir(os.path.join(downloads_path, f))]
        if not folders:
            print("Nenhuma pasta encontrada em 'Downloads'.")
            return

        folders = folders[::-1] 

        print("\nEscolha a lista que deseja rodar o MOSS:")
        for idx, folder in enumerate(folders):
            print(f"{idx + 1} - {folder}")

        choice = input("Digite o número da lista: ").strip()
        if not choice.isdigit() or not (1 <= int(choice) <= len(folders)):
            print("Opção inválida.")
            return

        selected_folder = folders[int(choice) - 1]
        base_path = os.path.join(downloads_path, selected_folder)
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
            metadata = ListMetadata.load_metadata_from_json(metadata_a_path)
        else:
            metadata = ListMetadata.load_metadata_from_json(metadata_b_path)

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
