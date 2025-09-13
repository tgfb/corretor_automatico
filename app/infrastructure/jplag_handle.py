import csv
import os
import shutil
from shutil import which
from utils.utils import log_error, log_info
from subprocess import run, CalledProcessError


def prepare_inputs_by_question(submissions_dir, question_num):
  
    try:
        if not os.path.isdir(submissions_dir):
            raise FileNotFoundError(f"Submissions não encontrado: {submissions_dir}")

        base_dir = os.path.dirname(submissions_dir)
        temporary_root = os.path.join(base_dir, "temporary")
        question_dir = os.path.join(temporary_root, f"q{question_num}")

        if os.path.exists(question_dir):
            shutil.rmtree(question_dir)
        os.makedirs(question_dir, exist_ok=True)

        copied = 0
        for login in os.listdir(submissions_dir):
            student_dir = os.path.join(submissions_dir, login)
            if not os.path.isdir(student_dir) or login.startswith("."):
                continue

            filename = f"q{question_num}_{login}.c"
            source = os.path.join(student_dir, filename)
            if os.path.isfile(source):
                dest_dir = os.path.join(question_dir, login)
                os.makedirs(dest_dir, exist_ok=True)
                shutil.copy(source, os.path.join(dest_dir, filename))
                copied += 1

        print(f"q{question_num}: {copied} arquivos copiados.")
        return question_dir if copied > 0 else None
    except Exception as e:
        log_error(f"Erro preparando q{question_num}: {e}")
        return None


def parse_results_csv(result_dir, threshold_0_1):
   
    pairs = []
    csv_path = os.path.join(result_dir, "results.csv")
    if not os.path.isfile(csv_path):
        return pairs

    try:
        with open(csv_path, "r", encoding="utf-8", newline="") as fh:
            reader = csv.reader(fh)
            for row in reader:
                if not row or row[0].startswith("#") or len(row) < 4:
                    continue
                student1, student2 = row[0].strip(), row[1].strip()
                try:
                    student1_result, student2_result = float(row[2]), float(row[3])
                except ValueError:
                    continue
                if max(student1_result, student2_result) >= threshold_0_1:
                    pairs.append((student1, student2, student1_result, student2_result))
    except Exception as e:
        log_error(f"Falha lendo CSV '{csv_path}': {e}")
    return pairs


def run_jplag_for_questions(submissions_dir, language, num_questions, jplag_jar_path, threshold_percent = 80):
   
    report_artifacts = []
    results = []

    try:
        if not os.path.isdir(submissions_dir):
            raise FileNotFoundError(f"Submissions não encontrado: {submissions_dir}")
        if not os.path.isfile(jplag_jar_path):
            raise FileNotFoundError(f"JAR do JPlag não encontrado: {jplag_jar_path}")
        if which("java") is None:
            raise EnvironmentError("Java não encontrado no PATH. Instale o Java (JRE/JDK) e tente novamente.")

        base_dir = os.path.dirname(submissions_dir)
        result_root = os.path.join(base_dir, "result")
        os.makedirs(result_root, exist_ok=True)

        threshold_0_1 = threshold_percent / 100.0

        for question in range(1, num_questions + 1):
            qid = f"q{question}"
            print(f"\nPreparando {qid}…")
            input_dir = prepare_inputs_by_question(submissions_dir, question)
            if not input_dir or not os.listdir(input_dir):
                log_info(f"{qid}: sem arquivos. Pulando.")
                continue

            result_dir = os.path.join(result_root, f"jplag_results_{qid}")
            cmd = [
                "java", "-jar", jplag_jar_path,
                "-l", language,
                "--mode", "run",
                "--overwrite",
                "-r", result_dir,
                "--csv-export",
                "--min-tokens", "15",
                input_dir,
            ]

            try:
                completed = run(cmd, check=False, capture_output=True, text=True)
                if completed.returncode != 0:
                    log_info(f"{qid}: retorno {completed.returncode}.")
                    continue

                html_path = os.path.join(result_dir, "index.html")
                zip_path = result_dir + ".jplag"  

                artifact = html_path if os.path.isfile(html_path) else (zip_path if os.path.isfile(zip_path) else None)
                if artifact:
                    report_artifacts.append((qid, os.path.abspath(artifact)))

            except Exception as e:
                log_error(f"{qid}: Erro ao executar JPlag: {e}")
                continue


            for student1, student2, stud1_result, stud2_result in parse_results_csv(result_dir, threshold_0_1):
                results.append({
                    "question": qid,
                    "student1": student1,
                    "percentage1": int(round(stud1_result * 100)),
                    "student2": student2,
                    "percentage2": int(round(stud2_result * 100)),
                })

            print(f"{qid}: pares ≥ {threshold_percent}%:", sum(1 for r in results if r["question"] == qid))

    except Exception as e:
        log_error(f"Erro geral: {e}")

    return report_artifacts, results
