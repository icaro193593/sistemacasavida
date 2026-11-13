PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    senha_hash TEXT NOT NULL,
    nome_completo TEXT NOT NULL,
    perfil TEXT NOT NULL DEFAULT 'atendente',
    ativo INTEGER NOT NULL DEFAULT 1,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    ultimo_login DATETIME
);

CREATE TABLE IF NOT EXISTS pacientes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prontuario_num TEXT UNIQUE,
    nome TEXT NOT NULL,
    data_nascimento TEXT,
    cpf TEXT UNIQUE,
    rg TEXT,
    sexo TEXT,
    estado_civil TEXT,
    telefone TEXT,
    whatsapp TEXT,
    email TEXT,
    nome_responsavel TEXT,
    telefone_responsavel TEXT,
    parentesco_responsavel TEXT,
    endereco_cep TEXT,
    endereco_logradouro TEXT,
    endereco_numero TEXT,
    endereco_complemento TEXT,
    endereco_bairro TEXT,
    endereco_cidade TEXT DEFAULT 'Juiz de Fora',
    endereco_uf TEXT DEFAULT 'MG',
    endereco_referencia TEXT,
    diagnostico TEXT,
    local_tratamento TEXT,
    medico_responsavel TEXT,
    data_diagnostico TEXT,
    estadiamento TEXT,
    status_tratamento TEXT DEFAULT 'Em tratamento',
    medicamentos_em_uso TEXT,
    necessidades_apoio TEXT,
    renda_familiar TEXT,
    beneficio_social TEXT,
    ocupacao TEXT,
    qtd_moradores INTEGER DEFAULT 1,
    status_instituto TEXT DEFAULT 'Ativo',
    observacoes TEXT,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    atualizado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    criado_por INTEGER REFERENCES usuarios(id),
    atualizado_por INTEGER REFERENCES usuarios(id)
);

CREATE TABLE IF NOT EXISTS atendimentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paciente_id INTEGER NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
    data_atendimento TEXT NOT NULL,
    tipo TEXT NOT NULL,
    descricao TEXT NOT NULL,
    profissional TEXT,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    usuario_id INTEGER REFERENCES usuarios(id)
);

CREATE TABLE IF NOT EXISTS backups_registro (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome_arquivo TEXT NOT NULL,
    tamanho_bytes INTEGER,
    tipo TEXT DEFAULT 'manual',
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    usuario_id INTEGER REFERENCES usuarios(id)
);

CREATE TABLE IF NOT EXISTS logs_auditoria (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER REFERENCES usuarios(id),
    usuario_nome TEXT,
    acao TEXT NOT NULL,
    detalhes TEXT,
    data_hora DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_pacientes_nome ON pacientes(nome);
CREATE INDEX IF NOT EXISTS idx_pacientes_cpf ON pacientes(cpf);
CREATE INDEX IF NOT EXISTS idx_pacientes_status ON pacientes(status_instituto);
CREATE INDEX IF NOT EXISTS idx_pacientes_diagnostico ON pacientes(diagnostico);
CREATE INDEX IF NOT EXISTS idx_atendimentos_paciente ON atendimentos(paciente_id);
CREATE INDEX IF NOT EXISTS idx_atendimentos_data ON atendimentos(data_atendimento);
