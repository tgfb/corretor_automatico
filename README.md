# Corretor Automático de Listas de Exercicios

Esta aplicação acessa uma turma do Google Classroom, lista as atividades dos alunos, baixa o código submetido para a atividade escolhida, verifica a formatação, verifica cópia e verifica se o código executa corretamente.

## Como Usar

## Pré-requisitos

Esta aplicação depende das [APIs do Google](https://developers.google.com/workspace/guides/get-started). É necessário seguir os passos do [Quick Start Guide python](https://developers.google.com/docs/api/quickstart/python) para criar o arquivo `credentials.json` contendo os seguintes escopos:

```bash
    "https://www.googleapis.com/auth/classroom.student-submissions.students.readonly"
    "https://www.googleapis.com/auth/classroom.profile.emails"
    "https://www.googleapis.com/auth/classroom.rosters.readonly"
    "https://www.googleapis.com/auth/classroom.courses.readonly"
    "https://www.googleapis.com/auth/drive"
    "https://www.googleapis.com/auth/spreadsheets"
```

- Python 3.10+ (ver `requirements.txt` para dependências Python)
- Java 11 ou superior instalado e acessível no PATH (`java -version`)
- Arquivo `jplag-6.1.0-jar-with-dependencies.jar` baixado manualmente
  e colocado em `app/infrastructure/external_tools/`

Para usar esta aplicação, é necessário instalar as bibliotecas python listadas no arquivo `requirements.txt`:

```bash
pip3 install -r requirements.txt
```

Instale o UnRAR de acordo com o seu sistema operacional:

#Linux 
```bash
sudo apt-get install unrar
```

#MacOS
```bash
brew install unrar
```

#Windows
https://www.rarlab.com/rar_add.htm

### Execução do script

Execute o script via linha de comando:

```bash
python3 corretor_automatico.py 
```

### Executar o `main` que utiliza o JPlag

Para executar o `main` que utiliza o JPlag, siga os passos abaixo:

1. Faça o download do arquivo `plag-6.1.0-jar-with-dependencies.jar` na página oficial do JPlag:  
   [https://github.com/jplag/JPlag/releases](https://github.com/jplag/JPlag/releases)

2. Mova o arquivo baixado para a pasta `infrastructure/externaltools` do projeto.

3. Execute o script principal com o comando:

   ```bash
   python main.py
