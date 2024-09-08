def list_classroom_data(service):
    while True:
        choice = input("O que você gostaria de listar? (1: Cursos, 2: Estudantes, 3: Tarefas, 4: Sair): ").strip()

        if choice == '1':
            try:
                results = service.courses().list().execute()
                courses = results.get("courses", [])
                if not courses:
                    print("Nenhum curso encontrado.")
                else:
                    print("Cursos disponíveis:")
                    for course in courses:
                        print(f"ID: {course['id']}, Nome: {course['name']}")
            except HttpError as error:
                print(f"Um erro ocorreu ao listar os cursos: {error}")
        
        elif choice == '2':
            classroom_id = input("Digite o ID da turma (classroom_id) para listar os estudantes: ").strip()
            try:
                students = service.courses().students().list(courseId=classroom_id).execute()
                if 'students' not in students or not students['students']:
                    print("Nenhum estudante encontrado para este curso.")
                else:
                    print("Estudantes inscritos na turma:")
                    for student in students['students']:
                        print(f"Nome: {student['profile']['name']['fullName']}, Email: {student['profile']['emailAddress']}")
            except HttpError as error:
                print(f"Um erro ocorreu ao listar os estudantes: {error}")
        
        elif choice == '3':
            classroom_id = input("Digite o ID da turma (classroom_id) para listar as tarefas: ").strip()
            try:
                assignments = service.courses().courseWork().list(courseId=classroom_id).execute()
                if 'courseWork' not in assignments or not assignments['courseWork']:
                    print("Nenhuma tarefa encontrada para este curso.")
                else:
                    print("Tarefas disponíveis na turma:")
                    for assignment in assignments['courseWork']:
                        print(f"ID: {assignment['id']}, Título: {assignment['title']}")
            except HttpError as error:
                print(f"Um erro ocorreu ao listar as tarefas: {error}")
        
        elif choice == '4':
            print("Saindo da lista de opções.")
            break
        
        else:
            print("Opção inválida. Por favor, escolha uma opção válida.")