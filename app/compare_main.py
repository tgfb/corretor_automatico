import os
import numpy as np
from pycparser import c_parser, c_ast
import re
import math
import time
from concurrent.futures import ProcessPoolExecutor
from collections import Counter
from itertools import combinations
import json
import sys

# -------------------------------
# Parser global (evita recriar)
# -------------------------------
PARSER = c_parser.CParser()

def gerar_ast(code: str):
    try:
        return PARSER.parse(code)
    except Exception as e:
        return None

# -------------------------------
# AST Signature
# -------------------------------
class ASTSignature(c_ast.NodeVisitor):
    """Cria uma assinatura normalizada da AST"""
    def __init__(self):
        self.tokens = []

    def generic_visit(self, node):
        token = type(node).__name__

        if token == "ID":
            self.tokens.append("VAR")
        elif token == "FuncCall":
            self.tokens.append("FUNC")
        elif token == "Constant":
            if node.type == "int":
                self.tokens.append("CONST_INT")
            elif node.type == "float":
                self.tokens.append("CONST_FLOAT")
            elif node.type == "char":
                self.tokens.append("CONST_CHAR")
            elif node.type == "double":
                self.tokens.append("CONST_DOUBLE")
            else:
                self.tokens.append("CONST")
        elif token in ["BinaryOp", "UnaryOp"]:
            self.tokens.append(node.op)
        else:
            self.tokens.append(token)

        super().generic_visit(node)

def extrair_assinatura(ast):
    visitor = ASTSignature()
    visitor.visit(ast)
    return visitor.tokens

# -------------------------------
# Funções por função
# -------------------------------
class ASTFunctionVisitor(c_ast.NodeVisitor):
    def __init__(self):
        self.functions = {}

    def visit_FuncDef(self, node):
        sig_visitor = ASTSignature()
        sig_visitor.visit(node)
        nome_func = getattr(node.decl, "name", "FUNC")
        self.functions[nome_func] = sig_visitor.tokens
        self.generic_visit(node)

# -------------------------------
# Similaridade
# -------------------------------
TOKEN_PESOS = {
    "IF": 2.0,
    "LOOP": 2.0,
    "FUNC": 1.5,
    "VAR": 0.5,
    "CONST_INT": 0.5,
    "CONST_STR": 0.5,
}

def jaccard_similarity(commom_tokens, all_tokens):
    return len(commom_tokens) / len(all_tokens)

def weighted_cosine_similarity(seq1, seq2, all_tokens):
    idx = {t: i for i, t in enumerate(all_tokens)}
    v1 = np.zeros(len(all_tokens))
    v2 = np.zeros(len(all_tokens))
    for t in seq1:
        v1[idx[t]] += TOKEN_PESOS.get(t, 1.0)
    for t in seq2:
        v2[idx[t]] += TOKEN_PESOS.get(t, 1.0)
    dot = np.dot(v1, v2)
    norm = np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-9
    return dot / norm

def ngram_similarity(seq1, seq2, n=4):
    if len(seq1) < n or len(seq2) < n:
        return 0.0
    def ngrams(seq, n):
        return [" ".join(seq[i:i+n]) for i in range(len(seq) - n + 1)]
    c1, c2 = Counter(ngrams(seq1, n)), Counter(ngrams(seq2, n))
    all_keys = set(c1) | set(c2)
    dot = sum(c1[k] * c2[k] for k in all_keys)
    norm1 = math.sqrt(sum(v*v for v in c1.values()))
    norm2 = math.sqrt(sum(v*v for v in c2.values()))
    return dot / (norm1 * norm2 + 1e-9)

def similaridade_combinada(seq1, seq2):
    if len(seq1) == 0 or len(seq2) == 0:
        return 0.0
    if len(seq1) < 0.5 * len(seq2) or len(seq1) > 2 * len(seq2):
        return 0.0
    inter = len(set(seq1) & set(seq2))
    if inter < 2:
        return 0.0
    seq1_set, seq2_set = set(seq1), set(seq2)
    all_tokens = seq1_set | seq2_set
    commom_tokens = seq1_set & seq2_set
    jacc = jaccard_similarity(commom_tokens, all_tokens)
    cos = weighted_cosine_similarity(seq1, seq2, all_tokens)
    ngram = ngram_similarity(seq1, seq2, n=4)
    return 0.7 * ngram + 0.1 * cos + 0.2 * jacc

def similaridade_funcoes(funcoes1, funcoes2):
    comuns = set(funcoes1) & set(funcoes2)
    if not comuns:
        return 0.0
    similaridades = [similaridade_combinada(funcoes1[f], funcoes2[f]) for f in comuns]
    return sum(similaridades) / len(similaridades)


# -------------------------------
# Utilitárias
# -------------------------------
RE_COMENTARIOS = re.compile(r"/\*.*?\*/", re.DOTALL)
RE_BARRA = re.compile(r"//.*")

def remover_comentarios(codigo):
    return RE_COMENTARIOS.sub("", RE_BARRA.sub("", codigo))

def remover_hashtag(codigo):
    return "\n".join(linha for linha in codigo.splitlines() if not linha.strip().startswith("#"))

# -------------------------------
# Classes
# -------------------------------
class Questao:
    def __init__(self, numero, assinatura, funcoes):
        self.numero = numero
        self.assinatura = assinatura
        self.funcoes = funcoes

class Aluno:
    def __init__(self, email):
        self.email = email
        self.questoes = [None for _ in range(4)]
        self.comentarios = []

    def addQuestao(self, questao):
        self.questoes[questao.numero - 1] = questao

# -------------------------------
# Carregar dados
# -------------------------------
def carregar_questoes(lista):
    alunos = []
    base = os.path.dirname(__file__)          
    raiz = os.path.abspath(os.path.join(base, "..")) 
    downloads = os.path.join(raiz, "Downloads", lista, "submissions")
    for aluno in os.listdir(downloads):
        caminho_aluno = os.path.join(downloads, aluno)
        if not os.path.isdir(caminho_aluno):
            continue
        aluno_obj = Aluno(aluno)
        for arquivo in os.listdir(caminho_aluno):
            if arquivo.endswith(".c"):
                caminho_arquivo = os.path.join(caminho_aluno, arquivo)
                try:
                    with open(caminho_arquivo, "r", encoding="utf-8") as f:
                        codigo = f.read()
                except:
                    continue
                if not codigo.strip():
                    continue
                codigo_limpo = remover_hashtag(remover_comentarios(codigo))
                ast = gerar_ast(codigo_limpo)
                if not ast:
                    continue
                assinatura = extrair_assinatura(ast)
                func_visitor = ASTFunctionVisitor()
                func_visitor.visit(ast)
                q_numero = int(arquivo.split("_")[0][1:])
                questao = Questao(q_numero, assinatura, func_visitor.functions)
                aluno_obj.addQuestao(questao)
        alunos.append(aluno_obj)
    return alunos

# -------------------------------
# Otimização: Comparação em chunks
# -------------------------------
def comparar_par_chunk(chunk, alunos_serializavel, threshold):
    resultados = []
    for i, j in chunk:
        aluno_a, aluno_b = alunos_serializavel[i], alunos_serializavel[j]
        for k in range(4):
            qa, qb = aluno_a["questoes"][k], aluno_b["questoes"][k]
            if not qa or not qb:
                continue
            sim_arquivo = similaridade_combinada(qa["assinatura"], qb["assinatura"])
            sim_funcoes = similaridade_funcoes(qa["funcoes"], qb["funcoes"])
            sim_final = round((sim_arquivo + sim_funcoes) / 2, 4)
            if sim_final >= threshold:
                resultados.append((i, j, k, sim_final))
    return resultados

# -------------------------------
# Comparar todas as questões
# -------------------------------
def comparar_questoes(alunos, threshold=0.85):
    # Serializar alunos para envio leve
    alunos_serializavel = [
        {
            "email": a.email,
            "questoes": [
                {
                    "assinatura": q.assinatura,
                    "funcoes": q.funcoes
                } if q else None for q in a.questoes
            ]
        } for a in alunos
    ]

    pares = list(combinations(range(len(alunos)), 2))
    chunk_size = math.ceil(len(pares) / os.cpu_count())  # ajustável
    resultados = []

    with ProcessPoolExecutor() as executor:
        chunks = [pares[i:i+chunk_size] for i in range(0, len(pares), chunk_size)]
        futures = [executor.submit(comparar_par_chunk, c, alunos_serializavel, threshold) for c in chunks]
        for f in futures:
            resultados.extend(f.result())

    # Adicionar comentários finais
    for i, j, k, sim_final in resultados:
        aluno_a, aluno_b = alunos[i], alunos[j]
        msg = f"SIMILARIDADE q{k + 1}_{aluno_b.email} {sim_final * 100:.2f}%"
        aluno_a.comentarios.append(msg)
        aluno_b.comentarios.append(msg.replace(aluno_b.email, aluno_a.email))

# -------------------------------
# Salvar
# -------------------------------

def salvar_json(lista: str, alunos: list[Aluno]):
    base = os.path.dirname(__file__)          
    raiz = os.path.abspath(os.path.join(base, "..")) 
    downloads = os.path.join(raiz, "Downloads", lista)

    arquivos = ["students_turmaA.json", "students_turmaB.json", "students_turmaC.json"]
    dados = {}

    for arq in arquivos:
        caminho = os.path.join(downloads, arq)
        with open(caminho, "r", encoding="utf-8") as f:
            lista_alunos = json.load(f)
            dados[arq] = {aluno["login"]: aluno for aluno in lista_alunos}

    for aluno in alunos:
        if len(aluno.comentarios) == 0:
            continue
        for arq in arquivos:
            if aluno.email in dados[arq]:
                if not dados[arq][aluno.email]["copia"]:
                    dados[arq][aluno.email]["comentario"] += "\n" + "\n".join(aluno.comentarios)
                    dados[arq][aluno.email]["copia"] = 1
                break

    for arq in arquivos:
        caminho = os.path.join(downloads, arq)
        with open(caminho, "w", encoding="utf-8") as f:
            lista_alunos = [dados[arq][key] for key in dados[arq].keys()]
            json.dump(lista_alunos, f, indent=4, ensure_ascii=False)
# -------------------------------
# Main
# -------------------------------
def main():
    _, lista_nome, dificuldade = sys.argv
    dificuldade = int(dificuldade)
    start_time = time.time()
    alunos = carregar_questoes(lista_nome)
    print(f"Tempo de carregamento: {(time.time() - start_time):.2f}s")

    threshold = 1 - (dificuldade - 1) / 20

    start_time = time.time()
    comparar_questoes(alunos, threshold)
    print(f"Tempo de comparação: {(time.time() - start_time):.2f}s")

    start_time = time.time()
    salvar_json(lista_nome, alunos)
    print(f"Tempo de salvar: {(time.time() - start_time):.2f}s")

if __name__ == "__main__":
    main()
