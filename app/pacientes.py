import csv
import io
import datetime
from flask import (
    Blueprint, current_app, flash, jsonify, redirect, render_template, request, url_for, Response
)
from app.db import get_db, log_audit
from app.sheets_sync import sincronizar_csv_no_banco, sincronizar_google_sheets

bp = Blueprint('pacientes', __name__)

COLUNAS_PLANILHA = [
    ('prontuario_num', 'Prontuário', True),
    ('nome', 'Nome', True),
    ('endereco', 'Endereço', True),
    ('responsavel_1', 'Responsável 1', True),
    ('telefone_1', 'Telefone 1', True),
    ('responsavel_2', 'Responsável 2', True),
    ('telefone_2', 'Telefone 2', True),
    ('telefone_3', 'Telefone 3', True),
    ('dn', 'DN', True),
    ('identidade', 'ID', True),
    ('cpf', 'CPF', True),
    ('obs', 'Obs', True),
    ('carimbo_data_hora', 'Carimbo de data/hora', False),
]

CAMPOS_PLANILHA = {col: label for col, label, editavel in COLUNAS_PLANILHA if editavel}

_CHAVES_PLANILHA = [col for col, _, _ in COLUNAS_PLANILHA]
_LABELS_POR_COLUNA = {col: label for col, label, _ in COLUNAS_PLANILHA}
_CLAUSULA_CPF_SEM_PONTOS = "REPLACE(REPLACE(COALESCE(cpf, ''), '.', ''), '-', '') LIKE ?"

OPERADORES_FILTRO = [
    ('contem', 'Contém'),
    ('igual', 'Igual a (=)'),
    ('maior', 'Maior que (>)'),
    ('maior_igual', 'Maior ou igual (>=)'),
    ('menor', 'Menor que (<)'),
    ('menor_igual', 'Menor ou igual (<=)'),
]
_OPERADORES_VALIDOS = {op for op, _ in OPERADORES_FILTRO}
_MAPA_OP_SQL = {
    'igual': '=',
    'maior': '>',
    'maior_igual': '>=',
    'menor': '<',
    'menor_igual': '<=',
}
_COLUNAS_DATA = {'dn', 'carimbo_data_hora'}

FILTROS_COLUNAS = {
    'todas': (
        "("
        + " OR ".join(f"{col} LIKE ?" for col in _CHAVES_PLANILHA)
        + f" OR {_CLAUSULA_CPF_SEM_PONTOS})"
    ),
    **{
        col: (
            f"(cpf LIKE ? OR {_CLAUSULA_CPF_SEM_PONTOS})"
            if col == 'cpf'
            else f"{col} LIKE ?"
        )
        for col in _CHAVES_PLANILHA
    },
}

COLUNAS_EXPORTACAO = [
    ('carimbo_data_hora', 'Carimbo de data/hora'),
] + [(col, label) for col, label, editavel in COLUNAS_PLANILHA if editavel]


def _sql_expr_data_ordenavel(col):
    """Converte DD/MM/YYYY ou YYYY-MM-DD em YYYYMMDD para comparação/ordenação no SQLite."""
    return (
        f"CASE "
        f"WHEN {col} LIKE '__/__/____%' THEN substr({col}, 7, 4) || substr({col}, 4, 2) || substr({col}, 1, 2) "
        f"WHEN {col} LIKE '____-__-__%' THEN substr({col}, 1, 4) || substr({col}, 6, 2) || substr({col}, 9, 2) "
        f"ELSE '' END"
    )


def _sql_expr_carimbo_ordenavel():
    """Converte DD/MM/YYYY HH:MM:SS em YYYYMMDDHH:MM:SS para ordenação cronológica exata."""
    return (
        "CASE "
        "WHEN carimbo_data_hora LIKE '__/__/____%' THEN "
        "substr(carimbo_data_hora, 7, 4) || substr(carimbo_data_hora, 4, 2) || substr(carimbo_data_hora, 1, 2) || substr(carimbo_data_hora, 11) "
        "WHEN carimbo_data_hora LIKE '____-__-__%' THEN "
        "substr(carimbo_data_hora, 1, 4) || substr(carimbo_data_hora, 6, 2) || substr(carimbo_data_hora, 9, 2) || substr(carimbo_data_hora, 11) "
        "ELSE '' END"
    )


def _parse_valor_data_filtro(texto):
    """Retorna ('ano', 'YYYY') ou ('data', 'YYYYMMDD') ou None."""
    s = (texto or '').strip()
    if len(s) == 4 and s.isdigit():
        return ('ano', s)
    parte = s.split()[0] if s else ''
    for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%Y/%m/%d'):
        try:
            dt = datetime.datetime.strptime(parte, fmt)
            return ('data', dt.strftime('%Y%m%d'))
        except ValueError:
            continue
    return None


def _extrair_operador_do_termo(termo, operador_atual):
    """Permite digitar operadores como '> 1970' ou '>= 01/01/1970' direto na busca."""
    if operador_atual != 'contem' or not termo:
        return operador_atual, termo
    prefixos = (
        ('>=', 'maior_igual'),
        ('<=', 'menor_igual'),
        ('>', 'maior'),
        ('<', 'menor'),
        ('=', 'igual'),
    )
    for pref, op in prefixos:
        if termo.startswith(pref) and len(termo) > len(pref):
            resto = termo[len(pref):].strip()
            if resto:
                return op, resto
    return operador_atual, termo


def _construir_clausula_order_by(ordem, direcao):
    dir_sql = 'DESC' if direcao == 'desc' else 'ASC'
    if ordem not in _CHAVES_PLANILHA:
        ordem = 'nome'

    vazio_por_ultimo = f"CASE WHEN {ordem} IS NULL OR TRIM({ordem}) = '' THEN 1 ELSE 0 END ASC"

    if ordem == 'prontuario_num':
        return (
            f"{vazio_por_ultimo}, "
            f"CASE WHEN prontuario_num GLOB '[0-9]*' THEN 0 ELSE 1 END ASC, "
            f"CAST(prontuario_num AS INTEGER) {dir_sql}, "
            f"prontuario_num COLLATE PT_BR {dir_sql}"
        )
    if ordem == 'dn':
        expr = _sql_expr_data_ordenavel('dn')
        return f"CASE WHEN ({expr}) = '' THEN 1 ELSE 0 END ASC, ({expr}) {dir_sql}, nome COLLATE PT_BR ASC"
    if ordem == 'carimbo_data_hora':
        expr = _sql_expr_carimbo_ordenavel()
        return f"CASE WHEN ({expr}) = '' THEN 1 ELSE 0 END ASC, ({expr}) {dir_sql}, id {dir_sql}"

    return f"{vazio_por_ultimo}, {ordem} COLLATE PT_BR {dir_sql}, nome COLLATE PT_BR ASC"


def _construir_consulta_pacientes(args):
    """Constrói cláusula WHERE, parâmetros e ORDER BY compartilhados entre listagem e exportação CSV."""
    termo_original = (args.get('busca') or '').strip()
    coluna_filtro = (args.get('coluna') or 'todas').strip() or 'todas'
    if coluna_filtro not in FILTROS_COLUNAS:
        coluna_filtro = 'todas'

    operador_filtro = (args.get('operador') or 'contem').strip() or 'contem'
    if operador_filtro not in _OPERADORES_VALIDOS:
        operador_filtro = 'contem'

    ordem = (args.get('ordem') or 'nome').strip() or 'nome'
    if ordem not in _CHAVES_PLANILHA:
        ordem = 'nome'

    direcao = (args.get('dir') or 'asc').strip().lower()
    if direcao not in ('asc', 'desc'):
        direcao = 'asc'

    query_base = "FROM pacientes WHERE 1=1"
    params = []

    if termo_original:
        op_efetivo, termo_efetivo = _extrair_operador_do_termo(termo_original, operador_filtro)

        if op_efetivo == 'contem' or coluna_filtro == 'todas':
            like_termo = f"%{termo_efetivo}%"
            apenas_digitos = ''.join(filter(str.isdigit, termo_efetivo))
            like_cpf_digitos = f"%{apenas_digitos}%" if apenas_digitos else like_termo

            query_base += f" AND {FILTROS_COLUNAS[coluna_filtro]}"
            if coluna_filtro == 'todas':
                params.extend([like_termo] * len(_CHAVES_PLANILHA) + [like_cpf_digitos])
            elif coluna_filtro == 'cpf':
                params.extend([like_termo, like_cpf_digitos])
            else:
                params.append(like_termo)
        else:
            op_sql = _MAPA_OP_SQL[op_efetivo]
            if coluna_filtro in _COLUNAS_DATA:
                parsed = _parse_valor_data_filtro(termo_efetivo)
                expr_data = _sql_expr_data_ordenavel(coluna_filtro)
                if parsed:
                    tipo_val, val_norm = parsed
                    if tipo_val == 'ano':
                        if op_efetivo == 'igual':
                            query_base += f" AND ({expr_data}) BETWEEN ? AND ?"
                            params.extend([f"{val_norm}0101", f"{val_norm}1231"])
                        elif op_efetivo == 'maior':
                            query_base += f" AND ({expr_data}) != '' AND ({expr_data}) > ?"
                            params.append(f"{val_norm}1231")
                        elif op_efetivo == 'maior_igual':
                            query_base += f" AND ({expr_data}) != '' AND ({expr_data}) >= ?"
                            params.append(f"{val_norm}0101")
                        elif op_efetivo == 'menor':
                            query_base += f" AND ({expr_data}) != '' AND ({expr_data}) < ?"
                            params.append(f"{val_norm}0101")
                        elif op_efetivo == 'menor_igual':
                            query_base += f" AND ({expr_data}) != '' AND ({expr_data}) <= ?"
                            params.append(f"{val_norm}1231")
                    else:
                        query_base += f" AND ({expr_data}) != '' AND ({expr_data}) {op_sql} ?"
                        params.append(val_norm)
                else:
                    query_base += f" AND COALESCE({coluna_filtro}, '') COLLATE NOCASE {op_sql} ?"
                    params.append(termo_efetivo)
            elif coluna_filtro == 'prontuario_num' and termo_efetivo.isdigit():
                query_base += f" AND prontuario_num GLOB '[0-9]*' AND CAST(prontuario_num AS INTEGER) {op_sql} ?"
                params.append(int(termo_efetivo))
            elif coluna_filtro == 'cpf' and op_efetivo == 'igual':
                apenas_digitos = ''.join(filter(str.isdigit, termo_efetivo))
                if apenas_digitos:
                    query_base += " AND (cpf = ? OR REPLACE(REPLACE(COALESCE(cpf, ''), '.', ''), '-', '') = ?)"
                    params.extend([termo_efetivo, apenas_digitos])
                else:
                    query_base += " AND COALESCE(cpf, '') COLLATE NOCASE = ?"
                    params.append(termo_efetivo)
            else:
                query_base += f" AND COALESCE({coluna_filtro}, '') COLLATE NOCASE {op_sql} ?"
                params.append(termo_efetivo)

    order_by = _construir_clausula_order_by(ordem, direcao)

    return {
        'termo': termo_original,
        'coluna_filtro': coluna_filtro,
        'operador_filtro': operador_filtro,
        'ordem': ordem,
        'direcao': direcao,
        'query_base': query_base,
        'params': params,
        'order_by': order_by,
    }


def _normalizar_valor_comparacao(valor):
    if valor is None:
        return ''
    return str(valor).strip()


def _formatar_valor_log(valor):
    if valor is None or str(valor).strip() == '':
        return '(vazio)'
    return str(valor).strip()


def _descrever_diferencas(registro_antigo, novos_valores, labels_map):
    mudancas = []
    chaves_antigo = set(registro_antigo.keys()) if hasattr(registro_antigo, 'keys') else set()
    for campo, novo_val in novos_valores.items():
        if campo not in labels_map:
            continue
        antigo_val = registro_antigo[campo] if campo in chaves_antigo else None
        if _normalizar_valor_comparacao(antigo_val) != _normalizar_valor_comparacao(novo_val):
            label = labels_map[campo]
            mudancas.append(
                f"- {label}: '{_formatar_valor_log(antigo_val)}' → '{_formatar_valor_log(novo_val)}'"
            )
    return mudancas


def gerar_numero_prontuario(db):
    """Gera o próximo número de prontuário único no formato CV-{ano}-{seq:04d}."""
    ano_atual = datetime.date.today().year
    prefixo = f"CV-{ano_atual}-"
    rows = db.execute(
        "SELECT prontuario_num FROM pacientes WHERE prontuario_num LIKE ?",
        (f"{prefixo}%",),
    ).fetchall()

    maior_seq = 0
    for row in rows:
        pront = row['prontuario_num'] or ''
        sufixo = pront[len(prefixo):]
        if sufixo.isdigit():
            maior_seq = max(maior_seq, int(sufixo))

    proximo_seq = maior_seq + 1
    while True:
        candidato = f"{prefixo}{proximo_seq:04d}"
        existe = db.execute(
            "SELECT 1 FROM pacientes WHERE prontuario_num = ?",
            (candidato,),
        ).fetchone()
        if not existe:
            return candidato
        proximo_seq += 1


def _registrar_paciente_excluido(db, paciente):
    agora = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    db.execute(
        """
        INSERT INTO pacientes_excluidos (prontuario_num, cpf, nome, excluido_em)
        VALUES (?, ?, ?, ?)
        """,
        (
            paciente['prontuario_num'] or None,
            paciente['cpf'] or None,
            paciente['nome'] or None,
            agora,
        ),
    )


@bp.route('/')
def index():
    consulta = _construir_consulta_pacientes(request.args)
    db = get_db()

    query = f"""
        SELECT id, carimbo_data_hora, prontuario_num, nome, endereco, responsavel_1, telefone_1,
               responsavel_2, telefone_2, telefone_3, dn, identidade, cpf, obs
        {consulta['query_base']}
        ORDER BY {consulta['order_by']}
    """
    pacientes = db.execute(query, consulta['params']).fetchall()
    total_registros = len(pacientes)

    return render_template(
        'pacientes/index.html',
        pacientes=pacientes,
        colunas_planilha=COLUNAS_PLANILHA,
        operadores_filtro=OPERADORES_FILTRO,
        termo=consulta['termo'],
        coluna_filtro=consulta['coluna_filtro'],
        operador_filtro=consulta['operador_filtro'],
        ordem=consulta['ordem'],
        direcao=consulta['direcao'],
        total_registros=total_registros,
    )


@bp.route('/novo', methods=('GET', 'POST'))
def novo():
    db = get_db()

    if request.method == 'POST':
        valores_form = {
            col: request.form.get(col, '').strip()
            for col in CAMPOS_PLANILHA
        }
        nome = valores_form['nome']
        prontuario_num = valores_form['prontuario_num'] or gerar_numero_prontuario(db)
        cpf = valores_form['cpf'] or None
        carimbo_data_hora = datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')

        if not nome:
            flash('O nome do assistido é obrigatório.', 'danger')
        else:
            try:
                db.execute(
                    """
                    INSERT INTO pacientes (
                        carimbo_data_hora, prontuario_num, nome, endereco, responsavel_1, telefone_1,
                        responsavel_2, telefone_2, telefone_3, dn, identidade, cpf, obs
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        carimbo_data_hora,
                        prontuario_num,
                        nome,
                        valores_form['endereco'],
                        valores_form['responsavel_1'],
                        valores_form['telefone_1'],
                        valores_form['responsavel_2'],
                        valores_form['telefone_2'],
                        valores_form['telefone_3'],
                        valores_form['dn'],
                        valores_form['identidade'],
                        cpf,
                        valores_form['obs'],
                    ),
                )
                db.commit()
                log_audit(
                    'CADASTRO',
                    f"Novo assistido adicionado: {nome} (Prontuário: {prontuario_num}, CPF: {cpf or '-'})",
                )
                flash(f'Assistido "{nome}" cadastrado com sucesso!', 'success')
                return redirect(url_for('pacientes.index'))
            except Exception as e:
                db.rollback()
                erro_str = str(e)
                if "UNIQUE constraint failed: pacientes.cpf" in erro_str:
                    flash('Já existe um assistido cadastrado com este CPF.', 'danger')
                elif "UNIQUE constraint failed: pacientes.prontuario_num" in erro_str:
                    flash('Já existe um assistido cadastrado com este número de prontuário.', 'danger')
                else:
                    flash(f'Erro ao cadastrar assistido: {e}', 'danger')

    prontuario_sugerido = gerar_numero_prontuario(db)
    return render_template(
        'pacientes/novo.html',
        prontuario_sugerido=prontuario_sugerido,
        campos_planilha=CAMPOS_PLANILHA,
        dados=request.form if request.method == 'POST' else {},
    )


@bp.route('/<int:id>/editar', methods=('GET', 'POST'))
def editar(id):
    db = get_db()
    paciente = db.execute("SELECT * FROM pacientes WHERE id = ?", (id,)).fetchone()
    if not paciente:
        flash('Assistido não encontrado.', 'warning')
        return redirect(url_for('pacientes.index'))

    if request.method == 'POST':
        valores_form = {
            col: request.form.get(col, '').strip()
            for col in CAMPOS_PLANILHA
        }
        nome = valores_form['nome']
        prontuario_num = valores_form['prontuario_num']
        cpf = valores_form['cpf'] or None

        if not nome:
            flash('O nome do assistido é obrigatório.', 'danger')
            return render_template('pacientes/editar.html', paciente={**dict(paciente), **valores_form})

        if not prontuario_num:
            flash('O número do prontuário é obrigatório (para remover o registro, use o botão Excluir Registro).', 'danger')
            return render_template('pacientes/editar.html', paciente={**dict(paciente), **valores_form})

        novos_valores = {
            **valores_form,
            'prontuario_num': prontuario_num,
            'cpf': cpf,
        }
        mudancas = _descrever_diferencas(paciente, novos_valores, CAMPOS_PLANILHA)

        try:
            db.execute(
                """
                UPDATE pacientes SET
                    prontuario_num = ?, nome = ?, endereco = ?,
                    responsavel_1 = ?, telefone_1 = ?, responsavel_2 = ?, telefone_2 = ?, telefone_3 = ?,
                    dn = ?, identidade = ?, cpf = ?, obs = ?,
                    atualizado_em = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    prontuario_num,
                    nome,
                    valores_form['endereco'],
                    valores_form['responsavel_1'],
                    valores_form['telefone_1'],
                    valores_form['responsavel_2'],
                    valores_form['telefone_2'],
                    valores_form['telefone_3'],
                    valores_form['dn'],
                    valores_form['identidade'],
                    cpf,
                    valores_form['obs'],
                    id,
                ),
            )
            db.commit()

            if mudancas:
                log_audit(
                    'EDICAO',
                    f"Paciente {nome} (Prontuário: {prontuario_num}) alterado:\n" + "\n".join(mudancas),
                )
            else:
                log_audit(
                    'EDICAO',
                    f"Paciente {nome} (Prontuário: {prontuario_num}) salvo sem alterações de campo.",
                )

            flash(f'Cadastro de "{nome}" atualizado com sucesso!', 'success')
            return redirect(url_for('pacientes.index'))
        except Exception as e:
            db.rollback()
            erro_str = str(e)
            if "UNIQUE constraint failed: pacientes.cpf" in erro_str:
                flash('Já existe outro assistido cadastrado com este CPF.', 'danger')
            elif "UNIQUE constraint failed: pacientes.prontuario_num" in erro_str:
                flash('Já existe outro assistido cadastrado com este número de prontuário.', 'danger')
            else:
                flash(f'Erro ao atualizar cadastro: {e}', 'danger')
            return render_template('pacientes/editar.html', paciente={**dict(paciente), **valores_form})

    return render_template('pacientes/editar.html', paciente=paciente)


@bp.route('/<int:id>/excluir', methods=('POST',))
def excluir(id):
    db = get_db()
    paciente = db.execute(
        "SELECT id, nome, prontuario_num, cpf FROM pacientes WHERE id = ?",
        (id,),
    ).fetchone()
    if paciente:
        _registrar_paciente_excluido(db, paciente)
        db.execute("DELETE FROM pacientes WHERE id = ?", (id,))
        db.commit()
        log_audit(
            'EXCLUSAO',
            f"Paciente removido: {paciente['nome']} "
            f"(Prontuário: {paciente['prontuario_num'] or '-'}, CPF: {paciente['cpf'] or '-'})",
        )
        flash(f'Registro de "{paciente["nome"]}" excluído com sucesso.', 'info')
    return redirect(url_for('pacientes.index'))


@bp.route('/editar-lote', methods=('POST',))
def editar_lote():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({'ok': False, 'erro': 'Payload JSON inválido.'}), 400

    alteracoes = payload.get('alteracoes')
    exclusoes = payload.get('exclusoes')
    if alteracoes is None:
        alteracoes = []
    if exclusoes is None:
        exclusoes = []

    if not isinstance(alteracoes, list) or not isinstance(exclusoes, list):
        return jsonify({'ok': False, 'erro': 'Formato inválido para alterações ou exclusões.'}), 400

    if not alteracoes and not exclusoes:
        return jsonify({'ok': False, 'erro': 'Nenhuma alteração enviada.'}), 400

    exclusoes_ids = []
    exclusoes_set = set()
    motivos_exclusao = {}
    for raw_id in exclusoes:
        try:
            del_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if del_id not in exclusoes_set:
            exclusoes_set.add(del_id)
            exclusoes_ids.append(del_id)
            motivos_exclusao[del_id] = 'exclusao_direta'

    for item in alteracoes:
        if not isinstance(item, dict):
            continue
        try:
            pid = int(item.get('id'))
        except (TypeError, ValueError):
            continue
        campos_brutos = item.get('campos') or {}
        if not isinstance(campos_brutos, dict):
            continue
        if 'prontuario_num' in campos_brutos:
            pront_val = campos_brutos.get('prontuario_num')
            pront_str = '' if pront_val is None else str(pront_val).strip()
            if pront_str == '':
                if pid not in exclusoes_set:
                    exclusoes_set.add(pid)
                    exclusoes_ids.append(pid)
                motivos_exclusao[pid] = 'prontuario_apagado'

    db = get_db()
    resumos_edicao = []
    resumos_exclusao = []

    try:
        for item in alteracoes:
            if not isinstance(item, dict):
                continue
            try:
                pid = int(item.get('id'))
            except (TypeError, ValueError):
                continue

            if pid in exclusoes_set:
                continue

            paciente = db.execute("SELECT * FROM pacientes WHERE id = ?", (pid,)).fetchone()
            if not paciente:
                continue

            campos_brutos = item.get('campos') or {}
            if not isinstance(campos_brutos, dict):
                continue

            campos_normalizados = {}
            for col, val in campos_brutos.items():
                if col not in CAMPOS_PLANILHA:
                    continue
                val_str = '' if val is None else str(val).strip()
                if col == 'nome' and not val_str:
                    db.rollback()
                    return jsonify({'ok': False, 'erro': 'O nome do assistido não pode ficar vazio.'}), 400
                if col == 'cpf':
                    campos_normalizados[col] = val_str or None
                else:
                    campos_normalizados[col] = val_str

            campos_alterados = {}
            for col, novo_val in campos_normalizados.items():
                if _normalizar_valor_comparacao(paciente[col]) != _normalizar_valor_comparacao(novo_val):
                    campos_alterados[col] = novo_val

            if not campos_alterados:
                continue

            mudancas = _descrever_diferencas(paciente, campos_alterados, CAMPOS_PLANILHA)
            set_clauses = [f"{col} = ?" for col in campos_alterados]
            set_clauses.append("atualizado_em = CURRENT_TIMESTAMP")
            valores = list(campos_alterados.values()) + [pid]

            db.execute(
                f"UPDATE pacientes SET {', '.join(set_clauses)} WHERE id = ?",
                valores,
            )

            nome_final = campos_alterados.get('nome', paciente['nome'])
            pront_final = (
                campos_alterados['prontuario_num']
                if 'prontuario_num' in campos_alterados
                else paciente['prontuario_num']
            )
            resumos_edicao.append((nome_final, pront_final or '-', mudancas))

        for del_id in exclusoes_ids:
            paciente = db.execute(
                "SELECT id, nome, prontuario_num, cpf FROM pacientes WHERE id = ?",
                (del_id,),
            ).fetchone()
            if paciente:
                _registrar_paciente_excluido(db, paciente)
                db.execute("DELETE FROM pacientes WHERE id = ?", (del_id,))
                resumos_exclusao.append((
                    del_id,
                    paciente['nome'],
                    paciente['prontuario_num'] or '-',
                    paciente['cpf'] or '-',
                    motivos_exclusao.get(del_id, 'exclusao_direta'),
                ))

        db.commit()
    except Exception as e:
        db.rollback()
        erro_str = str(e)
        if "UNIQUE constraint failed: pacientes.cpf" in erro_str:
            return jsonify({'ok': False, 'erro': 'Já existe outro assistido cadastrado com este CPF.'}), 400
        if "UNIQUE constraint failed: pacientes.prontuario_num" in erro_str:
            return jsonify({'ok': False, 'erro': 'Já existe outro assistido cadastrado com este número de prontuário.'}), 400
        return jsonify({'ok': False, 'erro': f'Erro ao salvar alterações na planilha: {e}'}), 400

    for nome_final, pront_final, mudancas in resumos_edicao:
        log_audit(
            'EDICAO',
            f"Paciente {nome_final} (Prontuário: {pront_final}) alterado:\n" + "\n".join(mudancas),
        )

    for del_id, nome_ex, pront_ex, cpf_ex, motivo in resumos_exclusao:
        log_audit(
            'EXCLUSAO',
            f"Paciente removido: {nome_ex} (Prontuário: {pront_ex}, CPF: {cpf_ex})",
        )

    partes = []
    if resumos_edicao:
        n_ed = len(resumos_edicao)
        partes.append(f"{n_ed} {'assistido atualizado' if n_ed == 1 else 'assistidos atualizados'}")
    if resumos_exclusao:
        n_ex = len(resumos_exclusao)
        partes.append(f"{n_ex} {'assistido excluído' if n_ex == 1 else 'assistidos excluídos'}")

    mensagem_resumo = (
        "Alterações salvas com sucesso: " + " e ".join(partes) + "."
        if partes
        else "Nenhuma alteração efetiva foi necessária."
    )

    return jsonify({
        'ok': True,
        'atualizados': len(resumos_edicao),
        'excluidos': len(resumos_exclusao),
        'mensagem': mensagem_resumo,
    }), 200


@bp.route('/exportar')
def exportar_csv():
    db = get_db()
    consulta = _construir_consulta_pacientes(request.args)

    ordem_colunas_param = (request.args.get('ordem_colunas') or '').strip()
    colunas_export = []
    if ordem_colunas_param:
        vistas = set()
        for raw_col in ordem_colunas_param.split(','):
            col_key = raw_col.strip()
            if col_key in _LABELS_POR_COLUNA and col_key not in vistas:
                colunas_export.append((col_key, _LABELS_POR_COLUNA[col_key]))
                vistas.add(col_key)
    if not colunas_export:
        colunas_export = list(COLUNAS_EXPORTACAO)

    colunas_sql = ", ".join(col for col, _ in colunas_export)
    pacientes = db.execute(
        f"""
        SELECT {colunas_sql}
        {consulta['query_base']}
        ORDER BY {consulta['order_by']}
        """,
        consulta['params'],
    ).fetchall()

    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')

    writer.writerow([label for _, label in colunas_export])

    for p in pacientes:
        linha = []
        for col, _ in colunas_export:
            valor = p[col] or ''
            if col == 'obs':
                valor = str(valor).replace('\r\n', ' ').replace('\n', ' ')
            linha.append(valor)
        writer.writerow(linha)

    data_str = datetime.date.today().strftime('%Y%m%d')
    sufixo_filtro = "_filtrado" if consulta['termo'] else ""
    nome_arquivo = f"assistidos_casa_vida_{data_str}{sufixo_filtro}.csv"

    if consulta['termo']:
        log_audit(
            'EXPORTACAO',
            f"Exportação filtrada de {len(pacientes)} assistido(s) para CSV "
            f"(coluna: {consulta['coluna_filtro']}, operador: {consulta['operador_filtro']}, busca: '{consulta['termo']}')"
        )
    else:
        log_audit('EXPORTACAO', f"Exportação completa de {len(pacientes)} assistidos para CSV")

    return Response(
        output.getvalue().encode('utf-8-sig'),
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename={nome_arquivo}"},
    )


@bp.route('/importar', methods=('GET', 'POST'))
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

            resultado = sincronizar_csv_no_banco(get_db(), texto, data_corte=None)
            if not resultado.get('ok'):
                flash(resultado.get('erro', 'Erro ao importar arquivo CSV.'), 'danger')
                return redirect(url_for('pacientes.importar'))

            log_audit('IMPORTACAO', resultado['mensagem'])
            flash(resultado['mensagem'], 'success')
            return redirect(url_for('pacientes.index'))

        except Exception as e:
            flash(f"Erro ao processar o arquivo CSV: {e}", "danger")

    return render_template('pacientes/importar.html')


@bp.route('/sincronizar-sheets', methods=('POST',))
def sincronizar_sheets():
    resultado = sincronizar_google_sheets(get_db(), current_app.config)

    if resultado.get('ok'):
        log_audit('SINCRONIZACAO_SHEETS', resultado['mensagem'])

    espera_json = (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or 'application/json' in request.headers.get('Accept', '')
    )
    if espera_json:
        return jsonify(resultado), (200 if resultado.get('ok') else 400)

    if resultado.get('ok'):
        flash(resultado['mensagem'], 'success')
    else:
        flash(resultado['erro'], 'danger')
    return redirect(url_for('pacientes.index'))
