# main_push_grades.py
import os
import sys
from googleapiclient.discovery import build
from infrastructure.auth_google import get_credentials
from utils.utils import read_id_from_file, get_available_turma_letters, log_info, log_error
from utils.sheet_id_handler import semester_informations
from infrastructure.classroom_gateway import list_classroom_data
from services.push_grades_from_sheets import push_spreadsheet_to_classroom  


def parse_args(argv):

    args = set(a.lower() for a in argv if a.startswith("-"))
    desired_title = next((a for a in argv if not a.startswith("-")), None)
    dry_run = "--execute" not in args          
    use_draft = "--publish" not in args        
    return desired_title, dry_run, use_draft


def main():
    try:
        desired_title, dry_run, use_draft = parse_args(sys.argv[1:])
        log_info(f"Start push grades (dry_run={dry_run}, use_draft={use_draft}, desired_title={desired_title})")

        try:
            classroom_service = build("classroom", "v1", credentials=get_credentials())
        except Exception as e:
            log_error(f"Failed to build Classroom service: {e}")
            return

        folder_id = read_id_from_file(os.path.join("input", "folder_id.txt"))
        if not folder_id:
            log_error("input/folder_id.txt not found or invalid.")
            return

        semester_sheet_id = read_id_from_file(os.path.join("input", "sheet_id.txt"))
        if not semester_sheet_id:
            log_error("input/sheet_id.txt not found or invalid.")
            return

        try:
            semester = semester_informations(semester_sheet_id)
        except Exception as e:
            log_error(f"Failed to read semester informations: {e}")
            return

        try:
            turma_letters = get_available_turma_letters(classroom_service, semester) or ["A", "B", "C"]
        except Exception as e:
            log_error(f"Failed to list available classes: {e}")
            turma_letters = ["A", "B", "C"]

        saved_assignment_title = desired_title  
        total_processed = 0

        for letter in turma_letters:
            turma_type = f"TURMA {letter}"
            try:
                course_id, coursework_id, classroom_name, list_name, list_title = list_classroom_data(
                    classroom_service,
                    semester,
                    turma_type=turma_type,
                    saved_assignment_title=saved_assignment_title
                )
                if not course_id or not coursework_id:
                    log_error(f"[{turma_type}] Missing course_id/coursework_id.")
                    continue

                if saved_assignment_title is None:
                    saved_assignment_title = list_title

                processed = push_spreadsheet_to_classroom(
                    classroom_service=classroom_service,
                    folder_id=folder_id,
                    course_id=course_id,
                    coursework_id=coursework_id,
                    classroom_name=classroom_name,
                    list_name=list_name,
                    assume_sheet_max=100.0,  
                    use_draft=use_draft,      
                    dry_run=dry_run           
                )
                log_info(f"[{turma_type}] Processed: {processed}")
                total_processed += processed

            except Exception as e:
                log_error(f"[{turma_type}] Error while pushing grades: {e}")
                continue

        print(f"\nTotal processed: {total_processed}")
        if dry_run:
            print("Dry-run mode. Re-run with --execute to actually push.")
        if use_draft:
            print("Grades pushed as draft. Use --publish to push as assigned grades.")

    except Exception as e:
        log_error(f"Fatal error in main: {e}")


if __name__ == "__main__":
    main()