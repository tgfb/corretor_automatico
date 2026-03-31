# Corretor Automático de Listas de Exercicios

Ferramenta para professores corrigirem automaticamente listas de exercícios de programação integrada ao Google Classroom, com verificação de formatação, organização dos arquivos, detecção de plágio, calculo das notas, estruturando todo o resultado da submissão em planilhas do Google Sheets. 

## Funcionalidades

- Integração com Google Classroom — acessa turmas, atividades e submissões dos alunos automaticamente
- Download automático — baixa os códigos submetidos para a atividade escolhida
- Organização das atividades — organiza todas as pastas deixando os arquivos prontos para execução
- Verificação de formatação — checa se o código segue as convenções exigidas e detecta arquivos enviados vazios
- Detecção de plágio — utiliza JPlag e MOSS (Stanford) ou algorítmo local para identificar similaridade entre submissões
- Integração com Beecrowd — exporta o resultado da avaliação da plataforma, adicionando na planilha a pontuação de cada aluno
- Exportação de resultados — salva as notas e relatórios diretamente no Google Sheets
- Interface gráfica (UI) - Executar scripts de uma forma simplificada

## Estrutura do projeto 

```bash
corretor_automatico/
├── app/
│   ├── core/
│   │   └── models/              # Modelos de dados da aplicação
│   ├── infrastructure/
│   │   └── external_tools/      # Coloque aqui o jplag.jar e o moss.pl
│   ├── input/                   # Arquivos de entrada/configuração
│   ├── secrets/                 # Credenciais (credentials.json, token, etc.)
│   ├── services/                # Lógica de negócio e integrações
│   ├── utils/                   # Funções utilitárias
│   ├── __init__.py
│   ├── beecrowd_main.py         # Entrada para correção via Beecrowd
│   ├── graphical_main.py        # Entrada para interface gráfica
│   ├── download_main.py         # Entrada para download das submissões
│   ├── jplag_main.py            # Entrada para detecção de plágio com JPlag
│   ├── moss_main.py             # Entrada para detecção de plágio com MOSS
│   ├── compare_main.py          # Entrada para detecção de plágio (processamento local)
│   └── spreadsheet_main.py      # Entrada para exportação no Google Sheets
├── old_app/
│   └── old_script/              # Versão legada do script
├── .gitignore
├── LICENSE
├── README.md
└── requirements.txt
```

## Pré-requisitos

| Requisito | Versão mínima | Observação |
|---|---|---|
| Python | 3.10+ | Ver `requirements.txt` |
| Java | 11+ | Deve estar acessível no PATH (`java -version`) |
| Perl | 5+ | Necessário para o MOSS |
| UnRAR | — | Instalação detalhada abaixo |
| `credentials.json` | — | Credenciais da API do Google |
| `jplag-6.1.0-jar-with-dependencies.jar` | 6.1.0 | Download manual no GitHub do JPlag |
| `moss.pl` | — | Solicitado por e-mail ao time do MOSS/Stanford |


## Instalação

1. Clone o repositório

```bash
git clone https://github.com/tgfb/corretor_automatico.git
cd corretor_automatico
```

2. Crie e ative um ambiente virtual
   
```bash
python3 -m venv venv
```
 - Linux/macOS:
   
```bash
source venv/bin/activate
```

- Windowns
```bash
venv\Scripts\activate
```

3. Instale as dependências Python
```bash
pip3 install -r requirements.txt
```

4. Instale o UnRAR
 - Linux:
   
```bash
sudo apt-get install unrar
```

- MacOS
```bash
brew install unrar
```
Windows:
Baixe e instale em: https://www.rarlab.com/rar_add.htm

5. Configure as credenciais do Google

Esta aplicação depende das [APIs do Google](https://developers.google.com/workspace/guides/get-started). É necessário seguir os passos do [Quick Start Guide python](https://developers.google.com/docs/api/quickstart/python) para criar o arquivo `credentials.json` contendo os seguintes escopos:

```bash
    "https://www.googleapis.com/auth/classroom.student-submissions.students.readonly"
    "https://www.googleapis.com/auth/classroom.profile.emails"
    "https://www.googleapis.com/auth/classroom.rosters.readonly"
    "https://www.googleapis.com/auth/classroom.courses.readonly"
    "https://www.googleapis.com/auth/drive"
    "https://www.googleapis.com/auth/spreadsheets"
```

---
6. Configure o JPlag

Para executar o `main` que utiliza o JPlag, siga os passos abaixo:

- Faça o download do arquivo `plag-6.1.0-jar-with-dependencies.jar` na página oficial do JPlag:  
   [https://github.com/jplag/JPlag/releases](https://github.com/jplag/JPlag/releases)
- Mova o arquivo baixado para a pasta `infrastructure/externaltools` do projeto.

---

7. Configure o MOSS (Measure of Software Similarity)**, da Universidade de Stanford, para análise de similaridade em códigos de programação submetidos por alunos.

Solicite suas credenciais no site oficial do MOSS — o script moss.pl será enviado por e-mail
Mova o arquivo moss.pl para app/infrastructure/external_tools/

⚠️ O arquivo moss.pl não está versionado neste repositório e não pode ser redistribuído publicamente. Cada usuário deve obtê-lo diretamente do MOSS.

## Conta no MOSS
O professor/administrador deve solicitar credenciais no [site oficial do MOSS](https://theory.stanford.edu/~aiken/moss/).
O time do MOSS enviará o script `moss.pl` por e-mail.

## Instale o Perl (caso necessário):

- **Perl instalado**
  - **Windows**: instale o [Strawberry Perl](http://strawberryperl.com/).
  - **macOS/Linux**: o Perl já vem instalado por padrão na maioria das distribuições. Verifique com:
```bash
perl -v
```
Se não estiver instalado, utilize o gerenciador de pacotes da sua distribuição:
```bash
# macOS
brew install perl

# Linux (Debian/Ubuntu)
sudo apt-get install perl

# Linux (Fedora/RHEL)
sudo dnf install perl
```

## Testando a Instalação

Depois de configurar, teste se o `perl` e o `moss.pl` estão funcionando:

```bash
perl app/infrastructure/external_tools/moss.pl -h
 ```
Isso deve exibir a ajuda do MOSS.

Você também pode rodar um teste com dois arquivos:

```bash

perl app/infrastructure/external_tools/moss.pl -l c -c "teste" path/to/file1.c path/to/file2.c
```
Se estiver tudo certo, o MOSS retornará um link como: http://moss.stanford.edu/results/123456789

---

## 🔑 Configuração das Credenciais da API do Google
 
Antes de executar o script, coloque os arquivos de credenciais da API do Google dentro da pasta `app/secrets/`:
 
```
app/secrets/
├── credentials.json      # Credenciais do projeto no Google Cloud Console
└── secrets.json          # Chaves de acesso da API
```
 
**Como obter esses arquivos:**
 
1. Acesse o [Google Cloud Console](https://console.cloud.google.com/)
2. Crie um projeto e ative as APIs necessárias (Classroom, Drive, Sheets)
3. Siga o [Quick Start Guide Python](https://developers.google.com/docs/api/quickstart/python) para gerar o `credentials.json` com os escopos:
 
```
https://www.googleapis.com/auth/classroom.student-submissions.students.readonly
https://www.googleapis.com/auth/classroom.profile.emails
https://www.googleapis.com/auth/classroom.rosters.readonly
https://www.googleapis.com/auth/classroom.courses.readonly
https://www.googleapis.com/auth/drive
https://www.googleapis.com/auth/spreadsheets
```
 
4. Mova os arquivos `credentials.json` e `secrets.json` para dentro de `app/secrets/`
 
> ⚠️ A pasta `secrets/` está no `.gitignore` e **nunca deve ser versionada**. Nunca suba esses arquivos para o GitHub.
 
---


## ⚙️ Configuração dos Arquivos de Entrada
 
Antes de executar qualquer script, é necessário preencher os arquivos de configuração dentro da pasta `app/input/`. Cada arquivo `.txt` deve conter apenas o ID correspondente, sem espaços ou quebras de linha extras.
 
---
 
### `folder_id.txt` — Pasta do Google Drive
 
ID da pasta do Google Drive onde as planilhas com os nomes dos alunos e notas serão salvas.
 
**Como encontrar o ID:**
 
```
https://drive.google.com/drive/folders/16gVVccYR8V_gJ31HV6S-BGKNpwkAN
                                        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                        copie esse trecho após o último /
```
 
Cole o ID no arquivo:
 
```
app/input/folder_id.txt
```
 
```
16gVVccYR8V_gJ31HV6S-BGKNpwkAN
```
 
---
 
### `sheet_id.txt` — Planilha principal do Google Sheets
 
ID da planilha do Google Sheets onde os resultados gerais serão exportados.
 
> ⚠️ **Importante:** o **título da aba** (ou da planilha) deve ser obrigatoriamente o **código do semestre que tem no título da turma do classroom**, no formato `2025.1` ou `2025.2`. O script usa esse nome para localizar e escrever os dados corretamente.
 
**Como encontrar o ID:**
 
```
https://docs.google.com/spreadsheets/d/1mHK0IyFzYMvX93tyCT5TokivSDn_vzv2A/edit
                                       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                       copie esse trecho entre o /d/ e o /edit
```

Cada planilha deve seguir o seguinte formato:
 
| Pontuação | Q | Beecrowd Number | Name | Questao 1 | Questao 2 | ... |
|---|---|---|---|---|---|---|
| 0.25 | 1 | 2167 | Queda do Motor | q1 | questao1 | ... |
| 0.25 | 2 | 1183 | Área acima da diagonal | q2 | questao2 | ... |
| 0.5 | 3 | 1582 | Teorema de Pitágoras | q3 | questao3 | ... |
| 0.5 | 4 | 1400 | Jogo Contando | q4 | questao4 | ... |
 
**Significado de cada coluna:**
 
- **Pontuação** — peso/valor daquela questão na nota final
- **Q** — número de questões que cada aluno deve entregar (define o total esperado de submissões)
> ⚠️ **Importante:** Os três campos abaixo não precisam ser obrigatoriamente preenchidos, porque são possíveis nomes que os alunos podem salvar os seus arquivos, e isso ajuda a identificar e ajudar na formatação para os arquivos serem salvos como q1_studentlogin.c

- **Beecrowd Number** — código do problema na plataforma Beecrowd
- **Name** — nome oficial do problema
- **Colunas seguintes** — possíveis nomes que o aluno pode ter dado ao arquivo da questão (ex: `q1`, `questao1`, `ex1`). O corretor usará esses nomes para identificar e **renomear o arquivo para o padrão definido**, por exemplo: `q1_login_do_aluno.c`
 
---
 
Cole o ID no arquivo:
 
```
app/input/sheet_id.txt
```
 
```
1mHK0IyFzYMvX93tyCT5TokivSDn_vzv2A
```
 
---
 
### `sheet_id_beecrowd.txt` — Planilhas de resultados do Beecrowd
 
IDs das planilhas geradas pelo Beecrowd com os resultados de cada turma. Caso haja mais de uma turma, cole um ID por linha:
 
```
app/input/sheet_id_beecrowd.txt
```
 
```
1mHK0IyFzYMvX93tyCT5TokivSDn_vzv2A
1mHK0IyFzYMvX93tyCT5TokivSDn_vzv2B
1mHK0IyFzYMvX93tyCT5TokivSDn_vzv2C
```
 
 
### `sheet_id_laudo.txt` — Planilha de alunos com laudo
 
ID da planilha do Google Sheets contendo a lista de todos os alunos que possuem laudo médico/acadêmico. O corretor utilizará essa informação durante a avaliação, marcando na planilha esses alunos.
 
Cole o ID em:
 
```
app/input/sheet_id_laudo.txt
```
 
---
 
> ✅ **Resumo rápido:** abra cada `.txt` dentro de `app/input/`, cole apenas o ID correspondente e salve. Feito isso, o script está pronto para ser executado.
 
---

## ▶️ Como Usar
 
O ponto de entrada principal para baixar e corrigir as submissões é o `download_main.py`. Ele recebe como argumento o **nome da lista** exatamente como está cadastrada na atividade no Google Classroom.
 
### Execução
 
```bash
cd app
python3 download_main.py "NOME DA LISTA"
```
 
**Exemplo:**
 
```bash
python3 download_main.py "LISTA 01"
```
 
> ⚠️ O nome da lista deve estar entre aspas e corresponder exatamente ao nome da atividade no Google Classroom.
 
---
 
### Outros scripts disponíveis
 
Cada funcionalidade também pode ser executada individualmente:
 
| Script | Comando | Descrição |
|---|---|---|
| `download_main.py` | `python3 download_main.py "LISTA 01"` | Baixa e organiza as submissões do Classroom |
| `jplag_main.py` | `python3 jplag_main.py "LISTA 01"` | Executa a detecção de plágio com JPlag |
| `moss_main.py` | `python3 moss_main.py "LISTA 01"` | Executa a detecção de plágio com MOSS |
| `compare_main.py` | `python3 compare_main.py` | Executa a detecção de plágio com algorítmo local |
| `spreadsheet_main.py` | `python3 spreadsheet_main.py "LISTA 01"` | Exporta os resultados para o Google Sheets |
| `beecrowd_main.py` | `python3 beecrowd_main.py "LISTA 01"` | Importa as notas do Beecrowd para a planilha |
| `graphical_main.py` | `python3 graphical_main.py` | Abre a interface gráfica para executar outros scripts |

## 📊 Integração com Google Sheets
 
O corretor exporta os resultados automaticamente para uma planilha no **Google Sheets**, criada dentro da pasta do Google Drive informada.
 
### Como configurar a pasta
 
Basta passar o **ID da pasta do Google Drive** onde a planilha deve ser criada. O ID está na URL da pasta:
 
```
https://drive.google.com/drive/folders/ESTE_E_O_ID_DA_PASTA
```
 
O script criará automaticamente a planilha dentro dessa pasta, e uma aba para cada lista na memsa planilha, não é necessário criar nada manualmente.
 
### O que a planilha contém
 
A planilha gerada inclui as seguintes informações por aluno:
 
### Colunas geradas
 
| Coluna | Descrição |
|---|---|
| **Nome do Aluno** | Nome completo conforme cadastrado no Classroom |
| **Email** | Email do aluno |
| **Student Login** | Login do aluno (usado para renomear os arquivos) |
| **Questão 1, 2, 3...** | Nota de cada questão, com o peso configurado na planilha do Beecrowd (ex: 0.25, 0.5) |
| **Entrega?** | Indica se o aluno entregou a atividade |
| **Atraso?** | Indica se a entrega foi feita após o prazo |
| **Formatação?** | Indica se o script não conseguiu corrigir a formatação ou se o arquivo estava com problema |
| **Cópia?** | Indica se foi detectada similaridade com a submissão de outro aluno (plágio) |
| **Nota Total** | Calculada automaticamente por fórmula dinâmica com base nas questões entregues e nos pesos |
| **Comentários** | Observações sobre a submissão do aluno (ex: erro de submissão, malware, spam) |
 
---
 
### Exemplo visual da planilha
 
```
| Aluno         | Q1 (0.25) | Q2 (0.25) | Q3 (0.5) | Q4 (0.5) | Entrega? | Atraso? | Formatação? | Cópia? | Nota Total | Comentários |
|---------------|-----------|-----------|----------|----------|----------|---------|-------------|--------|------------|-------------|
| João Silva    | 0.25      | 0.25      | 0.0      | 0.5      | 1        | 0       | 0           | 0      | 1.0        |             |
| Maria Souza   | 0.25      | 0.0       | 0.5      | 0.5      | 1        | 1       | 0           | 0      | 1.25       | Entrega com atraso |
| Pedro Lima    | 0.0       | 0.25      | 0.5      | 0.0      | 1        | 0       | 1           | 0      | 0.75       | Erro de formatação |
```
 
---
 
> 💡 **Dica:** certifique-se de que a conta Google usada nas credenciais tem **permissão de edição** na pasta do Drive indicada.
 
---


## 📄 Licença
 
Este projeto está licenciado sob a [Apache License 2.0](LICENSE).
 
---
 
## 🔗 Referências
 
- [JPlag — Detecção de Plágio](https://github.com/jplag/JPlag)
- [MOSS — Stanford University](https://theory.stanford.edu/~aiken/moss/)
- [Google Classroom API](https://developers.google.com/classroom)
- [Google Workspace Quick Start (Python)](https://developers.google.com/docs/api/quickstart/python)

