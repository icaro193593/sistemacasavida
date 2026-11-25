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
- [x] Planilha interativa de **Lista de Pacientes** com 13 colunas (`Prontuário`, `Nome`, `Endereço`, `Responsável 1`, `Telefone 1`, `Responsável 2`, `Telefone 2`, `Telefone 3`, `DN`, `ID`, `CPF`, `Obs`, `Carimbo de data/hora`), com ordenação por cabeçalho, reordenação de colunas por arrastar e redimensionamento de largura
- [x] Busca filtrada por coluna com operadores textuais e matemáticos
- [x] Cadastro individual, tela dedicada de edição/exclusão e **edição direta em lote na planilha** com modal de confirmação e diff das alterações
- [x] Importação e exportação para **CSV** sincronizada com filtros, ordenação e ordem das colunas
- [x] **Logs de auditoria** paginados com busca e filtro por ação (incluindo `Backup por E-mail`)
- [x] **Backups seguros** (`sqlite3.Connection.backup()` em modo `WAL`): geração manual, contagem de registros por backup, download, envio manual por e-mail (`.zip`), restauração da lista local ou por upload de `.db` / `.sqlite` / `.zip` e **backup automático semanal por e-mail** via Agendador de Tarefas do Windows (retenção automática dos últimos 8 backups semanais)
- [x] Sincronização sob demanda com o **Google Sheets** via botão **Sincronizar Google Sheets** (somente novos registros a partir da data de corte, sem sobrescrever edições locais nem reimportar excluídos)

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
│   ├── backup.py          # geração consistente (WAL), contagem, download, envio por e-mail e restauração de backups
│   ├── db.py              # conexão, inicialização do banco e auditoria
│   ├── logs.py            # visualização paginada, busca e filtro dos logs de auditoria
│   ├── pacientes.py       # rotas, planilha interativa, edição em lote, importação/exportação CSV e regras de pacientes
│   ├── sheets_sync.py     # importação append-only via CSV do Google Sheets a partir da data de corte
│   ├── templates/         # páginas HTML
│   └── static/            # CSS, JS e imagens (incluindo img/casa_vida.ico)
├── scripts/
│   ├── backup_semanal.py            # rotina de backup automático semanal com envio por e-mail e retenção
│   ├── instalar_sistema.ps1         # instala Python, venv, dependências, backup semanal e atalho
│   ├── instalar_tarefa_backup.ps1   # registra a tarefa semanal no Agendador de Tarefas do Windows
│   └── desinstalar_tarefa_backup.ps1 # remove a tarefa agendada de backup
├── data/                  # banco SQLite, chave secreta e log do backup semanal (não vão para o Git)
├── backups/               # cópias do banco (não vão para o Git)
├── .env.example           # modelo de variáveis de ambiente (Google Sheets e envio de backups por e-mail)
├── schema.sql             # estrutura das tabelas
├── config.py              # configurações e caminhos da aplicação
├── run.py                 # inicia o servidor (Waitress) e abre o navegador
├── iniciar.bat            # atalho para abrir o sistema no Windows (minimizado na barra de tarefas)
├── instalar.bat           # instalador automático de primeira execução no Windows
├── test_app.py            # testes automatizados
├── requirements.txt       # dependências
└── README.md
```

## Instalação

### Instalação rápida no Windows (recomendada)

1. Baixe e extraia o `.zip` do repositório (ou clone) na pasta definitiva (ex.: `C:\SistemaCasaVida`).
2. Coloque o arquivo `.env` preenchido na raiz da pasta *(ou preencha o `.env` gerado automaticamente após a instalação)*.
3. Dê **duplo clique em `instalar.bat`**: ele detecta/instala o Python 3 automaticamente (sem precisar de Administrador), cria o `venv`, instala o `requirements.txt`, registra o backup semanal no Agendador de Tarefas do Windows, cria o atalho **Sistema Casa Vida** na Área de Trabalho (minimizado e com o ícone `casa_vida.ico`) e já inicia o sistema no navegador.

### Instalação manual (desenvolvimento)

```bash
# 1. Clonar o repositório
git clone https://github.com/Matheussteiner1/sistemacasavida.git
cd sistemacasavida

# 2. Criar e ativar o ambiente virtual
python -m venv venv
venv\Scripts\activate

# 3. Instalar as dependências
pip install -r requirements.txt

# 4. (Opcional) Configurar a sincronização com o Google Sheets e o backup por e-mail
copy .env.example .env
```

Não é necessário executar comandos manuais para criar o banco de dados. Ao iniciar a aplicação pela primeira vez, o sistema executa automaticamente `db.init_db()` e cria o banco SQLite em `data/casa_vida.db` a partir do `schema.sql`.

O sistema não possui tela de login ou cadastro de usuários: ao acessar `http://127.0.0.1:5000`, ele abre diretamente na página **Assistidos e Prontuários**. Caso queira habilitar a sincronização com o Google Sheets ou o envio de backups por e-mail, copie `.env.example` para `.env` e preencha as variáveis correspondentes.

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

O arquivo `iniciar.bat` **minimiza a janela do CMD automaticamente** para a barra de tarefas, usa o Python do ambiente virtual `venv` (se existir) para executar `run.py`, mantém o servidor local ativo enquanto o sistema estiver em uso e abre o sistema no navegador padrão:

```bat
@echo off
if /i not "%~1"=="--minimized" if /i not "%~1"=="--no-min" (
    start "Sistema Casa Vida" /min cmd /c ""%~f0" --minimized"
    exit /b
)
title Sistema Casa Vida
cd /d "%~dp0"

if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe run.py
) else (
    python run.py
)
```

*(O script também exibe mensagens de status no terminal e, caso ocorra algum erro na inicialização, pausa para exibir o problema.)*

Crie um atalho para esse arquivo na área de trabalho (você pode definir `app/static/img/casa_vida.ico` como ícone do atalho). Para encerrar o sistema, basta abrir a janela minimizada na barra de tarefas e fechá-la (ou pressionar `Ctrl+C`).

## Configuração

As configurações ficam centralizadas em `config.py`, que também carrega automaticamente as variáveis definidas em um arquivo `.env` na raiz do projeto (sem dependências externas). Na primeira execução, os diretórios `data/` e `backups/` são criados automaticamente e uma chave secreta aleatória é gerada e salva em `data/.secret_key` (que **não** deve ser enviada ao Git):

| Constante / Configuração | Descrição |
|---|---|
| `DATABASE_PATH` (`Config.DATABASE`) | Caminho do arquivo SQLite (`data/casa_vida.db`) |
| `BACKUPS_DIR` | Pasta onde ficam os backups (`backups/`) |
| `SECRET_KEY_FILE` (`Config.SECRET_KEY`) | Arquivo local com a chave secreta das sessões (`data/.secret_key`) |

### Variáveis de ambiente (`.env`)

Para habilitar a sincronização com o Google Sheets e o envio de backups por e-mail, copie `.env.example` para `.env` e configure as variáveis abaixo:

**Sincronização com o Google Sheets:**

| Variável | Padrão | Descrição |
|---|---|---|
| `GOOGLE_SHEETS_CSV_URL` | `""` | **(Opção 1 — Recomendada)** URL CSV publicada na web (*Arquivo > Compartilhar > Publicar na Web* em formato `.csv`). Tem prioridade sobre ID/GID quando preenchida. |
| `GOOGLE_SHEETS_ID` | `""` | **(Opção 2)** ID da planilha na URL do Google Sheets (trecho entre `/d/` e `/edit`), usada para planilhas compartilhadas como leitura. |
| `GOOGLE_SHEETS_GID` | `0` | GID da aba desejada na planilha (usado em conjunto com `GOOGLE_SHEETS_ID`). |
| `GOOGLE_SHEETS_TIMEOUT` | `15` | Tempo limite, em segundos, das requisições HTTP ao Google Sheets. |
| `GOOGLE_SHEETS_MIN_DATE` | `2026-11-23` | Data de corte (`YYYY-MM-DD` ou `DD/MM/YYYY`): somente registros novos com data igual ou posterior são importados. |

**Backup automático e envio por e-mail (SMTP):**

| Variável | Padrão | Descrição |
|---|---|---|
| `SMTP_HOST` | `smtp.gmail.com` | Servidor SMTP utilizado para envio dos backups. |
| `SMTP_PORT` | `465` | Porta do servidor SMTP. |
| `SMTP_USE_SSL` | `true` | Define se a conexão SMTP usa SSL (`true`/`false`). |
| `SMTP_USER` | `""` | Conta remetente utilizada para enviar os backups (ex.: `seu-email@gmail.com`). |
| `SMTP_PASSWORD` | `""` | Senha da conta remetente *(no Gmail, usar Senha de App de 16 letras com 2FA ativo)*. |
| `SMTP_TIMEOUT` | `30` | Tempo limite, em segundos, da conexão SMTP. |
| `BACKUP_EMAIL_DESTINO` | `""` | Destinatário(s) do backup por e-mail *(aceita múltiplos e-mails separados por vírgula)*. |
| `BACKUP_AUTO_RETENCAO` | `8` | Quantidade máxima de backups automáticos semanais mantidos localmente em `backups/`. |

## Backup

O banco é um único arquivo (`data/casa_vida.db`) e os backups são gerados de forma consistente via `sqlite3.Connection.backup()`, método compatível com o modo SQLite `WAL` (sem risco de corrupção mesmo com o sistema em uso). Faça cópias periódicas também para um pendrive ou para a nuvem.

Na página **Backups** do sistema estão disponíveis:

- **Geração manual** de cópia de segurança local na pasta `backups/`.
- **Contagem de registros** exibida em coluna própria para cada backup listado.
- **Download** direto do arquivo de backup (via ícone na listagem).
- **Envio manual por e-mail**, compactando o backup em `.zip` e enviando para os destinatários configurados no `.env` (registrando a ação `Backup por E-mail` nos logs de auditoria).
- **Restauração segura** a partir de um backup da lista local ou via **upload de arquivo `.db`, `.sqlite` ou `.zip`**, com validação de integridade SQLite e criação automática de um backup pré-restauração antes de substituir o banco atual.

### Backup automático semanal (Agendador de Tarefas do Windows)

O projeto inclui scripts em `scripts/` para agendar o backup semanal automático com envio por e-mail e retenção automática dos últimos 8 backups semanais (log gravado em `data/backup_semanal.log`):

```powershell
# Instalar a tarefa agendada (toda segunda-feira às 09:00, execução silenciosa via pythonw.exe e StartWhenAvailable)
powershell -ExecutionPolicy Bypass -File scripts\instalar_tarefa_backup.ps1

# Testar a rotina manualmente com saída detalhada no terminal
.\venv\Scripts\python.exe scripts\backup_semanal.py --teste

# Remover a tarefa agendada
powershell -ExecutionPolicy Bypass -File scripts\desinstalar_tarefa_backup.ps1
```

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
3. A sincronização opera em modo **append-only** a partir da data de corte configurada em `GOOGLE_SHEETS_MIN_DATE`: apenas novos registros com data igual ou posterior são importados (com geração automática do número de prontuário quando necessário), preservando todas as edições locais e não reimportando registros já excluídos (registrados em `pacientes_excluidos`).

## Testes

Para executar a suíte de 15 testes automatizados com o ambiente virtual ativado:

```bash
python test_app.py
```

## Próximos passos

- Planejamento da organização automática dos documentos recebidos por e-mail, com banco de dados não relacional (apenas planejamento nesta etapa).
- Otimização do Windows da máquina da instituição, tratada em um script separado.

## Equipe

Projeto Casa Vida, desenvolvido por estudantes de Sistemas de Informação, Engenharia de Software, Marketing e Administração:

Arthur José Barbosa Medeiros, Bernardo Vizeu de Miranda, Ícaro de Alencar Araripe Andrade, Luiz Gouvêa, Enzo Dutra, João Vitor Faião, Gustavo Gavioli, Samuel Guimarães, Davi Grossi, Matheus Steiner Miletto e Pedro Lucas Ventura Meyer Goulart

## Licença

A definir...
