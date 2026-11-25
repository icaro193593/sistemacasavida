from flask import Blueprint, render_template, request
from app.db import get_db

bp = Blueprint('logs', __name__, url_prefix='/logs')

ACOES_LABELS = {
    'CADASTRO': 'Novo Registro',
    'EDICAO': 'Edição',
    'EDICAO_PLANILHA': 'Edição',
    'EXCLUSAO': 'Remoção',
    'SINCRONIZACAO_SHEETS': 'Sincronização Sheets',
    'IMPORTACAO': 'Importação CSV',
    'EXPORTACAO': 'Exportação CSV',
    'ATENDIMENTO': 'Atendimento',
    'BACKUP': 'Backup',
    'BACKUP_EMAIL': 'Backup por E-mail',
    'DOWNLOAD_BACKUP': 'Download Backup',
    'RESTAURACAO': 'Restauração Backup',
}


@bp.route('/')
def index():
    acao_filtro = request.args.get('acao', '').strip()
    termo = request.args.get('busca', '').strip()
    pagina = max(1, request.args.get('pagina', 1, type=int) or 1)
    itens_por_pagina = 25

    db = get_db()

    query_base = "FROM logs_auditoria WHERE 1=1"
    params = []

    if acao_filtro == 'EDICAO':
        query_base += " AND acao IN ('EDICAO', 'EDICAO_PLANILHA')"
    elif acao_filtro:
        query_base += " AND acao = ?"
        params.append(acao_filtro)

    if termo:
        like_termo = f"%{termo}%"
        acoes_correspondentes = [
            codigo for codigo, rotulo in ACOES_LABELS.items()
            if termo.lower() in rotulo.lower()
        ]
        if acoes_correspondentes:
            placeholders = ', '.join('?' for _ in acoes_correspondentes)
            query_base += f" AND (detalhes LIKE ? OR acao LIKE ? OR acao IN ({placeholders}))"
            params.extend([like_termo, like_termo, *acoes_correspondentes])
        else:
            query_base += " AND (detalhes LIKE ? OR acao LIKE ?)"
            params.extend([like_termo, like_termo])

    count_row = db.execute(f"SELECT COUNT(*) as total {query_base}", params).fetchone()
    total_registros = count_row['total']
    total_paginas = max(1, (total_registros + itens_por_pagina - 1) // itens_por_pagina)

    if pagina > total_paginas:
        pagina = total_paginas

    offset = (pagina - 1) * itens_por_pagina

    query = f"""
        SELECT id, acao, detalhes, data_hora
        {query_base}
        ORDER BY id DESC
        LIMIT ? OFFSET ?
    """
    params_pag = list(params)
    params_pag.extend([itens_por_pagina, offset])
    logs = db.execute(query, params_pag).fetchall()

    return render_template(
        'logs.html',
        logs=logs,
        acao_filtro=acao_filtro,
        termo=termo,
        pagina=pagina,
        total_paginas=total_paginas,
        total_registros=total_registros,
        acoes_labels=ACOES_LABELS,
    )
