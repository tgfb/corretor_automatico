import os
import sys
from utils.utils import log_error, log_info, set_log_folder
from core.models.student_submission import load_students_from_json, save_students_to_json
from infrastructure.jplag_handle import run_jplag_for_questions


def update_json_with_pairs(base_path, pairs, threshold_percent = 80):
    
    if not pairs:
        print("Nenhum par acima de 80% para atualizar nos JSONs.")
        return

    turmas = ["A", "B", "C"]  # ajuste conforme necessário
    for turma in turmas:
        json_path = os.path.join(base_path, f"students_turma{turma}.json")
        if not os.path.isfile(json_path):
            log_info(f"JSON não encontrado (turma {turma}). Pulando.")
            continue

        try:
            students = load_students_from_json(json_path)
            if not students:
                continue

            index = {student.login.strip().lower(): student for student in students}
            touched = False

            for item in pairs:
                if max(item["percentage1"], item["percentage2"]) < threshold_percent:
                    continue
                student1_raw, student2_raw = item["student1"], item["student2"]
                student1, student2 = student1_raw.strip().lower(), student2_raw.strip().lower()
                percentage1, percentage2 = item["percentage1"], item["percentage2"]
                qid = item["question"]

                for key in (student1, student2):
                    obj = index.get(key)
                    if obj:
                        obj.update_field("copia", 1)
                        obj.add_comment(f"{qid} | Cópia detectada: {student1_raw} ({percentage1}%) ↔ {student2_raw} ({percentage2}%)")
                        touched = True
     
            if touched:  
                save_students_to_json(students, json_path)
                print(f"Atualizado: {json_path}")
            
        except Exception as e:
            log_error(f"Falha ao atualizar {json_path}: {e}")


def main():
    if len(sys.argv) < 3:
        print("\nComo usar: python jplag_main.py 'LISTA 04' 4")
        print("(o segundo argumento é o número de questões)\n")
        return

    selected_folder = sys.argv[1]
    try:
        num_questions = int(sys.argv[2])
    except ValueError:
        print("O segundo argumento deve ser um inteiro (número de questões).")
        return

    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    downloads_dir = os.path.join(project_root, "Downloads")
    base_path = os.path.join(downloads_dir, selected_folder)
    set_log_folder(base_path)
    submissions_dir = os.path.join(base_path, "submissions")

    jplag_jar_path = os.path.join(script_dir, "infrastructure", "external_tools", "jplag-6.1.0-jar-with-dependencies.jar")

    if not os.path.isdir(submissions_dir):
        print(f"Pasta não encontrada: {submissions_dir}")
        return

    print("\nRodando JPlag…")
    report_artifacts, pairs = run_jplag_for_questions(
        submissions_dir=submissions_dir,
        language="c",          
        num_questions=num_questions,
        jplag_jar_path=jplag_jar_path,
        threshold_percent=80,       
    )

    print("\nRelatórios :")
    for qid, path in report_artifacts:
        print(f"{qid}: {path}")
    print("\n")
    
    update_json_with_pairs(base_path, pairs, threshold_percent=80)
    print("\n")


if __name__ == "__main__":
    main()
