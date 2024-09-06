import os
import io
import zipfile
import shutil
import re
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from gspread.exceptions import WorksheetNotFound

SCOPES = [
    "https://www.googleapis.com/auth/classroom.student-submissions.students.readonly",
    "https://www.googleapis.com/auth/classroom.profile.emails",
    "https://www.googleapis.com/auth/classroom.rosters.readonly",
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets"]

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
                
                try:
                    file_metadata = drive_service.files().get(fileId=file_id, fields='id, name').execute()
                    if not file_metadata:
                        print(f"Cannot retrieve metadata for file {file_name} for {student_name}.")
                        continue
                except HttpError as error:
                    if error.resp.status == 403 and 'cannotDownloadAbusiveFile' in str(error):
                        print(f"File {file_name} for {student_name} is identified as malware or spam and cannot be downloaded.")
                        continue
                    else:
                        print(f"An error occurred while retrieving file metadata for {student_name}: {error}")
                        continue
                
                if file_name.endswith('.c'):
                    if student_folder is None:
                        student_folder = os.path.join(download_folder, student_login)
                        if not os.path.exists(student_folder):
                            os.makedirs(student_folder)
                    file_path = os.path.join(student_folder, file_name)
                elif file_name.endswith('.rar'):
                    print(f"{student_login} não está com .zip está .rar")
                    continue
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
                        os.remove(file_path)  
                        continue
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

def create_folder_if_not_exists(folder_path):
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
        print(f"Pasta criada: {folder_path}")

def extract_zip(zip_file_path, extraction_path):
    with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
        zip_ref.extractall(extraction_path)

    macosx_path = os.path.join(extraction_path, '__MACOSX')
    if os.path.exists(macosx_path):
        print(f"Removendo pasta __MACOSX de {extraction_path}")
        shutil.rmtree(macosx_path)

def move_file(source, destination):
    try:
        shutil.move(source, destination)
    except shutil.Error as e:
        print(f"Erro ao mover arquivo: {e}")

def create_folder_if_not_exists(folder_path):
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

def organize_extracted_files(download_folder):
    submissions_folder = os.path.join(download_folder, 'submissions')
    create_folder_if_not_exists(submissions_folder)

    for item in os.listdir(download_folder):
        if item.endswith('.zip'):
            zip_file_path = os.path.join(download_folder, item)
            student_login = os.path.splitext(item)[0] 
            
            extraction_path = os.path.join(submissions_folder, student_login)
            create_folder_if_not_exists(extraction_path)
            
            try:
                extract_zip(zip_file_path, extraction_path)
            except zipfile.BadZipFile:
                print(f"Arquivo não é um zip válido: {zip_file_path}")
                continue

            # Verificar se o conteúdo extraído está diretamente na pasta ou em uma subpasta
            extracted_items = os.listdir(extraction_path)
            print(f"Arquivos extraídos de {student_login}: {extracted_items}")

            if len(extracted_items) == 1 and os.path.isdir(os.path.join(extraction_path, extracted_items[0])):
                extracted_folder = os.path.join(extraction_path, extracted_items[0])

                if extracted_items[0] == student_login:
                    print(f"A pasta extraída {extracted_items[0]} já tem o nome correto. Movendo arquivos para {extraction_path}.")
         
                    for file in os.listdir(extracted_folder):
                        source_file_path = os.path.join(extracted_folder, file)
                        destination_file_path = os.path.join(extraction_path, file)
                        print(f"Movendo arquivo: {source_file_path} -> {destination_file_path}")
                        move_file(source_file_path, destination_file_path)
                    
                    if not os.listdir(extracted_folder):
                        shutil.rmtree(extracted_folder)
                        print(f"Pasta extra deletada: {extracted_folder}")
                    else:
                        print(f"Pasta extra {extracted_folder} ainda contém arquivos e não será deletada.")
                        
                else:
                    print(f"A pasta extraída {extracted_items[0]} é diferente do nome esperado {student_login}")

                    for file in os.listdir(extracted_folder):
                        source_file_path = os.path.join(extracted_folder, file)
                        destination_file_path = os.path.join(extraction_path, file)
                        print(f"Movendo arquivo: {source_file_path} -> {destination_file_path}")
                        move_file(source_file_path, destination_file_path)

                    shutil.rmtree(extracted_folder)
                    print(f"Pasta deletada: {extracted_folder}")

            else:
                # Se não houver uma pasta extra, criar uma e mover os arquivos
                temp_folder = os.path.join(submissions_folder, student_login)
                create_folder_if_not_exists(temp_folder)
                
                for file in extracted_items:
                    source_file_path = os.path.join(extraction_path, file)
                    destination_file_path = os.path.join(temp_folder, file)
                    print(f"Movendo {file} para a pasta {temp_folder}")
                    move_file(source_file_path, destination_file_path)
                
                # Remover a pasta vazia de extração, se aplicável
                if not os.listdir(extraction_path):
                    os.rmdir(extraction_path)
                    print(f"Pasta de extração vazia removida: {extraction_path}")


def if_there_is_a_folder_inside(directory):
    def move_files_to_inicial_folder(root_folder):
        # Verifica se a pasta é oculta
        if os.path.basename(root_folder).startswith('.'):
            return

        # Lista todos os itens dentro do diretório atual
        items = os.listdir(root_folder)
        
        # Se houver subpastas, continue verificando recursivamente
        subfolders = [item for item in items if os.path.isdir(os.path.join(root_folder, item)) and not item.startswith('.')]
        
        if subfolders:
            for subfolder in subfolders:
                subfolder_path = os.path.join(root_folder, subfolder)
                move_files_to_inicial_folder(subfolder_path)
        
        # Mover arquivos não ocultos para a pasta inicial
        files = [item for item in items if os.path.isfile(os.path.join(root_folder, item)) and not item.startswith('.')]
        for file in files:
            file_path = os.path.join(root_folder, file)
            destination = os.path.join(directory, os.path.basename(root_folder), file)
            shutil.move(file_path, destination)
        
        # Após mover os arquivos, verificar se a pasta está vazia e excluí-la se estiver
        if root_folder != directory and not os.listdir(root_folder):
            os.rmdir(root_folder)

    # Lista todas as pastas A dentro do diretório X
    for folder_name in os.listdir(directory):
        folder_path = os.path.join(directory, folder_name)
        # Verifica se é uma pasta e não é oculta
        if os.path.isdir(folder_path) and not folder_name.startswith('.'):
            move_files_to_inicial_folder(folder_path)





def move_non_zip_files(download_folder):
    submissions_folder = os.path.join(download_folder, 'submissions')
    for item in os.listdir(download_folder):
        item_path = os.path.join(download_folder, item)
        if os.path.isdir(item_path) and item != 'submissions':
            destination_folder = os.path.join(submissions_folder, item)
            if not os.path.exists(destination_folder):
                os.rename(item_path, destination_folder)
                print(f"Moved {item} to {destination_folder}")

def get_gspread_client():
    creds = get_credentials()
    return gspread.authorize(creds)

def list_questions(sheet_id, sheet_name):
    try:
        client = get_gspread_client()
        sheet = client.open_by_key(sheet_id).worksheet(sheet_name) 
        rows = sheet.get_all_values()[1:] 

        questions_dict = {}
        for i, row in enumerate(rows, start=1):
            question_data = []
            question_data.append(f'{i}')
            question_data.append(f'q{i}')
            question_data.append(f'questao{i}')
            question_data.append(f'questão{i}')
        
            question_number = row[1].strip() if len(row) > 1 else ""
            question_data.append(question_number)
        
            question_name = row[2].strip() if len(row) > 2 else ""
            question_data.append(question_name)
        
            additional_names = row[3:]
            for name in additional_names:
                if name.strip():
                    question_data.append(name.strip())
        
            questions_dict[i] = question_data
    
        return questions_dict
    except WorksheetNotFound:
        print(f"A aba '{sheet_name}' não foi encontrada na planilha.")
        return None

def remove_empty_folders(submissions_folder):
    for folder_name in os.listdir(submissions_folder):
        folder_path = os.path.join(submissions_folder, folder_name)
        if os.path.isdir(folder_path):
            if not os.listdir(folder_path):  
                shutil.rmtree(folder_path)  
                print(f"A pasta '{folder_name}' foi deletada por não ter nenhum arquivo dentro.")

def rename_files_based_on_dictionary(submissions_folder, questions_dict):
    for student_login in os.listdir(submissions_folder):
        student_folder_path = os.path.join(submissions_folder, student_login)

        if os.path.isdir(student_folder_path):
            print(f"Verificando pasta do estudante: {student_folder_path}")
            
            for filename in os.listdir(student_folder_path):
                file_path = os.path.join(student_folder_path, filename)

                if os.path.isfile(file_path) and not filename.startswith('.'):
                    print(f"Verificando arquivo: {filename}")

                    base_filename_clean = os.path.splitext(filename)[0].lower().replace("_", " ")

                    found_match = False  
                    for question_number, possible_names in questions_dict.items():
                        for possible_name in possible_names:
                            possible_name_clean = possible_name.lower()
                            possible_name_parts = possible_name_clean.split()

                            if any(part in base_filename_clean for part in possible_name_parts):
                                new_filename = f"q{question_number}_{student_login}.c"
                                new_file_path = os.path.join(student_folder_path, new_filename)

                                os.rename(file_path, new_file_path)
                                print(f"Renamed '{filename}' to '{new_filename}' for student '{student_login}'")

                                found_match = True
                                break  
                        if found_match:
                            break  

                    if not found_match:
                        print(f"Nenhum nome correspondente encontrado para o arquivo {filename}")

def no_c_files_in_directory(submissions_folder):
    for root, dirs, files in os.walk(submissions_folder, topdown=False):
        # Processar arquivos não ocultos
        for file in files:
            if not file.startswith('.'):  # Ignorar arquivos ocultos
                file_path = os.path.join(root, file)
                file_name, file_extension = os.path.splitext(file)

                if file_name.lower() == 'makefile':
                    print(f"Deletando arquivo Makefile: {file_path}")
                    os.remove(file_path)
                elif file_extension and file_extension != '.c' and '.C':
                    print(f"Deletando arquivo com extensão diferente de .c: {file_path}")
                    os.remove(file_path)
                # Arquivos sem extensão são mantidos

        # Remover pastas não ocultas e vazias
        for dir in dirs:
            if not dir.startswith('.'):  # Ignorar pastas ocultas
                dir_path = os.path.join(root, dir)
                if not os.listdir(dir_path):  # Verifica se a pasta está vazia
                    print(f"Deletando pasta vazia: {dir_path}")
                    os.rmdir(dir_path)
                    

def list_classroom_data(service):
    while True:
        print("\nEscolha a turma:")
        try:
            results = service.courses().list().execute()
            courses = results.get("courses", [])
            
            pif_courses = [course for course in courses if 'PIF' in course['name']]
            
            if not pif_courses:
                print("Nenhum curso 'PIF' encontrado.")
            else:
                for index, course in enumerate(pif_courses, start=1):
                    print(f"{index} - {course['name']}")
                print(f"{len(pif_courses) + 1} - Sair")
                
                choice = int(input("Escolha um número para selecionar a turma: ").strip())
                if choice == len(pif_courses) + 1:
                    print("Saindo da lista de opções.")
                    return None, None, None, None
                
                if 1 <= choice <= len(pif_courses):
                    classroom_id = pif_courses[choice - 1]['id']
                    classroom_name = pif_courses[choice - 1]['name']
                else:
                    print("Opção inválida. Tente novamente.")
                    continue

        except HttpError as error:
            print(f"Um erro ocorreu ao listar os cursos: {error}")
            continue

        print("\nEscolha a lista de exercícios:")
        try:
            assignments = service.courses().courseWork().list(courseId=classroom_id).execute()
            course_work = assignments.get("courseWork", [])
            
            if not course_work:
                print("Nenhuma atividade encontrada para este curso.")
            else:
                valid_assignments = []
                for assignment in course_work:
                    title = assignment['title']
                    
                    if any(keyword in title for keyword in ['NOTA', 'NOTAS']) or re.match(r'^AV', title.split(' - ')[0]):
                        continue
                    
                    valid_assignments.append(assignment)
                
                if not valid_assignments:
                    print("Nenhuma atividade válida encontrada para este curso.")
                    return None, None, None, None

                valid_assignments = valid_assignments[::-1]
                for index, assignment in enumerate(valid_assignments):
                    print(f"{index} - {assignment['title']}")
                print(f"{len(valid_assignments)} - Sair")
                
                choice = int(input("Escolha um número para selecionar a lista de exercícios: ").strip())
                if choice == len(valid_assignments):
                    print("Saindo da lista de opções.")
                    return None, None, None, None
                
                if 0 <= choice < len(valid_assignments):
                    coursework_id = valid_assignments[choice]['id']
                    list_title = valid_assignments[choice]['title']
                
                    if 'LISTA' in list_title:
                        list_name = list_title.split(' - ')[0]
                    else:
                        list_name = ' '.join(list_title.split(' - ')[:-1]) 
                else:
                    print("Opção inválida. Tente novamente.")
                    continue

        except HttpError as error:
            print(f"Um erro ocorreu ao listar as tarefas: {error}")
            continue
        
        return classroom_id, coursework_id, classroom_name, list_name

def read_sheet_id_from_file(filename):
    try:
        with open(filename, 'r') as file:
            sheet_id = file.read().strip() 
        return sheet_id
    except FileNotFoundError:
        print(f"Arquivo {filename} não encontrado.")
        return None
    except Exception as e:
        print(f"Erro ao ler o arquivo {filename}: {e}")
        return None

def main():
    creds = get_credentials()
    try:
        classroom_service = build("classroom", "v1", credentials=creds)
        drive_service = build("drive", "v3", credentials=creds)

        classroom_id, coursework_id, classroom_name, list_name = list_classroom_data(classroom_service)
        if classroom_id and coursework_id and classroom_name and list_name : 
            print(f"\n Você escolheu a turma : {classroom_name}")
            print(f"\n E a atividade : {list_name} \n")
        else:
            print("Não foi possível obter todos os dados. Verifique a seleção e tente novamente.")
            return

        submissions = classroom_service.courses().courseWork().studentSubmissions().list(courseId=classroom_id, courseWorkId=coursework_id).execute()

        download_folder = 'Downloads'
        if not os.path.exists(download_folder):
            os.makedirs(download_folder)

        download_submissions(classroom_service, drive_service, submissions, download_folder, classroom_id)

        print("Download completo. Arquivos salvos em:", os.path.abspath(download_folder))

        organize_extracted_files(download_folder)
        move_non_zip_files(download_folder)

        print("Processo concluído. Arquivos salvos em:", os.path.abspath(download_folder))

        submissions_folder = os.path.join(download_folder, 'submissions')
        if_there_is_a_folder_inside(submissions_folder)
        #no_c_files_in_directory(submissions_folder)
        remove_empty_folders(submissions_folder)

        sheet_id = read_sheet_id_from_file('sheet_id.txt')
        questions_data = list_questions(sheet_id, list_name)

        if not questions_data:
            return
        else:
            rename_files_based_on_dictionary(submissions_folder, questions_data)

    except HttpError as error:
        print(f"Um erro ocorreu: {error}")

if __name__ == "__main__":
    main()
