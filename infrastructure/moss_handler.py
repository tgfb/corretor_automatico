import os
import subprocess
import re 
import requests
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from core.models.student_submission import load_students_from_json
from utils.utils import log_error, log_info


def moss_script(submissions_folder, language, list_name, num_questions):
    try:
        if not os.path.exists(submissions_folder):
            raise FileNotFoundError(f"A pasta '{submissions_folder}' não existe.")
         
        base_dir = os.path.dirname(os.path.abspath(__file__))
        moss_script_path = os.path.join(base_dir, "external_tools", "moss.pl")

        links = {} 
        moss_results = [] 

        for i in range(1, num_questions + 1):
            files = []
            for folder in os.listdir(submissions_folder):
                folder_path = os.path.join(submissions_folder, folder)
                if os.path.isdir(folder_path): 
                    question_file = f"q{i}_{folder}.c"
                    question_file_path = os.path.join(folder_path, question_file)
                    if os.path.isfile(question_file_path):
                        files.append(question_file_path)
                    else:
                        log_info(f"Arquivo não encontrado para q{i}: {question_file_path}")

            if not files:
                log_info(f"Nenhum arquivo encontrado para a questão {i}. Pulando para a próxima.")
                continue

            comment = f'"Análise de similaridade | {list_name} | Questão {i}"'
            command = ["perl", moss_script_path, "-l", language, "-c", comment, "-d"] + files

            log_info(f"\nExecutando comando MOSS para questão {i}...")

            try:
                result = subprocess.run(command, capture_output=True, text=True, check=True)
                output = result.stdout.strip()
                report_url = output.split("\n")[-1]  
                links[f"q{i}"] = report_url 
            except subprocess.CalledProcessError as e:
                log_error(f"Erro ao executar o script MOSS para q{i}: {e.stderr}")
                continue

        if not links:
            print("\nNenhum relatório foi gerado.")
        else:
            print("\nLinks gerados para cada questão:")
            for question, link in links.items():
                print(f"\n{question}: {link}")
                if validate_url(link):  
                    moss_data = analyze_moss_report(link)

                    for student_pair in moss_data:
                        student1, percentage1 = student_pair[0]
                        student2, percentage2 = student_pair[1]

                        moss_results.append({
                            "question": f"q{i}",
                            "student1": student1,
                            "percentage1": percentage1,
                            "student2": student2,
                            "percentage2": percentage2
                        })
                else:
                    log_info(f"URL inválida para questão {i}: {report_url}")


        return moss_results

    except Exception as e:
        log_error(f"Erro ao rodar o script MOSS: {str(e)}")

def moss_script2(submissions_folder, language, list_name, num_questions):
    try:
        if not os.path.exists(submissions_folder):
            raise FileNotFoundError(f"A pasta '{submissions_folder}' não existe.")
         
        base_dir = os.path.dirname(os.path.abspath(__file__))
        moss_script_path = os.path.join(base_dir, "external_tools", "moss.pl")
        print(moss_script_path)
        

        links = {} 
        moss_results = [] 

        print(f"Usando MOSS script: {moss_script_path}")

        for i in range(1, num_questions + 1):
            files = []
            for folder in os.listdir(submissions_folder):
                folder_path = os.path.join(submissions_folder, folder)
                #print(f"Verificando pasta: {folder_path}")

                if os.path.isdir(folder_path): 
                    question_file = f"q{i}_{folder}.c"
                    question_file_path = os.path.join(folder_path, question_file)

                    if os.path.isfile(question_file_path):
                        with open(question_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read().strip()
                            if len(content) < 10:
                                print(f"Arquivo muito pequeno: {question_file_path}")
                            else:
                                print(f"Arquivo válido: {question_file_path}")
                                files.append(question_file_path)

            print(f"Total de arquivos para q{i}: {len(files)}")
            if not files:
                log_info(f"Nenhum arquivo encontrado para a questão {i}. Pulando para a próxima.")
                continue
            
            comment = f'"Análise de similaridade | {list_name} | Questão {i}"'
            language = language.strip().lower()
            command = ["perl", moss_script_path, "-l", language, "-c", comment, "-d"] + files

            print(f"Comando a ser executado para q{i}:\n{' '.join(command)}")
            log_info(f"\nExecutando comando MOSS para questão {i}...")

            try:
                result = subprocess.run(command, capture_output=True, text=True, check=True)
                output = result.stdout.strip()
                print(f"Saída do MOSS para q{i}:\n{output}")
                report_url = output.split("\n")[-1]  
                links[f"q{i}"] = report_url 
            except subprocess.CalledProcessError as e:
                log_error(f"Erro ao executar o script MOSS para q{i}: {e.stderr}")
                continue

        if not links:
            print("\nNenhum relatório foi gerado.")
        else:
            print("\nLinks gerados para cada questão:")
            for question, link in links.items():
                print(f"\n{question}: {link}")
                if validate_url(link):  
                    moss_data = analyze_moss_report(link)

                    for student_pair in moss_data:
                        student1, percentage1 = student_pair[0]
                        student2, percentage2 = student_pair[1]

                        moss_results.append({
                            "question": question,
                            "student1": student1,
                            "percentage1": percentage1,
                            "student2": student2,
                            "percentage2": percentage2
                        })
                else:
                    log_info(f"URL inválida para questão {question}: {link}")

        return moss_results

    except Exception as e:
        log_error(f"Erro ao rodar o script MOSS: {str(e)}")


def validate_url(url):
    try: 
        parsed = urlparse(url)
        return bool(parsed.scheme and parsed.netloc)
    except Exception as e:
        log_error(f"Erro ao validar a URL: {str(e)}")


def analyze_moss_report(report_url):
    try:
        response = requests.get(report_url)
        response.raise_for_status()
        html_content = response.text

        soup = BeautifulSoup(html_content, 'html.parser')

        results = set()

        table_rows = soup.find_all('tr')
        
        for row in table_rows:
            columns = row.find_all('td')

            if len(columns) >= 2:  # Cada linha válida tem pelo menos 2 colunas (arquivo1, arquivo2)
                file1_text = columns[0].get_text(strip=True)
                file2_text = columns[1].get_text(strip=True)

                # Student login
                student1_match = re.search(r"/([^/]+)/\s*\(\d+%\)", file1_text)
                student2_match = re.search(r"/([^/]+)/\s*\(\d+%\)", file2_text)

                student1 = student1_match.group(1) if student1_match else file1_text
                student2 = student2_match.group(1) if student2_match else file2_text
                
                # Porcentagem
                match1 = re.search(r"\((\d+)%\)", file1_text)
                match2 = re.search(r"\((\d+)%\)", file2_text)

                percentage_file1 = int(match1.group(1)) if match1 else None
                percentage_file2 = int(match2.group(1)) if match2 else None

                # porcentagem  >= 80%
                if (percentage_file1 and percentage_file1 >= 80) or (percentage_file2 and percentage_file2 >= 80):
                    pair = tuple(sorted([(student1, percentage_file1), (student2, percentage_file2)]))
                    results.add(pair)

        print("\nArquivos com possível cópia detectada (>=80%):\n")
        for student_pair in results:
            student1, percentage1 = student_pair[0]
            student2, percentage2 = student_pair[1]
            print(f"Student 1: {student1} ({percentage1}%) <-> "
                  f"Student 2: {student2} ({percentage2}%)")

        return list(results)          

    except Exception as e:
        print(f"Erro ao processar o relatório Moss: {e}")

def update_moss_results_json(base_path, moss_results, num_questions):
    try:
        for turma in ["A", "B"]:
            json_path = os.path.join(base_path, f"students_turma{turma}.json")
            if not os.path.exists(json_path):
                log_info(f"Arquivo JSON não encontrado para turma {turma}")
                continue

            students = load_students_from_txt(json_path)

            for result in moss_results:
                question = result["question"]  
                for students in students:
                    if student.login == (result["student1"] or student.login == result["student2"]):
                        student.update_field("copia", 1)
                        student.add_comment(f"Cópia detectada: {result['student1']} ({result['percentage1']}%) <-> {result['student2']} ({result['percentage2']}%)")
                        updated = True 

            if updated:
                save_students_to_txt(students, json_path)
                log_info(f"Atualizado arquivo: {json_path}")

    except Exception as e:
        print(f"Erro ao atualizar JSON com resultados do Moss: {e}")

