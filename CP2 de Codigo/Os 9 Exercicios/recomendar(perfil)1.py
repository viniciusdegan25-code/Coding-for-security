from typing import Dict, Any
def recomendar(perfil: Dict[str, Any]) -> Dict[str, str]:
    """
    Avalia o perfil de dados com base em integridade relacional vs flexibilidade/escala,
    mapeando as garantias do Teorema CAP e os riscos de segurança OWASP Top 10 decorrentes
    de decisões arquiteturais inadequadas.
    """
    schema_fixo = perfil.get("schema_fixo", False)
    precisa_acid = perfil.get("precisa_acid", False)
    escala_horizontal = perfil.get("escala_horizontal", False)
    tolera_atraso = perfil.get("tolera_atraso_de_consistencia", False)
    dado_sensivel = perfil.get("dado_sensivel", False)
    if precisa_acid and schema_fixo and not escala_horizontal:
        banco = "MySQL"
    else:
        banco = "MongoDB"
    if not tolera_atraso or precisa_acid:
        cap = "CP"
    else:
        cap = "AP"
    if banco == "MySQL" and cap == "CP":
        if dado_sensivel:
            justificativa = (
                "Estrutura tabular com transações ACID rígidas e integridade referencial "
                "são mandatórias; autenticação/validação incorreta é pior do que indisponibilidade temporária."
            )
            risco_owasp = "A07:2021 - Identification and Authentication Failures / A01:2021 - Broken Access Control"
        else:
            justificativa = (
                "Operações transacionais exigem atomicidade e consistência estrita "
                "(isolamento de transações), evitando anomalias financeiras ou concorrência incorreta."
            )
            risco_owasp = "A04:2021 - Insecure Design (ausência de controles transacionais de integridade de estado)"
    elif banco == "MongoDB" and cap == "CP":
        justificativa = (
            "Exige ingestão flexível e distribuição horizontal de dados, mas com consistência "
            "estrita de escrita (Write Concern: majority), pois dados divergentes invalidam "
            "análises de conformidade e valor probatório."
        )
        risco_owasp = (
            "A08:2021 - Software and Data Integrity Failures "
            "(inconsistência de logs ou corrupção de trilha de auditoria impede verificação forense)"
        )
    else:
        if dado_sensivel:
            justificativa = (
                "Prioriza altíssima taxa de resposta e escalabilidade com consistência eventual; "
                "dados em trânsito/repouso precisam de isolamento rigoroso contra dessincronização."
            )
            risco_owasp = "A02:2021 - Cryptographic Failures / A07:2021 - Identification and Authentication Failures"
        else:
            justificativa = (
                "Volume massivo de ingestão não estruturada onde latência e tolerância a partição "
                "superam perdas milimétricas; parar de registrar eventos é pior do que ter atraso na replicação."
            )
            risco_owasp = (
                "A09:2021 - Security Logging and Monitoring Failures "
                "(descarte ou bloqueio de telemetria compromete a detecção de incidentes em tempo real)"
            )
    return {
        "banco": banco,
        "cap": cap,
        "justificativa": justificativa,
        "risco_owasp": risco_owasp,
    }
if __name__ == "__main__":
    perfis = {
        "credenciais_do_SOC": {
            "schema_fixo": True,
            "precisa_acid": True,
            "escala_horizontal": False,
            "tolera_atraso_de_consistencia": False,
            "dado_sensivel": True,
        },
        "telemetria_de_sensores": {
            "schema_fixo": False,
            "precisa_acid": False,
            "escala_horizontal": True,
            "tolera_atraso_de_consistencia": True,
            "dado_sensivel": False,
        },
        "trilha_de_auditoria": {
            "schema_fixo": False,
            "precisa_acid": False,
            "escala_horizontal": True,
            "tolera_atraso_de_consistencia": False,
            "dado_sensivel": True,
        },
        "carrinho_de_licencas": {
            "schema_fixo": True,
            "precisa_acid": True,
            "escala_horizontal": False,
            "tolera_atraso_de_consistencia": False,
            "dado_sensivel": False,
        },
        "cache_de_sessoes": {
            "schema_fixo": True,
            "precisa_acid": False,
            "escala_horizontal": True,
            "tolera_atraso_de_consistencia": True,
            "dado_sensivel": True,
        },
    }

    for nome, dados in perfis.items():
        resultado = recomendar(dados)
        print(f"[{nome}] -> {resultado['banco']} | {resultado['cap']}")
        print(f"  Justificativa: {resultado['justificativa']}")
        print(f"  Risco OWASP:   {resultado['risco_owasp']}\n")