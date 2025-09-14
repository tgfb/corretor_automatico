import math
from googleapiclient.discovery import build
from infrastructure.auth_google import get_credentials
from infrastructure.spreadsheet_handler import get_google_sheet_if_exists
from utils.utils import log_info, log_error

def find_email_and_total_columns(worksheet):
   
    try:
        header = worksheet.row_values(2)
        header_norm = [h.strip().upper() for h in header]
        col_email = header_norm.index("EMAIL")
        col_total = header_norm.index("NOTA TOTAL")
        return col_email, col_total
    except ValueError as e:
        log_error("Não foi possível encontrar as colunas 'EMAIL' e/ou 'NOTA TOTAL' na linha 2.")
        return None, None
    except Exception as e:
        log_error(f"Erro ao localizar colunas de e-mail/nota: {e}")
        return None, None


def read_email_to_grade_map(worksheet) :
  
    try:
        col_email, col_total = find_email_and_total_columns(worksheet)
        if col_email is None or col_total is None:
            return {}

        data = worksheet.get_all_values()
        results = {}

        for row_index in range(3, len(data)):  
            row = data[row_index]
            if len(row) <= max(col_email, col_total):
                continue

            email = (row[col_email] or "").strip().lower()
            grade_str = (row[col_total] or "").strip().replace(",", ".")
            if not email:
                continue

            try:
                grade = float(grade_str) if grade_str != "" else None
            except ValueError:
                grade = None

            if grade is not None and not math.isnan(grade):
                results[email] = grade

        return results
    except Exception as e:
        log_error(f"Erro ao ler mapa de e-mail → nota na planilha: {e}")
        return {}


def classroom() :
    try:
        return build("classroom", "v1", credentials=get_credentials())
    except Exception as e:
        log_error(f"Erro ao construir serviço Classroom: {e}")
        return None

def get_coursework(service, course_id, coursework_id):
    try:
        return service.courses().courseWork().get(courseId=course_id, id=coursework_id).execute()
    except Exception as e:
        log_error(f"Erro ao obter coursework ({course_id}/{coursework_id}): {e}")
        return None

def map_email_for_userid(service, course_id):
   
    mapping = {}
    try:
        req = service.courses().students().list(courseId=course_id, pageSize=200)
        while req is not None:
            resp = req.execute()
            for s in resp.get("students", []):
                profile = s.get("profile", {})
                email = (profile.get("emailAddress") or "").strip().lower()
                uid = profile.get("id")
                if email and uid:
                    mapping[email] = uid
            req = service.courses().students().list_next(req, resp)
    except Exception as e:
        log_error(f"Erro ao mapear e-mail → userId (course {course_id}): {e}")
    return mapping

def map_userid_for_submission(service, course_id, coursework_id) :

    mapping = {}
    try:
        req = service.courses().courseWork().studentSubmissions().list(
            courseId=course_id, courseWorkId=coursework_id, pageSize=200
        )
        while req is not None:
            resp = req.execute()
            for sub in resp.get("studentSubmissions", []):
                uid = sub.get("userId")
                if uid:
                    mapping[uid] = sub
            req = service.courses().courseWork().studentSubmissions().list_next(req, resp)
    except Exception as e:
        log_error(f"Erro ao mapear userId → submission (course {course_id}, cw {coursework_id}): {e}")
    return mapping

def patch_grade(service, course_id, coursework_id, submission_id, valor, usar_rascunho, dry_run):
    try:
        mask = "draftGrade" if usar_rascunho else "assignedGrade"
        body = {mask: valor}
        if dry_run:
            log_info(f"[DRY-RUN] PATCH {submission_id}: {mask}={valor}")
            return
        service.courses().courseWork().studentSubmissions().patch(
            courseId=course_id, courseWorkId=coursework_id, id=submission_id,
            updateMask=mask, body=body
        ).execute()
    except Exception as e:
        log_error(f"Erro ao aplicar PATCH de nota (submission {submission_id}): {e}")

def push_spreadsheet_to_classroom(classroom_service, folder_id, course_id, coursework_id, classroom_name, list_name, assume_sheet_max=100.0, use_draft=True, dry_run=True):
   
    try:
        sheet_tab = list_name.split(" - ")[0].strip()

        spreadsheet, worksheet = get_google_sheet_if_exists(classroom_name, sheet_tab, folder_id)
        if not worksheet:
            log_error(f"[{classroom_name}] Sheet/tab not found for '{classroom_name}' / '{sheet_tab}'.")
            return 0

        email_to_grade = read_email_to_grade_map(worksheet)
        if not email_to_grade:
            log_info(f"[{classroom_name}] Nothing to push: sheet has no grades.")
            return 0

        cw = get_coursework(classroom_service, course_id, coursework_id)
        if not cw:
            log_error(f"[{classroom_name}] Could not fetch coursework.")
            return 0

        max_points = cw.get("maxPoints")
        if max_points in (None, 0):
            log_error(f"[{classroom_name}] Coursework has no 'maxPoints' defined.")
            return 0

        email_to_user = map_email_for_userid(classroom_service, course_id)
        user_to_sub = map_userid_for_submission(classroom_service, course_id, coursework_id)

        processed = 0
        for email, sheet_grade in email_to_grade.items():
            try:
                user_id = email_to_user.get(email)
                if not user_id:
                    log_info(f"[{classroom_name}] Skipping {email}: not found in Classroom roster.")
                    continue

                sub = user_to_sub.get(user_id)
                if not sub:
                    log_info(f"[{classroom_name}] Skipping {email}: no submission for this coursework.")
                    continue

                scaled = round(
                    max(0.0, min(float(max_points), float(sheet_grade) * float(max_points) / float(assume_sheet_max))), 2)

                current = sub.get("draftGrade") if use_draft else sub.get("assignedGrade")
                if current is not None and abs(float(current) - scaled) < 1e-6:
                    continue

                patch_grade(classroom_service, course_id, coursework_id, sub["id"], scaled, use_draft, dry_run)
                processed += 1
            except Exception as e:
                log_error(f"[{classroom_name}] Failed to process {email}: {e}")
                continue

        return processed

    except Exception as e:
        log_error(f"Error pushing grades from spreadsheet to Classroom [{classroom_name}]: {e}")
        return 0
