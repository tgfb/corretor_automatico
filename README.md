# Corretor Automático de Listas de Exercicios

Ferramenta para professores corrigirem automaticamente listas de exercícios de programação integrada ao Google Classroom, com verificação de formatação, organização dos arquivos, detecção de plágio, estruturando todo o resultado da submissão em planilhas do Google Sheets. Também é possível incluir as notas da plataforma do Beecrowd.

## Funcionalidades

🏫 Integração com Google Classroom — acessa turmas, atividades e submissões dos alunos automaticamente
📥 Download automático — baixa os códigos submetidos para a atividade escolhida
🗂️ Organização das atividades — organiza todas as pastas deixando os arquivos prontos para execução
🎨 Verificação de formatação — checa se o código segue as convenções exigidas e detecta arquivos enviados vazios
🔍 Detecção de plágio — utiliza JPlag e MOSS (Stanford) para identificar similaridade entre submissões
🐝 Integração com Beecrowd — exporta o resultado da avaliação da plataforma, adicionando na planilha a pontuação de cada aluno
📊 Exportação de resultados — salva as notas e relatórios diretamente no Google Sheets

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
│   ├── download_main.py         # Entrada para download das submissões
│   ├── jplag_main.py            # Entrada para detecção de plágio com JPlag
│   ├── moss_main.py             # Entrada para detecção de plágio com MOSS
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

Coloque o arquivo credentials.json na raiz do projeto.

6. Configure o JPlag

Para executar o `main` que utiliza o JPlag, siga os passos abaixo:

- Faça o download do arquivo `plag-6.1.0-jar-with-dependencies.jar` na página oficial do JPlag:  
   [https://github.com/jplag/JPlag/releases](https://github.com/jplag/JPlag/releases)
- Mova o arquivo baixado para a pasta `infrastructure/externaltools` do projeto.

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


Execute o script via linha de comando:

## Preparativos para a execurção

```bash
python3 corretor_automatico.py 
```


