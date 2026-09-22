# Auditoria de Segurança — OWASP Top 10

1. **A03:2025 - Injection (SQL Injection)**: Concatenação direta de parâmetro em string SQL permite extração de registros arbitrários; corrigido com consulta parametrizada via `%s`.


2. **A05:2025 - Injection (Cross-Site Scripting - XSS)**: Interpolação crua do parâmetro `u` no HTML da rota `/perfil` permite execução de scripts no navegador; corrigido aplicando `markupsafe.escape()`.


3. **A01:2025 - Broken Access Control (BOLA/IDOR)**: Deleção em `/api/usuarios/<uid>` sem autenticação permite que qualquer pessoa apague registros; corrigido exigindo Bearer token e validação de perfil `admin`.


4. **A05:2025 - Security Misconfiguration (Stack Trace e Debug Ativo)**: Servidor em modo `debug=True` e rota `/api/relatorio` sem tratamento vazam nomes de tabelas e detalhes internos no erro 500; corrigido com `debug=False` e handler global genérico.


5. **A02:2025 - Cryptographic Failures / Sensitive Data Exposure**: Uso de `SELECT *` na busca expõe campos confidenciais como a coluna `senha`; corrigido restringindo a projeção estritamente a colunas públicas (`id, nome, nivel`).


6. **A07:2025 - Identification and Authentication Failures (Hardcoded Credentials)**: Variável `SENHA_MESTRA` e dados de conexão fixos no código-fonte expõem segredos; corrigido delegando leitura para variáveis de ambiente (`os.environ`).


7. **AUSÊNCIA 1 — A05:2025 - Security Misconfiguration (Ausência de Headers Defensivos)**: Não há configuração de cabeçalhos de segurança HTTP no servidor original; corrigido injetando `Content-Security-Policy`, `X-Content-Type-Options` e `X-Frame-Options` via `@app.after_request`.


8. **AUSÊNCIA 2 — A09:2025 - Security Logging and Monitoring Failures (Ausência de Auditoria e Logs)**: Não há rastreabilidade de acessos negados, tentativas de exploração ou ações críticas de exclusão; corrigido configurando logging estruturado em `auditoria.log`.