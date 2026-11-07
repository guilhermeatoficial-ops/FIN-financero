
import sqlite3
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# Chave usada para proteger as sessões
app.config['SECRET_KEY'] = 'troque-esta-chave-por-uma-chave-secreta'


# CONEXÃO COM O BANCO DE DADOS
def conectar_banco():
    conexao = sqlite3.connect('usuarios.db')
    conexao.row_factory = sqlite3.Row
    return conexao


# CRIAÇÃO DAS TABELAS
def criar_tabelas():
    conexao = conectar_banco()

    conexao.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL UNIQUE,
            idade INTEGER NOT NULL,
            senha TEXT NOT NULL
        )
    """)

    conexao.execute("""
        CREATE TABLE IF NOT EXISTS historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT NOT NULL,
            ferramenta TEXT NOT NULL,
            detalhes TEXT NOT NULL,
            resultado TEXT NOT NULL,
            data TEXT NOT NULL
        )
    """)

    conexao.commit()
    conexao.close()


criar_tabelas()


# CONVERTER TEXTO PARA NÚMERO
def ler_numero(campo):
    texto = request.form.get(campo, '').strip()
    return float(texto.replace(',', '.'))


# SALVAR CÁLCULO NO HISTÓRICO
def salvar_calculo(ferramenta, detalhes, resultado):
    conexao = conectar_banco()

    conexao.execute("""
        INSERT INTO historico
        (usuario, ferramenta, detalhes, resultado, data)
        VALUES (?, ?, ?, ?, ?)
    """, (
        session['usuario'],
        ferramenta,
        detalhes,
        str(resultado),
        datetime.now().strftime('%d/%m/%Y %H:%M')
    ))

    conexao.commit()
    conexao.close()


# PÁGINA INICIAL
@app.route('/')
def index():
    return render_template('index.html')


# PÁGINA DE CADASTRO
@app.route('/cadastro')
def pagina_cadastro():
    return render_template('cadastro.html')


# CADASTRAR USUÁRIO
@app.route('/cadastrar', methods=['POST'])
def cadastrar():
    nome = request.form['nome'].strip()
    idade = int(request.form['idade'])
    senha = request.form['senha']

    if idade < 18:
        return "Cadastro não permitido para menores de 18 anos."

    senha_hash = generate_password_hash(senha)
    conexao = conectar_banco()

    try:
        conexao.execute("""
            INSERT INTO usuarios (nome, idade, senha)
            VALUES (?, ?, ?)
        """, (nome, idade, senha_hash))

        conexao.commit()

        return render_template('cadastro_sucesso.html', nome=nome)

    except sqlite3.IntegrityError:
        return "Esse nome de usuário já está cadastrado."

    finally:
        conexao.close()


# LOGIN DO USUÁRIO
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        if 'usuario' in session:
            return redirect(url_for('painel'))

        return render_template('login.html')

    nome = request.form['nome'].strip()
    senha = request.form['senha']

    conexao = conectar_banco()

    try:
        usuario = conexao.execute(
            "SELECT senha FROM usuarios WHERE nome = ?",
            (nome,)
        ).fetchone()

        if not usuario:
            return render_template(
                'login.html',
                erro="Nome de usuário ou senha incorretos."
            )

        senha_salva = str(usuario['senha'])

        if senha_salva.startswith(('scrypt:', 'pbkdf2:')):
            senha_correta = check_password_hash(senha_salva, senha)
        else:
            senha_correta = senha_salva == senha

            if senha_correta:
                novo_hash = generate_password_hash(senha)
                conexao.execute(
                    "UPDATE usuarios SET senha = ? WHERE nome = ?",
                    (novo_hash, nome)
                )
                conexao.commit()

        if senha_correta:
            session.clear()
            session['usuario'] = nome
            return redirect(url_for('painel'))

        return render_template(
            'login.html',
            erro="Nome de usuário ou senha incorretos."
        )

    finally:
        conexao.close()


# PAINEL PRINCIPAL
@app.route('/painel')
def painel():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    return render_template('painel.html', nome=session['usuario'])


# SAIR DA CONTA
@app.route('/sair')
def sair():
    session.clear()
    return redirect(url_for('login'))


# PORCENTAGEM
@app.route('/porcentagem', methods=['GET', 'POST'])
def porcentagem():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    resultado = None
    erro = None

    if request.method == 'POST':
        try:
            valor = ler_numero('valor')
            taxa = ler_numero('taxa')
            operacao = request.form['operacao']

            if valor < 0 or taxa < 0:
                raise ValueError

            calculado = valor * taxa / 100

            if operacao == 'porcentagem':
                resultado = calculado
                nome_operacao = 'Porcentagem'
            elif operacao == 'desconto':
                resultado = valor - calculado
                nome_operacao = 'Desconto'
            elif operacao == 'acrescimo':
                resultado = valor + calculado
                nome_operacao = 'Acréscimo'
            else:
                raise ValueError

            detalhes = (
                f"{nome_operacao}: R$ {valor:.2f}, taxa de {taxa:.2f}%"
            )
            salvar_calculo('Porcentagem', detalhes, f"R$ {resultado:.2f}")

        except (ValueError, TypeError):
            erro = "Confira os valores informados."

    return render_template(
        'porcentagem.html',
        resultado=resultado,
        erro=erro
    )


# JUROS SIMPLES
@app.route('/juros-simples', methods=['GET', 'POST'])
def juros_simples():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    resultado = None
    erro = None

    if request.method == 'POST':
        try:
            capital = ler_numero('capital')
            taxa = ler_numero('taxa')
            tempo = ler_numero('tempo')

            if capital < 0 or taxa < 0 or tempo < 0:
                raise ValueError

            juros = capital * (taxa / 100) * tempo
            montante = capital + juros

            resultado = {
                'juros': juros,
                'montante': montante
            }

            detalhes = (
                f"Capital: R$ {capital:.2f}; "
                f"taxa por período: {taxa:.2f}%; "
                f"períodos: {tempo:g}"
            )

            salvar_calculo(
                'Juros simples',
                detalhes,
                f"Juros: R$ {juros:.2f}; Montante: R$ {montante:.2f}"
            )

        except (ValueError, TypeError):
            erro = "Confira os valores informados."

    return render_template(
        'juros_simples.html',
        resultado=resultado,
        erro=erro
    )


# JUROS COMPOSTOS
@app.route('/juros-compostos', methods=['GET', 'POST'])
def juros_compostos():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    resultado = None
    erro = None

    if request.method == 'POST':
        try:
            capital = ler_numero('capital')
            taxa = ler_numero('taxa')
            tempo = ler_numero('tempo')

            if capital < 0 or taxa < 0 or tempo < 0:
                raise ValueError

            montante = capital * (1 + taxa / 100) ** tempo
            juros = montante - capital

            resultado = {
                'juros': juros,
                'montante': montante
            }

            detalhes = (
                f"Capital: R$ {capital:.2f}; "
                f"taxa por período: {taxa:.2f}%; "
                f"períodos: {tempo:g}"
            )

            salvar_calculo(
                'Juros compostos',
                detalhes,
                f"Juros: R$ {juros:.2f}; Montante: R$ {montante:.2f}"
            )

        except (ValueError, TypeError, OverflowError):
            erro = "Confira os valores. A simulação pode estar grande demais."

    return render_template(
        'juros_compostos.html',
        resultado=resultado,
        erro=erro
    )


# CONVERSOR DE TEMPO
@app.route('/conversor-tempo', methods=['GET', 'POST'])
def conversor_tempo():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    resultado = None
    erro = None

    # Conversões usando dias como unidade intermediária.
    # Para esta ferramenta: 1 mês = 30 dias e 1 ano = 365 dias.
    fatores = {
        'segundos': 1 / 86400,
        'minutos': 1 / 1440,
        'horas': 1 / 24,
        'dias': 1,
        'meses': 30,
        'anos': 365
    }

    if request.method == 'POST':
        try:
            valor = ler_numero('valor')
            origem = request.form['origem']
            destino = request.form['destino']

            if valor < 0 or origem not in fatores or destino not in fatores:
                raise ValueError

            dias = valor * fatores[origem]
            convertido = dias / fatores[destino]

            resultado = {
                'valor': convertido,
                'unidade': destino
            }

            detalhes = f"{valor:g} {origem} para {destino}"

            salvar_calculo(
                'Conversor de tempo',
                detalhes,
                f"{convertido:.6g} {destino}"
            )

        except (ValueError, TypeError):
            erro = "Confira o valor e as unidades escolhidas."

    return render_template(
        'conversor_tempo.html',
        resultado=resultado,
        erro=erro
    )


# HISTÓRICO DE CÁLCULOS
@app.route('/historico')
def historico():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    conexao = conectar_banco()

    registros = conexao.execute("""
        SELECT ferramenta, detalhes, resultado, data
        FROM historico
        WHERE usuario = ?
        ORDER BY id DESC
    """, (session['usuario'],)).fetchall()

    conexao.close()

    return render_template('historico.html', registros=registros)


# INICIAR A APLICAÇÃO
if __name__ == '__main__':
    app.run(debug=True)
