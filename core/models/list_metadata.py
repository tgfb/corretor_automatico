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
    language: str = ""

    def save_metadata_to_json(self, path: str):
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(asdict(self), f, ensure_ascii=False, indent=4)
            log_info(f"Metadata salva com sucesso em {path}")
        except Exception as e:
            log_error(f"Erro ao salvar metadata em {path}: {e}")

    @staticmethod
    def load_metadata_from_json(path: str):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return ListMetadata(**data)
        except Exception as e:
            log_error(f"Erro ao carregar metadata de {path}: {e}")
            return None

    @staticmethod
    def update_language(path: str, language: str):
        try:
            metadata = ListMetadata.load_metadata_from_json(path)
            if not metadata:
                return
            metadata.language = language
            metadata.save_metadata_to_json(path)
            log_info(f"Campo 'language' atualizado para '{language}' em {path}")
        except Exception as e:
            log_error(f"Erro ao atualizar language no metadata: {e}")
