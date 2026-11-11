"""Carga: converte as tabelas tratadas no JSON consumido por docs/index.html."""
import json
from bisect import bisect_right
from pathlib import Path
from typing import Any

import pandas as pd
from prefect import task

from src.config import ARQUIVO_JSON_SAIDA, REDES
from src.transformacao import chave_proposta

JANELA_HISTORICO = 4  # semanas exibidas no gráfico "Evolução nas últimas 4 semanas" (aba Propostas)
JANELA_DESTAQUES = 6  # semanas exibidas no gráfico "Evolução nas últimas 6 semanas" (aba Destaques)
TOP_PROPOSTAS = 5     # propostas em destaque por semana (base da mediana na aba Propostas)

# campo do JSON -> coluna da tabela `propostas` (usado na variação vs. semana anterior)
CAMPOS_VARIACAO = {
    "engagement": "engagement_score",
    "posts": "mencoes",
    "authors": "autores_unicos",
    "reach": "alcance",
}


# --------------------------------------------------------------------------- #
# Conversões para tipos nativos (o json padrão não serializa NaN/NA/numpy)
# --------------------------------------------------------------------------- #
def _inteiro(valor: Any) -> int:
    return 0 if pd.isna(valor) else int(valor)


def _texto(valor: Any, padrao: str | None = None) -> str | None:
    return padrao if pd.isna(valor) else str(valor)


def _link(valor: Any) -> str | None:
    """URL da página da proposta (só http/https; qualquer outra coisa vira None)."""
    texto = _texto(valor)
    texto = texto.strip() if texto else ""
    return texto if texto.lower().startswith(("http://", "https://")) else None


def _periodo(inicio: pd.Timestamp, fim: pd.Timestamp, curto: bool = False) -> str:
    """'16/03 a 22/03/2026' (completo) ou '16/03 a 22/03' (curto, para rótulos)."""
    return f"{inicio:%d/%m} a {fim:%d/%m}" if curto else f"{inicio:%d/%m} a {fim:%d/%m/%Y}"


# --------------------------------------------------------------------------- #
# Montagem do payload
# --------------------------------------------------------------------------- #
def _totais_por_semana(tabelas: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Soma das redes por semana: engagement, menções (postagens), autores únicos e alcance."""
    redes = pd.concat([tabelas[aba] for aba in REDES.values()], ignore_index=True)
    return redes.groupby("semana")[["engagement_score", "mencoes", "autores_unicos", "alcance"]].sum()


def _canais_por_semana(tabelas: dict[str, pd.DataFrame]) -> dict[int, list[dict]]:
    """{semana: [{name, value}, ...]} na ordem das redes definida em REDES."""
    canais: dict[int, list[dict]] = {}
    for aba in REDES.values():
        for linha in tabelas[aba].itertuples(index=False):
            canais.setdefault(int(linha.semana), []).append(
                {"name": linha.rede_social, "value": _inteiro(linha.engagement_score)}
            )
    return canais


def _temas_por_semana(tabelas: dict[str, pd.DataFrame]) -> dict[int, list[dict]]:
    """{semana: [{name, value}, ...]} por categoria temática, do maior para o menor (sem zeros)."""
    temas = tabelas.get("temas")
    saida: dict[int, list[dict]] = {}
    if temas is None:
        return saida
    for linha in temas.itertuples(index=False):
        valor = _inteiro(linha.engagement_score)
        if valor > 0:
            saida.setdefault(int(linha.semana), []).append({"name": str(linha.tema), "value": valor})
    for lista in saida.values():
        lista.sort(key=lambda t: t["value"], reverse=True)
    return saida


def _mediana_top_propostas(propostas: pd.DataFrame, n: int = TOP_PROPOSTAS) -> int:
    """Mediana do engajamento das propostas que ficaram entre as `n` maiores de cada semana."""
    top = (
        propostas.sort_values(["semana", "engagement_score"], ascending=[True, False])
        .groupby("semana")
        .head(n)
    )
    return int(top["engagement_score"].median()) if not top.empty else 0


def _indice_propostas(propostas: pd.DataFrame) -> dict[int, dict[str, Any]]:
    """{semana: {chave_da_proposta: linha}} para comparar semanas e montar o histórico."""
    indice: dict[int, dict[str, Any]] = {}
    for linha in propostas.itertuples(index=False):
        indice.setdefault(int(linha.semana), {}).setdefault(chave_proposta(linha.proposta), linha)
    return indice


def _indice_analise(tabelas: dict[str, pd.DataFrame]) -> dict[tuple[int, str], dict]:
    """{(semana, chave): {mobilizacao, posts, comments, arguments[]}} a partir de `analise_propostas`."""
    analise = tabelas.get("analise_propostas")
    indice: dict[tuple[int, str], dict] = {}
    if analise is None:
        return indice
    for linha in analise.itertuples(index=False):
        registro = indice.setdefault(
            (int(linha.semana), chave_proposta(linha.proposta)),
            {
                "mobilizacao": _texto(linha.o_que_mobilizou),
                "posts": _inteiro(linha.posts_analisados),
                "comments": _inteiro(linha.comentarios_analisados),
                "arguments": [],
            },
        )
        registro["arguments"].append(
            {
                "name": str(linha.argumento),
                "count": _inteiro(linha.ocorrencias),
                "share": 0.0 if pd.isna(linha.percentual) else round(float(linha.percentual), 1),
                "description": _texto(linha.descricao, padrao=""),
                "sample": _texto(linha.postagem_representativa, padrao=""),
            }
        )
    return indice


def _indice_canais(tabelas: dict[str, pd.DataFrame]) -> dict[tuple[int, str], list[dict]]:
    """{(semana, chave): [{name, value}, ...]} a partir de `canal_destaque` (ordem de REDES)."""
    canal = tabelas.get("canal_destaque")
    indice: dict[tuple[int, str], list[dict]] = {}
    if canal is None:
        return indice
    for linha in canal.itertuples(index=False):
        indice.setdefault((int(linha.semana), chave_proposta(linha.proposta)), []).append(
            {"name": linha.rede_social, "value": _inteiro(linha.engagement_score)}
        )
    return indice


def _variacoes(atual: Any, anterior: Any) -> dict[str, float | None]:
    """Variação % de cada indicador contra a mesma proposta na semana anterior (None = sem base)."""
    saida: dict[str, float | None] = {}
    for campo, coluna in CAMPOS_VARIACAO.items():
        base = _inteiro(getattr(anterior, coluna)) if anterior is not None else 0
        saida[campo] = round((_inteiro(getattr(atual, coluna)) - base) / base * 100, 1) if base > 0 else None
    return saida


def _aparicao_anterior(chave: str, semana: int, ctx: dict[str, Any]) -> tuple[int | None, Any]:
    """(semana, linha) da aparição mais recente da proposta antes de `semana` (None se nunca apareceu)."""
    for s in range(semana - 1, ctx["semana_min"] - 1, -1):
        linha = ctx["indice"].get(s, {}).get(chave)
        if linha is not None:
            return s, linha
    return None, None


def _historico_proposta(chave: str, semana: int, ctx: dict[str, Any]) -> list[dict]:
    """Engajamento da proposta nas últimas N semanas até `semana`.

    `value` é None quando a proposta não estava entre as mais engajadas naquela semana.
    """
    primeira = max(semana - JANELA_HISTORICO + 1, ctx["semana_min"])
    historico = []
    for s in range(primeira, semana + 1):
        linha = ctx["indice"].get(s, {}).get(chave)
        historico.append(
            {
                "week": s,
                "value": None if linha is None else _inteiro(linha.engagement_score),
                "label": ctx["periodo_curto"].get(s, f"{s}ª semana"),
                "range": ctx["periodo"].get(s, ""),
            }
        )
    return historico


def _propostas_da_semana(df_semana: pd.DataFrame, eng_total: int, semana: int, ctx: dict[str, Any]) -> list[dict]:
    propostas = []
    for p in df_semana.itertuples(index=False):
        chave = chave_proposta(p.proposta)
        qual = ctx["analise"].get((semana, chave))
        # compara com a última semana em que a proposta apareceu (não só a imediatamente anterior)
        semana_anterior, anterior = _aparicao_anterior(chave, semana, ctx)
        propostas.append(
            {
                "id": str(p.proposta),
                "description": _texto(p.ementa, padrao=str(p.proposta)),
                "status": _texto(p.situacao, padrao=""),
                "link": _link(p.link),
                "engagement": _inteiro(p.engagement_score),
                "posts": _inteiro(p.mencoes),
                "authors": _inteiro(p.autores_unicos),
                "reach": _inteiro(p.alcance),
                "share": round(_inteiro(p.engagement_score) / eng_total * 100, 1) if eng_total else 0.0,
                "summary": _texto(p.o_que_dizem),
                "mobilization": (qual or {}).get("mobilizacao") or _texto(p.o_que_mobilizou),
                "sample": _texto(p.publicacao_representativa),
                "changes": _variacoes(p, anterior),
                "changes_week": semana_anterior,
                "history": _historico_proposta(chave, semana, ctx),
                "channels": ctx["canais"].get((semana, chave), []),
                "analysis": None if qual is None else {"posts": qual["posts"], "comments": qual["comments"]},
                "arguments": [] if qual is None else qual["arguments"],
            }
        )
    return propostas


def _montar_payload(tabelas: dict[str, pd.DataFrame]) -> dict[str, Any]:
    propostas = tabelas["propostas"]
    if propostas.empty:
        raise ValueError("Nenhuma proposta encontrada para estruturar o JSON.")

    totais = _totais_por_semana(tabelas)
    canais = _canais_por_semana(tabelas)
    semanas_totais = list(totais.index)
    # "Mediana anual": mediana do engajamento semanal de todas as semanas da base
    mediana = int(totais["engagement_score"].median())
    mediana_propostas = _mediana_top_propostas(propostas)
    temas = _temas_por_semana(tabelas)

    # período de cada semana (menor início / maior fim entre as propostas)
    periodos = propostas.groupby("semana").agg(ini=("data_inicio", "min"), fim=("data_fim", "max"))
    periodo = {int(s): _periodo(r.ini, r.fim) for s, r in periodos.iterrows()}
    periodo_curto = {int(s): _periodo(r.ini, r.fim, curto=True) for s, r in periodos.iterrows()}

    ctx = {
        "indice": _indice_propostas(propostas),
        "analise": _indice_analise(tabelas),
        "canais": _indice_canais(tabelas),
        "periodo": periodo,
        "periodo_curto": periodo_curto,
        "semana_min": int(propostas["semana"].min()),
    }

    dados_semanas: dict[str, Any] = {}
    for semana, df_semana in propostas.groupby("semana"):
        semana = int(semana)
        t = totais.loc[semana] if semana in totais.index else None
        eng, posts, autores, alcance = (0, 0, 0, 0) if t is None else map(_inteiro, t)

        # variação % de cada total contra a semana anterior (None se ela não existir na base)
        ant = totais.loc[semana - 1] if (semana - 1) in totais.index else None

        def variacao(coluna: str, atual: int) -> float | None:
            base = 0 if ant is None else _inteiro(ant[coluna])
            return round((atual - base) / base * 100, 1) if base > 0 else None

        # gráfico: as últimas N semanas até a semana selecionada (inclusive)
        fim_janela = bisect_right(semanas_totais, semana)
        historico = [
            {
                "week": int(s),
                "value": _inteiro(totais.at[s, "engagement_score"]),
                "label": periodo_curto.get(int(s), f"{s}ª semana"),  # eixo do gráfico e seletor
                "range": periodo.get(int(s), ""),                    # detalhe da semana
            }
            for s in semanas_totais[max(0, fim_janela - JANELA_DESTAQUES):fim_janela]
        ]

        dados_semanas[str(semana)] = {
            "edition": f"{semana}ª edição",
            "period": periodo[semana],
            "summary": f"Relatório das 5 propostas em maior destaque nas redes na {semana}ª semana.",
            "kpis": [
                {"label": "ENGAJAMENTO GERAL", "value": eng, "change": variacao("engagement_score", eng), "foot": "Pontos na semana"},
                {"label": "POSTAGENS", "value": posts, "change": variacao("mencoes", posts), "foot": "Total coletado"},
                {"label": "AUTORES ÚNICOS", "value": autores, "change": variacao("autores_unicos", autores), "foot": "Perfis distintos"},
                {"label": "ALCANCE ESTIMADO", "value": alcance, "change": variacao("alcance", alcance), "foot": "Pessoas impactadas"},
            ],
            "history": historico,
            "median": mediana,
            "proposal_median": mediana_propostas,
            "channels": canais.get(semana, []),
            "topics": temas.get(semana, []),
            "proposals": _propostas_da_semana(df_semana, eng, semana, ctx),
        }

    semanas = sorted(map(int, dados_semanas))

    # evolução anual: engajamento total de todas as semanas do ano da semana mais recente
    ano = int(periodos["fim"].max().year)
    evolucao_anual = [
        {
            "week": int(s),
            "value": _inteiro(totais.at[s, "engagement_score"]),
            "label": periodo_curto.get(int(s), f"{s}ª semana"),
        }
        for s in semanas_totais
        if int(s) in periodos.index and periodos.at[int(s), "ini"].year == ano
    ]

    return {
        "semana_padrao": str(semanas[-1]),
        "ano": ano,
        "evolucao_anual": evolucao_anual,
        "opcoes_semanas": [
            {"id": str(s), "rotulo": f"{s}ª semana", "periodo": periodo[s]} for s in reversed(semanas)
        ],
        "dados_semanas": dados_semanas,
    }


@task(name="Salvar JSON no Dashboard", log_prints=True)
def salvar_dados_json(tabelas: dict[str, pd.DataFrame], destino: Path = ARQUIVO_JSON_SAIDA) -> Path:
    """Gera o JSON do painel e o grava em docs/dados/ (pasta publicada no GitHub Pages)."""
    payload = _montar_payload(tabelas)

    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = destino.with_suffix(".tmp")  # escrita atômica: nunca deixa JSON pela metade
    temporario.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    temporario.replace(destino)

    print(f"JSON salvo em {destino} ({len(payload['dados_semanas'])} semanas).")
    return destino