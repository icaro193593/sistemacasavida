import io
import os
import smtplib
import sqlite3
import tempfile
import unittest
import zipfile
from email.message import EmailMessage
from unittest.mock import patch
import config
from app import create_app
from app.backup import (
    contar_registros_backup,
    executar_backup,
    limpar_backups_automaticos,
    listar_backups,
)
from app.db import get_db, init_db
from scripts import backup_semanal

TEST_DB_PATH = os.path.join(config.DATA_DIR, 'test_casa_vida.db')


class TestCasaVida(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for sufixo in ('', '-wal', '-shm'):
            caminho = f"{TEST_DB_PATH}{sufixo}"
            if os.path.exists(caminho):
                os.remove(caminho)
        cls.app = create_app({
            'TESTING': True,
            'DATABASE': TEST_DB_PATH,
            'WTF_CSRF_ENABLED': False,
            'GOOGLE_SHEETS_CSV_URL': '',
            'GOOGLE_SHEETS_ID': '',
            'GOOGLE_SHEETS_GID': '0',
            'GOOGLE_SHEETS_MIN_DATE': '2026-11-23',
        })
        cls.client = cls.app.test_client()

    @classmethod
    def tearDownClass(cls):
        for sufixo in ('', '-wal', '-shm'):
            caminho = f"{TEST_DB_PATH}{sufixo}"
            try:
                if os.path.exists(caminho):
                    os.remove(caminho)
            except Exception:
                pass

    def test_01_db_init_schema_13_colunas(self):
        with self.app.app_context():
            db = get_db()
            tabelas = {
                row['name']
                for row in db.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
            colunas_pacientes = {
                row['name']
                for row in db.execute("PRAGMA table_info(pacientes)").fetchall()
            }

        for obrigatoria in ('pacientes', 'backups_registro', 'logs_auditoria', 'pacientes_excluidos'):
            self.assertIn(obrigatoria, tabelas)
        self.assertNotIn('usuarios', tabelas)

        for col in (
            'carimbo_data_hora', 'prontuario_num', 'nome', 'endereco',
            'responsavel_1', 'telefone_1', 'responsavel_2', 'telefone_2',
            'telefone_3', 'dn', 'identidade', 'cpf', 'obs',
        ):
            self.assertIn(col, colunas_pacientes)
        self.assertNotIn('status_instituto', colunas_pacientes)
        self.assertNotIn('diagnostico', colunas_pacientes)
        print("[PASS] Teste 01: Banco inicializado com schema exato das 13 colunas da planilha.")

    def test_02_acesso_direto_navbar_e_layout_planilha(self):
        self.assertEqual(self.client.get('/auth/login').status_code, 404)

        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)

        # Navbar e controles principais
        for esperado in (
            'homelife.png',
            'Sistema de Gestão de Assistidos',
            'Assistidos',
            'Logs',
            'Backups',
            'Novo Paciente',
            'btn-editar-planilha',
            'Sincronizar Google Sheets',
            'Exportar CSV',
            'barra-edicao-planilha',
            'modal-confirmar-edicoes',
        ):
            self.assertIn(esperado, html)

        # Elementos removidos (auth, cards de métricas, colunas fictícias e coluna Ações por linha)
        for removido in (
            'Novo Cadastro',
            'Importar Planilha',
            'Usuários',
            'Administrador Casa Vida',
            'Total de Assistidos',
            'grid-stats',
            'Diagnóstico Oncológico',
            'Bairro / Cidade',
            '<th>Status</th>',
            '<th>Ações</th>',
            'Ver Prontuário',
        ):
            self.assertNotIn(removido, html)

        # Cabeçalhos exatos das 13 colunas reais da planilha (ordenáveis e arrastáveis)
        colunas_esperadas = (
            'Prontuário', 'Nome', 'Endereço', 'Responsável 1', 'Telefone 1',
            'Responsável 2', 'Telefone 2', 'Telefone 3', 'DN', 'ID', 'CPF',
            'Obs', 'Carimbo de data/hora',
        )
        for col in colunas_esperadas:
            self.assertIn(f'<span class="th-label">{col}</span>', html)
        self.assertIn('draggable="true"', html)
        self.assertIn('tabela-planilha-container', html)
        self.assertIn('name="operador"', html)
        self.assertIn('col-editar-fixa', html)

        # Select de busca com "Todas as colunas" + 13 colunas = 14 opções
        inicio_select = html.find('<select name="coluna"')
        fim_select = html.find('</select>', inicio_select)
        bloco_select = html[inicio_select:fim_select]
        self.assertEqual(bloco_select.count('<option '), 14)
        for col in colunas_esperadas:
            self.assertIn(col, bloco_select)

        print("[PASS] Teste 02: Layout da planilha com 13 colunas reais, sem Ações/Status e filtros validado.")

    def test_03_cadastrar_paciente_12_campos(self):
        resp = self.client.post('/novo', data={
            'prontuario_num': '1001',
            'nome': 'João da Silva Teste',
            'endereco': 'Rua São Mateus, 120 - Centro',
            'responsavel_1': 'Maria da Silva',
            'telefone_1': '98888-7777',
            'responsavel_2': 'Carlos da Silva',
            'telefone_2': '97777-6666 (filho)',
            'telefone_3': '3212-3456',
            'dn': '15/05/1970',
            'identidade': 'MG-12.345.678',
            'cpf': '123.456.789-00',
            'obs': 'Acompanhamento inicial',
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        self.assertIn('João da Silva Teste', html)
        self.assertIn('MG-12.345.678', html)
        self.assertIn('97777-6666 (filho)', html)
        print("[PASS] Teste 03: Cadastro de paciente com colunas reais da planilha validado.")

    def test_04_busca_por_coluna(self):
        self.client.post('/novo', data={
            'prontuario_num': '2002',
            'nome': 'Maria Oliveira Santos',
            'endereco': 'Av Rio Branco, 500',
            'responsavel_1': 'Pedro Santos',
            'telefone_1': '99111-2222',
            'responsavel_2': 'Ana Santos',
            'telefone_2': '99333-4444',
            'telefone_3': '',
            'dn': '20/09/1982',
            'identidade': 'MG-99.888.777',
            'cpf': '987.654.321-11',
            'obs': 'Observação especial',
        })

        casos_match = [
            ('todas', 'MG-99.888.777'),
            ('prontuario_num', '2002'),
            ('nome', 'Oliveira'),
            ('endereco', 'Rio Branco'),
            ('responsavel_1', 'Pedro Santos'),
            ('telefone_1', '99111-2222'),
            ('responsavel_2', 'Ana Santos'),
            ('telefone_2', '99333-4444'),
            ('dn', '20/09/1982'),
            ('identidade', 'MG-99.888.777'),
            ('cpf', '98765432111'),
            ('obs', 'Observação especial'),
        ]
        for col, termo in casos_match:
            r = self.client.get('/', query_string={'busca': termo, 'coluna': col})
            self.assertEqual(r.status_code, 200)
            html = r.get_data(as_text=True)
            self.assertIn('Maria Oliveira Santos', html, f'Falha ao buscar {termo} em {col}')
            self.assertNotIn('João da Silva Teste', html, f'Vazou outro registro em {col}')

        # Isolamento entre colunas
        r_vazio = self.client.get('/', query_string={'busca': 'Rio Branco', 'coluna': 'obs'})
        self.assertIn('0 registro(s) encontrado(s)', r_vazio.get_data(as_text=True))
        print("[PASS] Teste 04: Busca por coluna específica e isolamento validados.")

    def test_05_sincronizar_google_sheets(self):
        # 1) Sem config
        with patch.dict(self.app.config, {'GOOGLE_SHEETS_CSV_URL': '', 'GOOGLE_SHEETS_ID': ''}):
            r_err = self.client.post('/sincronizar-sheets', headers={'Accept': 'application/json'})
            self.assertEqual(r_err.status_code, 400)
            self.assertFalse(r_err.get_json()['ok'])

        # 2) Append-only + data de corte + bloqueio de excluídos
        with self.app.app_context():
            db = get_db()
            db.execute(
                "INSERT INTO pacientes_excluidos (prontuario_num, cpf, nome) VALUES (?, ?, ?)",
                ('9999', '111.222.333-44', 'Paciente Removido Localmente'),
            )
            db.commit()

        csv_mock = (
            "Carimbo de data/hora,Prontuário,Nome,Endereço,Responsável 1,Telefone 1,Responsável 2,Telefone 2,Telefone 3,DN,ID,CPF,Obs\n"
            "24/11/2026 10:00:00,1001,João Alterado no Sheets,Rua Nova,Resp Novo,90000-0000,,,,15/05/1970,MG-00,123.456.789-00,Obs Sheets\n"
            "20/11/2026 09:00:00,3000,Paciente Antigo,Rua Velha,Resp Velho,91111-1111,,,,01/01/1960,MG-11,222.333.444-55,\n"
            "25/11/2026 14:00:00,9999,Paciente Removido Localmente,Rua X,Resp X,92222-2222,,,,02/02/1965,MG-22,111.222.333-44,\n"
            "23/11/2026 18:00:00,3003,Ana Clara Sincronizada,Rua Benfica 50,Lucia,98888-2222,Marcos,97777-1111,3222-0000,10/10/1975,MG-33.444.555,55544433322,Nova obs\n"
        )

        with patch.dict(
            self.app.config,
            {
                'GOOGLE_SHEETS_CSV_URL': 'https://docs.google.com/spreadsheets/d/fake/export?format=csv',
                'GOOGLE_SHEETS_MIN_DATE': '2026-11-23',
            },
        ):
            with patch('app.sheets_sync.baixar_csv_planilha', return_value=csv_mock):
                r_ok = self.client.post('/sincronizar-sheets', headers={'Accept': 'application/json'})

        self.assertEqual(r_ok.status_code, 200)
        dados = r_ok.get_json()
        self.assertTrue(dados['ok'])
        self.assertEqual(dados['adicionados'], 1)
        self.assertEqual(dados['atualizados'], 0)
        self.assertEqual(dados['ja_existentes'], 1)
        self.assertEqual(dados['removidos_ignorados'], 1)
        self.assertEqual(dados['anteriores_data_corte'], 1)

        with self.app.app_context():
            db = get_db()
            # Existente preservado
            p1 = db.execute("SELECT * FROM pacientes WHERE prontuario_num = '1001'").fetchone()
            self.assertEqual(p1['nome'], 'João da Silva Teste')
            # Novo inserido com todas as 13 colunas
            p3 = db.execute("SELECT * FROM pacientes WHERE prontuario_num = '3003'").fetchone()
            self.assertIsNotNone(p3)
            self.assertEqual(p3['nome'], 'Ana Clara Sincronizada')
            self.assertEqual(p3['responsavel_2'], 'Marcos')
            self.assertEqual(p3['telefone_3'], '3222-0000')
            self.assertEqual(p3['identidade'], 'MG-33.444.555')
            self.assertEqual(p3['cpf'], '555.444.333-22')
            self.assertEqual(p3['carimbo_data_hora'], '23/11/2026 18:00:00')
            # Antigo e excluído não inseridos
            self.assertIsNone(db.execute("SELECT id FROM pacientes WHERE prontuario_num = '3000'").fetchone())
            self.assertIsNone(db.execute("SELECT id FROM pacientes WHERE prontuario_num = '9999'").fetchone())

        print("[PASS] Teste 05: Sincronização com Google Sheets nas 13 colunas reais validada.")

    def test_06_edicao_direta_e_exclusao_por_prontuario(self):
        with self.app.app_context():
            db = get_db()
            p1_id = db.execute("SELECT id FROM pacientes WHERE prontuario_num = '1001'").fetchone()['id']
            p3_id = db.execute("SELECT id FROM pacientes WHERE prontuario_num = '3003'").fetchone()['id']

        resp = self.client.post('/editar-lote', json={
            'alteracoes': [
                {
                    'id': p1_id,
                    'campos': {
                        'prontuario_num': '1001-ALT',
                        'responsavel_2': 'Roberto Atualizado',
                        'obs': 'Atualizado direto na planilha',
                    },
                },
                {
                    'id': p3_id,
                    'campos': {
                        'prontuario_num': '',
                    },
                },
            ],
            'exclusoes': [],
        })
        self.assertEqual(resp.status_code, 200)
        dados = resp.get_json()
        self.assertTrue(dados['ok'])
        self.assertEqual(dados['atualizados'], 1)
        self.assertEqual(dados['excluidos'], 1)

        with self.app.app_context():
            db = get_db()
            p1 = db.execute("SELECT * FROM pacientes WHERE id = ?", (p1_id,)).fetchone()
            self.assertEqual(p1['prontuario_num'], '1001-ALT')
            self.assertEqual(p1['responsavel_2'], 'Roberto Atualizado')
            self.assertEqual(p1['obs'], 'Atualizado direto na planilha')
            self.assertIsNone(db.execute("SELECT id FROM pacientes WHERE id = ?", (p3_id,)).fetchone())
            self.assertIsNotNone(db.execute("SELECT id FROM pacientes_excluidos WHERE prontuario_num = '3003'").fetchone())

        print("[PASS] Teste 06: Edição direta em lote, alteração de prontuário e exclusão por prontuário vazio validadas.")

    def test_07_logs_exportar_e_backups(self):
        r_logs = self.client.get('/logs/')
        self.assertEqual(r_logs.status_code, 200)
        html_logs = r_logs.get_data(as_text=True)
        self.assertIn('Logs de Alterações', html_logs)
        self.assertIn('1001-ALT', html_logs)
        self.assertIn('Ana Clara Sincronizada', html_logs)

        r_csv = self.client.get('/exportar')
        self.assertEqual(r_csv.status_code, 200)
        csv_txt = r_csv.data.decode('utf-8-sig')
        self.assertIn('Carimbo de data/hora;Prontuário;Nome;Endereço;Responsável 1;Telefone 1;Responsável 2;Telefone 2;Telefone 3;DN;ID;CPF;Obs', csv_txt)
        self.assertIn('João da Silva Teste', csv_txt)

        r_bkp = self.client.get('/backup/')
        self.assertEqual(r_bkp.status_code, 200)
        self.assertIn('Backups do Banco de Dados', r_bkp.get_data(as_text=True))
        print("[PASS] Teste 07: Logs, exportação CSV 13 colunas e backups validados.")

    def test_08_ordenacao_filtro_matematico_e_exportacao_sincronizada(self):
        # Filtro comparativo de data: DN > 1970 (deve pegar Maria 1982, não João 1970)
        r_dn = self.client.get('/', query_string={'busca': '1970', 'coluna': 'dn', 'operador': 'maior'})
        self.assertEqual(r_dn.status_code, 200)
        html_dn = r_dn.get_data(as_text=True)
        self.assertIn('Maria Oliveira Santos', html_dn)
        self.assertNotIn('João da Silva Teste', html_dn)

        # Mesmo filtro digitado direto na busca ('> 1970') e combinando dropdown + prefixo ('< 1980' com operador 'menor')
        r_dn_inline = self.client.get('/', query_string={'busca': '> 1970', 'coluna': 'dn'})
        html_dn_inline = r_dn_inline.get_data(as_text=True)
        self.assertIn('Maria Oliveira Santos', html_dn_inline)
        self.assertNotIn('João da Silva Teste', html_dn_inline)

        r_dn_menor_dup = self.client.get('/', query_string={'busca': '< 1980', 'coluna': 'dn', 'operador': 'menor'})
        html_dn_menor_dup = r_dn_menor_dup.get_data(as_text=True)
        self.assertIn('João da Silva Teste', html_dn_menor_dup)
        self.assertNotIn('Maria Oliveira Santos', html_dn_menor_dup)

        # Exportação CSV sincronizada com o filtro DN > 1970 + ordenação + ordem_colunas customizada
        r_csv_filtrado = self.client.get('/exportar', query_string={
            'busca': '1970',
            'coluna': 'dn',
            'operador': 'maior',
            'ordem': 'dn',
            'dir': 'desc',
            'ordem_colunas': 'nome,dn,prontuario_num',
        })
        self.assertEqual(r_csv_filtrado.status_code, 200)
        csv_txt = r_csv_filtrado.data.decode('utf-8-sig')
        linhas = [l for l in csv_txt.splitlines() if l.strip()]
        self.assertEqual(linhas[0], 'Nome;DN;Prontuário')
        self.assertEqual(len(linhas), 2)  # cabeçalho + apenas Maria (1982)
        self.assertIn('Maria Oliveira Santos', linhas[1])
        self.assertNotIn('João da Silva Teste', csv_txt)

        # Ordenação por DN asc vs desc
        r_asc = self.client.get('/', query_string={'ordem': 'dn', 'dir': 'asc'})
        html_asc = r_asc.get_data(as_text=True)
        self.assertTrue(html_asc.find('João da Silva Teste') < html_asc.find('Maria Oliveira Santos'))

        r_desc = self.client.get('/', query_string={'ordem': 'dn', 'dir': 'desc'})
        html_desc = r_desc.get_data(as_text=True)
        self.assertTrue(html_desc.find('Maria Oliveira Santos') < html_desc.find('João da Silva Teste'))

        # Carga completa em tela sem paginação nem lotes
        self.assertNotIn('class="paginacao"', html_asc)
        self.assertNotIn('rodape-tabela-infinita', html_asc)
        self.assertEqual(html_asc.count('data-paciente-id='), 2)

        print("[PASS] Teste 08: Ordenação no cabeçalho, filtro matemático (DN > 1970), CSV sincronizado e carga completa validados.")

    def test_09_tela_edicao_individual_sticky_e_exclusao(self):
        with self.app.app_context():
            db = get_db()
            p = db.execute("SELECT id, prontuario_num FROM pacientes WHERE prontuario_num = '2002'").fetchone()
            self.assertIsNotNone(p)
            pid = p['id']

        # Ícone de lápis fixo presente na tabela principal apontando para /<id>/editar (sem botão Prontuário)
        r_index = self.client.get('/')
        html_index = r_index.get_data(as_text=True)
        self.assertIn(f'href="/{pid}/editar"', html_index)
        self.assertIn('btn-icone-editar', html_index)
        self.assertNotIn('Ver Prontuário', html_index)

        # GET /<id>/editar exibe formulário limpo com os 12 campos reais
        r_get = self.client.get(f'/{pid}/editar')
        self.assertEqual(r_get.status_code, 200)
        html_edit = r_get.get_data(as_text=True)
        self.assertIn('Editar Cadastro de Assistido', html_edit)
        self.assertIn('Maria Oliveira Santos', html_edit)
        self.assertIn('MG-99.888.777', html_edit)

        # POST /<id>/editar atualiza e grava diff detalhado em /logs/
        r_post = self.client.post(f'/{pid}/editar', data={
            'prontuario_num': '2002',
            'nome': 'Maria Oliveira Atualizada',
            'endereco': 'Av Rio Branco, 777',
            'responsavel_1': 'Pedro Santos',
            'telefone_1': '99111-2222',
            'responsavel_2': 'Ana Santos',
            'telefone_2': '99333-4444',
            'telefone_3': '3200-1111',
            'dn': '20/09/1982',
            'identidade': 'MG-99.888.777',
            'cpf': '987.654.321-11',
            'obs': 'Atualizada pela tela individual',
        }, follow_redirects=True)
        self.assertEqual(r_post.status_code, 200)
        self.assertIn('Maria Oliveira Atualizada', r_post.get_data(as_text=True))

        r_logs = self.client.get('/logs/?acao=EDICAO')
        html_logs = r_logs.get_data(as_text=True)
        self.assertIn('Maria Oliveira Atualizada', html_logs)
        self.assertIn('Av Rio Branco, 777', html_logs)

        # POST /<id>/editar SEM nenhuma mudança NÃO deve atualizar nem criar novo log
        with self.app.app_context():
            db = get_db()
            logs_antes = db.execute("SELECT COUNT(*) FROM logs_auditoria").fetchone()[0]

        r_noop = self.client.post(f'/{pid}/editar', data={
            'prontuario_num': '2002',
            'nome': 'Maria Oliveira Atualizada',
            'endereco': 'Av Rio Branco, 777',
            'responsavel_1': 'Pedro Santos',
            'telefone_1': '99111-2222',
            'responsavel_2': 'Ana Santos',
            'telefone_2': '99333-4444',
            'telefone_3': '3200-1111',
            'dn': '20/09/1982',
            'identidade': 'MG-99.888.777',
            'cpf': '987.654.321-11',
            'obs': 'Atualizada pela tela individual',
        }, follow_redirects=True)
        self.assertEqual(r_noop.status_code, 200)
        self.assertIn('Nenhuma alteração foi feita.', r_noop.get_data(as_text=True))

        with self.app.app_context():
            db = get_db()
            logs_depois = db.execute("SELECT COUNT(*) FROM logs_auditoria").fetchone()[0]
            self.assertEqual(logs_antes, logs_depois)

        # POST /<id>/excluir remove, registra em pacientes_excluidos e grava log EXCLUSAO
        r_del = self.client.post(f'/{pid}/excluir', follow_redirects=True)
        self.assertEqual(r_del.status_code, 200)
        with self.app.app_context():
            db = get_db()
            self.assertIsNone(db.execute("SELECT id FROM pacientes WHERE id = ?", (pid,)).fetchone())
            self.assertIsNotNone(db.execute("SELECT id FROM pacientes_excluidos WHERE prontuario_num = '2002'").fetchone())

        print("[PASS] Teste 09: Tela dedicada /<id>/editar, lápis fixo (sticky), logs de diff e exclusão validados.")

    def test_10_acentos_ptbr_toasts_logs_e_backups(self):
        # Cadastra nomes com acento (Ângela) e com Z (Zilda) para validar ordenação PT_BR
        self.client.post('/novo', data={'prontuario_num': '5001', 'nome': 'Ângela Maria'})
        self.client.post('/novo', data={'prontuario_num': '5002', 'nome': 'Zilda Maria'})
        self.client.post('/novo', data={'prontuario_num': '5003', 'nome': 'Bruno Costa'})

        # Ordem crescente (buscando dentro do <tbody>): Ângela deve vir ANTES de Bruno e de Zilda
        html_asc = self.client.get('/', query_string={'ordem': 'nome', 'dir': 'asc'}).get_data(as_text=True)
        tbody_asc = html_asc[html_asc.find('<tbody>'):]
        idx_ang_asc = tbody_asc.find('Ângela Maria')
        idx_bru_asc = tbody_asc.find('Bruno Costa')
        idx_zil_asc = tbody_asc.find('Zilda Maria')
        self.assertTrue(idx_ang_asc < idx_bru_asc < idx_zil_asc)

        # Ordem decrescente: Zilda deve vir ANTES de Bruno, e Bruno ANTES de Ângela
        html_desc = self.client.get('/', query_string={'ordem': 'nome', 'dir': 'desc'}).get_data(as_text=True)
        tbody_desc = html_desc[html_desc.find('<tbody>'):]
        idx_zil_desc = tbody_desc.find('Zilda Maria')
        idx_bru_desc = tbody_desc.find('Bruno Costa')
        idx_ang_desc = tbody_desc.find('Ângela Maria')
        self.assertTrue(idx_zil_desc < idx_bru_desc < idx_ang_desc)

        # Backups sem caixa amarela de recomendação
        html_bkp = self.client.get('/backup/').get_data(as_text=True)
        self.assertNotIn('Recomendação de Segurança para a Instituição', html_bkp)

        # Logs sem 'Edição na Planilha', com ação centralizada e toast flutuante em base.html
        html_logs = self.client.get('/logs/').get_data(as_text=True)
        self.assertNotIn('Edição na Planilha', html_logs)
        self.assertIn('col-log-acao', html_logs)
        self.assertIn('toast-container', html_logs)

        print("[PASS] Teste 10: Ordenação PT-BR com acentos, toasts flutuantes, logs unificados e backups limpos validados.")

    def test_11_retencao_automatica_backups(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(self.app.config, {'BACKUPS_DIR': tmpdir, 'BACKUP_AUTO_RETENCAO': 8}):
                with self.app.app_context():
                    # Gera 2 backups manuais que devem permanecer intactos
                    m1, err_m1 = executar_backup(tipo='manual')
                    m2, err_m2 = executar_backup(tipo='manual')
                    self.assertIsNone(err_m1)
                    self.assertIsNone(err_m2)

                    # Gera mais de 8 backups automáticos (10 execuções)
                    for _ in range(10):
                        nome_auto, err_auto = executar_backup(tipo='automatico')
                        self.assertIsNone(err_auto)
                        self.assertTrue(nome_auto.startswith('casa_vida_backup_auto_'))

                    arquivos = os.listdir(tmpdir)
                    autos = [f for f in arquivos if f.startswith('casa_vida_backup_auto_') and f.endswith('.db')]
                    manuais = [
                        f for f in arquivos
                        if f.startswith('casa_vida_backup_')
                        and not f.startswith('casa_vida_backup_auto_')
                        and f.endswith('.db')
                    ]
                    self.assertEqual(len(autos), 8)
                    self.assertEqual(sorted(manuais), sorted([m1, m2]))

                    # Valida também chamada direta de limpar_backups_automaticos com excesso artificial
                    extra_1 = os.path.join(tmpdir, 'casa_vida_backup_auto_20000101_000001.db')
                    extra_2 = os.path.join(tmpdir, 'casa_vida_backup_auto_20000101_000002.db')
                    for idx, caminho_extra in enumerate((extra_1, extra_2), start=1):
                        with open(caminho_extra, 'wb') as f:
                            f.write(b'SQLite format 3\x00' + b'\x00' * 100)
                        os.utime(caminho_extra, (1000000 + idx, 1000000 + idx))

                    removidos = limpar_backups_automaticos()
                    self.assertEqual(len(removidos), 2)
                    self.assertFalse(os.path.exists(extra_1))
                    self.assertFalse(os.path.exists(extra_2))

                    autos_final = [
                        f for f in os.listdir(tmpdir)
                        if f.startswith('casa_vida_backup_auto_') and f.endswith('.db')
                    ]
                    self.assertEqual(len(autos_final), 8)
                    self.assertTrue(os.path.exists(os.path.join(tmpdir, m1)))
                    self.assertTrue(os.path.exists(os.path.join(tmpdir, m2)))

        print("[PASS] Teste 11: Retenção automática de 8 backups e preservação dos backups manuais validadas.")

    def test_12_pagina_backup_e_envio_email(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg_email = {
                'BACKUPS_DIR': tmpdir,
                'SMTP_HOST': 'smtp.gmail.com',
                'SMTP_PORT': 465,
                'SMTP_USE_SSL': True,
                'SMTP_USER': 'remetente@teste.org',
                'SMTP_PASSWORD': 'abcd efgh ijkl mnop',
                'BACKUP_EMAIL_DESTINO': 'destino@teste.org',
            }
            with patch.dict(self.app.config, cfg_email):
                r_get = self.client.get('/backup/')
                self.assertEqual(r_get.status_code, 200)
                html = r_get.get_data(as_text=True)
                self.assertIn('Registros', html)
                self.assertIn('Enviar Backup por E-mail', html)
                self.assertIn('action="/backup/restaurar-arquivo"', html)
                self.assertIn('accept=".db,.sqlite,.zip"', html)

                # 1) Envio manual com SMTP_SSL mockado
                with patch('smtplib.SMTP_SSL') as mock_smtp_ssl:
                    mock_server = mock_smtp_ssl.return_value.__enter__.return_value
                    r_ok = self.client.post('/backup/enviar-email', follow_redirects=True)
                    self.assertEqual(r_ok.status_code, 200)
                    html_ok = r_ok.get_data(as_text=True)
                    self.assertIn('enviado por e-mail com sucesso!', html_ok)

                    mock_smtp_ssl.assert_called_once()
                    mock_server.login.assert_called_once_with('remetente@teste.org', 'abcd efgh ijkl mnop')
                    mock_server.send_message.assert_called_once()

                    msg_enviada = mock_server.send_message.call_args[0][0]
                    self.assertIsInstance(msg_enviada, EmailMessage)
                    self.assertEqual(msg_enviada['To'], 'destino@teste.org')

                    anexos = list(msg_enviada.iter_attachments())
                    self.assertEqual(len(anexos), 1)
                    nome_anexo = anexos[0].get_filename()
                    self.assertTrue(nome_anexo.endswith('.zip'))

                    zip_bytes = anexos[0].get_payload(decode=True)
                    with zipfile.ZipFile(io.BytesIO(zip_bytes), 'r') as zf:
                        nomes_internos = zf.namelist()
                        self.assertEqual(len(nomes_internos), 1)
                        self.assertTrue(nomes_internos[0].endswith('.db'))
                        db_bytes = zf.read(nomes_internos[0])
                        self.assertTrue(db_bytes.startswith(b'SQLite format 3\x00'))

                with self.app.app_context():
                    db = get_db()
                    log_ok = db.execute(
                        "SELECT * FROM logs_auditoria WHERE acao = 'BACKUP_EMAIL' ORDER BY id DESC LIMIT 1"
                    ).fetchone()
                    self.assertIsNotNone(log_ok)
                    self.assertIn('destino@teste.org', log_ok['detalhes'])
                    self.assertIn('enviado por e-mail', log_ok['detalhes'])

                # 2) Falha de autenticação SMTP orientando sobre Senha de App
                with patch('smtplib.SMTP_SSL') as mock_smtp_err:
                    mock_server_err = mock_smtp_err.return_value.__enter__.return_value
                    mock_server_err.login.side_effect = smtplib.SMTPAuthenticationError(
                        535, b'5.7.8 Username and Password not accepted'
                    )
                    r_err = self.client.post('/backup/enviar-email', follow_redirects=True)
                    self.assertEqual(r_err.status_code, 200)
                    html_err = r_err.get_data(as_text=True)
                    self.assertIn('Erro ao enviar backup por e-mail', html_err)
                    self.assertNotIn('Erro ao enviar backup por e-mail: Erro ao enviar', html_err)
                    self.assertIn('Senha de App', html_err)

                with self.app.app_context():
                    db = get_db()
                    log_err = db.execute(
                        "SELECT * FROM logs_auditoria WHERE acao = 'BACKUP_EMAIL' ORDER BY id DESC LIMIT 1"
                    ).fetchone()
                    self.assertIsNotNone(log_err)
                    self.assertIn('Falha ao enviar backup por e-mail', log_err['detalhes'])
                    self.assertIn('Senha de App', log_err['detalhes'])

                # 3) Desconexão abrupta durante server.login (caso real do Gmail com senha comum)
                with patch('smtplib.SMTP_SSL') as mock_smtp_disc:
                    mock_server_disc = mock_smtp_disc.return_value.__enter__.return_value
                    mock_server_disc.login.side_effect = smtplib.SMTPServerDisconnected(
                        'Connection unexpectedly closed'
                    )
                    r_disc = self.client.post('/backup/enviar-email', follow_redirects=True)
                    self.assertEqual(r_disc.status_code, 200)
                    html_disc = r_disc.get_data(as_text=True)
                    self.assertIn('Erro ao enviar backup por e-mail:', html_disc)
                    self.assertIn('encerrou a conexão durante a autenticação', html_disc)
                    self.assertIn('Senha de App de 16 letras', html_disc)
                    self.assertNotIn('Erro ao enviar backup por e-mail: Erro ao enviar', html_disc)

                # 4) Falha SMTP genérica sem prefixo duplicado na mensagem flash
                with patch('smtplib.SMTP_SSL') as mock_smtp_conn_err:
                    mock_server_conn_err = mock_smtp_conn_err.return_value.__enter__.return_value
                    mock_server_conn_err.send_message.side_effect = smtplib.SMTPException(
                        'Conexão recusada pelo servidor'
                    )
                    r_smtp_err = self.client.post('/backup/enviar-email', follow_redirects=True)
                    self.assertEqual(r_smtp_err.status_code, 200)
                    html_smtp_err = r_smtp_err.get_data(as_text=True)
                    self.assertIn('Erro ao enviar backup por e-mail: Conexão recusada pelo servidor', html_smtp_err)
                    self.assertNotIn('Erro ao enviar backup por e-mail: Erro ao enviar', html_smtp_err)

        print("[PASS] Teste 12: Página /backup/, envio de e-mail com .zip válido, erro sem duplicação e Senha de App validados.")

    def test_13_restauracao_via_upload(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            backups_dir = os.path.join(tmpdir, 'backups')
            os.makedirs(backups_dir, exist_ok=True)
            db_alvo = os.path.join(tmpdir, 'alvo_restore.db')
            db_fonte = os.path.join(tmpdir, 'fonte_valida.db')
            db_zip_fonte = os.path.join(tmpdir, 'fonte_zip.db')

            def _criar_db_com_paciente(caminho, prontuario, nome):
                init_db(caminho)
                conn = sqlite3.connect(caminho)
                try:
                    conn.execute(
                        "INSERT INTO pacientes (prontuario_num, nome) VALUES (?, ?)",
                        (prontuario, nome),
                    )
                    conn.commit()
                finally:
                    conn.close()

            _criar_db_com_paciente(db_alvo, '7000', 'Paciente Original Pre-Restore')
            _criar_db_com_paciente(db_fonte, '8001', 'Paciente Restaurado DB')
            _criar_db_com_paciente(db_zip_fonte, '8002', 'Paciente Restaurado ZIP')

            with open(db_fonte, 'rb') as f:
                bytes_db_valido = f.read()

            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
                zf.write(db_zip_fonte, arcname='casa_vida_backup_zip.db')
            bytes_zip_valido = zip_buf.getvalue()

            with patch.dict(self.app.config, {'DATABASE': db_alvo, 'BACKUPS_DIR': backups_dir}):
                # 1) Upload de .db válido restaura registros, cria backup pre_restauracao e grava log
                r_db = self.client.post(
                    '/backup/restaurar-arquivo',
                    data={'arquivo_backup': (io.BytesIO(bytes_db_valido), 'backup_valido.db')},
                    content_type='multipart/form-data',
                    follow_redirects=True,
                )
                self.assertEqual(r_db.status_code, 200)
                self.assertIn('restaurado com sucesso', r_db.get_data(as_text=True))

                with self.app.app_context():
                    db = get_db()
                    nomes = [r['nome'] for r in db.execute("SELECT nome FROM pacientes").fetchall()]
                    self.assertEqual(nomes, ['Paciente Restaurado DB'])
                    log_rest = db.execute(
                        "SELECT * FROM logs_auditoria WHERE acao = 'RESTAURACAO' ORDER BY id DESC LIMIT 1"
                    ).fetchone()
                    self.assertIsNotNone(log_rest)
                    self.assertIn('backup_valido.db', log_rest['detalhes'])

                pre_backups = [
                    f for f in os.listdir(backups_dir)
                    if f.startswith('casa_vida_backup_') and f.endswith('.db')
                ]
                self.assertEqual(len(pre_backups), 1)
                conn_pre = sqlite3.connect(os.path.join(backups_dir, pre_backups[0]))
                try:
                    nomes_pre = [r[0] for r in conn_pre.execute("SELECT nome FROM pacientes").fetchall()]
                finally:
                    conn_pre.close()
                self.assertEqual(nomes_pre, ['Paciente Original Pre-Restore'])

                # 2) Upload de .zip válido restaura os registros esperados
                r_zip = self.client.post(
                    '/backup/restaurar-arquivo',
                    data={'arquivo_backup': (io.BytesIO(bytes_zip_valido), 'backup_email.zip')},
                    content_type='multipart/form-data',
                    follow_redirects=True,
                )
                self.assertEqual(r_zip.status_code, 200)
                self.assertIn('restaurado com sucesso', r_zip.get_data(as_text=True))

                with self.app.app_context():
                    db = get_db()
                    nomes = [r['nome'] for r in db.execute("SELECT nome FROM pacientes").fetchall()]
                    self.assertEqual(nomes, ['Paciente Restaurado ZIP'])

                # 3) Rejeições seguras (sem corromper o banco atual)
                zip_sem_db_buf = io.BytesIO()
                with zipfile.ZipFile(zip_sem_db_buf, 'w') as zf:
                    zf.writestr('readme.txt', 'apenas texto')

                zip_slip_buf = io.BytesIO()
                with zipfile.ZipFile(zip_slip_buf, 'w') as zf:
                    zf.writestr('../evil.db', bytes_db_valido)

                casos_invalidos = [
                    (b'conteudo texto corrompido' * 10, 'corrompido.db'),
                    (b'qualquer texto', 'invalido.txt'),
                    (zip_sem_db_buf.getvalue(), 'sem_banco.zip'),
                    (zip_slip_buf.getvalue(), 'zip_slip.zip'),
                ]
                for payload, nome_arq in casos_invalidos:
                    r_inv = self.client.post(
                        '/backup/restaurar-arquivo',
                        data={'arquivo_backup': (io.BytesIO(payload), nome_arq)},
                        content_type='multipart/form-data',
                        follow_redirects=True,
                    )
                    self.assertEqual(r_inv.status_code, 200)
                    self.assertIn('Erro ao restaurar banco', r_inv.get_data(as_text=True))

                    with self.app.app_context():
                        db = get_db()
                        nomes = [r['nome'] for r in db.execute("SELECT nome FROM pacientes").fetchall()]
                        self.assertEqual(nomes, ['Paciente Restaurado ZIP'])

                self.assertFalse(os.path.exists(os.path.join(tmpdir, 'evil.db')))

        print("[PASS] Teste 13: Restauração via upload (.db e .zip), pre_restauracao e rejeições seguras validados.")

    def test_14_script_backup_semanal(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = os.path.join(tmpdir, 'data')
            backups_dir = os.path.join(tmpdir, 'backups')
            os.makedirs(data_dir, exist_ok=True)
            os.makedirs(backups_dir, exist_ok=True)
            db_semanal = os.path.join(data_dir, 'semanal_test.db')

            app_semanal = create_app({
                'TESTING': True,
                'DATABASE': db_semanal,
                'BACKUPS_DIR': backups_dir,
                'BACKUP_AUTO_RETENCAO': 8,
                'SMTP_HOST': 'smtp.gmail.com',
                'SMTP_PORT': 465,
                'SMTP_USE_SSL': True,
                'SMTP_USER': 'semanal@teste.org',
                'SMTP_PASSWORD': 'senha-app-mock',
                'BACKUP_EMAIL_DESTINO': 'destino@teste.org',
            })

            with patch.object(backup_semanal.config, 'DATA_DIR', data_dir), \
                 patch('app.create_app', return_value=app_semanal):
                # 1) Execução com --sem-email
                with patch('smtplib.SMTP_SSL') as mock_smtp_sem_email:
                    rc_sem_email = backup_semanal.main(['--sem-email'])
                    self.assertEqual(rc_sem_email, 0)
                    mock_smtp_sem_email.assert_not_called()

                autos = [
                    f for f in os.listdir(backups_dir)
                    if f.startswith('casa_vida_backup_auto_') and f.endswith('.db')
                ]
                self.assertEqual(len(autos), 1)
                self.assertTrue(os.path.exists(os.path.join(data_dir, 'backup_semanal.log')))

                # 2) Execução completa com SMTP_SSL mockado
                with patch('smtplib.SMTP_SSL') as mock_smtp_ok:
                    mock_server = mock_smtp_ok.return_value.__enter__.return_value
                    rc_email = backup_semanal.main([])
                    self.assertEqual(rc_email, 0)
                    mock_smtp_ok.assert_called_once()
                    mock_server.send_message.assert_called_once()

                autos_depois = [
                    f for f in os.listdir(backups_dir)
                    if f.startswith('casa_vida_backup_auto_') and f.endswith('.db')
                ]
                self.assertEqual(len(autos_depois), 2)

                with app_semanal.app_context():
                    db = get_db()
                    acoes = [
                        r['acao']
                        for r in db.execute("SELECT acao FROM logs_auditoria ORDER BY id ASC").fetchall()
                    ]
                    self.assertIn('BACKUP', acoes)
                    self.assertIn('BACKUP_EMAIL', acoes)

        print("[PASS] Teste 14: Script scripts/backup_semanal.py (--sem-email e SMTP mockado) validado.")

    def test_15_listar_backups_contagem_registros(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            def _criar_backup_com_pacientes(nome_arquivo, qtd):
                caminho = os.path.join(tmpdir, nome_arquivo)
                init_db(caminho)
                conn = sqlite3.connect(caminho)
                try:
                    for i in range(qtd):
                        conn.execute(
                            "INSERT INTO pacientes (prontuario_num, nome) VALUES (?, ?)",
                            (f'9{qtd}{i}', f'Paciente {nome_arquivo} #{i}'),
                        )
                    conn.commit()
                finally:
                    conn.close()
                return caminho

            bkp_17 = _criar_backup_com_pacientes('backup_17_pacientes.db', 17)
            bkp_3 = _criar_backup_com_pacientes('backup_3_pacientes.db', 3)
            bkp_0 = _criar_backup_com_pacientes('backup_0_pacientes.db', 0)

            bkp_sem_tabela = os.path.join(tmpdir, 'backup_sem_tabela.db')
            conn_sem = sqlite3.connect(bkp_sem_tabela)
            try:
                conn_sem.execute("CREATE TABLE outra_tabela (id INTEGER PRIMARY KEY)")
                conn_sem.commit()
            finally:
                conn_sem.close()

            bkp_corrompido = os.path.join(tmpdir, 'backup_corrompido.db')
            with open(bkp_corrompido, 'wb') as f:
                f.write(b'conteudo-invalido-nao-sqlite' * 5)

            self.assertEqual(contar_registros_backup(bkp_17), 17)
            self.assertEqual(contar_registros_backup(bkp_3), 3)
            self.assertEqual(contar_registros_backup(bkp_0), 0)
            self.assertIsNone(contar_registros_backup(bkp_sem_tabela))
            self.assertIsNone(contar_registros_backup(bkp_corrompido))
            self.assertIsNone(contar_registros_backup(os.path.join(tmpdir, 'inexistente.db')))

            with patch.dict(self.app.config, {'BACKUPS_DIR': tmpdir}):
                with self.app.app_context():
                    itens = listar_backups()

                por_nome = {item['nome']: item for item in itens}
                self.assertEqual(por_nome['backup_17_pacientes.db']['registros'], 17)
                self.assertEqual(por_nome['backup_3_pacientes.db']['registros'], 3)
                self.assertEqual(por_nome['backup_0_pacientes.db']['registros'], 0)
                self.assertIsNone(por_nome['backup_sem_tabela.db']['registros'])
                self.assertIsNone(por_nome['backup_corrompido.db']['registros'])

                r_bkp = self.client.get('/backup/')
                self.assertEqual(r_bkp.status_code, 200)
                html = r_bkp.get_data(as_text=True)
                self.assertIn('Registros', html)

                tbody = html[html.find('<tbody>'):html.find('</tbody>')]
                for nome_arq, esperado in (
                    ('backup_17_pacientes.db', '17'),
                    ('backup_3_pacientes.db', '3'),
                    ('backup_0_pacientes.db', '0'),
                ):
                    idx_nome = tbody.find(nome_arq)
                    self.assertNotEqual(idx_nome, -1)
                    idx_fim_tr = tbody.find('</tr>', idx_nome)
                    linha_html = tbody[idx_nome:idx_fim_tr]
                    self.assertIn(esperado, linha_html)

        print("[PASS] Teste 15: listar_backups() e GET /backup/ com contagem de registros e tolerância a inválidos validados.")


if __name__ == '__main__':
    unittest.main(verbosity=2)
