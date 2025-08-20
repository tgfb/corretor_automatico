import re
from googleapiclient.errors import HttpError
from utils.utils import log_error, log_info


def list_classroom_data(service, semester, turma_type, saved_assignment_title=None):
    try:
        results = service.courses().list().execute()
        courses = results.get("courses", [])

        pif_courses = [
            course for course in courses
            if semester in course.get("name", "")
            and "PIF" in course.get("name", "")
            and turma_type.upper() in course.get("name", "").upper()
        ]

        if not pif_courses:
            print(f"Nenhuma turma encontrada para {semester} {turma_type}.\n")
            return None, None, None, None, None

        classroom = pif_courses[0]
        classroom_id = classroom["id"]
        classroom_name = classroom["name"]
        print(f"\nTurma selecionada automaticamente: {classroom_name}\n")

        print("Buscando listas de exercícios...\n")
        assignments = service.courses().courseWork().list(courseId=classroom_id).execute()
        course_work = assignments.get("courseWork", [])

        def is_valid(assg):
            title = assg.get("title", "")
            up = title.upper()
            if not ("LISTA" in up or "LISTAS" in up):
                return False
            if "NOTA" in up or "NOTAS" in up:
                return False
            if re.search(r'\bAV\s*\d+\b', up):
                return False
            return True

        valid_assignments = [a for a in course_work if is_valid(a)]
        valid_assignments = valid_assignments[::-1]

        if not valid_assignments:
            print("Nenhuma lista de exercícios encontrada.\n")
            return None, None, None, None, None

        selected = None

        if saved_assignment_title:
            target_exact = saved_assignment_title.strip().upper()
            target_norm = re.sub(r'[\s_]+', '', target_exact)

            selected = next(
                (a for a in valid_assignments if a.get("title", "").strip().upper() == target_exact),
                None
            )

            if not selected:
                for a in valid_assignments:
                    t = a.get("title", "")
                    t_norm = re.sub(r'[\s_]+', '', t.strip().upper())
                    if target_norm in t_norm:
                        selected = a
                        break

        if not selected:
            selected = valid_assignments[0]

        coursework_id = selected["id"]
        list_title = selected["title"]
        list_name = list_title.split(" - ")[0] if " - " in list_title else list_title

        print(f"Lista selecionada automaticamente: {list_title}")
        return classroom_id, coursework_id, classroom_name, list_name, list_title

    except HttpError as http_err:
        log_error(f"Erro na API do Classroom: {http_err}")
        return None, None, None, None, None
    except Exception as e:
        log_error(f"Erro inesperado ao selecionar dados do Classroom: {e}")
        return None, None, None, None, None