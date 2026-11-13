import os
import unittest
import io
import config
from app import create_app
from app.db import get_db, init_db
from werkzeug.security import check_password_hash

TEST_DB_PATH = os.path.join(config.DATA_DIR, 'test_casa_vida.db')

class TestCasaVida(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.path.exists(TEST_DB_PATH):
            os.remove(TEST_DB_PATH)
        cls.app = create_app({
            'TESTING': True,
            'DATABASE': TEST_DB_PATH,
            'WTF_CSRF_ENABLED': False
        })
        cls.client = cls.app.test_client()

    @classmethod
    def tearDownClass(cls):
        try:
            if os.path.exists(TEST_DB_PATH):
                os.remove(TEST_DB_PATH)
        except Exception:
            pass

    def test_01_db_init(self):
        with self.app.app_context():
            db = get_db()
            user = db.execute("SELECT * FROM usuarios WHERE username = 'admin'").fetchone()
            self.assertIsNotNone(user)
            self.assertTrue(check_password_hash(user['senha_hash'], 'admin123'))
            print("[PASS] Teste 01: Banco inicializado e usuário admin criado com sucesso.")

    def test_02_login(self):
        resp_err = self.client.post('/auth/login', data={'username': 'admin', 'senha': 'err'}, follow_redirects=True)
        self.assertIn(b'incorretos', resp_err.data)

        resp_ok = self.client.post('/auth/login', data={'username': 'admin', 'senha': 'admin123'}, follow_redirects=True)
        self.assertIn(b'Total de Assistidos', resp_ok.data)
        print("[PASS] Teste 02: Autenticação de usuário validada.")

    def test_03_cadastrar_paciente(self):
        self.client.post('/auth/login', data={'username': 'admin', 'senha': 'admin123'})
        
        resp = self.client.post('/novo', data={
            'nome': 'João da Silva Teste',
            'prontuario_num': 'CV-TESTE-001',
            'data_nascimento': '1970-05-15',
            'cpf': '123.456.789-00',
            'telefone': '(32) 98888-7777',
            'diagnostico': 'Neoplasia de Pulmão',
            'local_tratamento': 'ASCOMCER',
            'status_instituto': 'Ativo',
            'necessidades_apoio': ['Cesta Básica', 'Suplemento Alimentar']
        }, follow_redirects=True)

        self.assertEqual(resp.status_code, 200)
        self.assertIn('João da Silva Teste'.encode('utf-8'), resp.data)
        print("[PASS] Teste 03: Cadastro de assistido realizado com sucesso.")

    def test_04_atendimento(self):
        self.client.post('/auth/login', data={'username': 'admin', 'senha': 'admin123'})

        with self.app.app_context():
            db = get_db()
            p = db.execute("SELECT id FROM pacientes WHERE prontuario_num = 'CV-TESTE-001'").fetchone()
            paciente_id = p['id']

        resp = self.client.post(f'/{paciente_id}/atendimento/novo', data={
            'data_atendimento': '2026-11-11',
            'tipo': 'Entrega de Cesta Básica',
            'descricao': 'Entregue cesta de alimentos e 1 frasco de suplemento.',
            'profissional': 'Assistente Social Teste'
        }, follow_redirects=True)

        self.assertEqual(resp.status_code, 200)
        self.assertIn('Entrega de Cesta'.encode('utf-8'), resp.data)
        print("[PASS] Teste 04: Registro de atendimento e evolução gravado com sucesso.")

    def test_05_exportar_csv(self):
        self.client.post('/auth/login', data={'username': 'admin', 'senha': 'admin123'})
        resp = self.client.get('/exportar')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content_type, 'text/csv; charset=utf-8')
        self.assertIn('João da Silva Teste'.encode('utf-8'), resp.data)
        print("[PASS] Teste 05: Exportação CSV com UTF-8 gerada com sucesso.")

    def test_06_importar_planilha_csv(self):
        self.client.post('/auth/login', data={'username': 'admin', 'senha': 'admin123'})
        csv_conteudo = """Nome;CPF;Data Nasc;Telefone;Diagnostico;Hospital;Bairro;Cidade;Status;Observacoes
Maria Teste Planilha;999.888.777-66;12/03/1980;(32) 99123-4567;Câncer de Mama;ASCOMCER;Manoel Honório;Juiz de Fora;Ativo;Acolhida pelo projeto
"""
        data = {
            'arquivo_csv': (io.BytesIO(csv_conteudo.encode('utf-8')), 'planilha.csv')
        }
        resp = self.client.post('/importar', data=data, content_type='multipart/form-data', follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        with self.app.app_context():
            db = get_db()
            p = db.execute("SELECT * FROM pacientes WHERE cpf = '999.888.777-66'").fetchone()
            self.assertIsNotNone(p)
            self.assertEqual(p['nome'], 'Maria Teste Planilha')
            self.assertEqual(p['diagnostico'], 'Câncer de Mama')
            self.assertEqual(p['endereco_cidade'], 'Juiz de Fora')
        print("[PASS] Teste 06: Importação de planilha CSV validada.")

    def test_07_backup(self):
        self.client.post('/auth/login', data={'username': 'admin', 'senha': 'admin123'})
        resp = self.client.get('/backup/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Backups', resp.data)
        print("[PASS] Teste 07: Módulo de backups acessível.")

if __name__ == '__main__':
    unittest.main()
