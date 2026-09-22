import logging
import os
from functools import wraps
import mysql.connector
from flask import Flask, jsonify, request
from markupsafe import escape
app = Flask(__name__)
logging.basicConfig(
    filename="auditoria.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("app_seguro")
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_USER = os.environ.get("DB_USER", "app_usuarios")
DB_PASSWORD = os.environ.get("DB_PASSWORD")
DB_NAME = os.environ.get("DB_NAME", "seguranca")
def _carregar_tokens():
    """Formato da env var: 'token1:nivel1,token2:nivel2'."""
    bruto = os.environ.get("API_TOKENS", "")
    tokens = {}
    for par in bruto.split(","):
        if ":" in par:
            tok, nivel = par.split(":", 1)
            tokens[tok.strip()] = nivel.strip()
    return tokens
TOKENS_VALIDOS = _carregar_tokens()
def db():
    if not DB_PASSWORD:
        raise RuntimeError("DB_PASSWORD não configurada no ambiente.")
    return mysql.connector.connect(
        host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_NAME
    )
def requer_nivel(nivel_minimo):
    """
    Falha #3: DELETE sem autenticação/autorização.
    Corrige: A01:2025 - Broken Access Control
    Sem credencial -> 401. Credencial válida mas nível errado -> 403.
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            auth = request.headers.get("Authorization", "")
            if not auth.startswith("Bearer "):
                logger.warning(
                    "Acesso negado (sem credencial) em %s de %s",
                    request.path, request.remote_addr,
                )
                return jsonify({"erro": "autenticacao obrigatoria"}), 401
            token = auth[len("Bearer "):].strip()
            nivel_usuario = TOKENS_VALIDOS.get(token)
            if nivel_usuario is None:
                logger.warning(
                    "Token invalido em %s de %s", request.path, request.remote_addr
                )
                return jsonify({"erro": "autenticacao obrigatoria"}), 401

            if nivel_usuario != nivel_minimo:
                logger.warning(
                    "Nivel insuficiente (%s) em %s de %s",
                    nivel_usuario, request.path, request.remote_addr,
                )
                return jsonify({"erro": "privilegio insuficiente"}), 403
            return f(*args, **kwargs)
        return wrapper
    return decorator
@app.after_request
def adicionar_headers_seguranca(resp):
    """
    Falha #7: headers de segurança ausentes.
    Corrige: A02:2025 - Security Misconfiguration
    """
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Content-Security-Policy"] = "default-src 'self'"
    return resp
@app.route("/api/usuarios/buscar")
def buscar():
    nome = request.args.get("nome", "")
    try:
        con = db()
        cur = con.cursor(dictionary=True)
        cur.execute(
            "SELECT id, nome, nivel FROM usuarios WHERE nome LIKE %s",
            (f"%{nome}%",),
        )
        resultado = cur.fetchall()
        cur.close()
        con.close()
        return jsonify(resultado)
    except mysql.connector.Error:
        logger.exception("Erro ao consultar usuarios")
        return jsonify({"erro": "erro interno"}), 500
@app.route("/perfil")
def perfil():
    """
    Falha #2: XSS refletido (eco cru da query string).
    Corrige: A05:2025 - Injection -> escapar toda saída dinâmica.
    """
    u = request.args.get("u", "")
    return f"<h1>Bem-vindo, {escape(u)}</h1>"
@app.route("/api/usuarios/<int:uid>", methods=["DELETE"])
@requer_nivel("admin")
def remover(uid):
    try:
        con = db()
        cur = con.cursor()
        cur.execute("DELETE FROM usuarios WHERE id = %s", (uid,))
        con.commit()
        afetadas = cur.rowcount
        cur.close()
        con.close()
        logger.info("Usuario %s removido (token autorizado, nivel admin)", uid)
        if afetadas == 0:
            return jsonify({"erro": "usuario nao encontrado"}), 404
        return jsonify({"removido": uid})
    except mysql.connector.Error:
        logger.exception("Erro ao remover usuario")
        return jsonify({"erro": "erro interno"}), 500
@app.route("/api/relatorio")
def relatorio():
    """
    Falha #5: exceção não tratada expunha traceback e nome de tabela.
    Corrige: A10:2025 - Mishandling of Exceptional Conditions.
    """
    try:
        con = db()
        cur = con.cursor()
        cur.execute("SELECT * FROM tabela_inexistente")
        resultado = cur.fetchall()
        cur.close()
        con.close()
        return jsonify(resultado)
    except mysql.connector.Error:
        logger.exception("Erro ao gerar relatorio")
        return jsonify({"erro": "erro interno"}), 500
@app.errorhandler(Exception)
def erro_generico(e):
    """Rede de segurança final: nenhuma exceção não tratada vaza detalhe ao cliente."""
    logger.exception("Excecao nao tratada")
    return jsonify({"erro": "erro interno"}), 500
if __name__ == "__main__":
    app.run(debug=False, host="127.0.0.1", port=5000)