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

    var inputsCpf = document.querySelectorAll('.mascara-cpf');
    inputsCpf.forEach(function (input) {
        input.addEventListener('input', function (e) {
            var v = e.target.value.replace(/\D/g, '');
            if (v.length > 11) v = v.substring(0, 11);
            if (v.length > 9) {
                v = v.replace(/(\d{3})(\d{3})(\d{3})(\d{1,2})/, '$1.$2.$3-$4');
            } else if (v.length > 6) {
                v = v.replace(/(\d{3})(\d{3})(\d{1,3})/, '$1.$2.$3');
            } else if (v.length > 3) {
                v = v.replace(/(\d{3})(\d{1,3})/, '$1.$2');
            }
            e.target.value = v;
        });
    });

    var inputsTel = document.querySelectorAll('.mascara-telefone');
    inputsTel.forEach(function (input) {
        input.addEventListener('input', function (e) {
            var v = e.target.value.replace(/\D/g, '');
            if (v.length > 11) v = v.substring(0, 11);
            if (v.length > 10) {
                v = v.replace(/(\d{2})(\d{5})(\d{4})/, '($1) $2-$3');
            } else if (v.length > 6) {
                v = v.replace(/(\d{2})(\d{4})(\d{0,4})/, '($1) $2-$3');
            } else if (v.length > 2) {
                v = v.replace(/(\d{2})(\d{0,5})/, '($1) $2');
            }
            e.target.value = v;
        });
    });

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
});
