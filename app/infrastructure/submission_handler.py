import io
import os
import shutil
import stat, subprocess
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload
from core.models.student_submission import StudentSubmission
from utils.permission_utils import relax_permissions, relax_permissions_for_delete, _onerror_chmod_then_retry
from utils.utils import extract_prefix, get_submission_timestamp, calculate_delay, get_due_date, log_info, log_error

def create_student_folder_if_needed(download_folder, student_login):
    student_folder = os.path.join(download_folder, student_login)
    os.makedirs(student_folder, exist_ok=True)
    return student_folder

def rename_file_if_needed(file_name, student_folder, student_obj):
    student_login = student_obj.login
    file_path = os.path.join(student_folder, file_name)

    if file_name.endswith('.zip'):
        expected_name = f"{student_login}.zip"
        if file_name != expected_name:
            student_obj.update_field('formatacao', 0)
            student_obj.add_comment(f"Erro de submissão. Nome do zip incorreto: {file_name}.")
            corrected_path = os.path.join(student_folder, expected_name)
            shutil.move(file_path, corrected_path)

    elif file_name.endswith('.rar'):
        student_obj.update_field('formatacao', 0)
        student_obj.add_comment(f"Erro de submissão. Enviou .rar ({file_name}) ao invés de .zip.")
        expected_name = f"{student_login}.rar"
        relax_permissions(student_folder)
        if file_name != expected_name:
            corrected_path = os.path.join(student_folder, expected_name)
            shutil.move(file_path, corrected_path)
            student_obj.add_comment(f"Renomeado {file_name} para {expected_name}.")
       

def handle_attachment(file_id, file_name, student_folder, student_obj, drive_service):
    try:
        file_path = os.path.join(student_folder, file_name)
        request = drive_service.files().get_media(fileId=file_id)
        with io.FileIO(file_path, 'wb') as fh:
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            progress_percentage = 0
            while not done:
                status, done = downloader.next_chunk()
                progress_percentage = int(status.progress() * 100)
                log_info(f"Baixando {file_name} de {student_obj.name}: {progress_percentage}%")

        if progress_percentage == 0:
            student_obj.update_field('entregou', 0)
            student_obj.add_comment("Erro de submissão ou submissão não foi baixada.")
            if os.path.exists(file_path):
                os.remove(file_path)
            return

        raw_code_extensions = ['.c', '.cpp', '.py', '.java', '.js', '.rb', '.hs']
        if any(file_name.endswith(ext) for ext in raw_code_extensions):
            student_obj.update_field('entregou', 1)
            student_obj.add_comment("Erro de submissão: enviou arquivo(s), mas não enviou numa pasta compactada.")

            student_folder = create_student_folder_if_needed(student_folder, student_obj.login)
            new_path = os.path.join(student_folder, file_name)
            shutil.move(file_path, new_path)
            file_path = new_path 

        rename_file_if_needed(file_name, student_folder, student_obj)

    except HttpError as error:
        if error.resp.status == 403 and 'cannotDownloadAbusiveFile' in str(error):
            student_obj.update_field('entregou', 0)
            student_obj.add_comment("Erro de submissão: arquivo identificado como malware ou spam.")
            log_info(f"O arquivo {file_name} de {student_obj.name} foi identificado como malware/spam.\n")
            if os.path.exists(file_path):
                os.remove(file_path)
        else:
            student_obj.update_field('entregou', 0)
            student_obj.add_comment(f"Erro de submissão: erro ao baixar arquivo {file_name}.")
            log_info(f"Erro ao baixar arquivo {file_name} de {student_obj.name}: {error}")

def download_submissions(classroom_service, drive_service, submissions, download_folder, classroom_id, coursework_id, num_questions):
    try:
        students = []
        due_date = get_due_date(classroom_service, classroom_id, coursework_id)

        for submission in submissions.get('studentSubmissions', []):
            try:
                student_id = submission['userId']
                student = classroom_service.courses().students().get(courseId=classroom_id, userId=student_id).execute()
                student_email = student['profile']['emailAddress']
                student_login = extract_prefix(student_email)
                student_name = student['profile']['name']['fullName']

                entregou = 1
                atrasou = 0
                formatacao = 1
                copia = 0
                state = submission.get('state', 'UNKNOWN')

                log_info(f"\nHistórico de submissão: {submission.get('submissionHistory', [])}")
                submission_date = get_submission_timestamp(submission, student_id)
                attachments = submission.get('assignmentSubmission', {}).get('attachments', [])
                log_info(f"Due date: {due_date}, Submission date: {submission_date}, State: {state}")

                student_obj = StudentSubmission(
                    name=student_name,
                    email=student_email,
                    login=student_login,
                    questions={f"q{i+1}": "" for i in range(num_questions)},
                    entregou=entregou,
                    atrasou=atrasou,
                    formatacao=formatacao,
                    copia=copia
                )

                if not attachments:
                    student_obj.update_field('entregou', 0)
                    student_obj.add_comment("Erro de submissão. Não entregou a atividade.")
                    log_info(f"{student_name} Aluno não entregou submissão.")
                else:
                    if due_date and submission_date:
                        student_obj.update_field('atrasou', calculate_delay(due_date, submission_date))

                    for attachment in attachments:
                        file_id = attachment.get('driveFile', {}).get('id')
                        file_name = attachment.get('driveFile', {}).get('title')
                        handle_attachment(file_id, file_name, download_folder, student_obj, drive_service)

            except Exception as e:
                log_error(f"Erro ao processar submissão de aluno: {e}")
                student_obj.update_field('entregou', 0)
                student_obj.add_comment("Erro ao processar submissão.")
                log_info(f"Nenhum anexo encontrado para {student_name}")

            students.append(student_obj)

        return students

    except Exception as e:
        log_error(f"Erro geral ao baixar submissões: {e}")
        return []
