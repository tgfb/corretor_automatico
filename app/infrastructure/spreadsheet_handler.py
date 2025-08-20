from googleapiclient.discovery import build
from utils.utils import log_error, log_info
from infrastructure.auth_google import get_gspread_client
from infrastructure.auth_google import get_credentials


def get_google_sheet_if_exists(classroom_name, list_name, folder_id):
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
                return spreadsheet, worksheet
            except Exception:
                print(f"A aba '{list_name}' ainda não existe na planilha '{classroom_name}'.\n")
                return spreadsheet, None
        else:
            return None, None

    except Exception as e:
        log_error(f"Erro ao buscar planilha existente: {str(e)}")
        return None, None
    
def create_google_sheet_and_worksheet(classroom_name, list_name, folder_id):
    try:
        client = get_gspread_client()
        drive_service = build("drive", "v3", credentials=get_credentials())

        query = (
            f"'{folder_id}' in parents and mimeType='application/vnd.google-apps.spreadsheet' "
            f"and name='{classroom_name}'"
        )
        response = drive_service.files().list(
            q=query, spaces='drive', fields='files(id, name, trashed)'
        ).execute()

        for file in response.get("files", []):
            if not file.get("trashed", False):
                print(f"Planilha '{classroom_name}' já existe. Nenhuma planilha será criada.\n")
                return None, None

        spreadsheet = client.create(classroom_name)
        print(f"Planilha '{classroom_name}' criada com sucesso.\n")

        file_id = spreadsheet.id
        drive_service.files().update(
            fileId=file_id,
            addParents=folder_id,
            removeParents='root'
        ).execute()

        try:
            worksheet = spreadsheet.worksheet(list_name)
            print(f"A aba '{list_name}' já existe na planilha.\n")
        except:
            worksheet = spreadsheet.get_worksheet(0)
            worksheet.update_title(list_name)
            print(f"Aba inicial renomeada para '{list_name}'.\n")

        return spreadsheet, worksheet

    except Exception as e:
        log_error(f"Erro ao criar planilha e aba: {str(e)}")
        return None, None

def header_worksheet(worksheet, class_name, list_title, num_questions, score_dict):
    try:
        title = f"{class_name} - {list_title}"
        worksheet.insert_row([title], index=1)

        headers = ["NOME DO ALUNO", "EMAIL", "STUDENT LOGIN"] + \
                  [f"QUESTÃO {i+1}" for i in range(num_questions)] + \
                  ["ENTREGA?", "ATRASO?", "FORMATAÇÃO?", "CÓPIA?", "NOTA TOTAL", "COMENTÁRIO"]
        worksheet.insert_row(headers, index=2)

        log_info("Título, cabeçalho adicionados com sucesso.")
        return True
    except Exception as e:
        log_error(f"Erro ao configurar cabeçalho da planilha: {e}")
        return False

def insert_header_title(worksheet, score_dict, num_questions):
    try:
        score_row = [''] * 3
        score_row += [score_dict.get(f"q{i+1}", "") for i in range(num_questions)]
        score_row += [''] * 6
        worksheet.insert_row(score_row, index=3)

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

        log_info("Formatação aplicados com sucesso.")
    except Exception as e:
        log_error(f"Erro ao inserir título e aplicar formatação: {e}")

def freeze_and_sort(worksheet):
    try:
        spreadsheet = worksheet.spreadsheet
        sheet_id = worksheet.id

        data = worksheet.get_all_values()
        num_columns = len(data[0]) if data else 0

        spreadsheet.batch_update({
            "requests": [
                {
                    "updateSheetProperties": {
                        "properties": {
                            "sheetId": sheet_id,
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
                            "sheetId": sheet_id,
                            "startRowIndex": 3,  
                            "startColumnIndex": 0,
                            "endColumnIndex": num_columns
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

        for row_idx in range(3, last_filled_row + 1):
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
        range_start = "A4"
        worksheet.update(range_start, rows, value_input_option="USER_ENTERED")

        log_info(f"{len(rows)} alunos inseridos na planilha com sucesso (linha 4 em diante).")
    except Exception as e:
        log_error(f"Erro ao preencher a planilha com alunos em batch: {e}")

def align_middle_entire_sheet(worksheet):

    try:
        spreadsheet = worksheet.spreadsheet
        sheet_id = worksheet.id
        end_row = worksheet.row_count
        end_col = worksheet.col_count

        spreadsheet.batch_update({
            "requests": [
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 0,
                            "startColumnIndex": 0,
                            "endRowIndex": end_row,
                            "endColumnIndex": end_col
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "verticalAlignment": "MIDDLE",

                            }
                        },
                        "fields": "userEnteredFormat.verticalAlignment"
                    }
                }
            ]
        })
        log_info("Alinhamento vertical 'Middle' aplicado à planilha inteira.")
    except Exception as e:
        log_error(f"Erro ao aplicar alinhamento vertical 'Middle': {e}")

def align_and_resize(worksheet):

    try:
        spreadsheet = worksheet.spreadsheet
        sheet_id = worksheet.id

        data = worksheet.get_all_values()
        if not data or not data[0]:
            log_info("Planilha vazia, nada para alinhar/redimensionar.")
            return

        num_columns = len(data[0])
        end_col = max(1, num_columns - 1) 
        end_row = worksheet.row_count

        requests = []

        for col in range(3):
            requests.append({
                "autoResizeDimensions": {
                    "dimensions": {
                        "sheetId": sheet_id,
                        "dimension": "COLUMNS",
                        "startIndex": col,
                        "endIndex": col + 1
                    }
                }
            })

        requests.append({
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 0,
                    "endRowIndex": end_row,
                    "startColumnIndex": 1,        
                    "endColumnIndex": end_col     
                },
                "cell": {
                    "userEnteredFormat": {
                        "horizontalAlignment": "CENTER"
                    }
                },
                "fields": "userEnteredFormat.horizontalAlignment"
            }
        })

        spreadsheet.batch_update({"requests": requests})
        log_info("Auto-resize aplicado nas colunas 1-3 e alinhamento aplicado da coluna 2 até penúltima.")
    except Exception as e:
        log_error(f"Erro ao aplicar alinhamento/redimensionamento: {e}")
