import os
import io
import zipfile
import shutil
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

SCOPES = [
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/classroom.rosters.readonly",
    "https://www.googleapis.com/auth/classroom.student-submissions.students.readonly",
    "https://www.googleapis.com/auth/classroom.profile.emails",
    "https://www.googleapis.com/auth/drive.readonly"
]

def get_credentials():
    creds = None
    
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
       
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return creds

def list_classroom_data(service):
    """
    Lista cursos, estudantes e tarefas com base na escolha do usuário, com tratamento de erros.
    """
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

def download_submissions(classroom_service, drive_service, submissions, download_folder, classroom_id):
    for submission in submissions.get('studentSubmissions', []):
        student_id = submission['userId']
        student = classroom_service.courses().students().get(courseId=classroom_id, userId=student_id).execute()
        student_email = student['profile']['emailAddress']
        student_login = extract_prefix(student_email)
        student_name = student['profile']['name']['fullName']
        
        attachments = submission.get('assignmentSubmission', {}).get('attachments', [])

        student_folder = None
        if attachments:
            for attachment in attachments:
                file_id = attachment.get('driveFile', {}).get('id')
                file_name = attachment.get('driveFile', {}).get('title')
                request = drive_service.files().get_media(fileId=file_id)

                if file_name.endswith('.c'):
                    if student_folder is None:
                        student_folder = os.path.join(download_folder, student_login)
                        if not os.path.exists(student_folder):
                            os.makedirs(student_folder)
                    file_path = os.path.join(student_folder, file_name)
                else:
                    file_path = os.path.join(download_folder, file_name)

                try:
                    with io.FileIO(file_path, 'wb') as fh:
                        downloader = MediaIoBaseDownload(fh, request)
                        done = False
                        while not done:
                            status, done = downloader.next_chunk()
                            print(f"Downloading {file_name} for {student_name}: {int(status.progress() * 100)}%")
                except HttpError as error:
                    if error.resp.status == 403 and 'cannotDownloadAbusiveFile' in str(error):
                        print(f"File {file_name} for {student_name} is identified as malware or spam and cannot be downloaded.")
                    else:
                        print(f"An error occurred for {student_name}: {error}")
                    continue

                if file_name.endswith('.zip'):
                    expected_name = student_login + '.zip'
                    if file_name != expected_name:
                        corrected_path = os.path.join(download_folder, expected_name)
                        os.rename(file_path, corrected_path)
                        print(f"Renamed {file_name} to {expected_name} for {student_name}")

        else:
            print(f"No attachments found for {student_name}")
            
def extract_prefix(email):
    return email.split('@')[0]

def extract_zip_files(download_folder):
    submissions_folder = os.path.join(download_folder, 'submissions')
    if not os.path.exists(submissions_folder):
        os.makedirs(submissions_folder)

    for file_name in os.listdir(download_folder):
        file_path = os.path.join(download_folder, file_name)
        if file_name.endswith('.zip'):
            try:
            
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    zip_ref.extractall(submissions_folder)
                    print(f"Extracted {file_name} to {submissions_folder}")
                validate_extracted_folder(submissions_folder, file_name)
            except zipfile.BadZipFile:
                print(f"File {file_name} is not a valid zip file and was skipped.")
            except Exception as e:
                print(f"An error occurred while extracting {file_name}: {e}")

def validate_extracted_folder(submissions_folder, zip_file_name):
    student_login = zip_file_name[:-4] 
    extracted_folder = os.path.join(submissions_folder, student_login)
    
    if not os.path.isdir(extracted_folder):
       #Tentar algum código que funcione aqui pra renomear a pasta quando a pasta extraida não for o student_login
        os.makedirs(extracted_folder)
        print(f"Created folder for {student_login} in {submissions_folder}")

    move_c_files_to_folder(submissions_folder, student_login)

def move_c_files_to_folder(submissions_folder, student_login):
   
    student_folder = os.path.join(submissions_folder, student_login)
    
    for item in os.listdir(submissions_folder):
        item_path = os.path.join(submissions_folder, item)
        if os.path.isfile(item_path) and item.endswith('.c'):
            destination_path = os.path.join(student_folder, item)
            shutil.move(item_path, destination_path)
            print(f"Moved {item} to {student_folder}")

def move_non_zip_files(download_folder):
    submissions_folder = os.path.join(download_folder, 'submissions')
    for item in os.listdir(download_folder):
        item_path = os.path.join(download_folder, item)
        if os.path.isdir(item_path) and item != 'submissions':
            destination_folder = os.path.join(submissions_folder, item)
            if not os.path.exists(destination_folder):
                os.rename(item_path, destination_folder)
                print(f"Moved {item} to {destination_folder}")

def list_questions():
    questions_dict = {}
    num_questions = int(input("Quantas questões tem a lista: "))

    for i in range(1, num_questions + 1):
        question_data = []
        
        question_data.append(f'q{i}')
        question_data.append(f'questao{i}')
        question_data.append(f'questão{i}')
        
        question_number = input(f"Qual o número da questão {i} no beecrowd: ").strip()
        question_data.append(question_number)
        
        question_name = input("Qual o nome da questão no beecrowd: ").strip()
        question_data.append(question_name)
        #talvez salvar sem os espaços em branco??
        
        while True:
            additional_names = input("Quer digitar outro nome para esta questão? (s/n): ").strip().lower()
            if additional_names == 's':
                additional_name = input("Digite o novo nome da questão: ").strip()
                question_data.append(additional_name)
            elif additional_names == 'n':
                break
            else:
                print("Resposta inválida. Por favor, digite 's' para sim ou 'n' para não.")
        
        questions_dict[i] = question_data
    
    return questions_dict

def main():
    creds = get_credentials()
    try:
        classroom_service = build("classroom", "v1", credentials=creds)
        drive_service = build("drive", "v3", credentials=creds)

        list_classroom_data(classroom_service)

        classroom_id = input("Digite o ID da turma (classroom_id): ")
        coursework_id = input("Digite o ID do trabalho (coursework_id): ")

        submissions = classroom_service.courses().courseWork().studentSubmissions().list(courseId=classroom_id, courseWorkId=coursework_id).execute()

        download_folder = 'Downloads'
        if not os.path.exists(download_folder):
            os.makedirs(download_folder)

        download_submissions(classroom_service, drive_service, submissions, download_folder, classroom_id)

        print("Download completo. Arquivos salvos em:", os.path.abspath(download_folder))

        extract_zip_files(download_folder)
        move_non_zip_files(download_folder)

        print("Processo concluído. Arquivos salvos em:", os.path.abspath(download_folder))

        questions_data = list_questions()
        print(questions_data)


    except HttpError as error:
        print(f"Um erro ocorreu: {error}")

if __name__ == "__main__":
    main()
