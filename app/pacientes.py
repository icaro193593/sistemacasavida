import csv
import io
import datetime
from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for, Response, send_file
)
from app.auth import login_required, admin_required
from app.db import get_db, log_audit

bp = Blueprint('pacientes', __name__)

def gerar_numero_prontuario(db):
    ano_atual = datetime.date.today().year
    prefixo = f"CV-{ano_atual}-"
    row = db.execute(
        "SELECT prontuario_num FROM pacientes WHERE prontuario_num LIKE ? ORDER BY id DESC LIMIT 1",
        (f"{prefixo}%",)
    ).fetchone()

    if row and row['prontuario_num']:
        try:
            ultimo_seq = int(row['prontuario_num'].split('-')[-1])
            proximo_seq = ultimo_seq + 1
        except ValueError:
            proximo_seq = 1
    else:
        count = db.execute("SELECT COUNT(*) as c FROM pacientes").fetchone()['c']
        proximo_seq = count + 1

    return f"{prefixo}{proximo_seq:04d}"

def calcular_idade(data_nasc_str):
    if not data_nasc_str:
        return None
    try:
        nasc = datetime.datetime.strptime(data_nasc_str, "%Y-%m-%d").date()
        hoje = datetime.date.today()
        idade = hoje.year - nasc.year - ((hoje.month, hoje.day) < (nasc.month, nasc.day))
        return idade
    except Exception:
        return None

@bp.route('/')
@login_required
def index():
    termo = request.args.get('busca', '').strip()
    status_filtro = request.args.get('status', '').strip()
    diagnostico_filtro = request.args.get('diagnostico', '').strip()
    pagina = max(1, int(request.args.get('pagina', 1)))
    itens_por_pagina = 15
    offset = (pagina - 1) * itens_por_pagina

    db = get_db()

    query_base = "FROM pacientes WHERE 1=1"
    params = []

    if termo:
        query_base += " AND (nome LIKE ? OR prontuario_num LIKE ? OR cpf LIKE ? OR diagnostico LIKE ? OR telefone LIKE ?)"
        like_termo = f"%{termo}%"
        params.extend([like_termo, like_termo, like_termo, like_termo, like_termo])

    if status_filtro:
        query_base += " AND status_instituto = ?"
        params.append(status_filtro)

    if diagnostico_filtro:
        query_base += " AND diagnostico LIKE ?"
        params.append(f"%{diagnostico_filtro}%")

    count_row = db.execute(f"SELECT COUNT(*) as total {query_base}", params).fetchone()
    total_registros = count_row['total']
    total_paginas = max(1, (total_registros + itens_por_pagina - 1) // itens_por_pagina)

    query = f"""
        SELECT id, prontuario_num, nome, data_nascimento, cpf, telefone, whatsapp,
               diagnostico, local_tratamento, status_tratamento, status_instituto,
               endereco_bairro, endereco_cidade, atualizado_em
        {query_base}
        ORDER BY nome COLLATE NOCASE ASC
        LIMIT ? OFFSET ?
    """
    params_pag = list(params)
    params_pag.extend([itens_por_pagina, offset])
    pacientes = db.execute(query, params_pag).fetchall()

    stats = {
        'total': db.execute("SELECT COUNT(*) as c FROM pacientes").fetchone()['c'],
        'ativos': db.execute("SELECT COUNT(*) as c FROM pacientes WHERE status_instituto = 'Ativo'").fetchone()['c'],
        'espera': db.execute("SELECT COUNT(*) as c FROM pacientes WHERE status_instituto = 'Em Espera'").fetchone()['c'],
        'atendimentos_mes': db.execute(
            "SELECT COUNT(*) as c FROM atendimentos WHERE strftime('%Y-%m', data_atendimento) = strftime('%Y-%m', 'now')"
        ).fetchone()['c']
    }

    return render_template(
        'pacientes/index.html',
        pacientes=pacientes,
        termo=termo,
        status_filtro=status_filtro,
        diagnostico_filtro=diagnostico_filtro,
        pagina=pagina,
        total_paginas=total_paginas,
        total_registros=total_registros,
        stats=stats
    )

@bp.route('/novo', methods=('GET', 'POST'))
@login_required
def novo():
    db = get_db()

    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        prontuario_num = request.form.get('prontuario_num', '').strip() or gerar_numero_prontuario(db)
        data_nascimento = request.form.get('data_nascimento', '').strip()
        cpf = request.form.get('cpf', '').strip()
        rg = request.form.get('rg', '').strip()
        sexo = request.form.get('sexo', '').strip()
        estado_civil = request.form.get('estado_civil', '').strip()
        telefone = request.form.get('telefone', '').strip()
        whatsapp = request.form.get('whatsapp', '').strip()
        email = request.form.get('email', '').strip()

        nome_responsavel = request.form.get('nome_responsavel', '').strip()
        telefone_responsavel = request.form.get('telefone_responsavel', '').strip()
        parentesco_responsavel = request.form.get('parentesco_responsavel', '').strip()

        endereco_cep = request.form.get('endereco_cep', '').strip()
        endereco_logradouro = request.form.get('endereco_logradouro', '').strip()
        endereco_numero = request.form.get('endereco_numero', '').strip()
        endereco_complemento = request.form.get('endereco_complemento', '').strip()
        endereco_bairro = request.form.get('endereco_bairro', '').strip()
        endereco_cidade = request.form.get('endereco_cidade', '').strip() or 'Juiz de Fora'
        endereco_uf = request.form.get('endereco_uf', '').strip() or 'MG'
        endereco_referencia = request.form.get('endereco_referencia', '').strip()

        diagnostico = request.form.get('diagnostico', '').strip()
        local_tratamento = request.form.get('local_tratamento', '').strip()
        medico_responsavel = request.form.get('medico_responsavel', '').strip()
        data_diagnostico = request.form.get('data_diagnostico', '').strip()
        estadiamento = request.form.get('estadiamento', '').strip()
        status_tratamento = request.form.get('status_tratamento', 'Em tratamento').strip()
        medicamentos_em_uso = request.form.get('medicamentos_em_uso', '').strip()
        
        necessidades_lista = request.form.getlist('necessidades_apoio')
        outras_necessidades = request.form.get('outras_necessidades', '').strip()
        if outras_necessidades:
            necessidades_lista.append(outras_necessidades)
        necessidades_apoio = ", ".join(necessidades_lista)

        renda_familiar = request.form.get('renda_familiar', '').strip()
        beneficio_social = request.form.get('beneficio_social', '').strip()
        ocupacao = request.form.get('ocupacao', '').strip()
        try:
            qtd_moradores = int(request.form.get('qtd_moradores', 1) or 1)
        except ValueError:
            qtd_moradores = 1

        status_instituto = request.form.get('status_instituto', 'Ativo').strip()
        observacoes = request.form.get('observacoes', '').strip()

        if not nome:
            flash('O nome do paciente é obrigatório.', 'danger')
        else:
            try:
                cur = db.execute("""
                    INSERT INTO pacientes (
                        prontuario_num, nome, data_nascimento, cpf, rg, sexo, estado_civil,
                        telefone, whatsapp, email,
                        nome_responsavel, telefone_responsavel, parentesco_responsavel,
                        endereco_cep, endereco_logradouro, endereco_numero, endereco_complemento,
                        endereco_bairro, endereco_cidade, endereco_uf, endereco_referencia,
                        diagnostico, local_tratamento, medico_responsavel, data_diagnostico,
                        estadiamento, status_tratamento, medicamentos_em_uso, necessidades_apoio,
                        renda_familiar, beneficio_social, ocupacao, qtd_moradores,
                        status_instituto, observacoes, criado_por, atualizado_por
                    ) VALUES (
                        ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?,
                        ?, ?, ?,
                        ?, ?, ?, ?,
                        ?, ?, ?, ?,
                        ?, ?, ?, ?,
                        ?, ?, ?, ?,
                        ?, ?, ?, ?,
                        ?, ?, ?, ?
                    )
                """, (
                    prontuario_num, nome, data_nascimento or None, cpf or None, rg, sexo, estado_civil,
                    telefone, whatsapp, email,
                    nome_responsavel, telefone_responsavel, parentesco_responsavel,
                    endereco_cep, endereco_logradouro, endereco_numero, endereco_complemento,
                    endereco_bairro, endereco_cidade, endereco_uf, endereco_referencia,
                    diagnostico, local_tratamento, medico_responsavel, data_diagnostico or None,
                    estadiamento, status_tratamento, medicamentos_em_uso, necessidades_apoio,
                    renda_familiar, beneficio_social, ocupacao, qtd_moradores,
                    status_instituto, observacoes, g.user['id'], g.user['id']
                ))
                db.commit()
                novo_id = cur.lastrowid
                log_audit('CADASTRO', f"Paciente {nome} cadastrado (ID {novo_id}, Prontuário {prontuario_num})", g.user['id'], g.user['nome_completo'])
                flash(f'Paciente "{nome}" cadastrado com sucesso!', 'success')
                return redirect(url_for('pacientes.detalhes', id=novo_id))
            except Exception as e:
                db.rollback()
                if "UNIQUE constraint failed: pacientes.cpf" in str(e):
                    flash('Já existe um paciente cadastrado com este CPF.', 'danger')
                elif "UNIQUE constraint failed: pacientes.prontuario_num" in str(e):
                    flash('Já existe um paciente cadastrado com este número de prontuário.', 'danger')
                else:
                    flash(f'Erro ao cadastrar paciente: {e}', 'danger')

    prontuario_sugerido = gerar_numero_prontuario(db)
    return render_template('pacientes/novo.html', prontuario_sugerido=prontuario_sugerido)

@bp.route('/<int:id>')
@login_required
def detalhes(id):
    db = get_db()
    paciente = db.execute("SELECT * FROM pacientes WHERE id = ?", (id,)).fetchone()
    if not paciente:
        flash('Paciente não encontrado.', 'warning')
        return redirect(url_for('pacientes.index'))

    atendimentos = db.execute("""
        SELECT a.*, u.nome_completo AS usuario_nome
        FROM atendimentos a
        LEFT JOIN usuarios u ON a.usuario_id = u.id
        WHERE a.paciente_id = ?
        ORDER BY a.data_atendimento DESC, a.id DESC
    """, (id,)).fetchall()

    idade = calcular_idade(paciente['data_nascimento'])

    return render_template(
        'pacientes/detalhes.html',
        paciente=paciente,
        atendimentos=atendimentos,
        idade=idade,
        hoje=datetime.date.today().strftime('%Y-%m-%d')
    )

@bp.route('/<int:id>/editar', methods=('GET', 'POST'))
@login_required
def editar(id):
    db = get_db()
    paciente = db.execute("SELECT * FROM pacientes WHERE id = ?", (id,)).fetchone()
    if not paciente:
        flash('Paciente não encontrado.', 'warning')
        return redirect(url_for('pacientes.index'))

    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        prontuario_num = request.form.get('prontuario_num', '').strip()
        data_nascimento = request.form.get('data_nascimento', '').strip()
        cpf = request.form.get('cpf', '').strip()
        rg = request.form.get('rg', '').strip()
        sexo = request.form.get('sexo', '').strip()
        estado_civil = request.form.get('estado_civil', '').strip()
        telefone = request.form.get('telefone', '').strip()
        whatsapp = request.form.get('whatsapp', '').strip()
        email = request.form.get('email', '').strip()

        nome_responsavel = request.form.get('nome_responsavel', '').strip()
        telefone_responsavel = request.form.get('telefone_responsavel', '').strip()
        parentesco_responsavel = request.form.get('parentesco_responsavel', '').strip()

        endereco_cep = request.form.get('endereco_cep', '').strip()
        endereco_logradouro = request.form.get('endereco_logradouro', '').strip()
        endereco_numero = request.form.get('endereco_numero', '').strip()
        endereco_complemento = request.form.get('endereco_complemento', '').strip()
        endereco_bairro = request.form.get('endereco_bairro', '').strip()
        endereco_cidade = request.form.get('endereco_cidade', '').strip() or 'Juiz de Fora'
        endereco_uf = request.form.get('endereco_uf', '').strip() or 'MG'
        endereco_referencia = request.form.get('endereco_referencia', '').strip()

        diagnostico = request.form.get('diagnostico', '').strip()
        local_tratamento = request.form.get('local_tratamento', '').strip()
        medico_responsavel = request.form.get('medico_responsavel', '').strip()
        data_diagnostico = request.form.get('data_diagnostico', '').strip()
        estadiamento = request.form.get('estadiamento', '').strip()
        status_tratamento = request.form.get('status_tratamento', '').strip()
        medicamentos_em_uso = request.form.get('medicamentos_em_uso', '').strip()

        necessidades_lista = request.form.getlist('necessidades_apoio')
        outras_necessidades = request.form.get('outras_necessidades', '').strip()
        if outras_necessidades:
            necessidades_lista.append(outras_necessidades)
        necessidades_apoio = ", ".join(necessidades_lista)

        renda_familiar = request.form.get('renda_familiar', '').strip()
        beneficio_social = request.form.get('beneficio_social', '').strip()
        ocupacao = request.form.get('ocupacao', '').strip()
        try:
            qtd_moradores = int(request.form.get('qtd_moradores', 1) or 1)
        except ValueError:
            qtd_moradores = 1

        status_instituto = request.form.get('status_instituto', 'Ativo').strip()
        observacoes = request.form.get('observacoes', '').strip()

        if not nome:
            flash('O nome do paciente é obrigatório.', 'danger')
        else:
            try:
                db.execute("""
                    UPDATE pacientes SET
                        prontuario_num = ?, nome = ?, data_nascimento = ?, cpf = ?, rg = ?, sexo = ?, estado_civil = ?,
                        telefone = ?, whatsapp = ?, email = ?,
                        nome_responsavel = ?, telefone_responsavel = ?, parentesco_responsavel = ?,
                        endereco_cep = ?, endereco_logradouro = ?, endereco_numero = ?, endereco_complemento = ?,
                        endereco_bairro = ?, endereco_cidade = ?, endereco_uf = ?, endereco_referencia = ?,
                        diagnostico = ?, local_tratamento = ?, medico_responsavel = ?, data_diagnostico = ?,
                        estadiamento = ?, status_tratamento = ?, medicamentos_em_uso = ?, necessidades_apoio = ?,
                        renda_familiar = ?, beneficio_social = ?, ocupacao = ?, qtd_moradores = ?,
                        status_instituto = ?, observacoes = ?,
                        atualizado_em = CURRENT_TIMESTAMP, atualizado_por = ?
                    WHERE id = ?
                """, (
                    prontuario_num or None, nome, data_nascimento or None, cpf or None, rg, sexo, estado_civil,
                    telefone, whatsapp, email,
                    nome_responsavel, telefone_responsavel, parentesco_responsavel,
                    endereco_cep, endereco_logradouro, endereco_numero, endereco_complemento,
                    endereco_bairro, endereco_cidade, endereco_uf, endereco_referencia,
                    diagnostico, local_tratamento, medico_responsavel, data_diagnostico or None,
                    estadiamento, status_tratamento, medicamentos_em_uso, necessidades_apoio,
                    renda_familiar, beneficio_social, ocupacao, qtd_moradores,
                    status_instituto, observacoes, g.user['id'], id
                ))
                db.commit()
                log_audit('EDICAO', f"Paciente {nome} (ID {id}) atualizado", g.user['id'], g.user['nome_completo'])
                flash('Cadastro do paciente atualizado com sucesso!', 'success')
                return redirect(url_for('pacientes.detalhes', id=id))
            except Exception as e:
                db.rollback()
                flash(f'Erro ao atualizar registro: {e}', 'danger')

    return render_template('pacientes/editar.html', paciente=paciente)

@bp.route('/<int:id>/atendimento/novo', methods=('POST',))
@login_required
def novo_atendimento(id):
    db = get_db()
    paciente = db.execute("SELECT id, nome FROM pacientes WHERE id = ?", (id,)).fetchone()
    if not paciente:
        flash('Paciente não encontrado.', 'danger')
        return redirect(url_for('pacientes.index'))

    data_atendimento = request.form.get('data_atendimento', '').strip() or datetime.date.today().strftime('%Y-%m-%d')
    tipo = request.form.get('tipo', 'Atendimento Geral').strip()
    descricao = request.form.get('descricao', '').strip()
    profissional = request.form.get('profissional', '').strip() or g.user['nome_completo']

    if not descricao:
        flash('Descreva o atendimento ou benefício entregue.', 'warning')
        return redirect(url_for('pacientes.detalhes', id=id))

    db.execute("""
        INSERT INTO atendimentos (paciente_id, data_atendimento, tipo, descricao, profissional, usuario_id)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (id, data_atendimento, tipo, descricao, profissional, g.user['id']))
    db.commit()

    log_audit('ATENDIMENTO', f"Atendimento ({tipo}) registrado para o paciente {paciente['nome']}", g.user['id'], g.user['nome_completo'])
    flash('Atendimento registrado com sucesso!', 'success')
    return redirect(url_for('pacientes.detalhes', id=id))

@bp.route('/<int:id>/excluir', methods=('POST',))
@admin_required
def excluir(id):
    db = get_db()
    paciente = db.execute("SELECT id, nome FROM pacientes WHERE id = ?", (id,)).fetchone()
    if paciente:
        db.execute("DELETE FROM pacientes WHERE id = ?", (id,))
        db.commit()
        log_audit('EXCLUSAO', f"Paciente {paciente['nome']} (ID {id}) removido", g.user['id'], g.user['nome_completo'])
        flash(f'Registro de "{paciente["nome"]}" foi excluído com sucesso.', 'info')
    return redirect(url_for('pacientes.index'))

@bp.route('/exportar')
@login_required
def exportar_csv():
    db = get_db()
    pacientes = db.execute("""
        SELECT prontuario_num, nome, data_nascimento, cpf, rg, sexo, estado_civil,
               telefone, whatsapp, email, nome_responsavel, telefone_responsavel, parentesco_responsavel,
               endereco_cep, endereco_logradouro, endereco_numero, endereco_complemento,
               endereco_bairro, endereco_cidade, endereco_uf,
               diagnostico, local_tratamento, medico_responsavel, data_diagnostico, estadiamento,
               status_tratamento, medicamentos_em_uso, necessidades_apoio,
               renda_familiar, beneficio_social, ocupacao, qtd_moradores,
               status_instituto, observacoes, criado_em, atualizado_em
        FROM pacientes
        ORDER BY nome COLLATE NOCASE ASC
    """).fetchall()

    output = io.StringIO()
    output.write('\ufeff')
    writer = csv.writer(output, delimiter=';')

    colunas = [
        'Prontuário', 'Nome Completo', 'Data de Nascimento', 'CPF', 'RG', 'Sexo', 'Estado Civil',
        'Telefone', 'WhatsApp', 'E-mail', 'Responsável/Acompanhante', 'Tel. Responsável', 'Parentesco',
        'CEP', 'Logradouro', 'Número', 'Complemento', 'Bairro', 'Cidade', 'UF',
        'Diagnóstico Oncológico', 'Hospital/Local Tratamento', 'Médico Responsável', 'Data Diagnóstico', 'Estadiamento',
        'Status do Tratamento', 'Medicamentos em Uso', 'Necessidades de Apoio',
        'Renda Familiar', 'Benefício Social', 'Ocupação', 'Qtd Moradores',
        'Status no Instituto', 'Observações', 'Data de Cadastro', 'Última Atualização'
    ]
    writer.writerow(colunas)

    for p in pacientes:
        writer.writerow([
            p['prontuario_num'] or '',
            p['nome'] or '',
            p['data_nascimento'] or '',
            p['cpf'] or '',
            p['rg'] or '',
            p['sexo'] or '',
            p['estado_civil'] or '',
            p['telefone'] or '',
            p['whatsapp'] or '',
            p['email'] or '',
            p['nome_responsavel'] or '',
            p['telefone_responsavel'] or '',
            p['parentesco_responsavel'] or '',
            p['endereco_cep'] or '',
            p['endereco_logradouro'] or '',
            p['endereco_numero'] or '',
            p['endereco_complemento'] or '',
            p['endereco_bairro'] or '',
            p['endereco_cidade'] or '',
            p['endereco_uf'] or '',
            p['diagnostico'] or '',
            p['local_tratamento'] or '',
            p['medico_responsavel'] or '',
            p['data_diagnostico'] or '',
            p['estadiamento'] or '',
            p['status_tratamento'] or '',
            p['medicamentos_em_uso'] or '',
            p['necessidades_apoio'] or '',
            p['renda_familiar'] or '',
            p['beneficio_social'] or '',
            p['ocupacao'] or '',
            p['qtd_moradores'] or 1,
            p['status_instituto'] or '',
            (p['observacoes'] or '').replace('\n', ' '),
            p['criado_em'] or '',
            p['atualizado_em'] or ''
        ])

    data_str = datetime.date.today().strftime('%Y%m%d')
    nome_arquivo = f"assistidos_casa_vida_{data_str}.csv"
    
    log_audit('EXPORTACAO', f"Exportação completa de {len(pacientes)} assistidos para CSV", g.user['id'], g.user['nome_completo'])

    return Response(
        output.getvalue().encode('utf-8-sig'),
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename={nome_arquivo}"}
    )

@bp.route('/importar', methods=('GET', 'POST'))
@login_required
def importar():
    if request.method == 'POST':
        arquivo = request.files.get('arquivo_csv')
        if not arquivo or arquivo.filename == '':
            flash('Selecione um arquivo CSV para importar.', 'warning')
            return redirect(url_for('pacientes.importar'))

        if not arquivo.filename.lower().endswith('.csv'):
            flash('Por favor envie um arquivo com extensão .csv.', 'danger')
            return redirect(url_for('pacientes.importar'))

        try:
            bytes_conteudo = arquivo.read()
            try:
                texto = bytes_conteudo.decode('utf-8-sig')
            except UnicodeDecodeError:
                texto = bytes_conteudo.decode('latin-1')

            primeira_linha = texto.splitlines()[0] if texto.splitlines() else ''
            delimitador = ';' if primeira_linha.count(';') > primeira_linha.count(',') else ','

            leitor = csv.DictReader(io.StringIO(texto), delimiter=delimitador)
            
            mapeamento = {}
            for col in (leitor.fieldnames or []):
                col_limpa = col.strip().lower()
                if 'nome' in col_limpa and not any(k in col_limpa for k in ['mãe', 'mae', 'resp', 'cuidador']):
                    mapeamento['nome'] = col
                elif 'cpf' in col_limpa:
                    mapeamento['cpf'] = col
                elif 'nasc' in col_limpa or 'anivers' in col_limpa:
                    mapeamento['data_nascimento'] = col
                elif 'tel' in col_limpa or 'contato' in col_limpa or 'cel' in col_limpa:
                    if 'zap' in col_limpa or 'whats' in col_limpa:
                        mapeamento['whatsapp'] = col
                    elif 'telefone' not in mapeamento:
                        mapeamento['telefone'] = col
                elif 'cidade' in col_limpa or 'municipio' in col_limpa:
                    mapeamento['endereco_cidade'] = col
                elif 'bairro' in col_limpa:
                    mapeamento['endereco_bairro'] = col
                elif 'diag' in col_limpa or 'câncer' in col_limpa or 'cancer' in col_limpa or 'patologia' in col_limpa or col_limpa == 'cid' or 'cid-' in col_limpa or 'cid ' in col_limpa:
                    mapeamento['diagnostico'] = col
                elif 'hospital' in col_limpa or 'local' in col_limpa or ('tratamento' in col_limpa and 'status' not in col_limpa):
                    mapeamento['local_tratamento'] = col
                elif 'endere' in col_limpa or 'rua' in col_limpa or 'logradouro' in col_limpa:
                    mapeamento['endereco_logradouro'] = col
                elif 'status' in col_limpa:
                    mapeamento['status_instituto'] = col
                elif 'obs' in col_limpa:
                    mapeamento['observacoes'] = col
                elif 'pront' in col_limpa or 'registro' in col_limpa:
                    mapeamento['prontuario_num'] = col
                elif 'resp' in col_limpa or 'cuidador' in col_limpa or 'acompanhante' in col_limpa:
                    mapeamento['nome_responsavel'] = col
                elif 'necess' in col_limpa or 'apoio' in col_limpa or 'benef' in col_limpa:
                    mapeamento['necessidades_apoio'] = col

            if 'nome' not in mapeamento:
                flash('Não foi possível identificar a coluna de "Nome" no arquivo CSV. Verifique o cabeçalho da planilha.', 'danger')
                return redirect(url_for('pacientes.importar'))

            db = get_db()
            sucessos = 0
            duplicados = 0
            erros = 0

            for linha in leitor:
                nome_val = (linha.get(mapeamento.get('nome', '')) or '').strip()
                if not nome_val:
                    continue

                cpf_val = (linha.get(mapeamento.get('cpf', '')) or '').strip() or None
                if cpf_val:
                    cpf_limpo = ''.join(filter(str.isdigit, cpf_val))
                    if len(cpf_limpo) == 11:
                        cpf_val = f"{cpf_limpo[:3]}.{cpf_limpo[3:6]}.{cpf_limpo[6:9]}-{cpf_limpo[9:]}"

                existente = None
                if cpf_val:
                    existente = db.execute("SELECT id FROM pacientes WHERE cpf = ?", (cpf_val,)).fetchone()
                if not existente:
                    existente = db.execute("SELECT id FROM pacientes WHERE nome = ? COLLATE NOCASE", (nome_val,)).fetchone()

                if existente:
                    duplicados += 1
                    continue

                prontuario_val = (linha.get(mapeamento.get('prontuario_num', '')) or '').strip() or gerar_numero_prontuario(db)
                data_nasc_val = (linha.get(mapeamento.get('data_nascimento', '')) or '').strip() or None
                if data_nasc_val and '/' in data_nasc_val:
                    partes = data_nasc_val.split('/')
                    if len(partes) == 3:
                        data_nasc_val = f"{partes[2]}-{partes[1].zfill(2)}-{partes[0].zfill(2)}"

                telefone_val = (linha.get(mapeamento.get('telefone', '')) or '').strip()
                whatsapp_val = (linha.get(mapeamento.get('whatsapp', '')) or '').strip()
                diagnostico_val = (linha.get(mapeamento.get('diagnostico', '')) or '').strip()
                local_tratamento_val = (linha.get(mapeamento.get('local_tratamento', '')) or '').strip()
                endereco_bairro_val = (linha.get(mapeamento.get('endereco_bairro', '')) or '').strip()
                endereco_cidade_val = (linha.get(mapeamento.get('endereco_cidade', '')) or '').strip() or 'Juiz de Fora'
                endereco_logradouro_val = (linha.get(mapeamento.get('endereco_logradouro', '')) or '').strip()
                status_inst_val = (linha.get(mapeamento.get('status_instituto', '')) or '').strip() or 'Ativo'
                nome_resp_val = (linha.get(mapeamento.get('nome_responsavel', '')) or '').strip()
                necessidades_val = (linha.get(mapeamento.get('necessidades_apoio', '')) or '').strip()
                observacoes_val = (linha.get(mapeamento.get('observacoes', '')) or '').strip()

                try:
                    db.execute("""
                        INSERT INTO pacientes (
                            prontuario_num, nome, data_nascimento, cpf, telefone, whatsapp,
                            diagnostico, local_tratamento, endereco_bairro, endereco_cidade,
                            endereco_logradouro, status_instituto, nome_responsavel,
                            necessidades_apoio, observacoes, criado_por, atualizado_por
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        prontuario_val, nome_val, data_nasc_val, cpf_val, telefone_val, whatsapp_val,
                        diagnostico_val, local_tratamento_val, endereco_bairro_val, endereco_cidade_val,
                        endereco_logradouro_val, status_inst_val, nome_resp_val,
                        necessidades_val, observacoes_val, g.user['id'], g.user['id']
                    ))
                    sucessos += 1
                except Exception:
                    erros += 1

            db.commit()
            log_audit('IMPORTACAO', f"Planilha importada: {sucessos} novos pacientes, {duplicados} já existentes ignorados, {erros} erros.", g.user['id'], g.user['nome_completo'])
            flash(f"Importação concluída! {sucessos} pacientes adicionados com sucesso, {duplicados} já existentes ignorados.", "success")
            return redirect(url_for('pacientes.index'))

        except Exception as e:
            flash(f"Erro ao processar o arquivo CSV: {e}", "danger")

    return render_template('pacientes/importar.html')
