import re
import time
import gspread
from utils.utils import log_info, log_error
from infrastructure.auth_google import get_gspread_client
from infrastructure.google_utils import get_sheet_title, extract_turma_name
from core.utils.update_worksheet_comentario import update_worksheet_comentario

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

