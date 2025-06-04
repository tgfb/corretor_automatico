import os
import shutil
from subprocess import run, CalledProcessError


import os
import shutil

def prepare_jplag_input_by_question(submissions_folder, question_number):
   
    try:
        if not os.path.exists(submissions_folder):
            raise FileNotFoundError(f"Pasta de submissões não encontrada: {submissions_folder}")

        base_folder = os.path.dirname(submissions_folder)

        temporary_root = os.path.join(base_folder, "temporary")
        temporary_folder = os.path.join(temporary_root, f"q{question_number}")

        if os.path.exists(temporary_folder):
            shutil.rmtree(temporary_folder)
        os.makedirs(temporary_folder, exist_ok=True)

        arquivos_encontrados = 0

        for folder in os.listdir(submissions_folder):
            student_path = os.path.join(submissions_folder, folder)
            if not os.path.isdir(student_path):
                continue

            question_file = f"q{question_number}_{folder}.c"
            source_file = os.path.join(student_path, question_file)

            if os.path.isfile(source_file):
                dest_folder = os.path.join(temporary_folder, folder)
                os.makedirs(dest_folder, exist_ok=True)
                shutil.copy(source_file, os.path.join(dest_folder, question_file))
                arquivos_encontrados += 1
            else:
                print(f"Arquivo não encontrado para aluno '{folder}' na questão q{question_number}.")

        if arquivos_encontrados == 0:
            print(f"Nenhum arquivo encontrado para q{question_number}.")
        else:
            print(f"{arquivos_encontrados} arquivos copiados para análise da q{question_number}.")

        return temporary_folder  

    except Exception as e:
        print(f"Erro ao preparar arquivos da questão q{question_number}: {str(e)}")
        return None

def run_jplag_for_all_questions(submissions_folder, language, list_name, num_questions, jplag_jar_path="jplag.jar"):
    
    report_urls = []

    base_folder = os.path.dirname(submissions_folder)
    result_root = os.path.join(base_folder, "result")
    os.makedirs(result_root, exist_ok=True)

    for i in range(1, num_questions + 1):
        question_id = f"q{i}"

        print(f"\nPreparando arquivos para {question_id}...")
        temporary_folder = prepare_jplag_input_by_question(submissions_folder, i)

        if not temporary_folder or not os.listdir(temporary_folder):
            print(f"Nenhum arquivo preparado para {question_id}. Pulando.")
            continue

        result_folder = os.path.join(result_root, f"jplag_results_{question_id}")
        print(f"Executando JPlag para {question_id}...")

        cmd = [
            "java",
            "-jar", jplag_jar_path,
            "-l", language,
            "-r", result_folder,
            "-M", "RUN_AND_VIEW",
            "--csv-export",
            "--min-tokens", "15",
            "--similarity-threshold", "0.6", 
            temporary_folder
        ]

        try:
            run(cmd, check=True)
            index_path = os.path.abspath(os.path.join(result_folder, "index.html"))
            if os.path.exists(index_path):
                report_urls.append((question_id, index_path))
                print(f"Relatório gerado para {question_id}: {index_path}")
            else:
                print(f"index.html não encontrado para {question_id}.")
        except CalledProcessError as e:
            print(f"Erro ao executar JPlag para {question_id}: {e}")

    return report_urls