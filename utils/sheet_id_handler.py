import re
import gspread
from gspread.exceptions import WorksheetNotFound
from utils.utils import log_error
from infrastructure.auth_google import get_gspread_client

def semester_informations(sheet_id):
    try:
        client = get_gspread_client()
        spreadsheet = client.open_by_key(sheet_id)

        semester = spreadsheet.title.strip()
        
        if not re.match(r"^\d{4}\.\d$", semester):
            print(f"O título da planilha deve estar no formato 'YYYY.S' (ex: 2024.2). Encontrado: '{semester}'\n")
            return None, None

        return semester

    except Exception as e:
        log_error(f"Erro em pegar da planilha o semestre e a lista: {str(e)}")
   

def list_questions(sheet_id, sheet_name):
    try:
        client = get_gspread_client()
        spreadsheet = client.open_by_key(sheet_id)

        sheet = spreadsheet.worksheet(sheet_name)
        rows = sheet.get_all_values()[1:]  # Ignora cabeçalho

        if not rows:
            print(f"A planilha '{sheet_name}' não tem campos preenchidos.\n")

        questions_dict = {}
        score = {}
        #print("\nO dicionário está assim: ")
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
                #print(f"{question_data}")

            if row[0].strip():
                score[f'q{i}'] = row[0].strip()

        return questions_dict, i, score
    
    except Exception as e:
        log_error(f"Erro em pegar da planilha os nomes das questões: {str(e)}")
        
