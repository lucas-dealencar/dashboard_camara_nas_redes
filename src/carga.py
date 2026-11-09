"""Carga: converte as tabelas tratadas no JSON consumido por docs/index.html."""
import json
from bisect import bisect_right
from pathlib import Path
from typing import Any

import pandas as pd
from prefect import task

from src.config import ARQUIVO_JSON_SAIDA, REDES
from src.transformacao import chave_proposta

JANELA_HISTORICO = 4  # semanas exibidas no gráfico "Evolução nas últimas 4 semanas"

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
        anterior = ctx["indice"].get(semana - 1, {}).get(chave)
        propostas.append(
            {
                "id": str(p.proposta),
                "description": _texto(p.ementa, padrao=str(p.proposta)),
                "status": _texto(p.situacao, padrao=""),
                "engagement": _inteiro(p.engagement_score),
                "posts": _inteiro(p.mencoes),
                "authors": _inteiro(p.autores_unicos),
                "reach": _inteiro(p.alcance),
                "share": round(_inteiro(p.engagement_score) / eng_total * 100, 1) if eng_total else 0.0,
                "summary": _texto(p.o_que_dizem),
                "mobilization": (qual or {}).get("mobilizacao") or _texto(p.o_que_mobilizou),
                "sample": _texto(p.publicacao_representativa),
                "changes": _variacoes(p, anterior),
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

        # gráfico: as últimas N semanas até a semana selecionada (inclusive)
        fim_janela = bisect_right(semanas_totais, semana)
        historico = [
            {
                "week": int(s),
                "value": _inteiro(totais.at[s, "engagement_score"]),
                "label": periodo_curto.get(int(s), f"{s}ª semana"),  # eixo do gráfico e seletor
                "range": periodo.get(int(s), ""),                    # detalhe da semana
            }
            for s in semanas_totais[max(0, fim_janela - JANELA_HISTORICO):fim_janela]
        ]

        dados_semanas[str(semana)] = {
            "edition": f"{semana}ª edição",
            "period": periodo[semana],
            "summary": f"Relatório das 5 propostas em maior destaque nas redes na {semana}ª semana.",
            "kpis": [
                {"label": "ENGAJAMENTO GERAL", "value": eng, "change": None, "foot": "Pontos na semana"},
                {"label": "POSTAGENS", "value": posts, "change": None, "foot": "Total coletado"},
                {"label": "AUTORES ÚNICOS", "value": autores, "change": None, "foot": "Perfis distintos"},
                {"label": "ALCANCE ESTIMADO", "value": alcance, "change": None, "foot": "Pessoas impactadas"},
            ],
            "history": historico,
            "median": mediana,
            "channels": canais.get(semana, []),
            "topics": [],
            "proposals": _propostas_da_semana(df_semana, eng, semana, ctx),
        }

    semanas = sorted(map(int, dados_semanas))
    return {
        "semana_padrao": str(semanas[-1]),
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