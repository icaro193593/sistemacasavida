document.addEventListener('DOMContentLoaded', function () {
    var botoesFechar = document.querySelectorAll('.alerta-fechar');
    botoesFechar.forEach(function (btn) {
        btn.addEventListener('click', function () {
            var alerta = this.closest('.alerta');
            if (alerta) {
                alerta.style.opacity = '0';
                setTimeout(function () { alerta.remove(); }, 200);
            }
        });
    });

    function formatarCpf(valor) {
        var texto = String(valor || '').trim();
        if (!texto) return '';
        // Aplica máscara apenas quando o usuário digitar dígitos/separadores de CPF,
        // preservando entradas textuais especiais sem bloqueio.
        if (!/^[\d.\-]+$/.test(texto)) {
            return texto;
        }
        var v = texto.replace(/\D/g, '');
        if (!v) return '';
        if (v.length > 11) v = v.substring(0, 11);
        if (v.length > 9) {
            return v.replace(/(\d{3})(\d{3})(\d{3})(\d{1,2})/, '$1.$2.$3-$4');
        }
        if (v.length > 6) {
            return v.replace(/(\d{3})(\d{3})(\d{1,3})/, '$1.$2.$3');
        }
        if (v.length > 3) {
            return v.replace(/(\d{3})(\d{1,3})/, '$1.$2');
        }
        return v;
    }

    function formatarTelefone(valor) {
        var v = String(valor || '').replace(/\D/g, '');
        if (v.length > 11) v = v.substring(0, 11);
        if (v.length > 10) {
            return v.replace(/(\d{2})(\d{5})(\d{4})/, '($1) $2-$3');
        }
        if (v.length > 6) {
            return v.replace(/(\d{2})(\d{4})(\d{0,4})/, '($1) $2-$3');
        }
        if (v.length > 2) {
            return v.replace(/(\d{2})(\d{0,5})/, '($1) $2');
        }
        return v;
    }

    function aplicarMascara(seletor, formatador) {
        document.querySelectorAll(seletor).forEach(function (input) {
            input.addEventListener('input', function (e) {
                e.target.value = formatador(e.target.value);
            });
        });
    }

    aplicarMascara('.mascara-cpf', formatarCpf);
    aplicarMascara('.mascara-telefone', formatarTelefone);

    var inputsCep = document.querySelectorAll('.mascara-cep');
    inputsCep.forEach(function (input) {
        input.addEventListener('input', function (e) {
            var v = e.target.value.replace(/\D/g, '');
            if (v.length > 8) v = v.substring(0, 8);
            if (v.length > 5) {
                v = v.replace(/(\d{5})(\d{1,3})/, '$1-$2');
            }
            e.target.value = v;
        });
    });

    var inputNasc = document.getElementById('data_nascimento');
    var spanIdade = document.getElementById('idade_calculada');
    if (inputNasc && spanIdade) {
        function atualizarIdade() {
            var val = inputNasc.value;
            if (!val) {
                spanIdade.textContent = '';
                return;
            }
            var nasc = new Date(val);
            var hoje = new Date();
            var idade = hoje.getFullYear() - nasc.getFullYear();
            var m = hoje.getMonth() - nasc.getMonth();
            if (m < 0 || (m === 0 && hoje.getDate() < nasc.getDate())) {
                idade--;
            }
            if (idade >= 0 && idade < 130) {
                spanIdade.textContent = ' (' + idade + ' anos)';
            } else {
                spanIdade.textContent = '';
            }
        }
        inputNasc.addEventListener('change', atualizarIdade);
        atualizarIdade();
    }

    document.querySelectorAll('.confirmar-acao').forEach(function (el) {
        el.addEventListener('submit', function (e) {
            var msg = el.getAttribute('data-confirmacao') || 'Tem certeza que deseja executar esta ação?';
            if (!confirm(msg)) {
                e.preventDefault();
            }
        });
    });

    function exibirFeedback(tipo, mensagem) {
        var feedback = document.getElementById('sync-feedback');
        if (!feedback) return;
        feedback.innerHTML = '';

        var classeAlerta = 'alerta-info';
        if (tipo === 'success') classeAlerta = 'alerta-success';
        else if (tipo === 'danger') classeAlerta = 'alerta-danger';
        else if (tipo === 'warning') classeAlerta = 'alerta-warning';

        var alerta = document.createElement('div');
        alerta.className = 'alerta ' + classeAlerta;

        var span = document.createElement('span');
        span.textContent = mensagem;

        var btnFechar = document.createElement('button');
        btnFechar.type = 'button';
        btnFechar.className = 'alerta-fechar';
        btnFechar.setAttribute('aria-label', 'Fechar');
        btnFechar.innerHTML = '&times;';
        btnFechar.addEventListener('click', function () {
            alerta.style.opacity = '0';
            setTimeout(function () {
                feedback.innerHTML = '';
                feedback.style.display = 'none';
            }, 200);
        });

        alerta.appendChild(span);
        alerta.appendChild(btnFechar);
        feedback.appendChild(alerta);
        feedback.style.display = 'block';
    }

    var formSyncSheets = document.getElementById('form-sync-sheets');
    if (formSyncSheets) {
        formSyncSheets.addEventListener('submit', function (e) {
            e.preventDefault();

            var btnSync = document.getElementById('btn-sync-sheets');
            var btnTexto = btnSync ? btnSync.querySelector('.btn-sync-texto') : null;
            var textoOriginal = btnTexto ? btnTexto.textContent : 'Sincronizar Google Sheets';

            function restaurarBotao() {
                if (btnSync) {
                    btnSync.disabled = false;
                    btnSync.classList.remove('carregando');
                }
                if (btnTexto) {
                    btnTexto.textContent = textoOriginal;
                }
            }

            if (btnSync) {
                btnSync.disabled = true;
                btnSync.classList.add('carregando');
            }
            if (btnTexto) {
                btnTexto.textContent = 'Sincronizando...';
            }

            fetch(formSyncSheets.action, {
                method: 'POST',
                headers: {
                    'Accept': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                }
            })
                .then(function (response) {
                    return response.json().then(function (data) {
                        return { okHttp: response.ok, data: data };
                    });
                })
                .then(function (resultado) {
                    var data = resultado.data || {};
                    if (resultado.okHttp && data.ok) {
                        var msgSucesso = data.mensagem || 'Sincronização concluída com sucesso.';
                        exibirFeedback('success', msgSucesso);

                        if ((data.adicionados && data.adicionados > 0) || (data.atualizados && data.atualizados > 0)) {
                            setTimeout(function () {
                                window.location.reload();
                            }, 1500);
                        } else {
                            restaurarBotao();
                        }
                    } else {
                        var msgErro = data.erro || data.mensagem || 'Não foi possível concluir a sincronização com o Google Sheets.';
                        exibirFeedback('danger', msgErro);
                        restaurarBotao();
                    }
                })
                .catch(function () {
                    exibirFeedback('danger', 'Erro de conexão ao tentar sincronizar com o Google Sheets. Tente novamente.');
                    restaurarBotao();
                });
        });
    }

    // =========================================================
    // Controlador de Edição Direta na Planilha (12 colunas editáveis)
    // =========================================================
    var btnEditarPlanilha = document.getElementById('btn-editar-planilha');
    var barraEdicao = document.getElementById('barra-edicao-planilha');
    var tabelaAssistidos = document.getElementById('tabela-assistidos');
    var contadorAlteracoes = document.getElementById('contador-alteracoes');
    var btnCancelarEdicao = document.getElementById('btn-cancelar-edicao');
    var btnAplicarEdicoes = document.getElementById('btn-aplicar-edicoes');
    var modalConfirmar = document.getElementById('modal-confirmar-edicoes');
    var modalResumoTexto = document.getElementById('modal-resumo-texto');
    var modalListaMudancas = document.getElementById('modal-lista-mudancas');
    var modalErroEdicao = document.getElementById('modal-erro-edicao');
    var btnModalCancelar = document.getElementById('btn-modal-cancelar');
    var btnModalFechar = document.getElementById('btn-modal-fechar');
    var btnConfirmarEdicoes = document.getElementById('btn-confirmar-edicoes');

    if (btnEditarPlanilha && barraEdicao && tabelaAssistidos && modalConfirmar) {
        var modoEdicaoAtivo = false;
        var payloadPendente = null;
        var CAMPOS_LARGOS = ['nome', 'endereco', 'obs'];

        function normalizarValor(campo, valor) {
            var texto = String(valor || '').trim();
            if (campo === 'cpf') return formatarCpf(texto);
            return texto;
        }

        function obterLinhasPacientes() {
            return Array.prototype.slice.call(
                tabelaAssistidos.querySelectorAll('tbody tr[data-paciente-id]')
            );
        }

        function criarInputCelula(campo, valor, placeholder) {
            var input = document.createElement('input');
            input.type = 'text';
            input.className = 'input-celula' + (CAMPOS_LARGOS.indexOf(campo) !== -1 ? ' input-celula-largo' : '');
            input.value = valor || '';
            if (placeholder) input.placeholder = placeholder;
            return input;
        }

        function alternarOutrosInputsLinha(tr, desabilitar) {
            tr.querySelectorAll('td[data-editavel="true"]').forEach(function (td) {
                if (td.getAttribute('data-campo') === 'prontuario_num') return;
                td.querySelectorAll('.input-celula').forEach(function (el) {
                    el.disabled = desabilitar;
                });
            });
        }

        function verificarExclusaoPorProntuario(tr) {
            var tdPront = tr.querySelector('td[data-campo="prontuario_num"]');
            if (!tdPront) return false;
            var origPront = (tdPront.getAttribute('data-original') || '').trim();
            var inputPront = tdPront.querySelector('.input-celula');
            var atualPront = inputPront ? inputPront.value.trim() : '';
            var aviso = tdPront.querySelector('.aviso-exclusao-linha');

            var marcarExclusao = origPront !== '' && atualPront === '';
            tr.classList.toggle('linha-marcada-exclusao', marcarExclusao);
            alternarOutrosInputsLinha(tr, marcarExclusao);
            if (aviso) {
                aviso.style.display = marcarExclusao ? 'inline-block' : 'none';
            }

            if (marcarExclusao) {
                tr.querySelectorAll('td.celula-alterada').forEach(function (cel) {
                    cel.classList.remove('celula-alterada');
                });
            }
            return marcarExclusao;
        }

        function atualizarEstadoCelula(td, tr) {
            if (!td || !tr) return;
            var marcadaExclusao = verificarExclusaoPorProntuario(tr);
            if (marcadaExclusao) {
                td.classList.remove('celula-alterada');
                return;
            }

            var campo = td.getAttribute('data-campo');
            var orig = normalizarValor(campo, td.getAttribute('data-original') || '');
            var controle = td.querySelector('.input-celula');
            var atual = controle ? normalizarValor(campo, controle.value) : '';
            var alterado = atual !== orig;

            td.classList.toggle('celula-alterada', alterado);
        }

        function atualizarLinhaCompleta(tr) {
            var marcada = verificarExclusaoPorProntuario(tr);
            if (!marcada) {
                tr.querySelectorAll('td[data-editavel="true"]').forEach(function (td) {
                    atualizarEstadoCelula(td, tr);
                });
            }
            atualizarContadorAlteracoes();
        }

        function atualizarContadorAlteracoes() {
            if (!contadorAlteracoes) return;
            var linhas = obterLinhasPacientes();
            var total = 0;

            linhas.forEach(function (tr) {
                if (tr.classList.contains('linha-marcada-exclusao')) {
                    total += 1;
                    return;
                }
                var celulasAlteradas = tr.querySelectorAll('td.celula-alterada');
                total += celulasAlteradas.length;
            });

            contadorAlteracoes.textContent = total + ' alteração(ões)';
            contadorAlteracoes.className = 'badge ' + (total > 0 ? 'badge-ativo' : 'badge-espera');
        }

        function renderizarControlesLinha(tr) {
            var celulas = tr.querySelectorAll('td[data-editavel="true"]');
            celulas.forEach(function (td) {
                if (typeof td._htmlOriginal === 'undefined') {
                    td._htmlOriginal = td.innerHTML;
                }

                var campo = td.getAttribute('data-campo');
                var label = td.getAttribute('data-label') || campo;
                var valorInicial = normalizarValor(campo, td.getAttribute('data-original') || '');
                var placeholder = campo === 'cpf' ? '000.000.000-00' : label;

                td.innerHTML = '';

                var input = criarInputCelula(campo, valorInicial, placeholder);
                input.setAttribute('aria-label', label);

                input.addEventListener('input', function () {
                    if (campo === 'cpf') {
                        input.value = formatarCpf(input.value);
                    }
                    if (campo === 'prontuario_num') {
                        atualizarLinhaCompleta(tr);
                    } else {
                        atualizarEstadoCelula(td, tr);
                        atualizarContadorAlteracoes();
                    }
                });
                td.appendChild(input);

                if (campo === 'prontuario_num') {
                    var avisoExclusao = document.createElement('span');
                    avisoExclusao.className = 'aviso-exclusao-linha';
                    avisoExclusao.textContent = 'Será excluído';
                    avisoExclusao.style.display = 'none';
                    td.appendChild(avisoExclusao);
                }
            });
        }

        function entrarModoEdicao() {
            if (modoEdicaoAtivo) return;
            var linhas = obterLinhasPacientes();
            if (linhas.length === 0) {
                exibirFeedback('warning', 'Não há assistidos exibidos na tabela para editar.');
                return;
            }

            modoEdicaoAtivo = true;
            tabelaAssistidos.classList.add('tabela-modo-edicao');
            barraEdicao.style.display = 'flex';
            btnEditarPlanilha.disabled = true;

            linhas.forEach(renderizarControlesLinha);
            atualizarContadorAlteracoes();
        }

        function sairModoEdicao() {
            if (!modoEdicaoAtivo) return;
            modoEdicaoAtivo = false;
            tabelaAssistidos.classList.remove('tabela-modo-edicao');
            barraEdicao.style.display = 'none';
            btnEditarPlanilha.disabled = false;

            obterLinhasPacientes().forEach(function (tr) {
                tr.classList.remove('linha-marcada-exclusao');
                tr.querySelectorAll('td[data-editavel="true"]').forEach(function (td) {
                    td.classList.remove('celula-alterada');
                    if (typeof td._htmlOriginal !== 'undefined') {
                        td.innerHTML = td._htmlOriginal;
                        delete td._htmlOriginal;
                    }
                });
            });

            atualizarContadorAlteracoes();
        }

        function coletarAlteracoes() {
            var alteracoes = [];
            var exclusoes = [];
            var detalhesModal = [];
            var erroValidacao = null;

            obterLinhasPacientes().forEach(function (tr) {
                var id = parseInt(tr.getAttribute('data-paciente-id'), 10);
                var nomeOriginal = tr.getAttribute('data-paciente-nome') || ('Assistido #' + id);
                var prontuarioOriginal = tr.getAttribute('data-paciente-prontuario') || ('# ' + id);

                if (tr.classList.contains('linha-marcada-exclusao')) {
                    exclusoes.push(id);
                    detalhesModal.push({
                        tipo: 'exclusao',
                        id: id,
                        nome: nomeOriginal,
                        prontuario: prontuarioOriginal
                    });
                    return;
                }

                var camposAlterados = {};
                var mudancasVisuais = [];

                tr.querySelectorAll('td[data-editavel="true"]').forEach(function (td) {
                    var campo = td.getAttribute('data-campo');
                    var label = td.getAttribute('data-label') || campo;
                    var origRaw = td.getAttribute('data-original') || '';
                    var origNorm = normalizarValor(campo, origRaw);
                    var controle = td.querySelector('.input-celula');
                    var atualNorm = controle ? normalizarValor(campo, controle.value) : '';

                    if (campo === 'nome' && atualNorm === '' && !erroValidacao) {
                        erroValidacao = {
                            mensagem: 'O nome do assistido (' + prontuarioOriginal + ') não pode ficar vazio.',
                            controle: controle
                        };
                    }

                    if (atualNorm !== origNorm) {
                        camposAlterados[campo] = atualNorm;
                        mudancasVisuais.push({
                            label: label,
                            antes: origNorm,
                            depois: atualNorm
                        });
                    }
                });

                if (Object.keys(camposAlterados).length > 0) {
                    alteracoes.push({ id: id, campos: camposAlterados });
                    detalhesModal.push({
                        tipo: 'edicao',
                        id: id,
                        nome: camposAlterados.nome || nomeOriginal,
                        prontuario: camposAlterados.prontuario_num || prontuarioOriginal,
                        mudancas: mudancasVisuais
                    });
                }
            });

            return {
                alteracoes: alteracoes,
                exclusoes: exclusoes,
                detalhesModal: detalhesModal,
                erroValidacao: erroValidacao
            };
        }

        function fecharModalConfirmacao() {
            modalConfirmar.style.display = 'none';
            if (modalErroEdicao) {
                modalErroEdicao.style.display = 'none';
                modalErroEdicao.textContent = '';
            }
            if (btnConfirmarEdicoes) {
                btnConfirmarEdicoes.disabled = false;
                btnConfirmarEdicoes.textContent = 'Confirmar e Salvar no Banco';
            }
            if (btnModalCancelar) {
                btnModalCancelar.disabled = false;
            }
        }

        function abrirModalConfirmacao(coleta) {
            payloadPendente = {
                alteracoes: coleta.alteracoes,
                exclusoes: coleta.exclusoes
            };

            if (modalErroEdicao) {
                modalErroEdicao.style.display = 'none';
                modalErroEdicao.textContent = '';
            }

            if (modalResumoTexto) {
                var partes = [];
                if (coleta.alteracoes.length > 0) {
                    partes.push(coleta.alteracoes.length + ' registro(s) com dados alterados');
                }
                if (coleta.exclusoes.length > 0) {
                    partes.push(coleta.exclusoes.length + ' registro(s) marcado(s) para exclusão');
                }
                modalResumoTexto.textContent = 'Revise cuidadosamente as mudanças antes de gravar no banco de dados: ' + partes.join(' e ') + '.';
            }

            if (modalListaMudancas) {
                modalListaMudancas.innerHTML = '';

                coleta.detalhesModal.forEach(function (item) {
                    var grupo = document.createElement('div');
                    grupo.className = 'diff-grupo' + (item.tipo === 'exclusao' ? ' diff-exclusao' : '');

                    var titulo = document.createElement('div');
                    titulo.className = 'diff-titulo';

                    var tituloTexto = document.createElement('span');
                    tituloTexto.textContent = item.nome + ' (' + item.prontuario + ')';
                    titulo.appendChild(tituloTexto);

                    var badge = document.createElement('span');
                    badge.className = 'badge ' + (item.tipo === 'exclusao' ? 'badge-log-exclusao' : 'badge-log-edicao_planilha');
                    badge.textContent = item.tipo === 'exclusao' ? 'EXCLUSÃO' : 'Edição';
                    titulo.appendChild(badge);
                    grupo.appendChild(titulo);

                    if (item.tipo === 'exclusao') {
                        var avisoExclusao = document.createElement('div');
                        avisoExclusao.className = 'diff-item';
                        avisoExclusao.textContent = 'Prontuário apagado por completo — o registro de ' + item.nome + ' (' + item.prontuario + ') será excluído permanentemente do banco.';
                        grupo.appendChild(avisoExclusao);
                    } else {
                        item.mudancas.forEach(function (m) {
                            var linhaDiff = document.createElement('div');
                            linhaDiff.className = 'diff-item';

                            var spanCampo = document.createElement('span');
                            spanCampo.className = 'diff-campo';
                            spanCampo.textContent = m.label + ':';

                            var spanAntes = document.createElement('span');
                            spanAntes.className = 'diff-antes';
                            spanAntes.textContent = m.antes !== '' ? m.antes : '(vazio)';

                            var spanSeta = document.createElement('span');
                            spanSeta.className = 'diff-seta';
                            spanSeta.textContent = '→';

                            var spanDepois = document.createElement('span');
                            spanDepois.className = 'diff-depois';
                            spanDepois.textContent = m.depois !== '' ? m.depois : '(vazio)';

                            linhaDiff.appendChild(spanCampo);
                            linhaDiff.appendChild(spanAntes);
                            linhaDiff.appendChild(spanSeta);
                            linhaDiff.appendChild(spanDepois);
                            grupo.appendChild(linhaDiff);
                        });
                    }

                    modalListaMudancas.appendChild(grupo);
                });
            }

            modalConfirmar.style.display = 'flex';
        }

        btnEditarPlanilha.addEventListener('click', entrarModoEdicao);
        if (btnCancelarEdicao) {
            btnCancelarEdicao.addEventListener('click', sairModoEdicao);
        }

        if (btnAplicarEdicoes) {
            btnAplicarEdicoes.addEventListener('click', function () {
                var coleta = coletarAlteracoes();
                if (coleta.erroValidacao) {
                    exibirFeedback('danger', coleta.erroValidacao.mensagem);
                    if (coleta.erroValidacao.controle) {
                        coleta.erroValidacao.controle.focus();
                    }
                    return;
                }
                if (coleta.alteracoes.length === 0 && coleta.exclusoes.length === 0) {
                    exibirFeedback('warning', 'Nenhuma alteração foi feita na planilha.');
                    return;
                }
                abrirModalConfirmacao(coleta);
            });
        }

        if (btnModalCancelar) {
            btnModalCancelar.addEventListener('click', fecharModalConfirmacao);
        }
        if (btnModalFechar) {
            btnModalFechar.addEventListener('click', fecharModalConfirmacao);
        }
        modalConfirmar.addEventListener('click', function (e) {
            if (e.target === modalConfirmar) {
                fecharModalConfirmacao();
            }
        });
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && modalConfirmar.style.display !== 'none') {
                fecharModalConfirmacao();
            }
        });

        if (btnConfirmarEdicoes) {
            btnConfirmarEdicoes.addEventListener('click', function () {
                if (!payloadPendente) return;
                var urlEditarLote = tabelaAssistidos.getAttribute('data-url-editar-lote');
                if (!urlEditarLote) return;

                if (modalErroEdicao) {
                    modalErroEdicao.style.display = 'none';
                    modalErroEdicao.textContent = '';
                }

                btnConfirmarEdicoes.disabled = true;
                btnConfirmarEdicoes.textContent = 'Salvando...';
                if (btnModalCancelar) btnModalCancelar.disabled = true;

                fetch(urlEditarLote, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: JSON.stringify(payloadPendente)
                })
                    .then(function (response) {
                        return response.text().then(function (texto) {
                            var data = {};
                            try {
                                data = texto ? JSON.parse(texto) : {};
                            } catch (err) {
                                data = {};
                            }
                            return { okHttp: response.ok, data: data };
                        });
                    })
                    .then(function (resultado) {
                        var data = resultado.data || {};
                        if (resultado.okHttp && data.ok) {
                            fecharModalConfirmacao();
                            sairModoEdicao();
                            exibirFeedback('success', data.mensagem || 'Alterações salvas com sucesso.');
                            setTimeout(function () {
                                window.location.reload();
                            }, 800);
                        } else {
                            var msgErro = data.erro || data.mensagem || 'Não foi possível salvar as alterações no banco de dados.';
                            if (modalErroEdicao) {
                                modalErroEdicao.textContent = msgErro;
                                modalErroEdicao.style.display = 'block';
                            }
                            btnConfirmarEdicoes.disabled = false;
                            btnConfirmarEdicoes.textContent = 'Confirmar e Salvar no Banco';
                            if (btnModalCancelar) btnModalCancelar.disabled = false;
                        }
                    })
                    .catch(function () {
                        if (modalErroEdicao) {
                            modalErroEdicao.textContent = 'Erro de conexão ao salvar as alterações. Tente novamente.';
                            modalErroEdicao.style.display = 'block';
                        }
                        btnConfirmarEdicoes.disabled = false;
                        btnConfirmarEdicoes.textContent = 'Confirmar e Salvar no Banco';
                        if (btnModalCancelar) btnModalCancelar.disabled = false;
                    });
            });
        }
    }

    // Reordenação de colunas por arrastar e soltar (apenas na sessão atual; recarregar restaura padrão)
    var tabelaReordenavel = document.getElementById('tabela-assistidos');
    if (tabelaReordenavel) {
        var theadRow = tabelaReordenavel.querySelector('thead tr');
        var tbodyEl = tabelaReordenavel.querySelector('tbody');
        var btnExportarCsv = document.getElementById('btn-exportar-csv');
        var thArrastado = null;
        var arrastouRecentemente = false;

        function atualizarLinkExportacaoColunas() {
            if (!btnExportarCsv || !theadRow) return;
            var chaves = Array.prototype.map.call(
                theadRow.querySelectorAll('th[data-col-key]'),
                function (th) { return th.getAttribute('data-col-key'); }
            );
            try {
                var url = new URL(btnExportarCsv.getAttribute('href'), window.location.origin);
                url.searchParams.set('ordem_colunas', chaves.join(','));
                btnExportarCsv.setAttribute('href', url.pathname + url.search);
            } catch (e) {
                // fallback silencioso
            }
        }

        function moverColuna(indiceOrigem, indiceDestino) {
            if (indiceOrigem === indiceDestino || indiceOrigem < 0 || indiceDestino < 0) return;

            var ths = Array.prototype.slice.call(theadRow.children);
            var thOrigem = ths[indiceOrigem];
            var thDestino = ths[indiceDestino];
            if (!thOrigem || !thDestino) return;

            if (indiceOrigem < indiceDestino) {
                theadRow.insertBefore(thOrigem, thDestino.nextSibling);
            } else {
                theadRow.insertBefore(thOrigem, thDestino);
            }

            if (tbodyEl) {
                Array.prototype.forEach.call(tbodyEl.querySelectorAll('tr[data-paciente-id]'), function (tr) {
                    var tds = Array.prototype.slice.call(tr.children);
                    var tdOrigem = tds[indiceOrigem];
                    var tdDestino = tds[indiceDestino];
                    if (!tdOrigem || !tdDestino) return;
                    if (indiceOrigem < indiceDestino) {
                        tr.insertBefore(tdOrigem, tdDestino.nextSibling);
                    } else {
                        tr.insertBefore(tdOrigem, tdDestino);
                    }
                });
            }

            atualizarLinkExportacaoColunas();
        }

        if (theadRow) {
            Array.prototype.forEach.call(theadRow.querySelectorAll('th[draggable="true"]'), function (th) {
                th.addEventListener('dragstart', function (e) {
                    thArrastado = th;
                    arrastouRecentemente = true;
                    th.classList.add('th-arrastando');
                    if (e.dataTransfer) {
                        e.dataTransfer.effectAllowed = 'move';
                        e.dataTransfer.setData('text/plain', th.getAttribute('data-col-key') || '');
                    }
                });

                th.addEventListener('dragover', function (e) {
                    if (!thArrastado || thArrastado === th) return;
                    e.preventDefault();
                    if (e.dataTransfer) {
                        e.dataTransfer.dropEffect = 'move';
                    }
                    th.classList.add('th-alvo-soltar');
                });

                th.addEventListener('dragleave', function () {
                    th.classList.remove('th-alvo-soltar');
                });

                th.addEventListener('drop', function (e) {
                    if (!thArrastado || thArrastado === th) return;
                    e.preventDefault();
                    th.classList.remove('th-alvo-soltar');
                    var thsAtuais = Array.prototype.slice.call(theadRow.children);
                    var idxOrigem = thsAtuais.indexOf(thArrastado);
                    var idxDestino = thsAtuais.indexOf(th);
                    moverColuna(idxOrigem, idxDestino);
                });

                th.addEventListener('dragend', function () {
                    Array.prototype.forEach.call(theadRow.querySelectorAll('th'), function (el) {
                        el.classList.remove('th-arrastando');
                        el.classList.remove('th-alvo-soltar');
                    });
                    thArrastado = null;
                    setTimeout(function () {
                        arrastouRecentemente = false;
                    }, 80);
                });

                var linkSort = th.querySelector('.th-sort-link');
                if (linkSort) {
                    linkSort.addEventListener('click', function (e) {
                        if (arrastouRecentemente) {
                            e.preventDefault();
                        }
                    });
                }
            });
        }
    }
});
