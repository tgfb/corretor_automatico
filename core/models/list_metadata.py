from dataclasses import dataclass, asdict
import json
import os
from utils.utils import log_error, log_info

@dataclass
class ListMetadata:
    class_name: str
    list_name: str
    num_questions: int
    score: dict

def save_metadata_to_json(metadata: ListMetadata, path: str):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True) 
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(asdict(metadata), f, indent=4, ensure_ascii=False)
        log_info(f"Metadados salvos com sucesso em {path}")
    except Exception as e:
        log_error(f"Erro ao salvar metadados em {path}: {e}")

def load_metadata_from_json(path: str) -> ListMetadata:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return ListMetadata(**data)
    except Exception as e:
        log_error(f"Erro ao carregar metadados de {path}: {e}")
        return None
