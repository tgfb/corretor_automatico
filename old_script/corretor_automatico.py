import os
import io
import re
import time
import shutil
import string
import zipfile
import rarfile
import gspread
import requests
import subprocess
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urlparse
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
                copia = 0
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
                                    worksheet.append_rows([[student_name, student_email, student_login,  0, atrasou, formatacao,copia,None, "Erro de submissão: malware ou spam."]])
                                    alunos_registrados.add(student_login)
                                log_info(f"O arquivo {file_name} de {student_name} foi identificado como malware ou spam e não pode ser baixado.")
                                if os.path.exists(file_path):
                                    os.remove(file_path)
                            else:
                                log_info(f"Erro ao baixar arquivo {file_name} de {student_name}: {error}")
                                if worksheet is not None and student_login not in alunos_registrados:
                                    worksheet.append_rows([[student_name, student_email, student_login,  0, atrasou, formatacao,copia,None, "Erro de submissão ou submissão não foi baixada"]])
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
                    worksheet.append_rows([[student_name, student_email, student_login, entregou, atrasou, formatacao,copia,None, comentarios]])
                    alunos_registrados.add(student_login)
                
            except Exception as e:
                log_info(f"Erro ao processar {student_name}: {e}")
                if worksheet is not None and student_login not in alunos_registrados:
                    worksheet.append_rows([[student_name, student_email, student_login, 0, atrasou, formatacao,copia,None, "Erro de submissão: erro ao processar."]])
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
        data = worksheet.get_all_values()
        updates = []

        if num_questions is None:
            entrega_valor_index = 3 
            col_final_grade = 7
        else:
            entrega_valor_index = 3 + num_questions
            col_final_grade = 7 + num_questions

        for idx, row in enumerate(data):
            student_login = row[2] 
            if row[entrega_valor_index] == '0':
                updates.append({
                    'range': f'{chr(ord("H") + (num_questions if num_questions is not None else 0))}{idx + 1}', 
                    'values': [[0]]  
                })

                if row[col_final_grade] not in ('0', None, ''):
                    comentario = f"O aluno tirou 100 no beecrowd, mas a entrega no classroom foi zerada."
                    update_worksheet_comentario(worksheet, student_login, num_questions=num_questions, comentario=comentario) 
                
        if updates:
            worksheet.batch_update(updates)
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
        print(f"Ocorreu um erro ao inserir as colunas: {e}")
        exit()

def insert_score_row(worksheet, score):
    try:
        data = worksheet.get_all_values()

        requests = []

        requests.append({
            'insertDimension': {
                'range': {
                    'sheetId': worksheet.id,
                    'dimension': 'ROWS',
                    'startIndex': 1,  
                    'endIndex': 2
                },
                'inheritFromBefore': False
            }
        })

       
        if score is not None:
            new_row = [''] * 3 + list(score.values())  
        else:
            new_row = [''] * len(data[0])  

        formatted_values = []
        for cell in new_row:
            try:
                int_value = int(cell)
                formatted_values.append({'userEnteredValue': {'numberValue': int_value}})
            except ValueError:
                formatted_values.append({'userEnteredValue': {'stringValue': cell}})

       
        requests.append({
            'updateCells': {
                'range': {
                    'sheetId': worksheet.id,
                    'startRowIndex': 1,
                    'endRowIndex': 2,
                    'startColumnIndex': 0,
                    'endColumnIndex': len(new_row)
                },
                'rows': [{'values': formatted_values}],
                'fields': 'userEnteredValue'
            }
        })
        log_info("Requisição de atualização de células para nova linha adicionada\n\n")

        worksheet.spreadsheet.batch_update({'requests': requests})

    except Exception as e:
        log_error(f"Ocorreu um erro ao inserir a linha e as colunas: {e}")

def fill_scores_for_students(worksheet, num_questions, score=None):
    try:
        data = worksheet.get_all_values()
        score_values = {}
        
        if score is not None:
            for key, value in score.items():
                try:
                    score_values[key] = float(value)
                except ValueError:
                    continue
            score_sum = sum(score_values.values())
        else:
            score_sum = 100

        requests = []

        for row_idx, row in enumerate(data[1:], start=1): 
            final_score_column = 7 + num_questions if num_questions is not None else 7
            delivery_column = 7 if num_questions is None else final_score_column

            try:
                final_score_str = row[final_score_column].strip() if len(row) > final_score_column else ""
                delivery_score_str = row[delivery_column].strip() if len(row) > delivery_column else ""

                final_score = float(final_score_str) if final_score_str.replace('.', '', 1).isdigit() else None
                delivery_score = float(delivery_score_str) if delivery_score_str.replace('.', '', 1).isdigit() else None

                if num_questions is not None:
                    if final_score == score_sum:
                        question_scores = [
                            f"=${chr(68 + i)}$2" for i in range(num_questions)
                        ]
                    
                    elif final_score is not None and final_score == 0:
                        question_scores = ["=0"] * num_questions
                    
                    else:
                        continue
                
                else:
                    if delivery_score is not None and delivery_score == 0:
                        question_scores = ["=0"]
                    else:
                        continue

                for i, value in enumerate(question_scores):
                    column_index = 3 + i
                    requests.append({
                        'updateCells': {
                            'rows': [{
                                'values': [{'userEnteredValue': {'formulaValue' if isinstance(value, str) else 'numberValue': value}}]
                            }],
                            'fields': 'userEnteredValue',
                            'start': {
                                'sheetId': worksheet.id,
                                'rowIndex': row_idx,
                                'columnIndex': column_index
                            }
                        }
                    })

            except ValueError as ve:
                continue
                        
        if requests:
            body = {'requests': requests}
            worksheet.spreadsheet.batch_update(body)
            log_info("\nAtualização das pontuações concluída com sucesso.")
        else:
            log_info("\nNenhuma atualização necessária. Nenhuma request gerada.")

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
        col_copy = chr(ord('G') + num_questions)

        for row_idx in range(1, last_filled_row + 1):
            try:
                sum_formula = '+'.join([f"{col}{row_idx + 1}" for col in columns_to_sum])
                
                formula = f"=({sum_formula}) * (1 - (0.15*{col_delay}{row_idx + 1}) - (0.15*{col_form}{row_idx + 1}))*(1 - {col_copy}{row_idx+1})"

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
            # Congelar a primeira e a segunda linha
            {
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": worksheet.id,
                        "gridProperties": {
                            "frozenRowCount": 2
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
            # Aplicar formatação nas linhas 1, 2, 3
            {
                "repeatCell": {
                    "range": {
                        "sheetId": worksheet.id,
                        "startRowIndex": 0,
                        "endRowIndex": 3
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
            # Congelar as primeiras três linhas e três colunas
            {
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": worksheet.id,
                        "gridProperties": {
                            "frozenRowCount": 3,
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
    except Exception as e:
        log_error(f"Erro no metodo no hs files no diretorio {str(e)}")                    
                 
def rename_files(submissions_folder, list_title, questions_data, worksheet):
    try:
        if 'HASKELL' in list_title:
            no_hs_files_in_directory(worksheet, submissions_folder)
            rename_files_based_on_dictionary(submissions_folder, questions_data,worksheet, 1)
            language = 'haskell'
            return language
        else:
            no_c_files_in_directory(worksheet, submissions_folder)
            rename_files_based_on_dictionary(submissions_folder, questions_data,worksheet)
            language = 'c'
            return language
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
    
def get_sheet_title(sheet_id):
    try:
        client = get_gspread_client()
        spreadsheet = client.open_by_key(sheet_id)
        return spreadsheet.title
    except Exception as e:
        log_error(f"Erro ao obter título da planilha {sheet_id}: {e}")
        return None

def extract_turma_name(classroom_name):
    match = re.search(r'TURMA\s*[A-Z]', classroom_name)
    return match.group().replace(" ", "_") if match else classroom_name

def read_id_from_file_beecrowd(filename, list_name, classroom_name):
    try:
        with open(filename, 'r') as file:
            sheet_ids = file.readlines()
        
        matched_ids = []
        
        for sheet_id in sheet_ids:
            sheet_id = sheet_id.strip()
            
            sheet_title = get_sheet_title(sheet_id)
            
            if not sheet_title:
                log_info(f"Ignorando planilha {sheet_id}, pois não foi possível obter o título.")
                continue
            
            parts = sheet_title.split('_')
            if len(parts) < 2:
                log_info(f"Título inesperado: {sheet_title}. Pulando...")
                continue
            
            list_part = parts[0]
            class_part = '_'.join(parts[1:]) 
            
            match = re.search(r'TURMA_[A-Z]', class_part)
            if match:
                class_part = match.group()
            
            normalized_list_name = list_name.replace(" ", "").upper()
            normalized_classroom_name = extract_turma_name(classroom_name).replace(" ", "").upper()
            
            if list_part.upper() == normalized_list_name and class_part.upper() == normalized_classroom_name:
                matched_ids.append(sheet_id)
                return sheet_id
        
        if matched_ids:
            return matched_ids
        
        print(f"Não foi encontrado o sheet id da planilha do Beecrowd da {list_name}, da {classroom_name}.")
        return None
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

                worksheet = spreadsheet.add_worksheet(title=list_name, rows=100, cols=40)
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

def update_grades(sheet_id1, worksheet2, score, classroom_name):
    try: 
        client = get_gspread_client()

        worksheet1 = client.open_by_key(sheet_id1)
        worksheet1 = worksheet1.get_worksheet(0)  
        
        emails = [email.strip() for email in worksheet1.col_values(6)[1:] if email] 
        percentages = [percent.strip() for percent in worksheet1.col_values(10)[1:] if percent]   
        log_info(f"\nProcurando os emails {emails}")
        print("\nProcurando os alunos com a nota 100 e 0...\n")
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
                    value_to_update = 0
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
            with open("not_found_emails_100_or_0.txt", "a") as file:
                file.write(f"\nClassroom: {classroom_name}\n")
                for email in not_found_emails:
                    file.write(f"{email}\n")
        
        log_info(f"\nForam encontrados: {len(updates)} alunos nas duas planilhas com o mesmo email.")
        print(f"\nForam encontrados: {len(updates)} alunos nas duas planilhas com o mesmo email.")
        if len(updates) < len(emails): 
            print("\nNem todos os alunos acertaram 100 ou 0 foram encontrados na planilha de resultados. Revise os emails no not_found_emails_100_or_0.txt.")
                               
    except Exception as e:
        log_error(f"Erro ao atualizar planilha {str(e)}")  

def compare_emails(sheet_id_beecrowd, worksheet2, classroom_name):
    try:
        client = get_gspread_client()

        worksheet1 = client.open_by_key(sheet_id_beecrowd).get_worksheet(0) 

        emails_planilha1 = set(email.strip() for email in worksheet1.col_values(6)[1:] if email)
        emails_planilha2 = set(email.strip() for email in worksheet2.col_values(2)[1:] if email)

        only_in_planilha1 = emails_planilha1 - emails_planilha2

        only_in_planilha2 = emails_planilha2 - emails_planilha1

        with open("email_differences.txt", "a") as file:
            file.write(f"\nClassroom: {classroom_name}\n")
            file.write("Beecrowd\n")
            for email in sorted(only_in_planilha1):
                file.write(f"{email}\n")

            file.write("\nClassroom\n")
            for email in sorted(only_in_planilha2):
                file.write(f"{email}\n")

        print("\nArquivo email_differences.txt criado com sucesso. Nele você confere os emails que existem numa plataforma, mas não existem na outra.")

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


def delete_files(folder):
    try:
        if not os.path.exists(folder):
            print(f"O diretório {folder} não existe.")
            return

        for item in os.listdir(folder):
            item_path = os.path.join(folder, item)

            if item == "submissions":
                continue

            if os.path.isfile(item_path) or os.path.islink(item_path):
                os.remove(item_path)
            elif os.path.isdir(item_path):
                shutil.rmtree(item_path)

        log_info("\nArquivos e pastas, exceto 'submissions', foram deletados com sucesso.")  
    except Exception as e:
        log_error(f"Erro ao deletar os arquivos compactados: {str(e)}")

def delete_folder(folder):
    try:
        if os.path.exists(folder): 
            shutil.rmtree(folder)  
            print(f"Pasta '{folder}' deletada com sucesso.")
        else:
            print(f"A pasta '{folder}' não existe.")
    except Exception as e:
        print(f"Erro ao deletar a pasta '{folder}': {e}")

def moss_script(submissions_folder, language, list_name, num_questions):
    try:
        if not os.path.exists(submissions_folder):
            raise FileNotFoundError(f"A pasta '{submissions_folder}' não existe.")
         
        moss_script_path = "moss.pl"  
        links = {} 
        moss_results = [] 

        for i in range(1, num_questions + 1):
            files = []
            log_info(f"\nListando os arquivos da Questão {i}...")
            for folder in os.listdir(submissions_folder):
                folder_path = os.path.join(submissions_folder, folder)
                if os.path.isdir(folder_path): 
                    question_file = f"q{i}_{folder}.c"
                    question_file_path = os.path.join(folder_path, question_file)
                    if os.path.isfile(question_file_path):
                        files.append(question_file_path)
                    else:
                        log_info(f"Arquivo não encontrado para q{i}: {question_file_path}")

            if not files:
                log_info(f"Nenhum arquivo encontrado para a questão {i}. Pulando para a próxima.")
                continue

            comment = f"Análise de similaridade | {list_name} | Questão {i}"
            command = ["perl", moss_script_path, "-l", language, "-c", comment, "-d"] + files

            log_info(f"\nExecutando comando MOSS para questão {i}...")

            try:
                result = subprocess.run(command, capture_output=True, text=True, check=True)
                output = result.stdout.strip()
                report_url = output.split("\n")[-1]  
                links[f"q{i}"] = report_url 
            except subprocess.CalledProcessError as e:
                log_error(f"Erro ao executar o script MOSS para q{i}: {e.stderr}")
                continue

        if not links:
            print("\nNenhum relatório foi gerado.")
        else:
            print("\nLinks gerados para cada questão:")
            for question, link in links.items():
                print(f"\n{question}: {link}")
                if validate_url(link):  
                    moss_data = analyze_moss_report(link)

                    for student_pair in moss_data:
                        student1, percentage1 = student_pair[0]
                        student2, percentage2 = student_pair[1]

                        moss_results.append({
                            "question": f"q{i}",
                            "student1": student1,
                            "percentage1": percentage1,
                            "student2": student2,
                            "percentage2": percentage2
                        })
                else:
                    log_info(f"URL inválida para questão {i}: {report_url}")


        return moss_results

    except Exception as e:
        log_error(f"Erro ao rodar o script MOSS: {str(e)}")

def validate_url(url):
    try: 
        parsed = urlparse(url)
        return bool(parsed.scheme and parsed.netloc)
    except Exception as e:
        log_error(f"Erro ao validar a URL: {str(e)}")

def analyze_moss_report(report_url):
    try:
        response = requests.get(report_url)
        response.raise_for_status()
        html_content = response.text

        soup = BeautifulSoup(html_content, 'html.parser')

        results = set()

        table_rows = soup.find_all('tr')
        
        for row in table_rows:
            columns = row.find_all('td')

            if len(columns) >= 2:  # Cada linha válida tem pelo menos 2 colunas (arquivo1, arquivo2)
                file1_text = columns[0].get_text(strip=True)
                file2_text = columns[1].get_text(strip=True)

                # Student login
                student1_match = re.search(r"/([^/]+)/\s*\(\d+%\)", file1_text)
                student2_match = re.search(r"/([^/]+)/\s*\(\d+%\)", file2_text)

                student1 = student1_match.group(1) if student1_match else file1_text
                student2 = student2_match.group(1) if student2_match else file2_text
                
                # Porcentagem
                match1 = re.search(r"\((\d+)%\)", file1_text)
                match2 = re.search(r"\((\d+)%\)", file2_text)

                percentage_file1 = int(match1.group(1)) if match1 else None
                percentage_file2 = int(match2.group(1)) if match2 else None

                # porcentagem  >= 80%
                if (percentage_file1 and percentage_file1 >= 80) or (percentage_file2 and percentage_file2 >= 80):
                    pair = tuple(sorted([(student1, percentage_file1), (student2, percentage_file2)]))
                    results.add(pair)

        print("\nArquivos com possível cópia detectada (>=80%):\n")
        for student_pair in results:
            student1, percentage1 = student_pair[0]
            student2, percentage2 = student_pair[1]
            print(f"Student 1: {student1} ({percentage1}%) <-> "
                  f"Student 2: {student2} ({percentage2}%)")

        return list(results)          

    except Exception as e:
        print(f"Erro ao processar o relatório Moss: {e}")

def update_moss_results(worksheet, moss_results, num_questions):
    try:
        data = worksheet.get_all_values()
        updates = []

        for result in moss_results:
            student1, percentage1 = result["student1"], result["percentage1"]
            student2, percentage2 = result["student2"], result["percentage2"]

            for idx, row in enumerate(data):
                if len(row) <= 2:
                    continue  

                student_login = row[2]  

                if student_login == student1 or student_login == student2:
                    student = student1 if student_login == student1 else student2
                    percentage = percentage1 if student_login == student1 else percentage2
                    other_student = student2 if student_login == student1 else student1
                    other_percentage = percentage2 if student_login == student1 else percentage1
                    
                    log_info(f"Encontrado {student_login} na linha {idx + 1}. Marcando como cópia.")

                    # Atualiza a Cópia
                    col = ord('G') - ord('A') + num_questions   
                    
                    
                    cell_range = f'{chr(65 + col)}{idx + 1}'
                    updates.append({"range": cell_range, "values": [[1]]})

                    # Atualiza Comentários
                    col = ord('I') - ord('A') + 1  # Começa em K
                    while col < len(row) and row[col]:  
                        col += 1  
                    
                    cell_range = f'{chr(65 + col)}{idx + 1}'
                    comment_text = f"Student 1: {student} ({percentage}%) <-> Student 2: {other_student} ({other_percentage}%)"
                    updates.append({"range": cell_range, "values": [[comment_text]]})

        if updates:
            print("\n--- Aplicando atualizações... ---")
            worksheet.batch_update(updates)
            print("Atualização concluída com sucesso!")

    except Exception as e:
        print(f"Erro ao atualizar a planilha com resultados do Moss: {e}")

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
            worksheets = []
            goMoss = 1

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
                        worksheets.append(worksheet)
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

                language = rename_files(submissions_folder, list_title, questions_data, worksheet)
                print("\nProcesso de verificar e renomear arquivos finalizado.")
                delete_empty_subfolders(worksheet,submissions_folder)
                
                if worksheet is not None:
                    
                    sheet_id_beecrowd = read_id_from_file_beecrowd('sheet_id_beecrowd.txt', list_name, classroom_name)
                    if sheet_id_beecrowd:
                        update_grades(sheet_id_beecrowd, worksheet, score, classroom_name)
                        compare_emails(sheet_id_beecrowd, worksheet, classroom_name)
                        insert_columns(worksheet, num_questions)
                        update_final_grade_for_no_submission(worksheet, num_questions)
                        insert_score_row(worksheet, score)
                        fill_scores_for_students(worksheet, num_questions, score)
                        print("\nProcesso de colocar as notas do beecrowd na planilha finalizado.")
                        apply_dynamic_formula_in_column(worksheet, num_questions)
                        print("\nProcesso de colocar as fórmulas dinâmicas na planilha finalizado.")
                        
                        
                    else:
                        insert_score_row(worksheet, score)
                        update_final_grade_for_no_submission(worksheet, None) 
                        print("\nID da planilha do Beecrowd não foi encontrado no arquivo 'sheet_id_beecrowd.txt'. Não será adicionada as notas dos alunos que tiraram 0 ou 100 de acordo com a planilha do beecrowd.")

                    
                    freeze_and_sort(worksheet)
                    insert_header_title(worksheet, classroom_name, list_title)
                    print("\nProcesso de formatar a planilha finalizado.\n")
                    print(f"\nProcesso da {classroom_name} - {list_name} concluído.")
                
                delete = int(input("\nDeseja deletar todo o download dos arquivos compactados? \n0 - Não \n1 - Sim\n:"))
                if delete:
                    delete_files(download_folder)
                
                if goMoss != 1 :
                    moss = int(input("\n\nVocê quer rodar o moss agora? \n0 - Não \n1 - Sim\n:"))
                    if moss :
                        print("\nRodando o moss...")
                        moss_results = moss_script(submissions_folder, language, list_name, num_questions)

                        for ws in worksheets:
                            print(f"\nAtualizando {ws.title} com os resultados do MOSS...")
                            update_moss_results(ws, moss_results, num_questions)

                        goMoss = 1                    
                        delete = int(input("\nDeseja deletar a pasta submissions? \n0 - Não \n1 - Sim\n:"))
                        if delete:
                            delete_folder(submissions_folder)
                            delete_folder(download_folder)
                        
                    
                try:
                    num = int(input("\n\nDeseja baixar mais uma atividade? \n0 - Não \n1 - Sim\n\n:"))
                    if num == 0:
                        print("\nProcesso encerrado.")
                        break
                    elif num == 1:
                        goMoss += 1
                    else:
                        print("Opção inválida. Por favor, digite 0 ou 1.")
                except ValueError:
                    print("\nEntrada inválida. Encerrando processo.")
                    break
                
        except HttpError as error:
            print(f"Um erro ocorreu: {error}")
    except Exception as e:
        log_error(f"Erro no fluxo principal: {str(e)}")     
   

if __name__ == "__main__":
    main()
