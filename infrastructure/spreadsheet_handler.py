import gspread
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from utils.utils import log_error, log_info
from infrastructure.auth_google import get_gspread_client
from infrastructure.auth_google import get_credentials

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

def header_worksheet(worksheet, num_questions, score):
    try:
        question_headers = [f"QUESTÃO {i + 1}" for i in range(num_questions)]
        header = [['NOME DO ALUNO', 'EMAIL', 'STUDENT LOGIN'] + question_headers +
                  ['ENTREGA?', 'ATRASO?', 'FORMATAÇÃO?', 'CÓPIA?', 'NOTA TOTAL', 'COMENTÁRIOS']]
        if not worksheet.get_all_values():
            worksheet.append_rows(header, table_range='A1')

        score_row = [''] * 3
        score_row += [score.get(f'q{i + 1}', '') for i in range(num_questions)]
        score_row += [''] * 6
        worksheet.insert_row(score_row, index=2)

        log_info("Cabeçalho e linha de score adicionados com sucesso.")
    except Exception as e:
        log_error(f"Erro ao configurar cabeçalho da planilha: {e}")

def insert_header_title(worksheet, classroom_name, list_title):
    try:
        title = f"{classroom_name} - {list_title}"
        worksheet.insert_row([title], index=1)

        sheet_id = worksheet.id
        spreadsheet = worksheet.spreadsheet
        spreadsheet.batch_update({
            "requests": [
                {
                    "repeatCell": {
                        "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 3},
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
                {
                    "updateSheetProperties": {
                        "properties": {
                            "sheetId": sheet_id,
                            "gridProperties": {"frozenRowCount": 3, "frozenColumnCount": 3}
                        },
                        "fields": "gridProperties.frozenRowCount,gridProperties.frozenColumnCount"
                    }
                },
                {
                    "autoResizeDimensions": {
                        "dimensions": {
                            "sheetId": sheet_id,
                            "dimension": "COLUMNS",
                            "startIndex": 0,
                            "endIndex": 3
                        }
                    }
                }
            ]
        })

        log_info("Título e formatação aplicados com sucesso.")
    except Exception as e:
        log_error(f"Erro ao inserir título e aplicar formatação: {e}")

def freeze_and_sort(worksheet):
    try:
        spreadsheet = worksheet.spreadsheet
        spreadsheet.batch_update({
            "requests": [
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
                {
                    "sortRange": {
                        "range": {
                            "sheetId": worksheet.id,
                            "startRowIndex": 1
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
        })
        log_info("Congelamento e ordenação aplicados.")
    except Exception as e:
        log_error(f"Erro ao aplicar congelamento e ordenação: {e}")

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

def fill_worksheet_with_students(worksheet, students, num_questions):
    try:
        if not students:
            log_info("Nenhum aluno para inserir na planilha.")
            return

        rows = [student.to_list(num_questions) for student in students]
        worksheet.append_rows(rows)
        log_info(f"{len(rows)} alunos inseridos na planilha com sucesso.")
    except Exception as e:
        log_error(f"Erro ao preencher a planilha com alunos: {e}")

