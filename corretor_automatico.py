import os
import io
import re
import time
import shutil
import string
import zipfile
import rarfile
import gspread
from datetime import datetime
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from gspread.exceptions import WorksheetNotFound
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.http import MediaIoBaseDownload
from google_auth_oauthlib.flow import InstalledAppFlow
from oauth2client.service_account import ServiceAccountCredentials


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
                    
                    choice = int(input("\nEscolha um número para selecionar a turma: ").strip())
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
                    
                    choice = int(input("\nEscolha um número para selecionar a lista de exercícios: ").strip())
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
    
def download_submissions(classroom_service, drive_service, submissions, download_folder, classroom_id, coursework_id, worksheet):
    try:
        print("\nComeçou o download...")
        if worksheet is not None:
            existing_records = worksheet.get_all_values()  
            alunos_registrados = set() 

            for record in existing_records:
                if len(record) > 2: 
                    alunos_registrados.add(record[2])  

        for submission in submissions.get('studentSubmissions', []):
            try:
                student_id = submission['userId']
                student = classroom_service.courses().students().get(courseId=classroom_id, userId=student_id).execute()
                student_email = student['profile']['emailAddress']
                student_login = extract_prefix(student_email)
                student_name = student['profile']['name']['fullName']
                entregou = 1 
                atrasou = 0
                formatacao = 0
                comentarios = None
                state = submission.get('state', 'UNKNOWN')

                due_date = get_due_date(classroom_service, classroom_id, coursework_id)
                submission_date = get_submission_timestamp(submission, student_id)

                attachments = submission.get('assignmentSubmission', {}).get('attachments', [])
                student_folder = None

                log_info(f"Due date: {due_date}, Submission date: {submission_date}, State: {state}")
                
                if not attachments: 
                    entregou = 0
                    log_info("Aluno não entregou submissão.")
                else:  
                    atrasou = calculate_delay(due_date, submission_date) if due_date and submission_date else 0
                

                if attachments:
                    for attachment in attachments:
                        try:
                            file_id = attachment.get('driveFile', {}).get('id')
                            file_name = attachment.get('driveFile', {}).get('title')
                            request = drive_service.files().get_media(fileId=file_id)

                            file_metadata = drive_service.files().get(fileId=file_id, fields='id, name').execute()
                            if not file_metadata:
                                log_info(f"Não foi possível recuperar os metadados para o arquivo {file_name} de {student_name}.")
                                continue  

                            if file_name.endswith('.c'):
                                if student_folder is None:
                                    student_folder = os.path.join(download_folder, student_login)
                                    if not os.path.exists(student_folder):
                                        os.makedirs(student_folder)
                                        entregou = 1
                                        comentarios="Erro de submissão: enviou arquivo(s), mas não enviou numa pasta compactada."
                                file_path = os.path.join(student_folder, file_name)
                            else:
                                file_path = os.path.join(download_folder, file_name)

                            with io.FileIO(file_path, 'wb') as fh:
                                downloader = MediaIoBaseDownload(fh, request)
                                done = False
                                while not done:
                                    status, done = downloader.next_chunk()
                                    progress_percentage = int(status.progress() * 100)
                                    log_info(f"Baixando {file_name} de {student_name}: {progress_percentage}%")
                                
                                if progress_percentage == 0:
                                    comentarios = "Erro de submissão ou submissão não foi baixada."
                                    entregou = 0
                                    os.remove(file_path)

                        except HttpError as error:
                            if error.resp.status == 403 and 'cannotDownloadAbusiveFile' in str(error):
                                comentarios = "Erro de submissão."
                                if worksheet is not None and student_login not in alunos_registrados:
                                    worksheet.append_rows([[student_name, student_email, student_login,  0, atrasou, formatacao,None,None, "Erro de submissão: malware ou spam."]])
                                    alunos_registrados.add(student_login)
                                log_info(f"O arquivo {file_name} de {student_name} foi identificado como malware ou spam e não pode ser baixado.")
                                if os.path.exists(file_path):
                                    os.remove(file_path)
                            else:
                                log_info(f"Erro ao baixar arquivo {file_name} de {student_name}: {error}")
                                if worksheet is not None and student_login not in alunos_registrados:
                                    worksheet.append_rows([[student_name, student_email, student_login,  0, atrasou, formatacao,None,None, "Erro de submissão ou submissão não foi baixada"]])
                                    alunos_registrados.add(student_login)
                            continue  

                        if file_name.endswith('.zip'):
                            expected_name = student_login + '.zip'
                            if file_name != expected_name:
                                corrected_path = os.path.join(download_folder, expected_name)
                                os.rename(file_path, corrected_path)
                                log_info(f"Renomeado {file_name} para {expected_name} de {student_name}.")
                                if file_name.lower() != expected_name: 
                                    formatacao = 0
                                    comentarios = f"Erro de formatação de zip: renomeado {file_name} para {expected_name}. "
                        
                        if file_name.endswith('.rar'):
                            formatacao = 0
                            comentarios = f"Erro de formatação de zip: Foi enviado um rar {file_name}."
                            expected_name = student_login + '.rar'
                            if file_name != expected_name:
                                corrected_path = os.path.join(download_folder, expected_name)
                                os.rename(file_path, corrected_path)
                                log_info(f"Renomeado {file_name} para {expected_name} de {student_name}.")
                                if file_name.lower() != expected_name: 
                                    formatacao = 0
                                    comentarios = f"Erro de formatação de zip: renomeado {file_name} para {expected_name}. "
                                
                else:               
                    log_info(f"Nenhum anexo encontrado para {student_name}")
                    atrasou = 0
                    entregou = 0


                if worksheet is not None and student_login not in alunos_registrados:
                    worksheet.append_rows([[student_name, student_email, student_login, entregou, atrasou, formatacao,None,None, comentarios]])
                    alunos_registrados.add(student_login)
                
            except Exception as e:
                log_info(f"Erro ao processar {student_name}: {e}")
                if worksheet is not None and student_login not in alunos_registrados:
                    worksheet.append_rows([[student_name, student_email, student_login, 0, atrasou, formatacao,None,None, "Erro de submissão: erro ao processar."]])
                    alunos_registrados.add(student_login)
                continue  

    except Exception as e:
        log_error(f"Erro ao baixar submissões: {str(e)}")

def extract_prefix(email):
    try:
        return email.split('@')[0]
    except Exception as e:
        log_error(f"Erro em extrair o prefixo do email {str(e)}")
 
    
def get_submission_timestamp(submission, student_id):
    try:
        log_info(f"\nHistórico de submissão: {submission.get('submissionHistory', [])}")
        
        last_timestamp = None  
        
        for history_entry in submission.get('submissionHistory', []):
            state_history = history_entry.get('stateHistory', {})
            state = state_history.get('state')
            actor_user_id = state_history.get('actorUserId')
            timestamp = state_history.get('stateTimestamp')
                      
            if state == 'TURNED_IN' and actor_user_id == student_id:
                last_timestamp = timestamp
        
        return last_timestamp  
    except Exception as e:
        log_error(f"Erro ao calcular a data de submissão pelo estado de entregue: {e}")
        return None
    
def calculate_delay(due_date_str, submission_date_str):
    try:
        due_date = datetime.strptime(due_date_str, "%Y-%m-%dT%H:%M:%S.%fZ")
        submission_date = datetime.strptime(submission_date_str, "%Y-%m-%dT%H:%M:%S.%fZ")
        delay = submission_date - due_date
        if delay.total_seconds() > 0:
         
            delay_in_days = delay.days + 1
            return delay_in_days
        else:
            return 0
    except Exception as e:
        log_error(f"Erro ao calcular atraso: {e}")
        return 0

def get_due_date(classroom_service, classroom_id, coursework_id):
    try:
        coursework = classroom_service.courses().courseWork().get(courseId=classroom_id, id=coursework_id).execute()
        due_date = coursework.get('dueDate')
        due_time = coursework.get('dueTime')

        if due_date:
            year = due_date['year']
            month = due_date['month']
            day = due_date['day']
            
            if due_time:
                hours = due_time.get('hours', 2) # Time Zone GMT 
                minutes = due_time.get('minutes', 59)
                seconds = due_time.get('seconds', 59)
            else:
                hours, minutes, seconds = 2, 59, 59 # Time Zone GMT
            
            # Timestamp no formato "YYYY-MM-DDTHH:MM:SSZ"
            return f"{year}-{month:02d}-{day:02d}T{hours:02d}:{minutes:02d}:{seconds:02d}.000Z"
        else:
            return None
    except Exception as e:
        log_error(f"Erro ao obter data de entrega: {e}")
        return None

def update_worksheet(worksheet, student_login, entregou=None, formatacao=None):
    try:
        data = worksheet.get_all_values()
        
        for idx, row in enumerate(data):
            if row[2] == student_login: 
                entregou_atual = row[3] if entregou is None else entregou 
                formatacao_atual = row[5] if formatacao is None else formatacao
                
                worksheet.update([[int(entregou_atual)]], f'D{idx+1}')
                worksheet.update([[int(formatacao_atual)]], f'F{idx+1}')
                
                return
        log_info(f"Login {student_login} não encontrado na planilha.")
    except Exception as e:
        log_error(f"Erro ao atualizar a planilha com formatação ou entrega: {e}")

def update_worksheet_formatacao(worksheet, student_login, formatacao=None, comentario=None):
    try:
        data = worksheet.get_all_values()
        
        for idx, row in enumerate(data):
            if row[2] == student_login: 
                formatacao_atual = row[5] if formatacao is None else formatacao
                comentario_atual = row[6] if comentario is None else comentario

                col = 8
                while col < len(row) and row[col]:   
                    col += 1
                
                cell_range = f'{chr(65+col)}{idx+1}'

                worksheet.batch_update([
                    {
                        'range': f'F{idx+1}',
                        'values': [[int(formatacao_atual)]]
                    },
                    {
                        'range': cell_range,
                        'values': [[comentario_atual]]
                    }
                ])

                return
        log_info(f"Login {student_login} não encontrado na planilha.")
    except Exception as e:
        log_error(f"Erro ao atualizar a planilha com formatação e comentário: {e}")


def update_worksheet_comentario(worksheet, student_login, num_questions=None, comentario=None):
    try:
        data = worksheet.get_all_values()
        
        comentario_index = ord('I') - ord('A') + (num_questions or 0)

        for idx, row in enumerate(data):
            if row[2] == student_login:  

                col = comentario_index

                while col < len(row) and row[col]:   
                    col += 1 
                
                cell_range = f'{chr(65 + col)}{idx + 1}' 
                if comentario:  
                    worksheet.update(values=[[comentario]], range_name=cell_range)
                
                return 
        log_info(f"Login {student_login} não encontrado na planilha.")
    except Exception as e:
        log_error(f"Erro ao atualizar a planilha com comentário: {e}")


def update_final_grade_for_no_submission(worksheet, num_questions):
    try:
        print("Entrou aqui??")
        data = worksheet.get_all_values()
        updates = []

        if num_questions is None:
            entrega_valor_index = 3 
            col_final_grade = 'H'
        else:
            entrega_valor_index = 3 + num_questions
            col_final_grade = 7 + num_questions

        log_info(f"\n o percentage é {col_final_grade}, a entrega de valor é {entrega_valor_index}")
        for idx, row in enumerate(data):
            student_login = row[2] 
            log_info(f"\n o estudante {student_login} e o percentage é {type(row[col_final_grade])}, a entrega de valor é {type(row[entrega_valor_index])}")
            if row[entrega_valor_index] == '0':
                log_info(f"\n o student: {student_login} e o percentage é {row[col_final_grade]}, a entrega de valor é {row[entrega_valor_index]}")
                updates.append({
                    'range': f'{chr(ord("H") + num_questions)}{idx + 1}', 
                    'values': [[0]]  
                })

                if row[col_final_grade] not in ('0', None, ''):
                    log_info(f"\n o student: {student_login} e o percentage é {row[col_final_grade]}, a entrega de valor é {row[entrega_valor_index]}")
                    comentario = f"O aluno tirou {row[col_final_grade]} no beecrowd, mas a entrega no classroom foi zerada."
                    update_worksheet_comentario(worksheet, student_login, num_questions=num_questions, comentario=comentario) 
                
        if updates:
            worksheet.batch_update(updates)
            log_info(f"\n\nNotas finais atualizadas para alunos com entrega 0.")
        else:
            log_info("\nNenhuma atualização necessária; nenhum aluno com entrega 0.")
    except Exception as e:
        log_error(f"Erro ao atualizar notas finais para alunos com entrega 0: {e}")


def insert_columns(worksheet, num_questions):
    try:
        data = worksheet.get_all_values()

        requests = [] 

        for row_idx, row in enumerate(data):
            if row_idx == 0:
                new_columns = [f"QUESTÃO {i + 1}" for i in range(num_questions)]
            else:
                new_columns = [''] * num_questions  

            updated_row = row[:3] + new_columns + row[3:]

            formatted_values = []
            for cell in updated_row:
                try:
                    int_value = int(cell)
                    formatted_values.append({'userEnteredValue': {'numberValue': int_value}})
                except ValueError:
                    formatted_values.append({'userEnteredValue': {'stringValue': cell}})

            requests.append({
                'updateCells': {
                    'range': {
                        'sheetId': worksheet.id,
                        'startRowIndex': row_idx,
                        'endRowIndex': row_idx + 1,
                        'startColumnIndex': 0,
                        'endColumnIndex': len(updated_row)
                    },
                    'rows': [{'values': formatted_values}],
                    'fields': 'userEnteredValue'
                }
            })

        worksheet.spreadsheet.batch_update({'requests': requests})

    except Exception as e:
        log_error(f"Ocorreu um erro ao inserir as colunas: {e}")

def fill_scores_for_students(worksheet, num_questions, score):
    try:
        data = worksheet.get_all_values()
        score_values = {}
        
        for key, value in score.items():
            try:
                score_values[key] = float(value)
            except ValueError:
                continue

        score_sum = sum(score_values.values())
        
        requests = []

        for row_idx, row in enumerate(data[1:], start=1): 
            final_score_column = 7 + num_questions
            delivery_column=7
            try:
                if (len(row) > delivery_column and float(row[delivery_column]) == 0) or \
                   (len(row) > final_score_column and float(row[final_score_column]) == 0):
                    question_scores = [0] * num_questions
                
                elif len(row) > final_score_column and float(row[final_score_column]) == score_sum:
                    
                    question_scores = [score_values.get(f'q{i + 1}', 0) for i in range(num_questions)]
                else:
                    continue 

                    
                for i, score_value in enumerate(question_scores):
                    column_index = 3 + i  
                    requests.append({
                        'updateCells': {
                            'rows': [{
                                'values': [{'userEnteredValue': {'numberValue': score_value}}]
                            }],
                            'fields': 'userEnteredValue',
                            'start': {
                                'sheetId': worksheet.id,
                                'rowIndex': row_idx,
                                'columnIndex': column_index
                            }
                        }
                    })

            except ValueError:
                continue
                        
            body = {
                'requests': requests
            }
            worksheet.spreadsheet.batch_update(body)

    except Exception as e:
        log_error(f"Ocorreu um erro ao preencher pontuações: {e}")

def apply_dynamic_formula_in_column(worksheet, num_questions):
    try:
        data = worksheet.get_all_values()
        requests = []

        last_filled_row = 0
        for row_idx, row in enumerate(data):
            if row[0]:  
                last_filled_row = row_idx

        column_final_grades = 7 + num_questions

        columns_to_sum = ['D', 'E', 'F', 'G'][:num_questions]
        col_delay = chr(ord('E') + num_questions)
        col_form = chr(ord('F') + num_questions)

        for row_idx in range(1, last_filled_row + 1):
            try:
                sum_formula = '+'.join([f"{col}{row_idx + 1}" for col in columns_to_sum])
                #no final *(1 - Copia)
                formula = f"={sum_formula} * (1 - (0.15*{col_delay}{row_idx + 1}) - (0.15*{col_form}{row_idx + 1}))"

                requests.append({
                    'updateCells': {
                        'rows': [{
                            'values': [{'userEnteredValue': {'formulaValue': formula}}]
                        }],
                        'fields': 'userEnteredValue',
                        'start': {
                            'sheetId': worksheet.id,
                            'rowIndex': row_idx,
                            'columnIndex': column_final_grades 
                        }
                    }
                })

            except Exception as e:
                log_error(f"Erro ao processar a linha {row_idx + 1}: {e}")
                continue

        body = {
            'requests': requests
        }
        worksheet.spreadsheet.batch_update(body)
        print('\nFórmula dinâmica aplicada na coluna de nota final.')

    except Exception as e:
        log_error(f"Erro ao aplicar formula dinâmica: {e}")

def is_real_zip(file_path):
    try:
        with zipfile.ZipFile(file_path, 'r') as zip_ref:
            return zip_ref.testzip() is None
    except Exception as e:
        log_error(f"Erro ao verificar se é um zip: {str(e)}")
        return False

def extract_zip(worksheet,student_login,zip_file_path, extraction_path):
    try:
        if not is_real_zip(zip_file_path):
            log_info(f"O arquivo {zip_file_path} não é um .zip válido.")
            if worksheet is not None:
                update_worksheet(worksheet, student_login, entregou=0)
                update_worksheet_comentario(worksheet, student_login, comentario=f"O arquivo {zip_file_path} não é um .zip válido. ")
            return

        with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
            zip_ref.extractall(extraction_path)

        macosx_path = os.path.join(extraction_path, '__MACOSX')
        if os.path.exists(macosx_path):
            log_info(f"Removendo pasta __MACOSX de {extraction_path}")
            shutil.rmtree(macosx_path)
            if worksheet is not None:
                update_worksheet_comentario(worksheet, student_login, comentario="Deletado pasta __MACOSX ")

    except Exception as e:
        log_error(f"Erro ao extrair o zip {str(e)}") 

def extract_rar(worksheet, student_login, rar_file_path, extraction_path):
    try:
        try:
            with rarfile.RarFile(rar_file_path, 'r') as rar_ref:
                rar_ref.extractall(extraction_path)
        except rarfile.Error as e:
            log_info(f"Erro ao usar rarfile: {e}")
            log_info(f"Tentando extrair com unar...")

        macosx_path = os.path.join(extraction_path, '__MACOSX')
        if os.path.exists(macosx_path):
            log_info(f"Removendo pasta __MACOSX de {extraction_path}")
            shutil.rmtree(macosx_path)
            if worksheet is not None:
                update_worksheet_comentario(worksheet, student_login, comentario="Deletado pasta __MACOSX ")

    except Exception as e:
        log_error(f"Erro em extrair o rar {str(e)}")  
    
def move_file(source, destination):
    try:
        try:
            shutil.move(source, destination)
        except shutil.Error as e:
            log_info(f"Erro ao mover arquivo: {e}")
    except Exception as e:
        log_error(f"Erro ao mover o arquivo {str(e)}")  

def create_folder_if_not_exists(folder_path):
    try:
        if not os.path.exists(folder_path):
                os.makedirs(folder_path)
    except Exception as e:
        log_error(f"Erro em criar a pasta se não existir a pasta {str(e)}")       

def rename_directory_if_needed(worksheet,directory_path, expected_name):
    try:
        if os.path.isdir(directory_path):
            current_name = os.path.basename(directory_path)
            if current_name != expected_name:
                new_directory_path = os.path.join(os.path.dirname(directory_path), expected_name)
                os.rename(directory_path, new_directory_path)
                log_info(f"Pasta renomeada de {current_name} para {expected_name}")
                if current_name.lower() != expected_name:
                    if worksheet is not None:
                        update_worksheet_formatacao(worksheet,expected_name,formatacao=0, comentario=f"Erro de formatação de pasta: pasta renomeada de {current_name} para {expected_name}.")
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
                        extract_zip(worksheet,student_login,item_path, extraction_path)
                    elif item.endswith('.rar'):
                        extract_rar(worksheet, student_login,item_path, extraction_path)
                except (zipfile.BadZipFile, rarfile.Error) as e:
                    log_info(f"Erro ao extrair o arquivo {item}: {e}")
                    if worksheet is not None:
                        update_worksheet(worksheet, student_login, entregou=0, formatacao=0)
                        update_worksheet_comentario(worksheet, student_login, comentario="Erro de submissão: compactação com erro")
                    continue

                extracted_items = os.listdir(extraction_path)
                if not extracted_items:
                    if worksheet is not None:
                        update_worksheet(worksheet, student_login, entregou=0, formatacao=0)
                        update_worksheet_comentario(worksheet, student_login, comentario="Erro de submissão: zip vazio")
                    continue

                if len(extracted_items) == 1 and os.path.isdir(os.path.join(extraction_path, extracted_items[0])):
                    extracted_folder = os.path.join(extraction_path, extracted_items[0])
                    extracted_folder = rename_directory_if_needed(worksheet, extracted_folder, student_login)

                for extracted_item in os.listdir(extraction_path):
                    extracted_item_path = os.path.join(extraction_path, extracted_item)

                    if os.path.exists(extracted_item_path): 
                        if os.path.isfile(extracted_item_path):
                            if extracted_item.endswith('.zip'):
                                if worksheet is not None:
                                    update_worksheet_formatacao(worksheet,student_login,formatacao=0, comentario="Erro de formatação de pasta: zip dentro do zip.")
                                try:
                                    extract_zip(worksheet,student_login, extracted_item_path, extraction_path)
                                    os.remove(extracted_item_path)
                                except zipfile.BadZipFile:
                                    log_info(f"Erro ao extrair zip: {extracted_item_path}")
                            elif extracted_item.endswith('.rar'):
                                if worksheet is not None:
                                    update_worksheet_formatacao(worksheet,student_login,formatacao=0, comentario="Erro de formatação de pasta: rar dentro do rar.")
                                try:
                                    extract_rar(worksheet, student_login, extracted_item_path, extraction_path)
                                    os.remove(extracted_item_path)
                                except rarfile.Error:
                                    log_info(f"Erro ao extrair rar: {extracted_item_path}")
                    else:
                        log_info(f"Arquivo não encontrado: {extracted_item_path}")
            else:
                continue

            extracted_items = os.listdir(extraction_path)
            log_info(f"\nArquivos extraídos de {student_login}: {extracted_items}")
            for_not_executed = True
            if len(extracted_items) == 1:
                extracted_path = os.path.join(extraction_path, extracted_items[0])

                if os.path.isdir(extracted_path):
                    extracted_folder = extracted_path

                    if extracted_items[0] == student_login:
                        log_info(f"A pasta extraída {extracted_items[0]} já tem o nome correto. Movendo arquivos para {extraction_path}.")
                        
                        if os.path.exists(extracted_folder):
                            for file in os.listdir(extracted_folder):
                                for_not_executed = False
                                source_file_path = os.path.join(extracted_folder, file)
                                destination_file_path = os.path.join(extraction_path, file)

                                if os.path.exists(source_file_path):  
                                    log_info(f"Movendo arquivo: {source_file_path} -> {destination_file_path}")
                                    move_file(source_file_path, destination_file_path)
                                else:
                                    log_info(f"Arquivo não encontrado: {source_file_path}")
                            
                            if not os.listdir(extracted_folder):
                                shutil.rmtree(extracted_folder)
                                log_info(f"Pasta extra deletada: {extracted_folder}")
                                if for_not_executed:
                                    if worksheet is not None:
                                        update_worksheet(worksheet, student_login, entregou=0)
                                        update_worksheet_formatacao(worksheet,student_login,formatacao=0, comentario=f"Não tem arquivos dentro da pasta: pasta deletada.")
                            else:
                                log_info(f"Pasta extra {extracted_folder} ainda contém arquivos e não será deletada.")
                    else:
                        log_info(f"A pasta extraída {extracted_items[0]} é diferente do nome esperado {student_login}")
                        if worksheet is not None:
                            update_worksheet_formatacao(worksheet,student_login,formatacao=0, comentario=f"Erro de formatação de pasta: a pasta extraída {extracted_items[0]} é diferente do nome esperado {student_login}.")
                        if os.path.exists(extracted_folder):  
                            for file in os.listdir(extracted_folder):
                                source_file_path = os.path.join(extracted_folder, file)
                                destination_file_path = os.path.join(extraction_path, file)

                                if os.path.exists(source_file_path):  
                                    log_info(f"Movendo arquivo: {source_file_path} -> {destination_file_path}")
                                    move_file(source_file_path, destination_file_path)
                                else:
                                    log_info(f"Arquivo não encontrado: {source_file_path}")

                            shutil.rmtree(extracted_folder)
                            log_info(f"Pasta deletada: {extracted_folder}")
                else:
                    log_info(f"Erro de formatação: {student_login} enviou arquivos soltos sem pasta.")
                    if worksheet is not None:
                        update_worksheet_formatacao(worksheet, student_login, formatacao=0, comentario=f"Erro de formatação de pasta: enviou sem pasta")
    except Exception as e:
        log_error(f"Erro ao organizar arquivos extraídos: {str(e)}")

def if_there_is_a_folder_inside(worksheet,submissions_folder):
    try:
        def move_files_to_inicial_folder(first_folder, folder_name):
            if os.path.basename(first_folder).startswith('.'):
                return

            items = os.listdir(first_folder)
            
            subfolders = [item for item in items if os.path.isdir(os.path.join(first_folder, item)) and not item.startswith('.')]
            
            if subfolders:
                for subfolder in subfolders:
                    subfolder_path = os.path.join(first_folder, subfolder)

                    if subfolder in ['output', '.vscode']:
                        if worksheet is not None:
                            update_worksheet_formatacao(worksheet,folder_name,formatacao=0, comentario="Erro de formatação de pasta: output ou .vscode")
                        continue

                    if worksheet is not None:
                        update_worksheet_formatacao(worksheet,folder_name,formatacao=0, comentario="Erro de formatação de pasta: subpastas")
                    
                    move_files_to_inicial_folder(subfolder_path, folder_name)
            
            files = [item for item in items if os.path.isfile(os.path.join(first_folder, item)) and not item.startswith('.')]
            for file in files:
                file_path = os.path.join(first_folder, file)
                destination = os.path.join(submissions_folder, os.path.basename(first_folder), file)

                if not os.path.exists(os.path.dirname(destination)):
                    os.makedirs(os.path.dirname(destination))

                shutil.move(file_path, destination)
            
            if first_folder != submissions_folder and not os.listdir(first_folder):
                os.rmdir(first_folder)

        for folder_name in os.listdir(submissions_folder):
            folder_path = os.path.join(submissions_folder, folder_name)
            if os.path.isdir(folder_path) and not folder_name.startswith('.'):
                move_files_to_inicial_folder(folder_path, folder_name)

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
    except Exception as e:
        log_error(f"Erro ao mover arquivos que não estavão zipados {str(e)}")

def get_gspread_client():
    try:
        creds = get_credentials()
        return gspread.authorize(creds)
    except Exception as e:
        log_error(f"Erro em conseguir a credencial do google spreadsheet {str(e)}")

def freeze_and_sort(worksheet):
    try:
        requests = [
            # Congelar a primeira linha
            {
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": worksheet.id,
                        "gridProperties": {
                            "frozenRowCount": 1
                        }
                    },
                    "fields": "gridProperties.frozenRowCount"
                }
            },
            # Ordenar pela terceira coluna (índice 2) em ordem ascendente
            {
                "sortRange": {
                    "range": {
                        "sheetId": worksheet.id,
                        "startRowIndex": 1,  
                    },
                    "sortSpecs": [
                        {
                            "dimensionIndex": 2, 
                            "sortOrder": "ASCENDING"
                        }
                    ]
                }
            }
        ]

        worksheet.spreadsheet.batch_update({"requests": requests})

    except Exception as e:
        log_error(f"Erro em formatar a planilha {str(e)}")

def insert_header_title(worksheet, classroom_name, list_title):
    try:
        requests = [
            # Inserir linha vazia no início
            {
                "insertDimension": {
                    "range": {
                        "sheetId": worksheet.id,
                        "dimension": "ROWS",
                        "startIndex": 0,
                        "endIndex": 1
                    },
                    "inheritFromBefore": False
                }
            },
            # Atualizar o título na célula A1
            {
                "updateCells": {
                    "rows": [{
                        "values": [{
                            "userEnteredValue": {"stringValue": f"{classroom_name} - {list_title}"},
                        }]
                    }],
                    "fields": "userEnteredValue",
                    "start": {"sheetId": worksheet.id, "rowIndex": 0, "columnIndex": 0}
                }
            },
            # Aplicar formatação nas linhas 1 e 2
            {
                "repeatCell": {
                    "range": {
                        "sheetId": worksheet.id,
                        "startRowIndex": 0,
                        "endRowIndex": 2
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": {"red": 0.0, "green": 0.2, "blue": 0.6},
                            "horizontalAlignment": "CENTER",
                            "textFormat": {
                                "foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0},
                                "bold": True
                            }
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)"
                }
            },
            # Congelar as primeiras duas linhas e três colunas
            {
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": worksheet.id,
                        "gridProperties": {
                            "frozenRowCount": 2,
                            "frozenColumnCount": 3
                        }
                    },
                    "fields": "gridProperties.frozenRowCount,gridProperties.frozenColumnCount"
                }
            },
            # Redimensionar automaticamente as três primeiras colunas
            {
                "autoResizeDimensions": {
                    "dimensions": {
                        "sheetId": worksheet.id,
                        "dimension": "COLUMNS",
                        "startIndex": 0,
                        "endIndex": 3
                    }
                }
            }
        ]

        worksheet.spreadsheet.batch_update({"requests": requests})

    except Exception as e:
        log_error(f"Erro ao inserir título da planilha no cabeçalho e formatar a planilha: {str(e)}")


def list_questions_default(sheet_id):
    if sheet_id is not None:
        print("\nNão foi encontrado a aba na planilha para essa lista. Para renomear as questões será utilizado um dicionário padrão com possíveis nomes para as questões de 1 a 4.")
    else:
        print("\nNão foi submetido o id da planilha no arquivo 'sheet_id.txt'. Para renomear as questões será utilizado um dicionário de possíveis nomes para as questões de 1 a 4.")
    
    print("\nSe preencher a planilha personalizada possivelmente aumentará a quantidade de renomeações.")

    questions_dict = {
        1: ['1','q1', 'Q1', 'questao1', 'questão1' ],
        2: ['2','q2', 'Q2', 'questao2', 'questão2' ],
        3: ['3','q3', 'Q3', 'questao3', 'questão3' ],
        4: ['4','q4', 'Q4', 'questao4', 'questão4' ]
    }

    print("\nDicionário padrão:")
    for key, value in questions_dict.items():
        print(f"{value}")
    i = len(questions_dict)
    score = None
    return questions_dict,i, score

def list_questions(sheet_id, sheet_name):
    try:
        try:
            client = get_gspread_client()
            sheet = client.open_by_key(sheet_id).worksheet(sheet_name)
            rows = sheet.get_all_values()[1:]  
            if not rows:
                print(f"A planilha '{sheet_name}' não tem campos preenchidos. O sistema vai usar o dicionário padrão.")
                return list_questions_default(sheet_id)

            questions_dict = {}
            score = {}
            print("\nO dicionário está assim: ")
            for i, row in enumerate(rows, start=1):
                question_data = []
                
                question_data.append(f'{i}')
                question_data.append(f'q{i}')
                question_data.append(f'Q{i}')
                question_data.append(f'questao{i}')
                question_data.append(f'questão{i}')
                
                beecrowd_number = row[2].strip() if len(row) > 2 and row[2].strip() else ""
                if beecrowd_number:
                    question_data.append(beecrowd_number)
                    question_data.append(f'q{beecrowd_number}')
            
                question_name = row[3].strip() if len(row) > 3 and row[3].strip() else ""
                if question_name:
                    question_data.append(question_name)
            
                additional_names = row[4:]
                for name in additional_names:
                    name = name.strip()
                    if name: 
                        question_data.append(name)

                if question_data:
                    questions_dict[i] = question_data
                    print(f"{question_data}")
                
                if row[0].strip():
                    score[f'q{i}'] = row[0].strip()
        
            return questions_dict, i, score
        except WorksheetNotFound:
            print(f"A aba '{sheet_name}' não foi encontrada na planilha de nomes para as questões.")
            return list_questions_default(sheet_id)
    except Exception as e:
        log_error(f"Erro em pegar da planilha os nomes das questões vai usar o dicionário padrão {str(e)}")
        return list_questions_default(sheet_id)       

def remove_empty_folders(submissions_folder):
    try:
        for folder_name in os.listdir(submissions_folder):
            folder_path = os.path.join(submissions_folder, folder_name)
            if os.path.isdir(folder_path):
                if not os.listdir(folder_path):  
                    shutil.rmtree(folder_path)  
                    log_info(f"A pasta '{folder_name}' foi deletada por não ter nenhum arquivo dentro.")
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
                log_info(f"\nVerificando pasta do estudante: {student_folder_path}")
    
                used_questions = set()

                for filename in os.listdir(student_folder_path):
                    file_path = os.path.join(student_folder_path, filename)

                    if os.path.isfile(file_path) and not filename.startswith('.'):
                        log_info(f"Verificando arquivo: {filename}")
                        
                        for i in range(1, 5):
                            if haskell == 1:
                                expected_filename = f"q{i}_{student_login}.hs"
                            else:
                                expected_filename = f"q{i}_{student_login}.c"
                            
                            if filename == expected_filename:
                                log_info(f"O arquivo '{filename}' já está no formato correto.")
                                break  

                        else: 
                            base_filename_clean = re.sub(r"\(\d+\)", "", os.path.splitext(filename)[0].lower()) \
                                .replace("_", " ") \
                                .replace(student_login.lower(), "") \
                                .strip()

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
                                            log_info(f"Renomeando: '{filename}' para '{new_filename}' para o estudante '{student_login}'")
                                            used_questions.add(question_number) 
                                            if worksheet is not None:
                                                update_worksheet_formatacao(worksheet,student_login,formatacao=0, comentario=f"Erro de formatação no arquivo: renomeando '{filename}' para '{new_filename}'")
                                        
                                        found_match = True
                                        break  

                                if found_match:
                                    break  
                        
                            if not found_match:
                                log_info(f"Tentando correspondência parcial para o arquivo {filename}")
                                for question_number, possible_names in questions_dict.items():
                                    if question_number in used_questions:
                                        continue
                                    
                                    for possible_name in reversed(possible_names):
                                        possible_name_clean = possible_name.lower().strip()
                                        possible_name_parts = possible_name_clean.split()
                                        log_info(f"{possible_name_parts}")

                                        if any(part in base_filename_clean for part in possible_name_parts):
                                            if haskell == 1:
                                                new_filename = f"q{question_number}_{student_login}.hs"
                                            else:
                                                new_filename = f"q{question_number}_{student_login}.c"
                                            
                                            new_file_path = os.path.join(student_folder_path, new_filename)

                                            if filename != new_filename:
                                                if worksheet is not None:
                                                    update_worksheet_formatacao(worksheet,student_login,formatacao=1,comentario=(f"Erro de formatação no arquivo: tentando correspondência parcial {student_login}: de {filename} para {new_filename}"))
                                                verification_renamed(f"{student_login}: de {filename} para {new_filename}")
                                                os.rename(file_path, new_file_path)
                                                log_info(f"Renomeando'{filename}' para '{new_filename}' para o estudante '{student_login}'")
                                                used_questions.add(question_number) 
                                            else:
                                                log_info(f"O arquivo '{filename}' já está com o nome correto.")
                                            found_match = True
                                            break

                                    if found_match:
                                        break

                            if not found_match:
                                if worksheet is not None:
                                    update_worksheet_formatacao(worksheet,student_login,formatacao=1, comentario=(f"Erro de formatação no arquivo: não foi encontrado nenhum nome correspondente {student_login}: {filename}"))
                                verification_renamed(f"{student_login}: {filename}")
                                log_info(f"Nenhum nome correspondente encontrado para o arquivo {filename}")

    except Exception as e:
        log_error(f"Erro em renomear arquivos baseado nos nomes do dicionario {str(e)}")

def no_c_files_in_directory(worksheet,submissions_folder): 
    try:
        for root, dirs, files in os.walk(submissions_folder): 
            folder_name = os.path.basename(root) 
            for file in files:
                file_path = os.path.join(root, file)
                file_name, file_extension = os.path.splitext(file)

                if file.startswith("."):
                    log_info(f"Deletando arquivo oculto: {file_path}")
                    os.remove(file_path)
                    continue

                if file_name.lower() in ['makefile', 'main', 'main-debug']:
                    log_info(f"Deletando arquivo: {file_path}")
                    os.remove(file_path)
                    if worksheet is not None:
                        update_worksheet_formatacao(worksheet,folder_name,formatacao=0, comentario=(f"Erro de formatação no arquivo: deletado arquivo: {file_name} "))
                    continue

                if file_extension == '.C':
                    new_file_path = os.path.join(root, file_name + '.c')
                    os.rename(file_path, new_file_path)
                    if worksheet is not None:
                        update_worksheet_formatacao(worksheet,folder_name,formatacao=0, comentario=(f"Erro de formatação no arquivo: renomeando arquivo: de {file_path} par {new_file_path} "))
                
                if file_extension == '.cpp':
                            new_file_path = os.path.join(root, file_name + '.c')
                            log_info(f"Renomeando arquivo: {file_path} -> {new_file_path}")
                            os.rename(file_path, new_file_path)
                            if worksheet is not None:
                                update_worksheet_formatacao(worksheet,folder_name,formatacao=0,comentario=(f"Erro de formatação no arquivo: renomeado arquivo: {file_path} para {new_file_path} "))

                elif file_extension != '.c':
                    if file_extension:
                        if '.c' in file_name:
                            base_name = file_name.split('.c')[0] 
                            new_file_path = os.path.join(root, base_name + '.c')
                            log_info(f"Renomeando arquivo: {file_path} -> {new_file_path}")
                            os.rename(file_path, new_file_path)
                            if worksheet is not None:
                                update_worksheet_formatacao(worksheet,folder_name,formatacao=0,comentario=(f"Erro de formatação no arquivo: renomeado arquivo: {file_path} para {new_file_path} "))  
                        else:    
                            log_info(f"Deletando arquivo: {file_path}")
                            os.remove(file_path)
                            if worksheet is not None:
                                update_worksheet_formatacao(worksheet,folder_name,formatacao=0, comentario=(f"Erro de formatação no arquivo: deletado arquivo: {file_path} "))
                    else:
                        new_file_path = os.path.join(root, file_name + '.c')
                        log_info(f"Renomeando arquivo: {file_path} -> {new_file_path}")
                        os.rename(file_path, new_file_path)
                        if worksheet is not None:
                            update_worksheet_formatacao(worksheet,folder_name,formatacao=0,comentario=(f"Erro de formatação no arquivo: renomeado arquivo: de {file_path} para {new_file_path} "))
    except Exception as e:
        log_error(f"Erro no metodo no c files no diretorio {str(e)}")

def no_hs_files_in_directory(worksheet, submissions_folder):
    try:
        for root, dirs, files in os.walk(submissions_folder): 
            folder_name = os.path.basename(root) 
            for file in files:
                file_path = os.path.join(root, file)
                file_name, file_extension = os.path.splitext(file)

                if file.startswith("."):
                    log_info(f"Deletando arquivo oculto: {file_path}")
                    os.remove(file_path)
                    continue

                if file_name.lower() in ['makefile', 'main', 'main-debug']:
                    log_info(f"Deletando arquivo: {file_path}")
                    os.remove(file_path)
                    if worksheet is not None:
                        update_worksheet_formatacao(worksheet,folder_name,formatacao=0, comentario=(f"Erro de formatação no arquivo: deletado arquivo: {file_name} "))
                    continue
                
                if file_extension == '.HS':
                    new_file_path = os.path.join(root, file_name + '.hs')
                    os.rename(file_path, new_file_path)
                    if worksheet is not None:
                        update_worksheet_formatacao(worksheet,folder_name,formatacao=0, comentario=(f"Erro de formatação no arquivo: renomeando arquivo: {file_path} "))

                elif file_extension != '.hs':
                    if file_extension:
                        if '.hs' in file_name:
                            base_name = file_name.split('.hs')[0] 
                            new_file_path = os.path.join(root, base_name + '.hs')
                            log_info(f"Renomeando arquivo: {file_path} -> {new_file_path}")
                            os.rename(file_path, new_file_path)
                            if worksheet is not None:
                                update_worksheet_formatacao(worksheet,folder_name,formatacao=0,comentario=(f"Erro de formatação no arquivo: renomeado arquivo: {file_path} para {new_file_path}"))
                        log_info(f"Deletando arquivo: {file_path}")
                        os.remove(file_path)
                        if worksheet is not None:
                            update_worksheet_formatacao(worksheet,folder_name,formatacao=0, comentario=(f"Erro de formatação no arquivo: deletado arquivo: {file_name} "))
                    else:
                        new_file_path = os.path.join(root, file_name + '.hs')
                        log_info(f"Renomeando arquivo: {file_path} -> {new_file_path}")
                        os.rename(file_path, new_file_path)
                        if worksheet is not None:
                            update_worksheet_formatacao(worksheet,folder_name,formatacao=0, comentario=(f"Erro de formatação no arquivo: renomeando arquivo: {file_name} "))
    except Exception as e:
        log_error(f"Erro no metodo no hs files no diretorio {str(e)}")                    
                 
def rename_files(submissions_folder, list_title, questions_data, worksheet):
    try:
        if 'HASKELL' in list_title:
            no_hs_files_in_directory(worksheet, submissions_folder)
            rename_files_based_on_dictionary(submissions_folder, questions_data,worksheet, 1)
            return
        else:
            #if 'ARQUIVOS' not in list_title:
            no_c_files_in_directory(worksheet, submissions_folder)
            rename_files_based_on_dictionary(submissions_folder, questions_data,worksheet)
    except Exception as e:
        log_error(f"Erro no metodo renomear arquivos {str(e)}")          
        
def read_id_from_file(filename):
    try:
        with open(filename, 'r') as file:
            sheet_id = file.read().strip()
        return sheet_id
    except FileNotFoundError:
        log_info(f"Arquivo {filename} não encontrado.")
        return None
    except Exception as e:
        log_error(f"Erro ao ler o id da planilha do arquivo {filename}: {e}")
        return None 

def create_google_sheet_in_folder(classroom_name, list_name, folder_id):
    try:
        client = get_gspread_client()

        spreadsheet = client.create(classroom_name)
        print(f"Planilha '{classroom_name}' criada com sucesso.\n")
        print(f"A aba '{list_name}' foi criada na planilha '{classroom_name}'.\n")

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
            print(f"Planilha '{classroom_name}' já existe.\n")

            try:
                worksheet = spreadsheet.worksheet(list_name)
                print(f"A aba '{list_name}' já existe na planilha.\n")
                worksheet = None
                return worksheet
            except Exception:

                worksheet = spreadsheet.add_worksheet(title=list_name, rows=100, cols=20)
                print(f"A aba '{list_name}' foi criada na planilha '{classroom_name}'.\n")
            
            return worksheet
        else:
            spreadsheet = client.create(classroom_name)
            print(f"Planilha '{classroom_name}' criada com sucesso.\n")

            file_id = spreadsheet.id
            drive_service.files().update(fileId=file_id, addParents=folder_id, removeParents='root').execute()

            worksheet = spreadsheet.get_worksheet(0)
            worksheet.update_title(list_name)
            
            return worksheet

    except Exception as e:
        log_error(f"Erro ao criar ou verificar a planilha e aba: {str(e)}")

def header_worksheet(worksheet):
    try:
        if worksheet is not None:
            header = [['NOME DO ALUNO', 'EMAIL', 'STUDENT LOGIN', 'ENTREGA?', 'ATRASO?', 'FORMATAÇÃO?', 'CÓPIA?', 'NOTA TOTAL','COMENTÁRIOS']]
            
            first_row = worksheet.row_values(1)
            if not first_row:
                worksheet.append_rows(header, table_range='A1')
    except Exception as e:
        log_error(f"Erro ao criar o cabeçalho da planilha: {str(e)}")  

def update_grades(sheet_id1, worksheet2, score):
    try: 
        client = get_gspread_client()

        worksheet1 = client.open_by_key(sheet_id1)
        worksheet1 = worksheet1.get_worksheet(0)  
        
        emails = [email.strip() for email in worksheet1.col_values(6)[1:] if email] 
        percentages = [percent.strip() for percent in worksheet1.col_values(10)[1:] if percent]   
        log_info(f"\nProcurando os emails {emails}")
        print("\nProcurando os alunos com a nota 100 e 0.\n")
        updates = []
        not_found_emails = []

       
        if isinstance(score, dict):
            score_values = {key: float(value) for key, value in score.items()}
            score_sum = float(sum(score_values.values()))
        else:
            log_info("\nComo a pontuação estava None, foi usado a porcentagem do beecrowd para preencher 100, mas para calcular com a pontuação o 'score' precisa estar preenchido na planilha.\n")
            score_sum = 100  
  
        
        for idx, (email, percentage) in enumerate(zip(emails, percentages), start=2):
            if not email:
                break
            time.sleep(1)

            if percentage in ["100", "0"]: 
                try:
                    
                    cell = worksheet2.find(email, in_column=2)
                    if cell:
                        value_to_update = float(score_sum) if percentage == "100" else 0

                            
                        updates.append({
                            "range": f"H{cell.row}",
                            "values": [[value_to_update]]
                        })
                    else:
                        not_found_emails.append(f"{email}: {value_to_update}")
                except gspread.exceptions.APIError:
                    pass  

        if updates:
            worksheet2.batch_update(updates)

        if not_found_emails:
            with open("not_found_emails_100_or_0.txt", "w") as file:
                for email in not_found_emails:
                    file.write(f"{email}\n")
        
        log_info(f"\nForam encontrados: {len(updates)} alunos nas duas planilhas com o mesmo email.")
        print(f"\nForam encontrados: {len(updates)} alunos nas duas planilhas com o mesmo email.")
        if len(updates) < len(emails): 
            print("\nNem todos os alunos acertaram 100 ou 0 foram encontrados na planilha de resultados. Revise os emails no txt.")
                               
    except Exception as e:
        log_error(f"Erro ao atualizar planilha {str(e)}")  

def compare_emails(sheet_id_beecrowd, worksheet2):
    try:
        client = get_gspread_client()

        worksheet1 = client.open_by_key(sheet_id_beecrowd).get_worksheet(0) 

        # Extrai os e-mails das duas planilhas
        emails_planilha1 = set(email.strip() for email in worksheet1.col_values(6)[1:] if email)
        emails_planilha2 = set(email.strip() for email in worksheet2.col_values(2)[1:] if email)

        only_in_planilha1 = emails_planilha1 - emails_planilha2

        only_in_planilha2 = emails_planilha2 - emails_planilha1

        with open("email_differences.txt", "w") as file:
            file.write("Beecrowd\n")
            for email in sorted(only_in_planilha1):
                file.write(f"{email}\n")

            file.write("\nClassroom\n")
            for email in sorted(only_in_planilha2):
                file.write(f"{email}\n")

        print("\nArquivo email_differences.txt criado com sucesso.")

    except Exception as e:
        log_error(f"Erro ao comparar e-mails: {str(e)}")


def delete_empty_subfolders(worksheet,submissions_folder):
    try:
        for folder_name in os.listdir(submissions_folder):
            folder_path = os.path.join(submissions_folder, folder_name)

            if os.path.isdir(folder_path) and not os.listdir(folder_path):  
                shutil.rmtree(folder_path)
                log_info(f"Pasta deletada {folder_name}")
                if worksheet is not None:
                    update_worksheet(worksheet, folder_name, entregou=0)
                    update_worksheet_comentario(worksheet, folder_name, comentario=f"Pasta deletada {folder_name}")
    except Exception as e:
        log_error(f"Erro ao deletar pastas vazias dentro de {submissions_folder}: {str(e)}")

def log_error(error_message):
    try:
        with open("error_log.txt", "a") as log_file:
            log_file.write(f"{error_message}\n")
    except Exception as e:
        log_error(f"Erro no log {str(e)}")  

def log_info(message):
    try:
        with open("output_log.txt", "a") as file:
            file.write(message + "\n")
    except Exception as e:
        log_error(f"Erro no info {str(e)}")  

def main():
    try:
        creds = get_credentials()
        try:
            classroom_service = build("classroom", "v1", credentials=creds)
            drive_service = build("drive", "v3", credentials=creds)
            num = 1
            while num ==1:
                classroom_id, coursework_id, classroom_name, list_name, list_title = list_classroom_data(classroom_service)
                if classroom_id and coursework_id and classroom_name and list_name and list_title: 
                    print(f"\n\nVocê escolheu a turma : {classroom_name}")
                    print(f"\nE a atividade : {list_name} \n")
                else:
                    print("\n\nNão foi possível obter todos os dados. Verifique a seleção e tente novamente.\n")
                    return

                submissions = classroom_service.courses().courseWork().studentSubmissions().list(courseId=classroom_id, courseWorkId=coursework_id).execute()

                download_folder = 'Downloads'
                if not os.path.exists(download_folder):
                    os.makedirs(download_folder)
                
                sheet_id = read_id_from_file('sheet_id.txt')

                if sheet_id:  
                    try:
                        questions_data, num_questions, score = list_questions(sheet_id, list_name)
                        if score is not None:
                            print(f"\nA pontuação das questões é: {score}\n")
                        else:
                            print("\nNão foi passada a pontuação das questões. A pontuação é passada na primeira coluna da planilha 'sheet_id.txt' que contém os possíveis nomes das questões.\n")
                    except Exception as e:
                        print(f"Erro ao obter os nomes das questões da planilha: {e}")
                else:
                    questions_data, num_questions, score = list_questions_default(None)
                    print("\nNão foi passada a pontuação das questões, pois não foi passado o id da planilha em 'sheet_id.txt'. A pontuação é passada na primeira coluna da planilha.\n")

                folder_id = read_id_from_file('folder_id.txt')
                if folder_id: 
                    try:
                        worksheet = create_or_get_google_sheet_in_folder(classroom_name, list_name, folder_id)
                        header_worksheet(worksheet)
                    except HttpError as e:
                        print(f"\nErro ao criar ou verificar a planilha e aba: {e}")
                else:
                    worksheet = None
                    print("\nA planilha de resultados não será criada porque a folder_id.txt está vazia ou inválida.")

                
                download_submissions(classroom_service, drive_service, submissions, download_folder, classroom_id, coursework_id, worksheet)
                print("\n\nDownload completo. Arquivos salvos em:", os.path.abspath(download_folder))

                organize_extracted_files(download_folder, worksheet)
                move_non_zip_files(download_folder)
                submissions_folder = os.path.join(download_folder, 'submissions')
                if_there_is_a_folder_inside(worksheet, submissions_folder)
                delete_subfolders_in_student_folders(submissions_folder)
                remove_empty_folders(submissions_folder)

                print("\nProcesso de extrair e organizar pastas finalizado. Arquivos salvos em:", os.path.abspath(submissions_folder))

                rename_files(submissions_folder, list_title, questions_data, worksheet)
                print("\nProcesso de verificar e renomear arquivos finalizado.")
                delete_empty_subfolders(worksheet,submissions_folder)
               
                if worksheet is not None:
                    sheet_id_beecrowd = read_id_from_file('sheet_id_beecrowd.txt')
                    if sheet_id_beecrowd:
                        update_grades(sheet_id_beecrowd, worksheet, score)
                        compare_emails(sheet_id_beecrowd, worksheet)
                        insert_columns(worksheet, num_questions)
                        update_final_grade_for_no_submission(worksheet, num_questions)
                        if score is not None:
                            fill_scores_for_students(worksheet, num_questions, score)
                            print("\nComo não foi passado a pontuação não foi preenchido as colunas de cada questão. E o valor inserido em nota final foi 0 ou 100.")
                    else:
                        #update_final_grade_for_no_submission(worksheet, None)
                        print("\nID da planilha do Beecrowd não foi encontrado no arquivo 'sheet_id_beecrowd.txt'. Não será adicionada as notas dos alunos que tiraram 0 ou 100.")
                    
                    if score is None:
                        log_info(f"\nscore é {score}")
                        #apply_dynamic_formula_in_column(worksheet, num_questions)
                        print("\nProcesso de colocar as notas do beecrowd na planilha finalizado.")

                    freeze_and_sort(worksheet)
                    insert_header_title(worksheet, classroom_name, list_title)
                    print("\nProcesso de formatar a planilha finalizado.\n")
                    print(f"\nProcesso da {classroom_name} - {list_name} concluído.")
                    
                try:
                    num = int(input("\n\nDeseja baixar mais uma atividade? \n0 - Não \n1 - Sim \n \n "))
                    if num == 0:
                        print("\nProcesso encerrado.")
                        break
                except ValueError:
                    print("\nEntrada inválida. Encerrando processo.")
                    break
                
        except HttpError as error:
            print(f"Um erro ocorreu: {error}")
    except Exception as e:
        log_error(f"Erro no fluxo principal: {str(e)}")     
   

if __name__ == "__main__":
    main()
