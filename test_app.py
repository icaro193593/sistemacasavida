import os
import unittest
from unittest.mock import patch
import config
from app import create_app
from app.db import get_db

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
        self.assertIn('Backups e Segurança dos Dados', r_bkp.get_data(as_text=True))
        print("[PASS] Teste 07: Logs, exportação CSV 13 colunas e backups validados.")

    def test_08_ordenacao_filtro_matematico_e_exportacao_sincronizada(self):
        # Filtro comparativo de data: DN > 1970 (deve pegar Maria 1982, não João 1970)
        r_dn = self.client.get('/', query_string={'busca': '1970', 'coluna': 'dn', 'operador': 'maior'})
        self.assertEqual(r_dn.status_code, 200)
        html_dn = r_dn.get_data(as_text=True)
        self.assertIn('Maria Oliveira Santos', html_dn)
        self.assertNotIn('João da Silva Teste', html_dn)

        # Mesmo filtro digitado direto na busca ('> 1970')
        r_dn_inline = self.client.get('/', query_string={'busca': '> 1970', 'coluna': 'dn'})
        html_dn_inline = r_dn_inline.get_data(as_text=True)
        self.assertIn('Maria Oliveira Santos', html_dn_inline)
        self.assertNotIn('João da Silva Teste', html_dn_inline)

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


if __name__ == '__main__':
    unittest.main(verbosity=2)
