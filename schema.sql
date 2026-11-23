PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS pacientes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    carimbo_data_hora TEXT,
    prontuario_num TEXT UNIQUE,
    nome TEXT NOT NULL,
    endereco TEXT,
    responsavel_1 TEXT,
    telefone_1 TEXT,
    responsavel_2 TEXT,
    telefone_2 TEXT,
    telefone_3 TEXT,
    dn TEXT,
    identidade TEXT,
    cpf TEXT UNIQUE,
    obs TEXT,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    atualizado_em DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS backups_registro (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome_arquivo TEXT NOT NULL,
    tamanho_bytes INTEGER,
    tipo TEXT DEFAULT 'manual',
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS logs_auditoria (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    acao TEXT NOT NULL,
    detalhes TEXT,
    data_hora DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS pacientes_excluidos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prontuario_num TEXT,
    cpf TEXT,
    nome TEXT,
    excluido_em DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_pacientes_prontuario ON pacientes(prontuario_num);
CREATE INDEX IF NOT EXISTS idx_pacientes_nome ON pacientes(nome);
CREATE INDEX IF NOT EXISTS idx_pacientes_cpf ON pacientes(cpf);
CREATE INDEX IF NOT EXISTS idx_excluidos_prontuario ON pacientes_excluidos(prontuario_num);
CREATE INDEX IF NOT EXISTS idx_excluidos_cpf ON pacientes_excluidos(cpf);
