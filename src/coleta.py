import gspread
import pandas as pd
from prefect import task

from src.config import (
    ABA_ANALISE_PROPOSTAS,
    ABA_CANAL_DESTAQUE,
    ABA_ORIGEM,
    CAMINHO_CREDENCIAIS,
    SPREADSHEET_ID,
    SPREADSHEET_ID_QUALITATIVO,
)


@task(
    name="Extrair Dados do Google Sheets",
    retries=3,
    retry_delay_seconds=10,
    log_prints=True,
)
def extrair_dados_sheets() -> pd.DataFrame:
    """Carrega os registros brutos da aba `dados` da planilha Semanal BW."""
    print(f"Conectando ao Google Sheets: {SPREADSHEET_ID}...")
    gc = gspread.service_account(filename=str(CAMINHO_CREDENCIAIS))
    worksheet = gc.open_by_key(SPREADSHEET_ID).worksheet(ABA_ORIGEM)

    # UNFORMATTED_VALUE: números chegam como número (independe do formato/locale
    # da célula) e datas como serial do Sheets (tratado na transformação).
    registros = worksheet.get_all_records(value_render_option="UNFORMATTED_VALUE")

    df = pd.DataFrame(registros)
    print(f"Coleta concluída: {df.shape[0]} linhas e {df.shape[1]} colunas.")
    return df


def _ler_aba(planilha: gspread.Spreadsheet, nome: str) -> pd.DataFrame:
    """Lê uma aba inteira como DataFrame, ignorando colunas sem cabeçalho.

    Usa get_all_values (e não get_all_records) porque a planilha qualitativa tem
    células vazias nas colunas de apoio e linhas em branco no fim da aba.
    """
    valores = planilha.worksheet(nome).get_all_values(value_render_option="UNFORMATTED_VALUE")
    if not valores:
        raise ValueError(f"A aba '{nome}' está vazia.")

    cabecalho = [str(c).strip() for c in valores[0]]
    manter = [i for i, coluna in enumerate(cabecalho) if coluna]
    linhas = [[(linha[i] if i < len(linha) else "") for i in manter] for linha in valores[1:]]
    return pd.DataFrame(linhas, columns=[cabecalho[i] for i in manter])


@task(
    name="Extrair Análise Qualitativa do Google Sheets",
    retries=3,
    retry_delay_seconds=10,
    log_prints=True,
)
def extrair_dados_qualitativos() -> dict[str, pd.DataFrame]:
    """Carrega as abas `propostas` (análise) e `canal_destaque` da planilha qualitativa."""
    print(f"Conectando à planilha qualitativa: {SPREADSHEET_ID_QUALITATIVO}...")
    gc = gspread.service_account(filename=str(CAMINHO_CREDENCIAIS))
    planilha = gc.open_by_key(SPREADSHEET_ID_QUALITATIVO)

    abas = {
        ABA_ANALISE_PROPOSTAS: _ler_aba(planilha, ABA_ANALISE_PROPOSTAS),
        ABA_CANAL_DESTAQUE: _ler_aba(planilha, ABA_CANAL_DESTAQUE),
    }
    for nome, df in abas.items():
        print(f" - {nome}: {df.shape[0]} linhas e {df.shape[1]} colunas.")
    return abas