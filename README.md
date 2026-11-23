# Sistema Casa Vida

Sistema web leve para cadastro, consulta e atualização dos dados dos assistidos do **Instituto Casa Vida**, desenvolvido como projeto de extensão universitário. Feito com **Flask** e **SQLite**, para rodar localmente em um computador de hardware modesto, sem depender de servidor de banco de dados ou de internet.

> **Status:** funcional para uso local na instituição. As funcionalidades marcadas com `[x]` estão implementadas.

---

## Sobre o projeto

O Instituto Casa Vida é uma Organização da Sociedade Civil de Juiz de Fora (MG) que oferece apoio gratuito a pacientes oncológicos e seus familiares. O **Projeto Casa Vida** reúne estudantes de Sistemas de Informação, Engenharia de Software, Marketing e Administração para ajudar a instituição com organização, tecnologia e comunicação.

Este sistema dá continuidade ao trabalho iniciado com a planilha no Google Sheets, que substituiu os prontuários em papel. A proposta agora é oferecer uma ferramenta dedicada, mais segura e adequada à rotina da equipe.

## Objetivos

- Facilitar o cadastro, a consulta e a atualização dos dados dos pacientes pelos responsáveis da instituição.
- Funcionar bem em um computador antigo (processador de 2ª geração, sem SSD).
- Proteger os dados, que são sensíveis, com execução estritamente local (`127.0.0.1`) e rotina de backup.
- Servir de base para as próximas etapas do projeto (por exemplo, a organização dos documentos recebidos por e-mail).

## Funcionalidades

- [x] Acesso local direto na página **Assistidos e Prontuários** (sem tela de login ou gerenciamento de usuários)
- [x] Cadastro, edição e visualização do prontuário completo de pacientes (incluindo histórico de atendimentos)
- [x] Consulta com paginação e busca filtrada por coluna da tabela (Todas as colunas, Prontuário, Nome do Assistido, CPF, Diagnóstico Oncológico, Telefone / Contato, Bairro / Cidade e Status)
- [x] Importação e exportação de dados (CSV)
- [x] Geração, listagem e download de backups do banco de dados
- [x] Sincronização sob demanda com o Google Sheets via botão **Sincronizar Google Sheets** na página principal

## Tecnologias

| Camada | Tecnologia | Motivo |
|---|---|---|
| Back-end | Python + Flask | Leve, simples e flexível |
| Banco de dados | SQLite | Um único arquivo, sem servidor, backup simples |
| Servidor de produção | Waitress | Puro Python, leve e estável no Windows |
| Front-end | HTML, CSS e JavaScript simples | Sem etapa de build, baixo consumo |

## Requisitos

- Windows (versão utilizada na máquina da instituição)
- Python 3.x compatível com a versão do Windows instalada
- Navegador (Microsoft Edge ou Google Chrome)

## Estrutura do projeto

```
sistemacasavida/
├── app/
│   ├── __init__.py        # criação da aplicação Flask (create_app)
│   ├── backup.py          # geração, listagem e download de backups
│   ├── db.py              # conexão, inicialização do banco e auditoria
│   ├── pacientes.py       # rotas, importação/exportação CSV e regras de pacientes
│   ├── sheets_sync.py     # importação e upsert via CSV do Google Sheets
│   ├── templates/         # páginas HTML
│   └── static/            # CSS, JS e imagens
├── data/                  # banco SQLite e chave secreta (não vão para o Git)
├── backups/               # cópias do banco (não vão para o Git)
├── .env.example           # modelo de variáveis de ambiente para o Google Sheets
├── schema.sql             # estrutura das tabelas
├── config.py              # configurações e caminhos da aplicação
├── run.py                 # inicia o servidor (Waitress) e abre o navegador
├── iniciar.bat            # atalho para abrir o sistema no Windows
├── test_app.py            # testes automatizados
├── requirements.txt       # dependências
└── README.md
```

## Instalação

```bash
# 1. Clonar o repositório
git clone https://github.com/icaro193593/sistemacasavida.git
cd sistemacasavida

# 2. Criar e ativar o ambiente virtual
python -m venv venv
venv\Scripts\activate

# 3. Instalar as dependências
pip install -r requirements.txt

# 4. (Opcional) Configurar a sincronização com o Google Sheets
copy .env.example .env
```

Não é necessário executar comandos manuais para criar o banco de dados. Ao iniciar a aplicação pela primeira vez, o sistema executa automaticamente `db.init_db()` e cria o banco SQLite em `data/casa_vida.db` a partir do `schema.sql`.

O sistema não possui tela de login ou cadastro de usuários: ao acessar `http://127.0.0.1:5000`, ele abre diretamente na página **Assistidos e Prontuários**. Caso queira habilitar a sincronização com o Google Sheets, copie `.env.example` para `.env` e preencha as variáveis correspondentes.

## Como executar

Com o ambiente virtual ativado (`venv\Scripts\activate`):

**Para desenvolvimento (com recarregamento automático e modo debug):**

```bash
flask --app app run --debug
```

**Para uso na instituição (modo leve, com Waitress):**

```bash
python run.py
```

O `run.py` inicia o sistema com o servidor **Waitress** escutando apenas na própria máquina (`127.0.0.1:5000`), com fallback para o servidor embutido do Flask caso o Waitress não esteja instalado, e abre o navegador automaticamente (exceto quando `FLASK_ENV=development`):

```python
if os.environ.get("FLASK_ENV") != "development":
    t = threading.Thread(target=abrir_navegador, args=(URL,), daemon=True)
    t.start()

try:
    from waitress import serve
    print(f"[INFO] Servidor Waitress ativo.")
    serve(app, host=HOST, port=PORT, threads=6)
except ImportError:
    print("[AVISO] Executando via servidor embutido do Flask...")
    app.run(host=HOST, port=PORT, debug=False)
```

Caso o navegador não abra automaticamente, acesse `http://127.0.0.1:5000`.

### Atalho com duplo clique

O arquivo `iniciar.bat` usa o Python do ambiente virtual `venv` (se existir) para executar `run.py`, que inicia o servidor e abre o sistema no navegador padrão:

```bat
@echo off
title Sistema Casa Vida
cd /d "%~dp0"

if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe run.py
) else (
    python run.py
)
```

*(O script também exibe mensagens de status no terminal e pausa caso ocorra algum erro na inicialização.)*

Crie um atalho para esse arquivo na área de trabalho.

## Configuração

As configurações ficam centralizadas em `config.py`, que também carrega automaticamente as variáveis definidas em um arquivo `.env` na raiz do projeto (sem dependências externas). Na primeira execução, os diretórios `data/` e `backups/` são criados automaticamente e uma chave secreta aleatória é gerada e salva em `data/.secret_key` (que **não** deve ser enviada ao Git):

| Constante / Configuração | Descrição |
|---|---|
| `DATABASE_PATH` (`Config.DATABASE`) | Caminho do arquivo SQLite (`data/casa_vida.db`) |
| `BACKUPS_DIR` | Pasta onde ficam os backups (`backups/`) |
| `SECRET_KEY_FILE` (`Config.SECRET_KEY`) | Arquivo local com a chave secreta das sessões (`data/.secret_key`) |

### Variáveis de ambiente (`.env`)

Para habilitar a sincronização com o Google Sheets, copie `.env.example` para `.env` e configure:

| Variável | Padrão | Descrição |
|---|---|---|
| `GOOGLE_SHEETS_CSV_URL` | `""` | **(Opção 1 — Recomendada)** URL CSV publicada na web (*Arquivo > Compartilhar > Publicar na Web* em formato `.csv`). Tem prioridade sobre ID/GID quando preenchida. |
| `GOOGLE_SHEETS_ID` | `""` | **(Opção 2)** ID da planilha na URL do Google Sheets (trecho entre `/d/` e `/edit`), usada para planilhas compartilhadas como leitura. |
| `GOOGLE_SHEETS_GID` | `0` | GID da aba desejada na planilha (usado em conjunto com `GOOGLE_SHEETS_ID`). |
| `GOOGLE_SHEETS_TIMEOUT` | `15` | Tempo limite, em segundos, das requisições HTTP ao Google Sheets. |

## Backup

O banco é um único arquivo. Faça cópias periódicas para a pasta `backups/` e, de preferência, para um pendrive ou para a nuvem. O objetivo é que a instituição nunca perca os dados, como já aconteceu uma vez com o computador.

## Segurança e LGPD

O sistema trata **dados pessoais sensíveis (dados de saúde)**, que têm proteção especial na Lei Geral de Proteção de Dados (LGPD). Por isso:

- Mantenha o servidor acessível somente na própria máquina (`127.0.0.1`), restringindo o uso físico do computador à equipe autorizada.
- Registre apenas os dados necessários para o atendimento.
- Nunca envie o arquivo `.env`, o banco de dados, backups, planilhas reais ou chaves ao repositório do Git. Certifique-se de mantê-los listados no `.gitignore`.
- Use dados fictícios para testes e demonstrações.

## Sincronização com o Google Sheets

O banco **SQLite** (`data/casa_vida.db`) continua sendo a fonte primária local dos dados do sistema. Quando configurada no `.env`, a sincronização funciona sob demanda a partir do botão **Sincronizar Google Sheets** na página principal (**Assistidos e Prontuários**):

1. O módulo `app/sheets_sync.py` resolve a URL CSV da planilha (priorizando `GOOGLE_SHEETS_CSV_URL` ou montando a URL de exportação com `GOOGLE_SHEETS_ID` e `GOOGLE_SHEETS_GID`) e baixa os dados usando apenas a biblioteca padrão do Python.
2. Os cabeçalhos da planilha são mapeados automaticamente para os campos da tabela `pacientes`.
3. O sistema executa um **upsert** no SQLite: registros já existentes são identificados por **Prontuário** ou **CPF** (ou por nome, caso ambos estejam ausentes) e têm seus campos atualizados; novos registros são inseridos com geração automática do número de prontuário quando não informado.

## Próximos passos

- Planejamento da organização automática dos documentos recebidos por e-mail, com banco de dados não relacional (apenas planejamento nesta etapa).
- Otimização do Windows da máquina da instituição, tratada em um script separado.

## Equipe

Projeto Casa Vida, desenvolvido por estudantes de Sistemas de Informação, Engenharia de Software, Marketing e Administração:

Arthur José Barbosa Medeiros, Bernardo Vizeu de Miranda, Ícaro de Alencar Araripe Andrade, Luiz Gouvêa, Enzo Dutra, João Vitor Faião, Gustavo Gavioli, Samuel Guimarães, Davi Grossi, Matheus Steiner Miletto e Pedro Lucas Ventura Meyer Goulart

## Licença

A definir...
