import unicodedata
from infrastructure.auth_google import get_gspread_client
from utils.utils import log_info, log_error, read_id_from_file

def _normalize_name(student_string):
    if not student_string:
        return ""
    normalized = unicodedata.normalize("NFKD", student_string)
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))  # remove acentos
    normalized = normalized.strip().lower()
    normalized = " ".join(normalized.split()) 
    return normalized

def highlight_rows_by_names_from_laudo(worksheet,laudo_sheet_id_path = "input/sheet_id_laudo.txt", rgb = (0.86, 0.95, 0.80), name_column_index = 0, header_rows = 3):
 
    try:
   
        laudo_sheet_id = read_id_from_file(laudo_sheet_id_path)
        if not laudo_sheet_id:
            raise ValueError(f"Arquivo '{laudo_sheet_id_path}' não encontrado ou inválido.")

        client = get_gspread_client()
        laudo_spreadsheet = client.open_by_key(laudo_sheet_id)
        laudo_worksheet = laudo_spreadsheet.get_worksheet(0)  
        laudo_names_raw = laudo_worksheet.col_values(1)       
        laudo_names_normalized = {
            _normalize_name(name) for name in laudo_names_raw if _normalize_name(name)
        }

        if not laudo_names_normalized:
            log_info("Nenhum nome válido encontrado na planilha de laudo.")
            return 0

        all_values = worksheet.get_all_values()
        if not all_values:
            log_info("Worksheet alvo vazia; nada a destacar.")
            return 0

        num_columns_used = max((len(row) for row in all_values), default=worksheet.col_count)
        if num_columns_used == 0:
            num_columns_used = worksheet.col_count or 1

        start_row_index_zero_based = header_rows        
        end_row_index_zero_based = len(all_values)      

        matching_row_indexes = []
        for row_index in range(start_row_index_zero_based, end_row_index_zero_based):
            row = all_values[row_index]
            student_name = row[name_column_index] if len(row) > name_column_index else ""
            if _normalize_name(student_name) in laudo_names_normalized:
                matching_row_indexes.append(row_index)

        if not matching_row_indexes:
            log_info("Nenhuma linha correspondente encontrada para destacar.")
            return 0

        background = {"red": float(rgb[0]), "green": float(rgb[1]), "blue": float(rgb[2])}
        sheet_id = worksheet.id
        requests = []
        for row_index in matching_row_indexes:
            requests.append({
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": row_index,
                        "endRowIndex": row_index + 1,
                        "startColumnIndex": 0,
                        "endColumnIndex": num_columns_used
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": background
                        }
                    },
                    "fields": "userEnteredFormat.backgroundColor"
                }
            })

        worksheet.spreadsheet.batch_update({"requests": requests})
        log_info(f"Linhas destacadas: {len(matching_row_indexes)}")
        return len(matching_row_indexes)

    except Exception as e:
        log_error(f"Erro ao destacar linhas por nomes do laudo: {e}")
        return 0
