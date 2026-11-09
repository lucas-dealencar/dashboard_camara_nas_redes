"""Transforma a aba `dados` (formato "largo") nas 7 tabelas do molde Base_Dashboard_Camara
e, quando informada, a planilha qualitativa nas tabelas `analise_propostas` e `canal_destaque`."""
import re

import pandas as pd
from prefect import task

from src.config import ABA_ANALISE_PROPOSTAS, ABA_CANAL_DESTAQUE, REDES

# Parlamentares sem "- PARTIDO/UF" no texto de Autor; o molde os preenche à mão.
OVERRIDES_PARTIDO_UF = {
    "Sen. Alessandro Vieira": ("MDB", "SE"),
    "Sen. Flávio Dino": ("PSB", "MA"),
}

# "... - PL/RO"  ou  "... (PTB/AL)"  no fim do texto
REGEX_PARTIDO_UF = r"[-(]\s*(?P<partido>[^/()\-]+?)\s*/\s*(?P<uf>[A-Z]{2})\s*\)?\s*$"

# Tag artificial: o nome da proposta traz um "00" isolado (PEC00/2026, PL 00/2026).
# Lookarounds: "00" não precedido nem seguido de dígito -> não pega PL 1009/2022,
# PL 100/2022 nem PL 1/2000, onde o "00" faz parte de um número maior.
REGEX_TAG_ARTIFICIAL = r"(?<!\d)00(?!\d)"

# Texto da aba métricas_da_semana (o molde usa "Contexto teste"; sem fonte real, fica vazio).
CONTEXTO_PADRAO = None

COLUNAS_DATA = ["data_inicio", "data_fim"]
COLUNAS_NUMERICAS = ["Menções", "Alcance", "Autores_unicos", "Engagement_Score"]
METRICAS = ["mencoes", "alcance", "autores_unicos", "engagement_score"]

COLUNAS_PROPOSTAS = [
    "proposta", "tipo_proposicao", "data_inicio", "data_fim", "semana", "categoria",
    "autor", "partido", "uf", "ementa", "situacao",
    "o_que_dizem", "o_que_mobilizou", "publicacao_representativa",
    "mencoes", "alcance", "autores_unicos", "engagement_score", "link",
]
COLUNAS_REDE = [
    "tipo_metrica", "data_inicio", "data_fim", "semana", "categoria",
    "rede_social", *METRICAS,
]
COLUNAS_METRICAS = ["semana", "contexto"]
ABAS_ESPERADAS = {
    "propostas": COLUNAS_PROPOSTAS,
    "métricas_da_semana": COLUNAS_METRICAS,
    **{aba: COLUNAS_REDE for aba in REDES.values()},
}

RENOMEAR = {
    "Semana": "semana", "Categoria": "categoria", "Autor": "autor", "Link": "link",
    "Ementa": "ementa", "Situação": "situacao", "Menções": "mencoes",
    "Alcance": "alcance", "Autores_unicos": "autores_unicos",
    "Engagement_Score": "engagement_score",
}


# --------------------------------------------------------------------------- #
# Limpeza
# --------------------------------------------------------------------------- #
def _normalizar_tipos(df: pd.DataFrame) -> pd.DataFrame:
    """O gspread devolve '' nas células vazias, datas como serial do Sheets
    (ou texto) e números possivelmente como texto."""
    df = df.replace("", pd.NA)

    for col in COLUNAS_DATA:
        serial = pd.to_numeric(df[col], errors="coerce")
        texto = df[col].where(serial.isna())
        iso = pd.to_datetime(texto, format="ISO8601", errors="coerce")  # 2026-03-16
        br = pd.to_datetime(texto.where(iso.isna()), format="%d/%m/%Y", errors="coerce")
        datas = pd.to_datetime(serial, unit="D", origin="1899-12-30").fillna(iso).fillna(br)
        df[col] = datas.dt.normalize()

    df[COLUNAS_NUMERICAS] = df[COLUNAS_NUMERICAS].apply(pd.to_numeric, errors="raise")
    return df


def _converter_semana(df: pd.DataFrame) -> pd.DataFrame:
    """'12ª' -> 12 (int64): a semana é o id que liga as tabelas."""
    numeros = df["Semana"].astype("string").str.extract(r"(\d+)", expand=False)
    if numeros.isna().any():
        raise ValueError(f"Valores de 'Semana' sem número: {df.loc[numeros.isna(), 'Semana'].unique()}")
    return df.assign(Semana=numeros.astype("int64"))


def _limpar_textos(df: pd.DataFrame) -> pd.DataFrame:
    """Remove espaços/quebras de linha nas pontas ('PEC 18/2025\\n', 'PL/RO ')."""
    df = df.copy()
    for col in df.select_dtypes(include=["object", "string"]).columns:
        df[col] = df[col].astype("string").str.strip().replace("", pd.NA)
    return df


# --------------------------------------------------------------------------- #
# Montagem das tabelas do molde
# --------------------------------------------------------------------------- #
def _montar_propostas(df: pd.DataFrame) -> pd.DataFrame:
    p = df[df["Categoria"] == "Proposta"].rename(columns=RENOMEAR).rename(columns={"Nome": "proposta"})

    artificiais = p["proposta"].str.contains(REGEX_TAG_ARTIFICIAL, regex=True, na=False)
    if artificiais.any():
        print(f"Tags artificiais removidas ({artificiais.sum()}): {sorted(p.loc[artificiais, 'proposta'].unique())}")
    p = p[~artificiais].copy()

    # "PL 1/2026" -> PL;  "EMC 1 PEC 221/2019" -> EMC
    p["tipo_proposicao"] = p["proposta"].str.split().str[0]

    p[["partido", "uf"]] = p["autor"].str.extract(REGEX_PARTIDO_UF)
    for autor, (partido, uf) in OVERRIDES_PARTIDO_UF.items():
        sem_partido = (p["autor"] == autor) & p["partido"].isna()
        p.loc[sem_partido, ["partido", "uf"]] = [partido, uf]

    # preenchidas à mão depois; não existem na origem
    for col in ["o_que_dizem", "o_que_mobilizou", "publicacao_representativa"]:
        p[col] = pd.Series(pd.NA, index=p.index, dtype="string")

    p["engagement_score"] = p["engagement_score"].astype("int64")
    # ordem do molde: semana crescente, engagement decrescente dentro da semana
    p = p.sort_values(["semana", "engagement_score"], ascending=[True, False], kind="stable")
    return p[COLUNAS_PROPOSTAS].reset_index(drop=True)


def _montar_redes(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    o = df[df["Categoria"] == "Origem"].rename(columns=RENOMEAR).rename(columns={"Nome": "rede_social"})

    desconhecidas = set(o["rede_social"]) - set(REDES)
    if desconhecidas:
        raise ValueError(f"Rede(s) sem tabela de destino: {desconhecidas}")

    o = o.assign(tipo_metrica="Resumo Semanal da Rede").astype({m: "int64" for m in METRICAS})
    o = o[COLUNAS_REDE].sort_values("semana", kind="stable")
    return {aba: o[o["rede_social"] == rede].reset_index(drop=True) for rede, aba in REDES.items()}


def _montar_metricas(semanas: pd.Series) -> pd.DataFrame:
    m = pd.DataFrame({"semana": sorted(semanas.unique())})
    m["contexto"] = pd.Series(CONTEXTO_PADRAO, index=m.index, dtype="string")
    return m[COLUNAS_METRICAS]


def _validar(tabelas: dict[str, pd.DataFrame]) -> None:
    """Falha cedo se o resultado fugir do molde."""
    for aba, colunas in ABAS_ESPERADAS.items():
        if aba not in tabelas or list(tabelas[aba].columns) != colunas:
            raise ValueError(f"[{aba}] ausente ou com colunas fora do molde")

    for aba in REDES.values():
        if tabelas[aba].empty:
            raise ValueError(f"[{aba}] sem nenhuma linha na planilha de origem")
        if tabelas[aba].duplicated("semana").any():
            raise ValueError(f"[{aba}] semana duplicada")

    for aba in ["propostas", *REDES.values()]:
        if tabelas[aba][["semana", *COLUNAS_DATA]].isna().any().any():
            raise ValueError(f"[{aba}] semana/data nula")


# --------------------------------------------------------------------------- #
# Planilha qualitativa (abas `propostas` e `canal_destaque`)
# --------------------------------------------------------------------------- #
COLUNAS_ANALISE_ORIGEM = [
    "proposta", "argumentos", "percentual", "ocorrencias", "post", "comentario",
    "o_que_mobilizou", "texto", "semana",
]
COLUNAS_ANALISE = [
    "semana", "proposta", "ordem", "argumento", "percentual", "ocorrencias",
    "posts_analisados", "comentarios_analisados", "o_que_mobilizou",
    "descricao", "postagem_representativa",
]
COLUNAS_CANAL = ["semana", "proposta", "rede_social", "engagement_score"]

# A coluna `texto` traz "<descrição do argumento>\nPostagem representativa:\n<exemplo>".
REGEX_POSTAGEM_REPRESENTATIVA = r"(?i)\s*Postagem\s+representativa\s*:\s*"

# Cabeçalho da aba `canal_destaque` (sem acento/pontuação, minúsculo) -> nome em REDES.
CANAIS_CABECALHO = {
    "instagram": "Instagram",
    "facebook": "Facebook",
    "xtwitter": "X (Twitter)",
    "twitter": "X (Twitter)",
    "x": "X (Twitter)",
    "bluesky": "Bluesky",
    "youtube": "YouTube",
}


def chave_proposta(valor) -> str:
    """Chave de junção entre abas: 'PL 1559/2021 ' e 'pl1559/2021' viram a mesma."""
    return re.sub(r"\s+", "", str(valor)).lower()


def _limpar_celulas(df: pd.DataFrame) -> pd.DataFrame:
    """Tira espaços/quebras das pontas e troca texto vazio por NA (independe da versão do pandas)."""
    def limpar(valor):
        if isinstance(valor, str):
            valor = valor.strip()
            return pd.NA if valor == "" else valor
        return valor

    return df.astype(object).apply(lambda coluna: coluna.map(limpar))


def _para_float(valor) -> float:
    """'51%', '3,5%', '1.234', 12 -> float; vazio -> NaN."""
    if valor is None or (not isinstance(valor, str) and pd.isna(valor)):
        return float("nan")
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return float(valor)
    texto = str(valor).strip().replace("%", "").replace(" ", "")
    if not texto:
        return float("nan")
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", texto):
        texto = texto.replace(".", "")
    try:
        return float(texto)
    except ValueError as erro:
        raise ValueError(f"Valor numérico inválido na planilha qualitativa: {valor!r}") from erro


def _semana_inteira(serie: pd.Series) -> pd.Series:
    """'44' / '44ª' / 44 -> 44 (int64)."""
    def extrair(valor):
        if pd.isna(valor):
            return None
        achado = re.search(r"\d+", str(valor))
        return int(achado.group()) if achado else None

    numeros = serie.map(extrair)
    if numeros.isna().any():
        raise ValueError("Linhas da planilha qualitativa sem número de semana.")
    return numeros.astype("int64")


def _percentuais(serie: pd.Series) -> pd.Series:
    """Percentual em pontos (51.0 = 51%).

    Células formatadas como % chegam como fração (0.51) em UNFORMATTED_VALUE;
    textos como '51%' ou '3,5%' já vêm em pontos.
    """
    tinha_simbolo = serie.map(lambda v: isinstance(v, str) and "%" in v)
    numeros = serie.map(_para_float)
    fracao = ~tinha_simbolo & numeros.notna()
    if fracao.any() and numeros[fracao].max() <= 1:
        numeros = numeros.where(~fracao, numeros * 100)
    return numeros.round(2)


def _montar_analise(bruto: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por argumento de cada proposta em destaque.

    A planilha repete (ou deixa em branco, se houver células mescladas) o texto de
    `o_que_mobilizou`, `post` e `comentario` em todas as linhas da mesma proposta, e o
    nome em `proposta` pode variar entre linhas (ex.: 'PLP 255/2025', 'PLP 255/2026').
    Por isso as linhas são agrupadas por blocos consecutivos de (semana, o_que_mobilizou)
    e o nome oficial é o da primeira linha do bloco.
    """
    df = bruto.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]
    faltando = set(COLUNAS_ANALISE_ORIGEM) - set(df.columns)
    if faltando:
        raise ValueError(f"[aba {ABA_ANALISE_PROPOSTAS}] colunas ausentes: {sorted(faltando)}")

    df = _limpar_celulas(df[COLUNAS_ANALISE_ORIGEM]).dropna(how="all")
    df = df[df["proposta"].notna() & df["argumentos"].notna()].reset_index(drop=True)
    if df.empty:
        raise ValueError(f"[aba {ABA_ANALISE_PROPOSTAS}] sem nenhuma linha de análise.")

    df["semana"] = _semana_inteira(df["semana"].ffill())

    mobilizou = df["o_que_mobilizou"].ffill().fillna("")
    novo_bloco = mobilizou.ne(mobilizou.shift()) | df["semana"].ne(df["semana"].shift())
    df["_bloco"] = novo_bloco.cumsum()

    bloco = df.groupby("_bloco")
    df["proposta"] = bloco["proposta"].transform("first")
    df["ordem"] = bloco.cumcount() + 1
    df["o_que_mobilizou"] = mobilizou.where(mobilizou != "", pd.NA)

    for origem, destino in [("post", "posts_analisados"), ("comentario", "comentarios_analisados")]:
        df[destino] = df[origem].map(_para_float)
        df[destino] = df.groupby("_bloco")[destino].transform("max").fillna(0).astype("int64")

    df["argumento"] = df["argumentos"]
    df["percentual"] = _percentuais(df["percentual"])
    df["ocorrencias"] = df["ocorrencias"].map(_para_float).fillna(0).astype("int64")

    partes = df["texto"].fillna("").astype(str).str.split(REGEX_POSTAGEM_REPRESENTATIVA, n=1, regex=True, expand=True)
    if partes.shape[1] < 2:
        partes[1] = ""
    df["descricao"] = partes[0].str.strip().replace("", pd.NA)
    df["postagem_representativa"] = partes[1].fillna("").str.strip().replace("", pd.NA)

    df = df.sort_values(["semana", "_bloco", "ordem"], kind="stable")
    return df[COLUNAS_ANALISE].reset_index(drop=True)


def _montar_canal(bruto: pd.DataFrame) -> pd.DataFrame:
    """Aba `canal_destaque` (uma coluna por rede) -> formato longo: semana, proposta, rede, pontos."""
    df = bruto.copy()
    df.columns = [re.sub(r"[^a-z0-9]", "", str(c).lower()) for c in df.columns]
    for obrigatoria in ("proposta", "semana"):
        if obrigatoria not in df.columns:
            raise ValueError(f"[aba {ABA_CANAL_DESTAQUE}] coluna '{obrigatoria}' ausente")

    colunas_rede = {c: CANAIS_CABECALHO[c] for c in df.columns if c in CANAIS_CABECALHO}
    if not colunas_rede:
        raise ValueError(f"[aba {ABA_CANAL_DESTAQUE}] nenhuma coluna de rede reconhecida")
    ausentes = set(REDES) - set(colunas_rede.values())
    if ausentes:
        print(f"Aviso: aba {ABA_CANAL_DESTAQUE} sem coluna para {sorted(ausentes)}; contadas como 0.")

    df = _limpar_celulas(df[["proposta", "semana", *colunas_rede]]).dropna(how="all")
    df = df[df["proposta"].notna()].copy()
    df["semana"] = _semana_inteira(df["semana"].ffill())

    longo = df.melt(id_vars=["semana", "proposta"], value_vars=list(colunas_rede), var_name="coluna", value_name="valor")
    longo["rede_social"] = longo["coluna"].map(colunas_rede)
    longo["engagement_score"] = longo["valor"].map(_para_float).fillna(0).round().astype("int64")
    longo = longo.groupby(["semana", "proposta", "rede_social"], as_index=False, sort=False)["engagement_score"].sum()

    ordem_redes = {rede: i for i, rede in enumerate(REDES)}
    longo["_ordem"] = longo["rede_social"].map(ordem_redes)
    longo = longo.sort_values(["semana", "_ordem"], kind="stable")
    return longo[COLUNAS_CANAL].reset_index(drop=True)


def _tipo_numero(valor) -> str | None:
    """'PLP 255/2026' -> 'plp255' (ignora o ano). None se o nome não segue o padrão 'TIPO N/AAAA'."""
    achado = re.fullmatch(r"([A-Za-z]+)\s*(\d+)\s*/\s*\d{4}", str(valor).strip())
    return f"{achado.group(1).lower()}{achado.group(2)}" if achado else None


def _alinhar_qualitativo(tabelas: dict[str, pd.DataFrame]) -> None:
    """Reescreve `proposta` das tabelas qualitativas com o nome oficial do ranking da semana.

    A planilha qualitativa nem sempre repete o ano do ranking (ex.: 'PLP 255/2026' para a
    proposta 'PLP 255/2025'). Ordem de tentativa, sempre dentro da mesma semana:
    1) nome igual (ignorando espaços/maiúsculas); 2) mesmo tipo e número, se houver uma só
    candidata no ranking. O que não casar é avisado e fica de fora do dashboard.
    """
    oficiais: dict[int, dict[str, str]] = {}
    for r in tabelas["propostas"].itertuples(index=False):
        oficiais.setdefault(int(r.semana), {}).setdefault(chave_proposta(r.proposta), str(r.proposta))

    for nome in ("analise_propostas", "canal_destaque"):
        tabela = tabelas[nome]
        resolvido: dict[tuple[int, str], str | None] = {}
        for semana, proposta in dict.fromkeys(zip(tabela["semana"].astype(int), tabela["proposta"].astype(str))):
            ranking = oficiais.get(semana, {})
            exato = ranking.get(chave_proposta(proposta))
            if exato is None:
                base = _tipo_numero(proposta)
                candidatas = {o for o in ranking.values() if base and _tipo_numero(o) == base}
                exato = candidatas.pop() if len(candidatas) == 1 else None
                if exato:
                    print(f"[{nome}] semana {semana}: '{proposta}' associada a '{exato}' (mesmo tipo e número).")
                else:
                    print(f"Aviso: [{nome}] semana {semana}: '{proposta}' não encontrada no ranking da aba `dados`; será ignorada.")
            resolvido[(semana, proposta)] = exato

        chaves = list(zip(tabela["semana"].astype(int), tabela["proposta"].astype(str)))
        oficial = pd.Series([resolvido[c] for c in chaves], index=tabela.index, dtype=object)
        tabela = tabela.assign(proposta=oficial)[oficial.notna()]
        tabelas[nome] = tabela.reset_index(drop=True)


@task(name="Transformar Dados", log_prints=True)
def transformar_dados(
    dados: pd.DataFrame, qualitativo: dict[str, pd.DataFrame] | None = None
) -> dict[str, pd.DataFrame]:
    """Limpa os dados brutos e os separa nas tabelas do molde.

    `qualitativo` (opcional): saída de `extrair_dados_qualitativos`. Sem ele, o dashboard
    continua funcionando e a aba "Propostas" mostra só KPIs e evolução.
    """
    print("Iniciando a transformação dos dados brutos...")
    df = _limpar_textos(_converter_semana(_normalizar_tipos(dados)))

    tabelas = {
        "propostas": _montar_propostas(df),
        "métricas_da_semana": _montar_metricas(df["Semana"]),
        **_montar_redes(df),
    }
    _validar(tabelas)

    if qualitativo:
        tabelas["analise_propostas"] = _montar_analise(qualitativo[ABA_ANALISE_PROPOSTAS])
        tabelas["canal_destaque"] = _montar_canal(qualitativo[ABA_CANAL_DESTAQUE])
        _alinhar_qualitativo(tabelas)

    print("Transformação e validação concluídas.")
    for aba, t in tabelas.items():
        print(f" - {aba:20s} {t.shape}")
    return tabelas