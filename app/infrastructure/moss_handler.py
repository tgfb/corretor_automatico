import os
import re
import shutil
import subprocess
import requests
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from core.models.student_submission import load_students_from_json, save_students_to_json
from utils.utils import log_error, log_info
from utils.moss_utils import norm, extract_login_from_cell_text, extract_percentage


def moss_script(submissions_folder, language, list_name, num_questions, copy_threshold = 80):

    try:
        if not os.path.exists(submissions_folder):
            raise FileNotFoundError(f"A pasta '{submissions_folder}' não existe.")

        base_dir = os.path.dirname(os.path.abspath(__file__))
        moss_script_path = os.path.join(base_dir, "external_tools", "moss.pl")

        perl = shutil.which("perl")
        if not perl:
            raise FileNotFoundError("Perl não encontrado no PATH. Instale Strawberry Perl e reabra o terminal.")
        if not os.path.isfile(moss_script_path):
            raise FileNotFoundError(f"moss.pl não encontrado: {moss_script_path}")

        links = {}
        moss_results = []

        language = (language or "").strip().lower() or "c"

        for i in range(1, num_questions + 1):
            question_key = f"q{i}"
            files = []
            for folder in os.listdir(submissions_folder):
                folder_path = os.path.join(submissions_folder, folder)
                if not os.path.isdir(folder_path) or folder.startswith('.'):
                    continue
                question_file = f"q{i}_{folder}.c"
                question_file_path = os.path.join(folder_path, question_file)
                if os.path.isfile(question_file_path):
                    files.append(question_file_path)
                else:
                    log_info(f"{question_key}: arquivo não encontrado: {question_file_path}")

            if not files:
                log_info(f"[MOSS] {question_key}: nenhum arquivo encontrado. Pulando.")
                continue

            comment = f"Análise de similaridade | {list_name} | Questão {i}"
            command = [perl, moss_script_path, "-l", language, "-c", comment] + files
            log_info(f"Executando {question_key} (arquivos={len(files)})")

            try:
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=120,
                    check=False
                )
            except subprocess.TimeoutExpired as e:
                log_error(f"[MOSS] {question_key}: timeout após {e.timeout}s")
                continue
            except Exception as e:
                log_error(f"[MOSS] {question_key}: falha ao invocar perl/moss.pl: {e}")
                continue

            if result.returncode != 0:
                tail_err = "\n".join((result.stderr or "").splitlines()[-10:])
                log_error(f"[MOSS] {question_key}: retorno {result.returncode}. stderr (fim):\n{tail_err}")
                continue

            output = (result.stdout or "").strip()
            if not output:
                log_error(f"[MOSS] {question_key}: stdout vazio.")
                continue

            urls = re.findall(r'https?://[^\s"<>\']+', output)
            if urls:
                report_url = urls[-1].strip()
                links[question_key] = report_url
                log_info(f"[MOSS] {question_key}: relatório -> {report_url}")
                continue

            lower = output.lower()
            if "<html" in lower and "</html>" in lower:
                inline_pairs = analyze_moss_html(output)
                for (student1, percentage1), (student2, percentage2) in inline_pairs:
                    if (percentage1 or 0) >= copy_threshold or (percentage2 or 0) >= copy_threshold:
                        moss_results.append({
                            "question": question_key,
                            "student1": student1,
                            "percentage1": percentage1,
                            "student2": student2,
                            "percentage2": percentage2
                        })
                continue

            log_error(f"[MOSS] {question_key}: nenhuma URL e stdout não parece HTML.")


        for question, link in links.items():
            if not validate_url(link):
                log_info(f"[MOSS] URL inválida para {question}: {link}")
                continue
            parsed_pairs = analyze_moss_report(link)
            print(f"\n{question}: {link}\n")
            print("Arquivo com possíveis cópias detectadas (>=80):\n") 
            for (student1, percentage1), (student2, percentage2) in parsed_pairs:
                if (percentage1 or 0) >= copy_threshold or (percentage2 or 0) >= copy_threshold:
                    moss_results.append({
                        "question": question,
                        "student1": student1,
                        "percentage1": percentage1,
                        "student2": student2,
                        "percentage2": percentage2
                    })
                    print(f"Student 1: {student1} ({percentage1}%) <-> Student 2: {student2} ({percentage2}%)")
        return moss_results

    except Exception as e:
        log_error(f"Erro ao rodar o script MOSS: {e}")
        return []


def validate_url(url):
    try:
        parsed = urlparse(url)
        return bool(parsed.scheme and parsed.netloc)
    except Exception as e:
        log_error(f"Erro ao validar a URL: {e}")
        return False


def analyze_moss_html(html_content):
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        results = set()

        for row in soup.find_all('tr'):
            cols = row.find_all('td')
            if len(cols) < 2:
                continue

            file1_text = cols[0].get_text(strip=True)
            file2_text = cols[1].get_text(strip=True)

            student1 = extract_login_from_cell_text(file1_text)
            student2 = extract_login_from_cell_text(file2_text)
            percentage1 = extract_percentage(file1_text)
            percentage2 = extract_percentage(file2_text)

            results.add(tuple(sorted(
                [(student1, percentage1), (student2, percentage2)],
                key=lambda x: norm(x[0])
            )))

        return list(results)
    except Exception as e:
        log_error(f"Erro ao processar HTML do MOSS: {e}")
        return []


def analyze_moss_report(report_url):

    try:
        resp = requests.get(report_url, timeout=30)
        resp.raise_for_status()
        return analyze_moss_html(resp.text)
    except Exception as e:
        print(f"Erro ao processar o relatório MOSS: {e}")
        return []


def update_moss_results_json(base_path, moss_results, copy_threshold = 80):
    try:
        turmas = ["A", "B", "C"]  # se tiver mais turmas, adicione aqui
        for turma in turmas:
            json_path = os.path.join(base_path, f"students_turma{turma}.json")
            if not os.path.exists(json_path):
                log_info(f"JSON não encontrado para turma {turma}.")
                continue

            students = load_students_from_json(json_path)
            updated = False

            for result in moss_results:
                percentage1 = result.get("percentage1")
                percentage2 = result.get("percentage2")
                if (percentage1 or 0) < copy_threshold and (percentage2 or 0) < copy_threshold:
                    continue  

                question = result["question"]
                student1_raw = result["student1"]
                student2_raw = result["student2"]
                student1 = norm(student1_raw)
                student2 = norm(student2_raw)

                for student in students:
                    login = norm(student.login)
                    if login == student1 or login == student2:
                        student.update_field("copia", 1)
                        student.add_comment(
                            f"{question} | Cópia detectada: {student1_raw} ({percentage1}%) <-> {student2_raw} ({percentage2}%)"
                        )
                        updated = True

            if updated:
                save_students_to_json(students, json_path)
                log_info(f"Atualizado arquivo: {json_path}")

    except Exception as e:
        print(f"Erro ao atualizar JSON com resultados do Moss: {e}")
