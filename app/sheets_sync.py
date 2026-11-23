import csv
import datetime
import io
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

_CAMPOS_PACIENTE = (
    'carimbo_data_hora',
    'prontuario_num',
    'nome',
    'endereco',
    'responsavel_1',
    'telefone_1',
    'responsavel_2',
    'telefone_2',
    'telefone_3',
    'dn',
    'identidade',
    'cpf',
    'obs',
)

_CAMPOS_UNICOS = {'prontuario_num', 'cpf'}

_ALIASES_EXATOS = {
    'carimbo de data hora': 'carimbo_data_hora',
    'carimbo de data e hora': 'carimbo_data_hora',
    'timestamp': 'carimbo_data_hora',
    'data cadastro': 'carimbo_data_hora',
    'data de cadastro': 'carimbo_data_hora',
    'criado em': 'carimbo_data_hora',
    'ultima atualizacao': 'carimbo_data_hora',
    'data registro': 'carimbo_data_hora',
    'prontuario': 'prontuario_num',
    'prontuario num': 'prontuario_num',
    'numero prontuario': 'prontuario_num',
    'n prontuario': 'prontuario_num',
    'registro': 'prontuario_num',
    'nome': 'nome',
    'nome completo': 'nome',
    'nome do assistido': 'nome',
    'nome do paciente': 'nome',
    'assistido': 'nome',
    'paciente': 'nome',
    'endereco': 'endereco',
    'logradouro': 'endereco',
    'rua': 'endereco',
    'responsavel 1': 'responsavel_1',
    'responsavel': 'responsavel_1',
    'nome responsavel': 'responsavel_1',
    'cuidador': 'responsavel_1',
    'acompanhante': 'responsavel_1',
    'telefone 1': 'telefone_1',
    'telefone': 'telefone_1',
    'fone': 'telefone_1',
    'celular': 'telefone_1',
    'contato': 'telefone_1',
    'responsavel 2': 'responsavel_2',
    'telefone 2': 'telefone_2',
    'whatsapp': 'telefone_2',
    'zap': 'telefone_2',
    'telefone 3': 'telefone_3',
    'dn': 'dn',
    'data nascimento': 'dn',
    'data de nascimento': 'dn',
    'nascimento': 'dn',
    'dt nascimento': 'dn',
    'id': 'identidade',
    'identidade': 'identidade',
    'rg': 'identidade',
    'cpf': 'cpf',
    'obs': 'obs',
    'observacoes': 'obs',
    'observacao': 'obs',
}
for _campo in _CAMPOS_PACIENTE:
    _ALIASES_EXATOS.setdefault(_campo.replace('_', ' '), _campo)


def _normalizar_texto(texto):
    """Remove acentos, converte para minúsculas e normaliza separadores."""
    if not texto:
        return ''
    decomposed = unicodedata.normalize('NFKD', str(texto))
    sem_acentos = ''.join(ch for ch in decomposed if not unicodedata.combining(ch))
    limpo = sem_acentos.lower().strip()
    for sep in ('_', '-', '/', '.', ',', ':', ';', '(', ')', 'º', '°'):
        limpo = limpo.replace(sep, ' ')
    return ' '.join(limpo.split())


def _somente_digitos(valor):
    return ''.join(ch for ch in str(valor or '') if ch.isdigit())


def _eh_cpf_numerico(texto):
    return bool(texto) and all(ch.isdigit() or ch in '.- ' for ch in texto)


def _normalizar_cpf(valor):
    """Formata CPF com 11 dígitos puros como 000.000.000-00; preserva demais textos limpos."""
    texto = (valor or '').strip()
    if not texto:
        return None
    if _eh_cpf_numerico(texto):
        digitos = _somente_digitos(texto)
        if len(digitos) == 11:
            return f"{digitos[:3]}.{digitos[3:6]}.{digitos[6:9]}-{digitos[9:]}"
    return texto


def _parse_data_objeto(valor):
    """Converte strings comuns de data/hora do Sheets/Forms em datetime.date."""
    if isinstance(valor, datetime.datetime):
        return valor.date()
    if isinstance(valor, datetime.date):
        return valor

    texto = (valor or '').strip()
    if not texto:
        return None

    parte_data = texto.split()[0].rstrip(',')
    if 'T' in parte_data:
        parte_data = parte_data.split('T')[0]

    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d/%m/%y', '%d-%m-%Y', '%Y/%m/%d'):
        try:
            return datetime.datetime.strptime(parte_data, fmt).date()
        except ValueError:
            continue
    return None


def _inferir_campo_por_heuristica(norm):
    """Mapeia cabeçalhos flexíveis para as 13 colunas reais quando não há correspondência exata."""
    palavras = set(norm.split())
    if not norm:
        return None

    if 'carimbo' in norm or 'timestamp' in norm:
        return 'carimbo_data_hora'
    if 'pront' in norm or 'registro' in palavras:
        return 'prontuario_num'
    if 'tel' in norm or 'fone' in norm or 'cel' in norm or 'contato' in norm:
        if '3' in palavras:
            return 'telefone_3'
        if '2' in palavras:
            return 'telefone_2'
        return 'telefone_1'
    if 'whatsapp' in norm or 'whats' in norm or 'zap' in palavras:
        return 'telefone_2'
    if 'resp' in norm or 'cuidador' in norm or 'acompanhante' in norm:
        if '2' in palavras:
            return 'responsavel_2'
        return 'responsavel_1'
    if 'dn' in palavras or 'nasc' in norm or 'anivers' in norm:
        return 'dn'
    if 'identidade' in palavras or 'rg' in palavras or norm == 'id':
        return 'identidade'
    if 'cpf' in palavras:
        return 'cpf'
    if 'endere' in norm or 'logradouro' in norm or 'rua' in palavras:
        return 'endereco'
    if 'obs' in norm:
        return 'obs'
    if 'nome' in palavras and not any(k in norm for k in ('mae', 'pai', 'resp', 'cuidador', 'acompanhante')):
        return 'nome'
    if ('data' in norm or 'criado' in norm or 'atualiz' in norm or 'cadastro' in norm) and not any(
        k in norm for k in ('nasc', 'anivers')
    ):
        return 'carimbo_data_hora'
    return None


def _mapear_cabecalhos(cabecalhos):
    """Mapeia nomes de campos da tabela pacientes para os nomes reais das colunas do CSV."""
    mapeamento = {}
    colunas_restantes = []

    for col in (cabecalhos or []):
        if not col or not col.strip():
            continue
        norm = _normalizar_texto(col)
        campo_exato = _ALIASES_EXATOS.get(norm)
        if campo_exato and campo_exato not in mapeamento:
            mapeamento[campo_exato] = col
        else:
            colunas_restantes.append((col, norm))

    for col, norm in colunas_restantes:
        campo = _inferir_campo_por_heuristica(norm)
        if campo and campo not in mapeamento:
            mapeamento[campo] = col

    return mapeamento


def _normalizar_linha(linha, mapeamento):
    """Extrai os campos mapeados preservando os textos originais da planilha."""
    dados = {}
    for campo, col_csv in mapeamento.items():
        bruto = (linha.get(col_csv) or '').strip()
        if campo == 'cpf':
            dados[campo] = _normalizar_cpf(bruto)
        elif campo == 'prontuario_num':
            dados[campo] = bruto or None
        else:
            dados[campo] = bruto
    return dados


def _gerar_numero_prontuario(db):
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


def _buscar_paciente_existente(db, dados):
    """Busca paciente existente por prontuario_num, cpf ou nome (quando sem id único)."""
    prontuario_num = dados.get('prontuario_num')
    if prontuario_num:
        existente = db.execute(
            "SELECT id FROM pacientes WHERE prontuario_num = ?",
            (prontuario_num,),
        ).fetchone()
        if existente:
            return existente

    cpf = dados.get('cpf')
    if cpf:
        cpf_digitos = _somente_digitos(cpf) if _eh_cpf_numerico(cpf) else ''
        if cpf_digitos:
            existente = db.execute(
                "SELECT id FROM pacientes WHERE cpf = ? OR REPLACE(REPLACE(cpf, '.', ''), '-', '') = ?",
                (cpf, cpf_digitos),
            ).fetchone()
        else:
            existente = db.execute(
                "SELECT id FROM pacientes WHERE cpf = ?",
                (cpf,),
            ).fetchone()
        if existente:
            return existente

    if not prontuario_num and not cpf:
        return db.execute(
            "SELECT id FROM pacientes WHERE nome = ? COLLATE NOCASE",
            (dados['nome'],),
        ).fetchone()

    return None


def _inserir_paciente(db, dados):
    """Insere novo paciente com as 13 colunas reais e prontuário único."""
    registro = dict(dados)

    if not registro.get('prontuario_num'):
        registro['prontuario_num'] = _gerar_numero_prontuario(db)

    colunas = []
    valores = []
    for campo in _CAMPOS_PACIENTE:
        if campo not in registro:
            continue
        valor = registro[campo]
        if campo in _CAMPOS_UNICOS and not valor:
            valor = None
        colunas.append(campo)
        valores.append(valor)

    placeholders = ', '.join('?' for _ in colunas)
    sql = f"INSERT INTO pacientes ({', '.join(colunas)}) VALUES ({placeholders})"
    db.execute(sql, valores)


def obter_url_planilha(cfg):
    """Resolve a URL de exportação CSV do Google Sheets a partir da configuração."""
    if not cfg:
        return None

    csv_url = (cfg.get('GOOGLE_SHEETS_CSV_URL') or '').strip()
    if csv_url:
        return csv_url

    sheet_id = (cfg.get('GOOGLE_SHEETS_ID') or '').strip()
    if not sheet_id:
        return None

    gid = str(cfg.get('GOOGLE_SHEETS_GID') or '0').strip() or '0'
    sheet_id_seguro = urllib.parse.quote(sheet_id, safe='')
    query = urllib.parse.urlencode({'format': 'csv', 'gid': gid})
    return f"https://docs.google.com/spreadsheets/d/{sheet_id_seguro}/export?{query}"


def baixar_csv_planilha(url, timeout=15):
    """Baixa o conteúdo CSV da planilha do Google Sheets usando apenas stdlib."""
    req = urllib.request.Request(
        url,
        headers={'User-Agent': 'SistemaCasaVida/1.0'},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            conteudo = resp.read()
    except urllib.error.HTTPError as exc:
        raise RuntimeError(
            f"Erro HTTP {exc.code} ao baixar a planilha do Google Sheets: {exc.reason}."
        ) from exc
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, TimeoutError):
            raise RuntimeError(
                "Tempo esgotado ao tentar acessar a planilha do Google Sheets."
            ) from exc
        raise RuntimeError(
            f"Erro de conexão ao baixar a planilha do Google Sheets: {exc.reason}."
        ) from exc
    except TimeoutError as exc:
        raise RuntimeError(
            "Tempo esgotado ao tentar acessar a planilha do Google Sheets."
        ) from exc

    try:
        return conteudo.decode('utf-8-sig')
    except UnicodeDecodeError:
        return conteudo.decode('latin-1')


def _foi_excluido_no_banco(db, dados):
    """Verifica se o registro já foi removido intencionalmente do banco local."""
    try:
        prontuario_num = dados.get('prontuario_num')
        if prontuario_num:
            excluido = db.execute(
                "SELECT id FROM pacientes_excluidos WHERE prontuario_num = ?",
                (prontuario_num,),
            ).fetchone()
            if excluido:
                return True

        cpf = dados.get('cpf')
        if cpf:
            cpf_digitos = _somente_digitos(cpf) if _eh_cpf_numerico(cpf) else ''
            if cpf_digitos:
                excluido = db.execute(
                    "SELECT id FROM pacientes_excluidos WHERE cpf = ? OR REPLACE(REPLACE(COALESCE(cpf, ''), '.', ''), '-', '') = ?",
                    (cpf, cpf_digitos),
                ).fetchone()
            else:
                excluido = db.execute(
                    "SELECT id FROM pacientes_excluidos WHERE cpf = ?",
                    (cpf,),
                ).fetchone()
            if excluido:
                return True

        if not prontuario_num and not cpf and dados.get('nome'):
            excluido = db.execute(
                "SELECT id FROM pacientes_excluidos WHERE nome = ? COLLATE NOCASE",
                (dados['nome'],),
            ).fetchone()
            if excluido:
                return True
    except Exception:
        return False

    return False


def sincronizar_csv_no_banco(db, texto_csv, data_corte=None):
    """Processa o CSV inserindo SOMENTE novos registros a partir da data de corte.

    Regras de prioridade do banco local:
    - Nunca remove registros do SQLite local.
    - Nunca sobrescreve registros já existentes no SQLite local.
    - Nunca reimporta registros previamente excluídos do SQLite local (pacientes_excluidos).
    - Se data_corte estiver configurada e a planilha possuir carimbo_data_hora,
      puxa apenas linhas com data >= data_corte.
    """
    texto_limpo = (texto_csv or '').lstrip('\ufeff\r\n')
    linhas = [linha for linha in texto_limpo.splitlines() if linha.strip()]
    primeira_linha = linhas[0] if linhas else ''
    delimitador = ';' if primeira_linha.count(';') > primeira_linha.count(',') else ','

    leitor = csv.DictReader(io.StringIO(texto_limpo), delimiter=delimitador)
    mapeamento = _mapear_cabecalhos(leitor.fieldnames)

    if 'nome' not in mapeamento:
        return {
            'ok': False,
            'erro': 'Não foi possível identificar a coluna de Nome na planilha do Google Sheets.',
        }

    data_corte_obj = _parse_data_objeto(data_corte) if data_corte else None
    tem_coluna_data = 'carimbo_data_hora' in mapeamento

    adicionados = 0
    ja_existentes = 0
    removidos_ignorados = 0
    anteriores_data_corte = 0
    ignorados = 0
    erros = 0

    for linha in leitor:
        dados = _normalizar_linha(linha, mapeamento)
        if not dados.get('nome'):
            ignorados += 1
            continue

        if data_corte_obj and tem_coluna_data:
            data_linha = _parse_data_objeto(dados.get('carimbo_data_hora'))
            if data_linha is not None and data_linha < data_corte_obj:
                anteriores_data_corte += 1
                continue

        try:
            existente = _buscar_paciente_existente(db, dados)
            if existente:
                ja_existentes += 1
                continue

            if _foi_excluido_no_banco(db, dados):
                removidos_ignorados += 1
                continue

            _inserir_paciente(db, dados)
            adicionados += 1
        except Exception:
            erros += 1

    db.commit()

    detalhes_extras = []
    if ja_existentes > 0:
        detalhes_extras.append(f"{ja_existentes} já existente(s) mantido(s) intacto(s)")
    if removidos_ignorados > 0:
        detalhes_extras.append(f"{removidos_ignorados} já removido(s) localmente ignorado(s)")
    if anteriores_data_corte > 0 and data_corte_obj:
        detalhes_extras.append(
            f"{anteriores_data_corte} anterior(es) a {data_corte_obj.strftime('%d/%m/%Y')} ignorado(s)"
        )
    if erros > 0:
        detalhes_extras.append(f"{erros} erro(s)")

    mensagem = f"Sincronização concluída: {adicionados} novo(s) registro(s) adicionado(s)."
    if detalhes_extras:
        mensagem += " (" + "; ".join(detalhes_extras) + ".)"

    return {
        'ok': True,
        'adicionados': adicionados,
        'atualizados': 0,
        'ja_existentes': ja_existentes,
        'removidos_ignorados': removidos_ignorados,
        'anteriores_data_corte': anteriores_data_corte,
        'ignorados': ignorados,
        'erros': erros,
        'mensagem': mensagem,
    }


def sincronizar_google_sheets(db, cfg):
    """Executa a sincronização: resolve URL, baixa CSV e insere apenas registros novos."""
    url = obter_url_planilha(cfg)
    if not url:
        return {
            'ok': False,
            'erro': (
                'Planilha do Google Sheets não configurada. '
                'Defina GOOGLE_SHEETS_CSV_URL ou GOOGLE_SHEETS_ID no arquivo .env.'
            ),
        }

    try:
        timeout = int(cfg.get('GOOGLE_SHEETS_TIMEOUT', 15) or 15)
        data_corte = cfg.get('GOOGLE_SHEETS_MIN_DATE', '2026-11-23')
        texto_csv = baixar_csv_planilha(url, timeout=timeout)
        return sincronizar_csv_no_banco(db, texto_csv, data_corte=data_corte)
    except Exception as exc:
        return {
            'ok': False,
            'erro': str(exc),
        }
