import os
import unicodedata
from infrastructure.auth_google import get_gspread_client
from utils.utils import log_info, log_error, read_id_from_file
from utils import utils  

def normalize_name(student_string):
    try:
        if not student_string:
            return ""
        normalized = unicodedata.normalize("NFKD", student_string)
        normalized = "".join(c for c in normalized if not unicodedata.combining(c))
        normalized = normalized.strip().lower()
        normalized = " ".join(normalized.split())
        return normalized
    except Exception as e:
        log_error(f"Erro ao normalizar nome: {e}")
        return ""

def get_laudo_names(laudo_sheet_id_path="input/sheet_id_laudo.txt", name_col_index=0):
   
    try:
        laudo_sheet_id = read_id_from_file(laudo_sheet_id_path)
        if not laudo_sheet_id:
            raise ValueError(f"Arquivo '{laudo_sheet_id_path}' não encontrado ou inválido.")

        client = get_gspread_client()
        laudo_ws = client.open_by_key(laudo_sheet_id).get_worksheet(0)

        col_1based = name_col_index + 1
        laudo_raw = laudo_ws.col_values(col_1based)

        laudo_map = {}
        for n in laudo_raw:
            norm = normalize_name(n)
            if norm:
                laudo_map.setdefault(norm, n) 

        laudo_norm_set = set(laudo_map.keys())
        return laudo_norm_set, laudo_map
    except Exception as e:
        log_error(f"Erro ao obter nomes do laudo: {e}")
        return set(), {}

def highlight_rows_by_names_from_laudo(
    worksheet,
    laudo_sheet_id_path="input/sheet_id_laudo.txt",
    rgb=(0.86, 0.95, 0.80),
    name_column_index=0,
    header_rows=3
):
    try:
        laudo_names_normalized, _ = get_laudo_names(
            laudo_sheet_id_path=laudo_sheet_id_path,
            name_col_index=name_column_index
        )
        if not laudo_names_normalized:
            log_info("Nenhum nome válido encontrado na planilha de laudo.")
            return 0

        all_values = worksheet.get_all_values()
        if not all_values:
            log_info("Worksheet alvo vazia; nada a destacar.")
            return 0

        num_columns_used = max((len(row) for row in all_values), default=worksheet.col_count) or worksheet.col_count or 1

        start_row_index_zero_based = header_rows
        end_row_index_zero_based = len(all_values)

        matching_row_indexes = []
        for row_index in range(start_row_index_zero_based, end_row_index_zero_based):
            row = all_values[row_index]
            student_name = row[name_column_index] if len(row) > name_column_index else ""
            if normalize_name(student_name) in laudo_names_normalized:
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
                    "cell": {"userEnteredFormat": {"backgroundColor": background}},
                    "fields": "userEnteredFormat.backgroundColor"
                }
            })

        worksheet.spreadsheet.batch_update({"requests": requests})
        log_info(f"Linhas destacadas: {len(matching_row_indexes)}")
        return len(matching_row_indexes)

    except Exception as e:
        log_error(f"Erro ao destacar linhas por nomes do laudo: {e}")
        return 0

def log_laudo_names_not_found(
    target_worksheets,
    laudo_sheet_id_path="input/sheet_id_laudo.txt",
    name_column_index=0,
    header_rows=3,
    filename="log_students_with_laudo_not_found.txt"
):
    try:
        laudo_norm_set, laudo_map = get_laudo_names(
            laudo_sheet_id_path=laudo_sheet_id_path,
            name_col_index=name_column_index
        )
        if not laudo_norm_set:
            msg = "Nenhum nome válido encontrado na planilha de laudo."
            log_info(msg)
            return 0

        encontrados_norm = set()
        for ws in target_worksheets:
            vals = ws.get_all_values() or []
            for row in vals[header_rows:]:
                nome = row[name_column_index] if len(row) > name_column_index else ""
                norm = normalize_name(nome)
                if norm in laudo_norm_set:
                    encontrados_norm.add(norm)

        faltantes_norm = laudo_norm_set - encontrados_norm
        if faltantes_norm:
            faltantes_print = "\n".join(sorted(laudo_map[n] for n in faltantes_norm))
            msg = f"Alunos no Laudo não encontrados em NENHUMA das outras planilhas:\n{faltantes_print}"
            log_info(msg)

            base_folder = utils.FOLDER_PATH if utils.FOLDER_PATH else "output"
            output_folder = os.path.join(base_folder, "output") if not base_folder.endswith("output") else base_folder

            os.makedirs(output_folder, exist_ok=True)
            full_path = os.path.join(output_folder, filename)

            with open(full_path, "a", encoding="utf-8") as f:
                f.write(msg + "\n\n")

            print(f"\nLog salvo em {full_path}")
            return len(faltantes_norm)
        else:
            msg = "Todos os alunos do Laudo foram encontrados em pelo menos uma das outras planilhas."
            log_info(msg)
            return 0
    except Exception as e:
        log_error(f"Erro ao listar faltantes do Laudo: {e}")
        return 0