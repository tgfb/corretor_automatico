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

### Esse projeto utiliza o **JPlag**

Para executar o `main` que utiliza o JPlag, siga os passos abaixo:

1. Faça o download do arquivo `plag-6.1.0-jar-with-dependencies.jar` na página oficial do JPlag:  
   [https://github.com/jplag/JPlag/releases](https://github.com/jplag/JPlag/releases)

2. Mova o arquivo baixado para a pasta `infrastructure/externaltools` do projeto.


   
### Este projeto utiliza o **MOSS (Measure of Software Similarity)**, da Universidade de Stanford, para análise de similaridade em códigos de programação submetidos por alunos.


## Requisitos

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

## Conta no MOSS
O professor/administrador deve solicitar credenciais no [site oficial do MOSS](https://theory.stanford.edu/~aiken/moss/).
O time do MOSS enviará o script `moss.pl` por e-mail.

## Estrutura do Projeto

Coloque o arquivo `moss.pl` dentro da pasta `infrastructure/externaltools` do projeto.

**Importante:** 
O arquivo `moss.pl` **não é versionado neste repositório**. Cada usuário deve obtê-lo diretamente do MOSS, pois não pode ser redistribuído publicamente.

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



