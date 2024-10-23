import os
import io
import zipfile
import rarfile
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
    try:
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
    except Exception as e:
        log_error(f"Erro em pegar as credenciais: {str(e)}")

def list_classroom_data(service):
    try:
        while True:
            print("\nEscolha a turma:")
            try:
                results = service.courses().list().execute()
                courses = results.get("courses", [])
                
                pif_courses = [course for course in courses if 'PIF' in course['name']]
                
                if not pif_courses:
                    print("Nenhuma turma de PIF encontrada.")
                else:
                    for index, course in enumerate(pif_courses, start=1):
                        print(f"{index} - {course['name']}")
                    print(f"{len(pif_courses) + 1} - Sair")
                    
                    choice = int(input("Escolha um número para selecionar a turma: ").strip())
                    if choice == len(pif_courses) + 1:
                        print("Saindo da lista de opções.")
                        return None, None, None, None, None
                    
                    if 1 <= choice <= len(pif_courses):
                        classroom_id = pif_courses[choice - 1]['id']
                        classroom_name = pif_courses[choice - 1]['name']
                    else:
                        print("Opção inválida. Tente novamente.")
                        continue

            except HttpError as error:
                print(f"Ocorreu um erro ao listar as turmas: {error}")
                continue

            print("\nEscolha a lista de exercícios:")
            try:
                assignments = service.courses().courseWork().list(courseId=classroom_id).execute()
                course_work = assignments.get("courseWork", [])
                
                if not course_work:
                    print(f"Nenhuma lista de exercícios encontrada para esta turma: {classroom_name}")
                else:
                    valid_assignments = []
                    for assignment in course_work:
                        title = assignment['title']
                        
                        if any(keyword in title for keyword in ['LISTA', 'LISTAS']):
                            valid_assignments.append(assignment)
                    
                    if not valid_assignments:
                        print(f"Nenhuma lista de exercícios válida encontrada para esta turma: {classroom_name}")
                        return None, None, None, None, None

                    valid_assignments = valid_assignments[::-1]
                    for index, assignment in enumerate(valid_assignments):
                        print(f"{index} - {assignment['title']}")
                    print(f"{len(valid_assignments)} - Sair")
                    
                    choice = int(input("Escolha um número para selecionar a lista de exercícios: ").strip())
                    if choice == len(valid_assignments):
                        print("Saindo da lista de opções.")
                        return None, None, None, None, None
                    
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
                print(f"Um erro ocorreu ao listar as listas de exercícios: {error}")
                continue
            
            return classroom_id, coursework_id, classroom_name, list_name, list_title
    except Exception as e:
        log_error(f"Erro em listar dados do classroom: {str(e)}")    
    
def download_submissions(classroom_service, drive_service, submissions, download_folder, classroom_id, worksheet):
    try:
        if worksheet is not None:
            header = [['Nome do Aluno', 'Email', 'Student Login', 'Entregou?', 'Atrasou?', 'Formatação', 'Comentários']]
            
            first_row = worksheet.row_values(1)
            if not first_row:
                worksheet.append_rows(header, table_range='A1')

            existing_records = worksheet.get_all_values()  
            alunos_registrados = set() 

            for record in existing_records:
                if len(record) > 2: 
                    alunos_registrados.add(record[2])  

        for submission in submissions.get('studentSubmissions', []):
            student_id = submission['userId']
            student = classroom_service.courses().students().get(courseId=classroom_id, userId=student_id).execute()
            student_email = student['profile']['emailAddress']
            student_login = extract_prefix(student_email)
            student_name = student['profile']['name']['fullName']
            late = submission.get('late', False)
            entregou = "1" 
            atrasou = "1" if late else "0"
            formatacao = 0
            comentarios = None
            
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
                            print(f"Não foi possível recuperar os metadados para o arquivo {file_name} de {student_name}.")
                            continue 
                    except HttpError as error:
                        if error.resp.status == 403 and 'cannotDownloadAbusiveFile' in str(error):
                            print(f"O arquivo {file_name} de {student_name} foi identificado como malware ou spam e não pode ser baixado.")
                            continue  
                        else:
                            print(f"Ocorreu um erro ao recuperar os metadados do arquivo para {student_name}: {error}")
                            continue  
       
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
                                progress_percentage = int(status.progress() * 100)
                                print(f"Baixando {file_name} de {student_name}: {progress_percentage}%")
                            
                            if progress_percentage == 0:
                                comentarios = "Não foi baixado arquivos, verificar o que foi entregue no classroom"
                                entregou = "0"
                                os.remove(file_path)
                            
                    except HttpError as error:
                        if error.resp.status == 403 and 'cannotDownloadAbusiveFile' in str(error):
                            print(f"O arquivo {file_name} de {student_name} foi identificado como malware ou spam e não pode ser baixado.")
                            os.remove(file_path) 
                            if worksheet is not None and student_login not in alunos_registrados:
                                worksheet.append_rows([[student_name, student_email, student_login, "Malware ou spam", atrasou, formatacao, comentarios]])
                                alunos_registrados.add(student_login)
                            continue
                        else:
                            print(f"Ocorreu um erro com {student_name}: {error}")
                            if worksheet is not None and student_login not in alunos_registrados:
                                worksheet.append_rows([[student_name, student_email, student_login, "Erro de download", atrasou, formatacao, comentarios]])
                                alunos_registrados.add(student_login)
                            continue

                    if file_name.endswith('.zip'):
                        expected_name = student_login + '.zip'
                        if file_name != expected_name:
                            corrected_path = os.path.join(download_folder, expected_name)
                            os.rename(file_path, corrected_path)
                            print(f"Renomeado {file_name} para {expected_name} de {student_name}")

            else:
                print(f"Nenhum anexo encontrado para {student_name}")
                atrasou = "0"
                entregou = "0"
            
            if worksheet is not None and student_login not in alunos_registrados:
                worksheet.append_rows([[student_name, student_email, student_login, entregou, atrasou, formatacao, comentarios]])
                alunos_registrados.add(student_login)

    except Exception as e:
        log_error(f"Erro ao baixar submissões: {str(e)}")

def extract_prefix(email):
    try:
        return email.split('@')[0]
    except Exception as e:
        log_error(f"Erro em extrair o prefixo do email {str(e)}")

def update_worksheet(worksheet, student_login, entregou=None, formatacao=None):
    try:
        data = worksheet.get_all_values()
        
        for idx, row in enumerate(data):
            if row[2] == student_login: 
                entregou_atual = row[3] if entregou is None else entregou 
                formatacao_atual = row[5] if formatacao is None else formatacao
                
                worksheet.update([[entregou_atual]], f'D{idx+1}')   
                worksheet.update([[formatacao_atual]], f'F{idx+1}')
                
                print(f"Atualizado para {student_login} com status: {entregou_atual}, {formatacao_atual}")
                return
        print(f"Login {student_login} não encontrado na planilha.")
    except Exception as e:
        print(f"Erro ao atualizar a planilha: {e}")

def update_worksheet_comentario(worksheet, student_login, comentario=None):
    try:
        data = worksheet.get_all_values()
        
        for idx, row in enumerate(data):
            if row[2] == student_login: 
                comentario_atual = row[6] if comentario is None else comentario
                
                #worksheet.update([[comentario_atual]], f'G{idx+1}')   

                col = 5
                while col < len(row) and row[col]:   
                    col += 1
                
                cell_range = f'{chr(65+col)}{idx+1}'
                worksheet.update([[comentario_atual]], cell_range)
                
                print(f"Atualizado para {student_login} com status: {comentario_atual}")
                return
        print(f"Login {student_login} não encontrado na planilha.")
    except Exception as e:
        print(f"Erro ao atualizar a planilha: {e}")

def is_real_zip(file_path):
    try:
        with zipfile.ZipFile(file_path, 'r') as zip_ref:
            if zip_ref.testzip() is None:
                return True
            else:
                return False
    except zipfile.BadZipFile:
        return False

def extract_zip(zip_file_path, extraction_path):
    try:
        if not is_real_zip(zip_file_path):
            print(f"O arquivo {zip_file_path} não é um .zip válido.")
            return

        with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
            zip_ref.extractall(extraction_path)

        macosx_path = os.path.join(extraction_path, '__MACOSX')
        if os.path.exists(macosx_path):
            print(f"Removendo pasta __MACOSX de {extraction_path}")
            shutil.rmtree(macosx_path)

    except Exception as e:
        log_error(f"Erro ao extrair o zip {str(e)}") 

def extract_rar(rar_file_path, extraction_path):
    try:
        try:
            with rarfile.RarFile(rar_file_path, 'r') as rar_ref:
                rar_ref.extractall(extraction_path)
        except rarfile.Error as e:
            print(f"Erro ao usar rarfile: {e}")
            print(f"Tentando extrair com unar...")

        macosx_path = os.path.join(extraction_path, '__MACOSX')
        if os.path.exists(macosx_path):
            print(f"Removendo pasta __MACOSX de {extraction_path}")
            shutil.rmtree(macosx_path)

    except Exception as e:
        log_error(f"Erro em extrair o rar {str(e)}")  
    
def move_file(source, destination):
    try:
        try:
            shutil.move(source, destination)
        except shutil.Error as e:
            print(f"Erro ao mover arquivo: {e}")
    except Exception as e:
        log_error(f"Erro ao mover o arquivo {str(e)}")  

def create_folder_if_not_exists(folder_path):
    try:
        if not os.path.exists(folder_path):
                os.makedirs(folder_path)
                print(f"Pasta criada: {folder_path}")
    except Exception as e:
        log_error(f"Erro em criar a pasta se não existir a pasta {str(e)}")       

def rename_directory_if_needed(directory_path, expected_name):
    try:
        if os.path.isdir(directory_path):
            current_name = os.path.basename(directory_path)
            if current_name != expected_name:
                new_directory_path = os.path.join(os.path.dirname(directory_path), expected_name)
                os.rename(directory_path, new_directory_path)
                print(f"Pasta renomeada de {current_name} para {expected_name}")
                return new_directory_path
        return directory_path
    except Exception as e:
        log_error(f"Erro ao renomear o diretorio se necessário {str(e)}") 

def organize_extracted_files(download_folder, worksheet):
    try:
        submissions_folder = os.path.join(download_folder, 'submissions')
        create_folder_if_not_exists(submissions_folder)

        for item in os.listdir(download_folder):
            item_path = os.path.join(download_folder, item)

            if item.endswith('.zip') or item.endswith('.rar'):
                student_login = os.path.splitext(item)[0]  
                extraction_path = os.path.join(submissions_folder, student_login)
                create_folder_if_not_exists(extraction_path)

                try:
                    if item.endswith('.zip'):
                        extract_zip(item_path, extraction_path)
                    elif item.endswith('.rar'):
                        extract_rar(item_path, extraction_path)
                except (zipfile.BadZipFile, rarfile.Error) as e:
                    print(f"Erro ao extrair o arquivo {item}: {e}")
                    if worksheet is not None:
                        update_worksheet(worksheet, student_login, entregou="Compactação com erro")
                    continue

                extracted_items = os.listdir(extraction_path)
                if not extracted_items:
                    print(f"O arquivo {item} foi extraído, mas o diretório está vazio.")
                    if worksheet is not None:
                        update_worksheet(worksheet, student_login, entregou="Zip vazio")
                    continue

                if len(extracted_items) == 1 and os.path.isdir(os.path.join(extraction_path, extracted_items[0])):
                    extracted_folder = os.path.join(extraction_path, extracted_items[0])
                    extracted_folder = rename_directory_if_needed(extracted_folder, student_login)

                for extracted_item in os.listdir(extraction_path):
                    extracted_item_path = os.path.join(extraction_path, extracted_item)

                    if os.path.exists(extracted_item_path):  
                        if os.path.isfile(extracted_item_path):
                            if extracted_item.endswith('.zip'):
                                print(f"Extraindo arquivo zip aninhado: {extracted_item}")
                                try:
                                    extract_zip(extracted_item_path, extraction_path)
                                    os.remove(extracted_item_path)
                                except zipfile.BadZipFile:
                                    print(f"Erro ao extrair zip aninhado: {extracted_item_path}")
                            elif extracted_item.endswith('.rar'):
                                print(f"Extraindo arquivo rar aninhado: {extracted_item}")
                                try:
                                    extract_rar(extracted_item_path, extraction_path)
                                    os.remove(extracted_item_path)
                                except rarfile.Error:
                                    print(f"Erro ao extrair rar aninhado: {extracted_item_path}")
                    else:
                        print(f"Arquivo não encontrado: {extracted_item_path}")
            else:
                continue

            extracted_items = os.listdir(extraction_path)
            print(f"Arquivos extraídos de {student_login}: {extracted_items}")

            if len(extracted_items) == 1 and os.path.isdir(os.path.join(extraction_path, extracted_items[0])):
                extracted_folder = os.path.join(extraction_path, extracted_items[0])

                if extracted_items[0] == student_login:
                    print(f"A pasta extraída {extracted_items[0]} já tem o nome correto. Movendo arquivos para {extraction_path}.")
                    
                    if os.path.exists(extracted_folder):
                        for file in os.listdir(extracted_folder):
                            source_file_path = os.path.join(extracted_folder, file)
                            destination_file_path = os.path.join(extraction_path, file)

                            if os.path.exists(source_file_path):  
                                print(f"Movendo arquivo: {source_file_path} -> {destination_file_path}")
                                move_file(source_file_path, destination_file_path)
                            else:
                                print(f"Arquivo não encontrado: {source_file_path}")
                        
                        if not os.listdir(extracted_folder):
                            shutil.rmtree(extracted_folder)
                            print(f"Pasta extra deletada: {extracted_folder}")
                        else:
                            print(f"Pasta extra {extracted_folder} ainda contém arquivos e não será deletada.")
                else:
                    print(f"A pasta extraída {extracted_items[0]} é diferente do nome esperado {student_login}")
                    if os.path.exists(extracted_folder):  
                        for file in os.listdir(extracted_folder):
                            source_file_path = os.path.join(extracted_folder, file)
                            destination_file_path = os.path.join(extraction_path, file)

                            if os.path.exists(source_file_path):  
                                print(f"Movendo arquivo: {source_file_path} -> {destination_file_path}")
                                move_file(source_file_path, destination_file_path)
                            else:
                                print(f"Arquivo não encontrado: {source_file_path}")

                        shutil.rmtree(extracted_folder)
                        print(f"Pasta deletada: {extracted_folder}")
    except Exception as e:
        log_error(f"Erro ao organizar arquivos extraídos: {str(e)}")

def if_there_is_a_folder_inside(submissions_folder):
    try:
        def move_files_to_inicial_folder(first_folder):
            if os.path.basename(first_folder).startswith('.'):
                return

            items = os.listdir(first_folder)
            
            subfolders = [item for item in items if os.path.isdir(os.path.join(first_folder, item)) and not item.startswith('.')]
            
            if subfolders:
                for subfolder in subfolders:
                    subfolder_path = os.path.join(first_folder, subfolder)
                    move_files_to_inicial_folder(subfolder_path)
            
            files = [item for item in items if os.path.isfile(os.path.join(first_folder, item)) and not item.startswith('.')]
            for file in files:
                file_path = os.path.join(first_folder, file)
                destination = os.path.join(submissions_folder, os.path.basename(first_folder), file)
        
                shutil.move(file_path, destination)
            
            if first_folder != submissions_folder and not os.listdir(first_folder):
                os.rmdir(first_folder)

        for folder_name in os.listdir(submissions_folder):
            folder_path = os.path.join(submissions_folder, folder_name)
            if os.path.isdir(folder_path) and not folder_name.startswith('.'):
                move_files_to_inicial_folder(folder_path)
    except Exception as e:
        log_error(f"Erro se existe uma pasta dentro da pasta: {str(e)}")

def delete_subfolders_in_student_folders(submissions_folder):
    try:
        for student_folder in os.listdir(submissions_folder):
            student_folder_path = os.path.join(submissions_folder, student_folder)

            if os.path.isdir(student_folder_path): 
                for item in os.listdir(student_folder_path):
                    item_path = os.path.join(student_folder_path, item)

                    if os.path.isdir(item_path): 
                        print(f"Deletando subpasta: {item_path}")
                        shutil.rmtree(item_path)
    except Exception as e:
        log_error(f"Erro ao deletar pastas dentro das pastas dos estudantes: {str(e)}")

def move_non_zip_files(download_folder):
    try:
        submissions_folder = os.path.join(download_folder, 'submissions')
        for item in os.listdir(download_folder):
            item_path = os.path.join(download_folder, item)
            if os.path.isdir(item_path) and item != 'submissions':
                destination_folder = os.path.join(submissions_folder, item)
                if not os.path.exists(destination_folder):
                    os.rename(item_path, destination_folder)
                    print(f"Moved {item} to {destination_folder}")
    except Exception as e:
        log_error(f"Erro ao mover arquivos que não estavão zipados {str(e)}")

def get_gspread_client():
    try:
        creds = get_credentials()
        return gspread.authorize(creds)
    except Exception as e:
        log_error(f"Erro em conseguir a credencial do google spreadsheet {str(e)}")

def list_questions_default():
    print("\nNão encontrei planilha para essa lista. Para renomear as questões será utilizado um dicionário de possíveis nomes para as questões de 1 a 4.")

      
    questions_dict = {
        1: ['1', 'q1', 'Q1', 'questao1', 'questão1'],
        2: ['2', 'q2', 'Q2', 'questao2', 'questão2'],
        3: ['3', 'q3', 'Q3', 'questao3', 'questão3'],
        4: ['4', 'q4', 'Q4', 'questao4', 'questão4']
    }

    return questions_dict

def list_questions(sheet_id, sheet_name):
    try:
        try:
            client = get_gspread_client()
            sheet = client.open_by_key(sheet_id).worksheet(sheet_name) 
            rows = sheet.get_all_values()[1:] 

            if not rows:
                print(f"A planilha '{sheet_name}' está vazia. O sistema vai usar o dicionário padrão.")
                return list_questions_default()

            questions_dict = {}
            for i, row in enumerate(rows, start=1):
                question_data = []
                question_data.append(f'{i}')
                question_data.append(f'q{i}')
                question_data.append(f'Q{i}')
                question_data.append(f'questao{i}')
                question_data.append(f'questão{i}')
            
                beecrowd_number = row[1].strip() if len(row) > 1 and row[1].strip() else ""
                if beecrowd_number:
                    question_data.append(beecrowd_number)
                    question_data.append(f'q{beecrowd_number}')
            
                question_name = row[2].strip() if len(row) > 2 and row[2].strip() else ""
                if question_name:
                    question_data.append(question_name)
            
                additional_names = row[3:]
                for name in additional_names:
                    name = name.strip()
                    if name: 
                        question_data.append(name)
            
                if question_data:
                    questions_dict[i] = question_data
                    print(f"O dicionário está assim: {question_data}")
        
            return questions_dict
        except WorksheetNotFound:
            print(f"A aba '{sheet_name}' não foi encontrada na planilha, o sistema vai usar o dicionário padrão.")
            return list_questions_default()
    except Exception as e:
        log_error(f"Erro em pegar da planilha os nomes das questões vai usar o dicionário padrão {str(e)}")
        return list_questions_default()       

def remove_empty_folders(submissions_folder):
    try:
        for folder_name in os.listdir(submissions_folder):
            folder_path = os.path.join(submissions_folder, folder_name)
            if os.path.isdir(folder_path):
                if not os.listdir(folder_path):  
                    shutil.rmtree(folder_path)  
                    print(f"A pasta '{folder_name}' foi deletada por não ter nenhum arquivo dentro.")
    except Exception as e:
        log_error(f"Erro em remover pastas vazias {str(e)}")

def verification_renamed(message):
    try:
        with open("verifiqueRenomeacao.txt", "a") as renamed_verification:
            renamed_verification.write(f"{message}\n")
    except Exception as e:
        log_error(f"Não foi possível criar ou escrever no arquivo de verificação: {str(e)}")

def rename_files_based_on_dictionary(submissions_folder, questions_dict, worksheet, haskell=None):
    try:

        for student_login in os.listdir(submissions_folder):
            student_folder_path = os.path.join(submissions_folder, student_login)

            if os.path.isdir(student_folder_path):
                print(f"Verificando pasta do estudante: {student_folder_path}")
    
                used_questions = set()

                for filename in os.listdir(student_folder_path):
                    file_path = os.path.join(student_folder_path, filename)

                    if os.path.isfile(file_path) and not filename.startswith('.'):
                        print(f"Verificando arquivo: {filename}")
                        
                        for i in range(1, 5):
                            if haskell == 1:
                                expected_filename = f"q{i}_{student_login}.hs"
                            else:
                                expected_filename = f"q{i}_{student_login}.c"
                            
                            if filename == expected_filename:
                                print(f"O arquivo '{filename}' já está no formato correto.")
                                break  

                        else: 
                            base_filename_clean = os.path.splitext(filename)[0].lower().replace("_", " ").replace(student_login.lower(), "").strip()

                            found_match = False  
                            for question_number, possible_names in questions_dict.items():
                                if question_number in used_questions:
                                    continue

                                for possible_name in reversed(possible_names):
                                    possible_name_clean = possible_name.lower().strip()

                                    if base_filename_clean == possible_name_clean:
                                        if haskell == 1:
                                            new_filename = f"q{question_number}_{student_login}.hs"
                                        else:
                                            new_filename = f"q{question_number}_{student_login}.c"

                                        new_file_path = os.path.join(student_folder_path, new_filename)

                                        if filename != new_filename:
                                            os.rename(file_path, new_file_path)
                                            print(f"RENOMEADO: '{filename}' para '{new_filename}' para o estudante '{student_login}'")
                                            used_questions.add(question_number) 
                                        else:
                                            print(f"O arquivo '{filename}' já está com o nome correto.")
                                        found_match = True
                                        break  

                                if found_match:
                                    break  
                        
                            if not found_match:
                                if worksheet is not None:
                                    update_worksheet(worksheet, student_login, formatacao="1")
                                print(f"Tentando correspondência parcial para o arquivo {filename}")
                                for question_number, possible_names in questions_dict.items():
                                    if question_number in used_questions:
                                        print(f"Chave q{question_number} já foi usada para {student_login}, pulando.")
                                        continue
                                    
                                    for possible_name in reversed(possible_names):
                                        possible_name_clean = possible_name.lower().strip()
                                        possible_name_parts = possible_name_clean.split()
                                        print(f"{possible_name_parts}")

                                        if any(part in base_filename_clean for part in possible_name_parts):
                                            if haskell == 1:
                                                new_filename = f"q{question_number}_{student_login}.hs"
                                            else:
                                                new_filename = f"q{question_number}_{student_login}.c"
                                            
                                            new_file_path = os.path.join(student_folder_path, new_filename)

                                            if filename != new_filename:
                                                if worksheet is not None:
                                                    update_worksheet_comentario(worksheet, student_login, comentario=(f"Tentando correspondência parcial {student_login}: de {filename} para {new_filename}"))
                                                verification_renamed(f"{student_login}: de {filename} para {new_filename}")
                                                os.rename(file_path, new_file_path)
                                                print(f"Renamed '{filename}' to '{new_filename}' for student '{student_login}'")
                                                used_questions.add(question_number) 
                                            else:
                                                print(f"O arquivo '{filename}' já está com o nome correto.")
                                            found_match = True
                                            break

                                    if found_match:
                                        break

                            if not found_match:
                                if worksheet is not None:
                                    update_worksheet_comentario(worksheet, student_login, comentario=(f"Não encontrou nenhum nome correspondente {student_login}: {filename}"))
                                verification_renamed(f"{student_login}: {filename}")
                                print(f"Nenhum nome correspondente encontrado para o arquivo {filename}")
                                if worksheet is not None:
                                    update_worksheet(worksheet, student_login, formatacao="1")

    except Exception as e:
        log_error(f"Erro em renomear arquivos baseado nos nomes do dicionario {str(e)}")

def no_c_files_in_directory(submissions_folder):
    try:
        for root, dirs, files in os.walk(submissions_folder): 
            for file in files:
                file_path = os.path.join(root, file)
                file_name, file_extension = os.path.splitext(file)

                if file_name.lower() == 'makefile':
                    print(f"Deletando arquivo Makefile: {file_path}")
                    os.remove(file_path)
                    continue  

                if file_extension == '.C':
                    new_file_path = os.path.join(root, file_name + '.c')
                    os.rename(file_path, new_file_path)

                elif file_extension != '.c':
                    if file_extension:
                        print(f"Deletando arquivo: {file_path}")
                        os.remove(file_path)
                    else:
                        new_file_path = os.path.join(root, file_name + '.c')
                        print(f"Renomeando arquivo: {file_path} -> {new_file_path}")
                        os.rename(file_path, new_file_path)
    except Exception as e:
        log_error(f"Erro no metodo no c files no diretorio {str(e)}")

def no_hs_files_in_directory(submissions_folder):
    try:
        for root, dirs, files in os.walk(submissions_folder): 
            for file in files:
                file_path = os.path.join(root, file)
                file_name, file_extension = os.path.splitext(file)
                print("\n \n entrando na função \n \n")

                if file_name.lower() == 'makefile':
                    print(f"Deletando arquivo Makefile: {file_path}")
                    os.remove(file_path)
                    continue  
                
                if file_extension == '.HS':
                    new_file_path = os.path.join(root, file_name + '.hs')
                    os.rename(file_path, new_file_path)

                elif file_extension != '.hs':
                    if file_extension:
                        print(f"Deletando arquivo: {file_path}")
                        os.remove(file_path)
                    else:
                        new_file_path = os.path.join(root, file_name + '.hs')
                        print(f"Renomeando arquivo: {file_path} -> {new_file_path}")
                        os.rename(file_path, new_file_path)
    except Exception as e:
        log_error(f"Erro no metodo no hs files no diretorio {str(e)}")                    
                 
def rename_files(submissions_folder, list_title, questions_data, worksheet):
    try:
        if 'HASKELL' in list_title:
            no_hs_files_in_directory(submissions_folder)
            rename_files_based_on_dictionary(submissions_folder, questions_data,worksheet, 1)
            return
        else:
            if 'ARQUIVOS' not in list_title:
                no_c_files_in_directory(submissions_folder)
            rename_files_based_on_dictionary(submissions_folder, questions_data,worksheet)
    except Exception as e:
        log_error(f"Erro no metodo renomear arquivos {str(e)}")          
        
def read_id_from_file(filename):
    try:
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
    except Exception as e:
        log_error(f"Erro ao ler o id da planilha do arquivo que tem o id da planilha {str(e)}")  

def create_google_sheet_in_folder(classroom_name, list_name, folder_id):
    try:
        client = get_gspread_client()

        spreadsheet = client.create(classroom_name)
        print(f"Planilha '{classroom_name}' criada com sucesso.")

        drive_service = build("drive", "v3", credentials=get_credentials())
        file_id = spreadsheet.id  
        # Move a planilha para a pasta especificada
        drive_service.files().update(fileId=file_id, addParents=folder_id, removeParents='root').execute()

        worksheet = spreadsheet.get_worksheet(0)
        worksheet.update_title(list_name)

        return worksheet
    except Exception as e:
        log_error(f"Erro ao criar ou preencher a planilha: {str(e)}")

def create_or_get_google_sheet_in_folder(classroom_name, list_name, folder_id):
    try:
        client = get_gspread_client()
        drive_service = build("drive", "v3", credentials=get_credentials())

        query = f"'{folder_id}' in parents and mimeType='application/vnd.google-apps.spreadsheet' and name='{classroom_name}' and trashed=false"
        response = drive_service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()

        if response['files']:
            spreadsheet_id = response['files'][0]['id']
            spreadsheet = client.open_by_key(spreadsheet_id)
            print(f"Planilha '{classroom_name}' já existe.")

            try:
                worksheet = spreadsheet.worksheet(list_name)
                print(f"A aba '{list_name}' já existe na planilha.")
                #worksheet = None
                return worksheet
            except Exception:

                worksheet = spreadsheet.add_worksheet(title=list_name, rows=100, cols=20)
                print(f"A aba '{list_name}' foi criada na planilha '{classroom_name}'.")
            
            return worksheet
        else:
            spreadsheet = client.create(classroom_name)
            print(f"Planilha '{classroom_name}' criada com sucesso.")

            file_id = spreadsheet.id
            drive_service.files().update(fileId=file_id, addParents=folder_id, removeParents='root').execute()

            worksheet = spreadsheet.get_worksheet(0)
            worksheet.update_title(list_name)
            
            return worksheet

    except Exception as e:
        log_error(f"Erro ao criar ou verificar a planilha e aba: {str(e)}")


def log_error(error_message):
    try:
        with open("error_log.txt", "a") as log_file:
            log_file.write(f"{error_message}\n")
    except Exception as e:
        log_error(f"Erro no log {str(e)}")  

def main():
    try:
        creds = get_credentials()
        try:
            classroom_service = build("classroom", "v1", credentials=creds)
            drive_service = build("drive", "v3", credentials=creds)
            num = 1
            state = 0
            while num ==1:
                classroom_id, coursework_id, classroom_name, list_name, list_title = list_classroom_data(classroom_service)
                if classroom_id and coursework_id and classroom_name and list_name and list_title: 
                    print(f"\n Você escolheu a turma : {classroom_name}")
                    print(f"\n E a atividade : {list_name} \n")
                else:
                    print("Não foi possível obter todos os dados. Verifique a seleção e tente novamente.")
                    return

                submissions = classroom_service.courses().courseWork().studentSubmissions().list(courseId=classroom_id, courseWorkId=coursework_id).execute()

                download_folder = 'Downloads'
                if not os.path.exists(download_folder):
                    os.makedirs(download_folder)

                folder_id = read_id_from_file('folder_id.txt')
                worksheet = create_or_get_google_sheet_in_folder(classroom_name, list_name, folder_id)
                download_submissions(classroom_service, drive_service, submissions, download_folder, classroom_id, worksheet)
                
                print("Download completo. Arquivos salvos em:", os.path.abspath(download_folder))

                organize_extracted_files(download_folder, worksheet)
                move_non_zip_files(download_folder)
                
                print("Processo concluído. Arquivos salvos em:", os.path.abspath(download_folder))

                submissions_folder = os.path.join(download_folder, 'submissions')
                if_there_is_a_folder_inside(submissions_folder)
                delete_subfolders_in_student_folders(submissions_folder)
                remove_empty_folders(submissions_folder)

                sheet_id = read_id_from_file('sheet_id.txt')
                questions_data = list_questions(sheet_id, list_name)
                rename_files(submissions_folder, list_title, questions_data, worksheet)  
                
                
                try:
                    num = int(input("\n Deseja baixar mais uma atividade? \n 0 - Não \n 1 - Sim \n \n "))
                    if num == 0:
                        print("\n Processo encerrado.")
                        break
                except ValueError:
                    print("Entrada inválida. Encerrando processo.")
                    break

                
        except HttpError as error:
            print(f"Um erro ocorreu: {error}")
    except Exception as e:
        log_error(f"Erro no fluxo principal: {str(e)}")        

if __name__ == "__main__":
    main()
