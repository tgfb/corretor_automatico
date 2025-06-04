import os
import sys
from infrastructure.jplag_handle import run_jplag_for_all_questions

def main():
    if len(sys.argv) < 3:
        print("\nComo usar: python jplag_main.py 'LISTA 04' 4\n (o nuúmero é a quantidade de questões")
        return

    selected_folder = sys.argv[1]
    try:
        num_questions = int(sys.argv[2])
    except ValueError:
        print("O segundo argumento deve ser um número inteiro representando o número de questões.")
        return

    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    downloads_path = os.path.join(script_dir, "Downloads")
    base_path = os.path.join(downloads_path, selected_folder)
    submissions_folder = os.path.join(base_path, "submissions")

    jplag_jar_path = os.path.join(script_dir, "infrastructure", "external_tools", "jplag-6.1.0-jar-with-dependencies.jar")

    if not os.path.exists(submissions_folder):
        print(f"A pasta '{submissions_folder}' não foi encontrada.")
        return

    report_urls = run_jplag_for_all_questions(
        submissions_folder=submissions_folder,
        language="c",
        list_name=selected_folder,
        num_questions=num_questions,
        jplag_jar_path=jplag_jar_path
    )

    print("\nRelatórios gerados:")
    for qi, url in report_urls:
        print(f"{qi}: file://{url}")

if __name__ == "__main__":
    main()