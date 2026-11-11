# Sistema Casa Vida

Sistema web leve para cadastro, consulta e atualização dos dados dos assistidos do **Instituto Casa Vida**, desenvolvido como projeto de extensão universitário. Feito com **Flask** e **SQLite**, para rodar localmente em um computador de hardware modesto, sem depender de servidor de banco de dados ou de internet.

> **Status:** em desenvolvimento. As funcionalidades marcadas com `[ ]` ainda estão planejadas.

---

## Sobre o projeto

O Instituto Casa Vida é uma Organização da Sociedade Civil de Juiz de Fora (MG) que oferece apoio gratuito a pacientes oncológicos e seus familiares. O **Projeto Casa Vida** reúne estudantes de Sistemas de Informação, Engenharia de Software, Marketing e Administração para ajudar a instituição com organização, tecnologia e comunicação.

Este sistema dá continuidade ao trabalho iniciado com a planilha no Google Sheets, que substituiu os prontuários em papel. A proposta agora é oferecer uma ferramenta dedicada, mais segura e adequada à rotina da equipe.

## Objetivos

- Facilitar o cadastro, a consulta e a atualização dos dados dos pacientes pelos responsáveis da instituição.
- Funcionar bem em um computador antigo (processador de 2ª geração, sem SSD).
- Proteger os dados, que são sensíveis, com controle de acesso e backup.
- Servir de base para as próximas etapas do projeto (por exemplo, a organização dos documentos recebidos por e-mail).

## Funcionalidades

- [ ] Login com usuário e senha (senhas armazenadas com hash)
- [ ] Cadastro de pacientes
- [ ] Consulta com busca e filtros
- [ ] Edição e atualização de registros
- [ ] Importação dos dados da planilha atual (CSV)
- [ ] Exportação de dados (CSV)
- [ ] Backup do banco de dados
- [ ] Sincronização com o Google Sheets (opcional, planejada)

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

## Estrutura sugerida do projeto

```
casa-vida-sistema/
├── app/
│   ├── __init__.py        # criação da aplicação Flask
│   ├── auth.py            # login e controle de acesso
│   ├── db.py              # conexão e funções do banco
│   ├── pacientes.py       # rotas e regras de pacientes
│   ├── templates/         # páginas HTML
│   └── static/            # CSS, JS e imagens
├── data/                  # banco SQLite (não vai para o Git)
├── backups/               # cópias do banco (não vão para o Git)
├── schema.sql             # estrutura das tabelas
├── config.py              # configurações
├── run.py                 # inicia o servidor
├── iniciar.bat            # atalho para abrir o sistema
├── requirements.txt       # dependências
└── README.md
```

## Instalação

```bash
# 1. Clonar o repositório
git clone <URL-DO-REPOSITORIO>
cd casa-vida-sistema

# 2. Criar e ativar o ambiente virtual
python -m venv venv
venv\Scripts\activate

# 3. Instalar as dependências
pip install -r requirements.txt

# 4. Criar o banco de dados
flask --app app init-db

# 5. Criar o primeiro usuário
flask --app app create-user
```

## Como executar

**Para desenvolvimento:**

```bash
flask --app app run --debug
```

**Para uso na instituição (modo leve):**

```bash
python run.py
```

O `run.py` inicia o sistema com o Waitress, escutando apenas na própria máquina:

```python
from waitress import serve
from app import create_app

serve(create_app(), host="127.0.0.1", port=5000)
```

Depois, acesse `http://127.0.0.1:5000` no navegador.

### Atalho com duplo clique

O arquivo `iniciar.bat` inicia o servidor e abre o sistema em uma janela de aplicativo, sem abas nem barra de endereço:

```bat
@echo off
cd /d %~dp0
call venv\Scripts\activate
start "" /min python run.py
timeout /t 3 >nul
start "" msedge --app=http://127.0.0.1:5000
```

Crie um atalho para esse arquivo na área de trabalho.

## Configuração

As configurações ficam no `config.py` e, para valores secretos, em variáveis de ambiente ou em um arquivo `.env` (que **não** deve ser enviado ao Git):

| Variável | Descrição |
|---|---|
| `SECRET_KEY` | Chave secreta da aplicação (sessões) |
| `DATABASE_PATH` | Caminho do arquivo SQLite |
| `BACKUP_DIR` | Pasta onde ficam os backups |

## Backup

O banco é um único arquivo. Faça cópias periódicas para a pasta `backups/` e, de preferência, para um pendrive ou para a nuvem. O objetivo é que a instituição nunca perca os dados, como já aconteceu uma vez com o computador.

## Segurança e LGPD

O sistema trata **dados pessoais sensíveis (dados de saúde)**, que têm proteção especial na Lei Geral de Proteção de Dados (LGPD). Por isso:

- Use o sistema apenas com login e senha, e limite o acesso a quem realmente precisa.
- Mantenha o servidor acessível somente na própria máquina (`127.0.0.1`).
- Registre apenas os dados necessários para o atendimento.
- Nunca envie o banco de dados, backups, planilhas reais ou chaves ao repositório do Git. Use o `.gitignore`.
- Use dados fictícios para testes e demonstrações.

## Sincronização com o Google Sheets (planejada)

A ideia é manter o SQLite como fonte principal dos dados e enviar as alterações para a planilha (sincronização em mão única), usando a biblioteca `gspread` e uma conta de serviço do Google. A planilha ficaria para consulta, relatórios e backup na nuvem. A chave da conta de serviço deve ficar fora do repositório e a planilha não deve ter link público.

## Próximos passos

- Planejamento da organização automática dos documentos recebidos por e-mail, com banco de dados não relacional (apenas planejamento nesta etapa).
- Otimização do Windows da máquina da instituição, tratada em um script separado.

## Equipe

Projeto Casa Vida, desenvolvido por estudantes de Sistemas de Informação, Engenharia de Software, Marketing e Administração:

Arthur José Barbosa Medeiros, Bernardo Vizeu de Miranda, Ícaro de Alencar Araripe Andrade, Luiz Gouvêa, Enzo Dutra, João Vitor Faião, Gustavo Gavioli, Samuel Guimarães, Davi Grossi, Matheus Steiner Miletto e Pedro Lucas Ventura Meyer Goulart

## Licença

A definir...
