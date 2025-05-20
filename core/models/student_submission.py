from dataclasses import dataclass, asdict
import json
from utils.utils import log_error, log_info

@dataclass
class StudentSubmission:
    name: str
    email: str
    login: str
    entregou: int
    atrasou: int
    formatacao: int
    copia: int
    nota_total: str = ''
    comentario: str = ''

    def to_list(self, num_questions: int):
        try:
            return [self.name, self.email, self.login] + [''] * num_questions + [
                self.entregou, self.atrasou, self.formatacao, self.copia, self.nota_total, self.comentario
            ]
        except Exception as e:
            log_error(f"Erro ao converter student {self.login} para lista: {e}")
            return []
    
    def add_comment(self, text):
        try:
            if text and text not in self.comentario:
                if self.comentario:
                    self.comentario += f" {text}"
                else:
                    self.comentario = text
        except Exception as e:
            log_error(f"Erro ao adicionar comentário para {self.login}: {e}")
    
    def update_field(self, field, value):
        try:
            if hasattr(self, field):
                setattr(self, field, value)
            else:
                log_error(f"Campo '{field}' não encontrado para o aluno {self.login}")
        except Exception as e:
            log_error(f"Erro ao atualizar campo '{field}' para {self.login}: {e}")

def save_students_to_txt(student_list, path):
    try:
        with open(path, 'w', encoding='utf-8') as file:
            for student in student_list:
                json.dump(asdict(student), file, ensure_ascii=False)
                file.write('\n')
        log_info(f"Lista de alunos salva com sucesso em {path}")
    except Exception as e:
        log_error(f"Erro ao salvar alunos em {path}: {e}")

def load_students_from_txt(path):
    students = []
    try:
        with open(path, 'r', encoding='utf-8') as file:
            for line in file:
                data = json.loads(line.strip())
                students.append(StudentSubmission(**data))
        log_info(f"Lista de alunos carregada com sucesso de {path}")
    except Exception as e:
        log_error(f"Erro ao carregar alunos de {path}: {e}")
    return students

