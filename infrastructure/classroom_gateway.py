from googleapiclient.errors import HttpError
from utils.utils import log_error

def list_classroom_data(service, semester, turma_type, saved_assignment_title=None):
    try:
        results = service.courses().list().execute()
        courses = results.get("courses", [])
        pif_courses = [
            course for course in courses 
            if semester in course["name"] and "PIF" in course["name"] and turma_type.upper() in course["name"].upper()
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

        valid_assignments = [
            a for a in course_work if any(k in a["title"].upper() for k in ["LISTA", "LISTAS"])
        ]

        valid_assignments = valid_assignments[::-1]

        if not valid_assignments:
            print("Nenhuma lista de exercícios encontrada.\n")
            return None, None, None, None, None

        if saved_assignment_title:
            selected = next((a for a in valid_assignments if a["title"] == saved_assignment_title), None)
            if not selected:
                print(f"A lista '{saved_assignment_title}' não foi encontrada.\n")
                return None, None, None, None, None
        else:
            print("\nEscolha a lista de exercícios:")
            for index, assignment in enumerate(valid_assignments):
                print(f"{index} - {assignment['title']}")
            print(f"{len(valid_assignments)} - Sair")

            choice = int(input("\nDigite o número da lista: ").strip())
            if choice == len(valid_assignments):
                print("Saindo da seleção.\n")
                return None, None, None, None, None
            if 0 <= choice < len(valid_assignments):
                selected = valid_assignments[choice]
            else:
                print("Opção inválida.\n")
                return None, None, None, None, None

        coursework_id = selected["id"]
        list_title = selected["title"]
        list_name = list_title.split(" - ")[0] if " - " in list_title else list_title

        return classroom_id, coursework_id, classroom_name, list_name, list_title

    except HttpError as http_err:
        log_error(f"Erro na API do Classroom: {http_err}")
        return None, None, None, None, None
    except Exception as e:
        log_error(f"Erro inesperado ao selecionar dados do Classroom: {e}")
        return None, None, None, None, None
