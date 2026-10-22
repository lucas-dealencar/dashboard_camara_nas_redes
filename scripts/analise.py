from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd


BASE = Path(__file__).resolve().parent.parent
EXCEL_PADRAO = BASE / "dados_drive" / "Base_Dashboard_Camara.xlsx"
SAIDA_PADRAO = BASE / "dados_painel" / "dados_dashboard.json"

ABAS_REDES = {
    "instagram": "Instagram",
    "x_twitter": "X (Twitter)",
    "facebook": "Facebook",
    "bluesky": "Bluesky",
    "youtube": "YouTube",
}

COLUNAS_PROPOSTAS = [
    "proposta", "data_inicio", "data_fim", "semana", "categoria", "ementa",
    "situacao", "mencoes", "alcance", "autores_unicos", "engagement_score",
]

MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]
MESES_ABR = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set",
             "out", "nov", "dez"]

AVISOS: list[str] = []


def aviso(msg: str) -> None:
    AVISOS.append(msg)
    print(f"[AVISO] {msg}")


# ----------------------------------------------------------------------------
# Formatação 
# ----------------------------------------------------------------------------
def fmt_int_pt(v) -> str:
    return f"{int(round(float(v))):,}".replace(",", ".")


def fmt_dec_pt(x: float, casas: int = 1) -> str:
    return f"{x:.{casas}f}".replace(".", ",")


def display_compacto(v) -> str:
    """757000 -> '757 mil'; 1222405 -> '1,2 mi'; 159 -> '159'."""
    v = float(v)
    for lim, suf in ((1e6, " mi"), (1e3, " mil")):
        if v >= lim:
            s = f"{v / lim:.1f}"
            if s.endswith(".0"):
                s = s[:-2]
            return s.replace(".", ",") + suf
    return str(int(round(v)))


def intervalo_longo(ini: pd.Timestamp, fim: pd.Timestamp) -> str:
    if ini.year == fim.year and ini.month == fim.month:
        return f"{ini.day} a {fim.day} de {MESES[fim.month - 1]} de {fim.year}"
    if ini.year == fim.year:
        return (f"{ini.day} de {MESES[ini.month - 1]} a "
                f"{fim.day} de {MESES[fim.month - 1]} de {fim.year}")
    return (f"{ini.day} de {MESES[ini.month - 1]} de {ini.year} a "
            f"{fim.day} de {MESES[fim.month - 1]} de {fim.year}")


def intervalo_curto(ini: pd.Timestamp, fim: pd.Timestamp) -> str:
    if ini.month == fim.month:
        return f"{ini.day}–{fim.day} {MESES_ABR[fim.month - 1]}"
    return f"{ini.day} {MESES_ABR[ini.month - 1]}–{fim.day} {MESES_ABR[fim.month - 1]}"


def limpar(obj):
    """Converte tipos numpy/pandas e troca NaN por None (JSON válido)."""
    if isinstance(obj, dict):
        return {k: limpar(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [limpar(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        f = float(obj)
        return None if math.isnan(f) or math.isinf(f) else f
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    if obj is pd.NaT:
        return None
    return obj


# ----------------------------------------------------------------------------
# Leitura e preparo
# ----------------------------------------------------------------------------
def exigir(df: pd.DataFrame, aba: str, cols: list[str]) -> None:
    faltando = [c for c in cols if c not in df.columns]
    if faltando:
        sys.exit(f"Aba '{aba}': colunas ausentes {faltando}. Encontradas: {list(df.columns)}")


def preparar(df: pd.DataFrame) -> pd.DataFrame:
    """Padroniza datas. A semana é identificada pela data de início (segunda-feira),
    o que evita colisão de 'semana' entre anos."""
    df = df.copy()
    df["data_inicio"] = pd.to_datetime(df["data_inicio"], errors="coerce")
    if "data_fim" in df.columns:
        df["data_fim"] = pd.to_datetime(df["data_fim"], errors="coerce")
    else:
        df["data_fim"] = pd.NaT
    df = df.dropna(subset=["data_inicio"])
    df["data_inicio"] = df["data_inicio"].dt.normalize()
    df["data_fim"] = df["data_fim"].fillna(df["data_inicio"] + pd.Timedelta(days=6)).dt.normalize()
    if "semana" not in df.columns:
        df["semana"] = df["data_inicio"].dt.isocalendar().week.astype(int)
    return df


def carregar(caminho: Path):
    xls = pd.ExcelFile(caminho)
    nomes = xls.sheet_names
    if "propostas" not in nomes:
        sys.exit("Aba 'propostas' não encontrada no Excel.")
    redes = [a for a in ABAS_REDES if a in nomes]
    if not redes:
        sys.exit("Nenhuma aba de rede social encontrada (x_twitter, facebook, instagram...).")
    for a in ABAS_REDES:
        if a not in nomes:
            aviso(f"Aba de rede '{a}' ausente; ignorada.")
    dfs = {"propostas": xls.parse("propostas")}
    for a in redes:
        dfs[a] = xls.parse(a)
    for alvo, variantes in (("metricas", ("métricas_da_semana", "metricas_da_semana")),
                            ("propostas_canais", ("propostas_canais",))):
        for v in variantes:
            if v in nomes:
                dfs[alvo] = xls.parse(v)
                break
    return dfs, redes


# ----------------------------------------------------------------------------
# Cálculos
# ----------------------------------------------------------------------------
def tabela_semanal(dfs: dict, redes: list[str]):
    """Engajamento por semana (soma das redes) e por rede."""
    partes = []
    for aba in redes:
        d = preparar(dfs[aba])
        exigir(d, aba, ["engagement_score"])
        d["engagement_score"] = pd.to_numeric(d["engagement_score"], errors="coerce").fillna(0)
        d["rede"] = ABAS_REDES[aba]  # a origem precisa ser rotulada ANTES do concat
        partes.append(d[["data_inicio", "data_fim", "semana", "rede", "engagement_score"]])
    redes_df = pd.concat(partes, ignore_index=True)

    sem = redes_df.groupby("data_inicio").agg(
        semana=("semana", "first"),
        data_fim=("data_fim", "first"),
        engajamento=("engagement_score", "sum"),
    ).sort_index()
    sem = sem[sem["engajamento"] > 0]  # semanas sem postagens não entram (nota do gráfico)
    sem["ano"] = sem.index.isocalendar().year.values
    sem["variacao"] = (sem["engajamento"].pct_change() * 100).round(1)  # NaN fica None no JSON
    return sem, redes_df


def serie_kpi(dfs: dict, redes: list[str], df_prop: pd.DataFrame, candidatos_metricas: list[str],
              col_rede: str, col_prop: str, rotulo: str):
    """Série semanal de um KPI, nesta ordem de prioridade:
    1) 'métricas_da_semana', se tiver data_inicio e uma coluna correspondente;
    2) soma das abas de rede (fonte usada na base atual: mencoes, autores_unicos, alcance);
    3) soma por proposta (último recurso: cobre só as propostas monitoradas)."""
    m = dfs.get("metricas")
    if m is not None and "data_inicio" in m.columns:
        mp = preparar(m)
        mapa = {str(c).strip().lower(): c for c in mp.columns}
        col = next((mapa[c] for c in candidatos_metricas if c in mapa), None)
        if col:
            return pd.to_numeric(mp[col], errors="coerce").groupby(mp["data_inicio"]).sum(min_count=1)

    series = []
    for aba in redes:
        d = dfs[aba]
        if col_rede in d.columns:
            dd = preparar(d)
            series.append(pd.to_numeric(dd[col_rede], errors="coerce").groupby(dd["data_inicio"]).sum(min_count=1))
    if series:
        if col_rede == "autores_unicos":
            aviso("KPI 'AUTORES': soma dos autores únicos de cada rede; quem publica em mais de uma "
                  "rede é contado em cada uma (o total é um limite superior).")
        return pd.concat(series, axis=1).sum(axis=1, min_count=1)

    aviso(f"KPI '{rotulo}': sem coluna em 'métricas_da_semana' nem nas abas de rede; usei a soma por "
          f"proposta (subestima o total).")
    return pd.to_numeric(df_prop[col_prop], errors="coerce").groupby(df_prop["data_inicio"]).sum(min_count=1)


def montar_kpi(label, serie, data_alvo, data_ant, fmt, foot):
    if serie is None or data_alvo not in serie.index or pd.isna(serie[data_alvo]):
        aviso(f"KPI '{label}' sem valor na semana alvo.")
        return {"label": label, "value": None, "format": fmt, "change": None, "foot": foot}
    valor = float(serie[data_alvo])
    ant = serie.get(data_ant) if data_ant is not None else None
    change = round((valor - ant) / ant * 100, 1) if ant not in (None, 0) and not pd.isna(ant) else None
    return {"label": label, "value": int(round(valor)), "format": fmt, "change": change, "foot": foot}


def montar_temas(p: pd.DataFrame, mapa_temas: dict):
    """Temas com maior engajamento. Na base atual 'categoria' vale 'Proposta' em todas as linhas
    (não é tema), então o tema vem de uma coluna 'tema' em propostas ou de temas_propostas.json."""
    if "tema" in p.columns:
        tema = p["tema"]
    elif mapa_temas:
        tema = p["proposta"].map(mapa_temas)
    else:
        tema = None
    if tema is None or tema.dropna().empty:
        aviso("Temas: a coluna 'categoria' da base vale 'Proposta' em todas as linhas e não serve como tema. "
              "Crie uma coluna 'tema' na aba propostas ou um temas_propostas.json ({\"PL 1/2026\": \"Saúde\"}); "
              "enquanto isso, 'Temas com maior engajamento' fica vazio.")
        return []
    t = (p.assign(categoria=tema.fillna("Outros").values)
         .groupby("categoria")["engagement_score"].sum())
    t = t.sort_values(ascending=False)
    outros = float(t.get("Outros", 0))
    t = t.drop("Outros", errors="ignore")
    top = t.head(5)
    outros += float(t.iloc[5:].sum())
    itens = [{"name": k, "value": int(v), "display": display_compacto(v)} for k, v in top.items()]
    if outros > 0:
        itens.append({"name": "Outros", "value": int(outros), "display": display_compacto(outros)})
    return itens


def canais_por_proposta(dfs: dict, data_alvo):
    d = dfs.get("propostas_canais")
    if d is None:
        return {}
    d = preparar(d)
    exigir(d, "propostas_canais", ["proposta", "rede", "engagement_score"])
    d = d[d["data_inicio"] == data_alvo]
    out = {}
    for prop, g in d.groupby("proposta"):
        s = g.groupby("rede")["engagement_score"].sum().sort_values(ascending=False)
        out[prop] = [{"name": ABAS_REDES.get(r, r), "value": int(v), "display": fmt_int_pt(v)}
                     for r, v in s.items() if v > 0]
    return out


def resumo_capa(kpi_eng, vs_mediana, top1):
    c = kpi_eng["change"]
    partes = []
    if c is not None:
        verbo = "diminuiu" if c < 0 else "aumentou"
        txt = f"O engajamento {verbo} {fmt_dec_pt(abs(c))}% em relação à semana anterior"
        if vs_mediana is not None:
            rel = "abaixo" if vs_mediana < 0 else "acima"
            txt += f" e ficou {fmt_dec_pt(abs(vs_mediana))}% {rel} da mediana do ano"
        partes.append(txt + ".")
    if top1:
        partes.append(f"O destaque foi a proposta {top1['id']}, que concentrou "
                      f"{fmt_dec_pt(top1['share'])}% dos pontos de engajamento da semana.")
    return " ".join(partes)


# ----------------------------------------------------------------------------
# Montagem do relatório
# ----------------------------------------------------------------------------
def montar_relatorio(dfs, redes, semana_alvo, edicao, caminho_quali: Path):
    exigir(dfs["propostas"], "propostas", COLUNAS_PROPOSTAS)
    df_prop = preparar(dfs["propostas"])
    for c in ("engagement_score", "mencoes", "alcance", "autores_unicos"):
        df_prop[c] = pd.to_numeric(df_prop[c], errors="coerce")
    df_prop["engagement_score"] = df_prop["engagement_score"].fillna(0)

    sem, _ = tabela_semanal(dfs, redes)
    if sem.empty:
        sys.exit("Sem engajamento nas abas de redes.")

    if semana_alvo is None:
        data_alvo = sem.index.max()
    else:
        cand = sem[sem["semana"] == semana_alvo]
        if cand.empty:
            sys.exit(f"Semana {semana_alvo} não encontrada. Disponíveis: {sorted(sem['semana'].unique())}")
        data_alvo = cand.index.max()

    linha = sem.loc[data_alvo]
    anteriores = sem[sem.index < data_alvo]
    data_ant = anteriores.index.max() if not anteriores.empty else None
    if data_ant is not None and (data_alvo - data_ant).days != 7:
        aviso(f"A semana anterior na base começa em {data_ant.date()} (não é a semana imediatamente anterior).")
    total = float(linha["engajamento"])

    # mediana do ano vigente (até a semana alvo, sem semanas zeradas)
    ano = int(linha["ano"])
    mediana = float(sem[(sem["ano"] == ano) & (sem.index <= data_alvo)]["engajamento"].median())
    vs_mediana = round((total - mediana) / mediana * 100, 1) if mediana else None

    # histórico: últimas 4 semanas
    hist = sem[sem.index <= data_alvo].tail(4)
    history = [{
        "week": int(r["semana"]),
        "label": intervalo_curto(idx, r["data_fim"]),
        "range": intervalo_longo(idx, r["data_fim"]),
        "value": int(round(r["engajamento"])),
        "display": display_compacto(r["engajamento"]),
    } for idx, r in hist.iterrows()]
    for h in history:
        if mediana and h["value"] < 0.25 * mediana:
            aviso(f"Semana {h['week']} tem só {h['display']} (<25% da mediana): possível coleta incompleta.")

    # KPIs
    kpis = [
        montar_kpi("ENGAJAMENTO GERAL", sem["engajamento"], data_alvo, data_ant, "compact",
                   "Em relação à semana anterior"),
        montar_kpi("POSTAGENS",
                   serie_kpi(dfs, redes, df_prop, ["postagens", "total_postagens"], "mencoes", "mencoes", "POSTAGENS"),
                   data_alvo, data_ant, "integer", "Publicações no período monitorado"),
        montar_kpi("AUTORES",
                   serie_kpi(dfs, redes, df_prop, ["autores"], "autores_unicos", "autores_unicos", "AUTORES"),
                   data_alvo, data_ant, "integer", "Autores únicos nas publicações"),
        montar_kpi("ALCANCE ESTIMADO",
                   serie_kpi(dfs, redes, df_prop, ["alcance_estimado"], "alcance", "alcance", "ALCANCE ESTIMADO"),
                   data_alvo, data_ant, "integer", "Estimativa reportada pela fonte"),
    ]

    # canais da semana
    _, redes_df = tabela_semanal(dfs, redes)
    por_canal = (redes_df[redes_df["data_inicio"] == data_alvo]
                 .groupby("rede")["engagement_score"].sum().sort_values(ascending=False))
    channels = [{"name": r, "value": int(v), "display": display_compacto(v)}
                for r, v in por_canal.items() if v > 0]

    # propostas da semana
    p = df_prop[df_prop["data_inicio"] == data_alvo]
    if p.empty:
        sys.exit("Nenhuma proposta na semana alvo.")
    if p["proposta"].duplicated().any():
        aviso("Há mais de uma linha por proposta na semana; os valores foram somados "
              "(autores únicos pode estar duplicado).")
    agg = p.groupby("proposta", as_index=False).agg(
        description=("ementa", "first"), status=("situacao", "first"),
        engagement=("engagement_score", "sum"), posts=("mencoes", "sum"),
        authors=("autores_unicos", "sum"), reach=("alcance", "sum"),
    ).sort_values("engagement", ascending=False).head(10)

    ant_eng = {}
    if data_ant is not None:
        pa = df_prop[df_prop["data_inicio"] == data_ant]
        ant_eng = pa.groupby("proposta")["engagement_score"].sum().to_dict()

    canais_prop = canais_por_proposta(dfs, data_alvo)

    caminho_temas = caminho_quali.with_name("temas_propostas.json")
    mapa_temas = json.loads(caminho_temas.read_text(encoding="utf-8")) if caminho_temas.exists() else {}

    quali = {}
    if caminho_quali.exists():
        quali = json.loads(caminho_quali.read_text(encoding="utf-8"))
    else:
        aviso(f"{caminho_quali.name} não encontrado: resumo, mobilização, argumentos e "
              f"publicação representativa ficarão vazios no front.")

    proposals = []
    for _, r in agg.iterrows():
        pid = r["proposta"]
        ant = ant_eng.get(pid)
        item = {
            "id": pid,
            "description": r["description"] if pd.notna(r["description"])
            else "Proposta legislativa monitorada no período.",
            "status": r["status"] if pd.notna(r["status"]) else None,
            "engagement": int(r["engagement"]),
            "share": round(r["engagement"] / total * 100, 1) if total else None,
            "posts": int(r["posts"]) if pd.notna(r["posts"]) else None,
            "authors": int(r["authors"]) if pd.notna(r["authors"]) else None,
            "reach": int(r["reach"]) if pd.notna(r["reach"]) else None,
            "change": round((r["engagement"] - ant) / ant * 100, 1) if ant else None,
            "channels": canais_prop.get(pid, []),
        }
        q = quali.get(pid, {})
        for k in ("summary", "mobilization", "sample", "arguments"):
            if k in q:
                item[k] = q[k]
        if not canais_prop.get(pid) and q.get("channels"):
            item["channels"] = q["channels"]
        proposals.append(item)

    top5 = proposals[:5]
    summary = quali.get("_resumo") or resumo_capa(kpis[0], vs_mediana, top5[0] if top5 else None)

    relatorio = {
        "edition": f"{int(linha['semana'])}ª semana · {edicao}ª edição",
        "period": intervalo_longo(data_alvo, linha["data_fim"]),
        "summary": summary,
        "kpis": kpis,
        "history": history,
        "median": int(round(mediana)),
        "channels": channels,
        "topics": montar_temas(p, mapa_temas),
        "proposals": proposals,
        "methodology": METODOLOGIA,
    }
    validar(relatorio, total)
    return relatorio


def validar(rel: dict, total: float) -> None:
    obrig = ["edition", "period", "summary", "kpis", "history", "median",
             "channels", "topics", "proposals", "methodology"]
    for k in obrig:
        if not rel.get(k) and rel.get(k) != 0:
            aviso(f"Chave '{k}' vazia.")
    soma_canais = sum(c["value"] for c in rel["channels"])
    soma_temas = sum(t["value"] for t in rel["topics"])
    if total and abs(soma_canais - total) / total > 0.01:
        aviso(f"Soma dos canais ({soma_canais}) difere do total semanal ({int(total)}).")
    if total and soma_temas > total * 1.02:
        aviso(f"Soma dos temas ({soma_temas}) excede o total semanal ({int(total)}).")
    soma_shares = sum(p["share"] or 0 for p in rel["proposals"])
    if soma_shares > 100.5:
        aviso(f"Participações somam {soma_shares:.1f}% (>100%): engajamento das propostas excede o total.")
    for p in rel["proposals"][:5]:
        if p.get("channels"):
            s = sum(c["value"] for c in p["channels"])
            if p["engagement"] and abs(s - p["engagement"]) / p["engagement"] > 0.01:
                aviso(f"{p['id']}: soma dos canais ({s}) difere do engajamento ({p['engagement']}).")
        if not p.get("arguments"):
            aviso(f"{p['id']}: sem argumentos qualitativos.")


# ----------------------------------------------------------------------------
# Texto fixo de metodologia 
# ----------------------------------------------------------------------------
METODOLOGIA = {
    "gerais": [
        {"title": "Objetivo do relatório", "text": "Apresentar a repercussão pública das propostas legislativas nas redes sociais abertas, acompanhando o engajamento, os canais de maior concentração, argumentos e fatores associados à mobilização."},
        {"title": "Fonte e cobertura", "text": "Os dados são extraídos da plataforma Brandwatch e abrangem publicações de acesso público. O monitoramento parte de propostas previamente cadastradas; matérias não cadastradas não são captadas."},
        {"title": "Frequência semanal", "text": "O período segue o padrão ISO 8601: semana de segunda-feira a domingo, com numeração sequencial anual. Os relatórios são produzidos semanalmente."},
        {"title": "Alcance dos resultados", "text": "Os resultados são indicativos do debate nas publicações monitoradas e não têm base estatística para representar a opinião geral da sociedade brasileira."},
    ],
    "calculos": [
        {"title": "Engajamento", "text": "Soma das interações registradas pela plataforma em cada rede. Cada métrica considerada recebe peso igual. Instagram considera comentários e curtidas; Bluesky, Facebook e TikTok consideram comentários, curtidas e compartilhamentos; X considera curtidas, respostas e repostagens."},
        {"title": "Outras métricas", "text": "Postagens é o total coletado; autores conta perfis únicos; alcance soma a estimativa reportada pela fonte, calculada com base na quantidade de seguidores do autor. As métricas são comparadas à semana anterior."},
        {"title": "Mediana anual", "text": "A mediana do ano vigente serve como referência para avaliar se o engajamento semanal ou de uma proposta ficou acima, abaixo ou próximo do padrão anual."},
        {"title": "Tratamento dos dados", "text": "A base passa por padronização, verificação de duplicidades, identificação de conteúdos fora do tema e consolidação das métricas por canal. Publicações idênticas do mesmo autor são excluídas."},
    ],
    "analise": [
        {"title": "Delimitação de conteúdo", "text": "A análise qualitativa considera postagens que alcancem cinco pontos ou mais de engajamento. Publicações fora do tema e repetidas são excluídas da análise final."},
        {"title": "Classificação e argumentos", "text": "Publicações relevantes são classificadas por posicionamento e agrupadas por argumentos semelhantes. Os relatórios apresentam os cinco argumentos mais frequentes e publicações representativas."},
        {"title": "Inteligência artificial", "text": "Ferramentas de IA apoiam classificação, agrupamento, síntese e organização. A validação final dos números, textos e classificações é feita por servidores da Coordenação."},
        {"title": "Contexto e mobilização", "text": "Fatos públicos, andamento legislativo, declarações, cobertura jornalística e conteúdos das redes ajudam a interpretar possíveis fatores associados à participação, sem alterar os resultados apurados."},
    ],
}


# ----------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser(description="Gera o JSON do relatório Câmara nas Redes.")
    ap.add_argument("--excel", type=Path, default=EXCEL_PADRAO)
    ap.add_argument("--saida", type=Path, default=SAIDA_PADRAO)
    ap.add_argument("--semana", type=int, default=None, help="Número da semana (padrão: a mais recente).")
    ap.add_argument("--edicao", type=int, default=1, help="Número da edição da semana (padrão: 1).")
    ap.add_argument("--quali", type=Path, default=None, help="JSON da análise qualitativa.")
    args = ap.parse_args()

    caminho_quali = args.quali or args.saida.with_name("analise_qualitativa.json")
    dfs, redes = carregar(args.excel)
    relatorio = limpar(montar_relatorio(dfs, redes, args.semana, args.edicao, caminho_quali))

    args.saida.parent.mkdir(parents=True, exist_ok=True)
    texto = json.dumps(relatorio, ensure_ascii=False, indent=2)
    args.saida.write_text(texto, encoding="utf-8")
    args.saida.with_suffix(".js").write_text(
        "window.CAMARA_DEMO_DATA = " + json.dumps(relatorio, ensure_ascii=False) + ";\n", encoding="utf-8")

    print(f"\nJSON salvo: {args.saida} ({args.saida.stat().st_size / 1024:.1f} KB)")
    print(f"Semana: {relatorio['edition']} | {relatorio['period']}")
    print(f"Propostas: {len(relatorio['proposals'])} | Canais: {len(relatorio['channels'])} | "
          f"Temas: {len(relatorio['topics'])} | Avisos: {len(AVISOS)}")


if __name__ == "__main__":
    main()