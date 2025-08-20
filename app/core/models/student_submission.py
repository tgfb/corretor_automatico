from dataclasses import dataclass, asdict, field
import json
from utils.utils import log_error, log_info

@dataclass
class StudentSubmission:
    name: str
    email: str
    login: str
    questions: dict = field(default_factory=dict)
    entregou: int = 0
    atrasou: int = 0
    formatacao: int = 0
    copia: int = 0
    nota_total: str = ''
    comentario: str = ''
     
    def to_list(self, num_questions: int):
        try:
            question_scores = [self.questions.get(f"q{i+1}", '') for i in range(num_questions)]
            return [self.name, self.email, self.login] + question_scores + [
                self.entregou, self.atrasou, self.formatacao, self.copia, self.nota_total, self.comentario
            ]
        except Exception as e:
            log_error(f"Erro ao converter student {self.login} para lista: {e}")
            return []

    def add_comment(self, text):
        try:
            if text and text not in self.comentario:
                if self.comentario:
                    self.comentario += f"\n- {text}"
                else:
                    self.comentario = f"- {text}"
        except Exception as e:
            log_error(f"Erro ao adicionar comentário para {self.login}: {e}")

    def update_field(self, field, value):
        try:
            if hasattr(self, field):
                setattr(self, field, value)
            elif field.startswith('q') and field[1:].isdigit():
                self.questions[field] = value
            else:
                log_error(f"Campo '{field}' não encontrado para o aluno {self.login}")
        except Exception as e:
            log_error(f"Erro ao atualizar campo '{field}' para {self.login}: {e}")

def save_students_to_json(student_list, path):
    try:
        data = []
        for student in student_list:
            d = asdict(student)
            q_flat = d.pop("questions", {})
            d.update(q_flat) 
            data.append(d)

        with open(path, 'w', encoding='utf-8') as file:
            json.dump(data, file, ensure_ascii=False, indent=4)
        log_info(f"Lista de alunos salva com sucesso em {path}")
    except Exception as e:
        log_error(f"Erro ao salvar alunos em {path}: {e}")

def load_students_from_json(path):
    students = []
    try:
        with open(path, 'r', encoding='utf-8') as file:
            data_list = json.load(file)
            for data in data_list:
                questions = {k: data.pop(k) for k in list(data.keys()) if k.startswith('q')}
                student = StudentSubmission(**data, questions=questions)
                students.append(student)
        log_info(f"Lista de alunos carregada com sucesso de {path}")
    except Exception as e:
        log_error(f"Erro ao carregar alunos de {path}: {e}")
    return students
