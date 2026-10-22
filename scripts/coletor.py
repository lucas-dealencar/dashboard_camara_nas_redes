import argparse
import io
import re
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# ----------------------------------------------------------------------------
# Resolução dinâmica de caminhos
# ----------------------------------------------------------------------------
PASTA_SCRIPTS = Path(__file__).resolve().parent
RAIZ = PASTA_SCRIPTS.parent

ARQUIVO_TOKEN = PASTA_SCRIPTS / "token.json"
ARQUIVO_CREDENCIAIS = PASTA_SCRIPTS / "credentials.json"
ARQUIVO_SERVICE_ACCOUNT = PASTA_SCRIPTS / "service_account.json"
PASTA_SAIDA_PADRAO = RAIZ / "dados_drive"

PASTA_ID = "1-vaxZwsEOiMFJHCa02QwNwuErJblYKFT"
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

MIME_PASTA = "application/vnd.google-apps.folder"
MIME_SHEETS = "application/vnd.google-apps.spreadsheet"
MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
MIME_XLS = "application/vnd.ms-excel"
MIME_CSV = "text/csv"


# ----------------------------------------------------------------------------
# Autenticação
# ----------------------------------------------------------------------------
def autenticar(modo: str):
    if modo == "service":
        creds = service_account.Credentials.from_service_account_file(
            str(ARQUIVO_SERVICE_ACCOUNT), scopes=SCOPES
        )
    else:
        creds = None
        if ARQUIVO_TOKEN.exists():
            creds = Credentials.from_authorized_user_file(str(ARQUIVO_TOKEN), SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                fluxo = InstalledAppFlow.from_client_secrets_file(
                    str(ARQUIVO_CREDENCIAIS), SCOPES
                )
                creds = fluxo.run_local_server(port=0)
            with open(ARQUIVO_TOKEN, "w", encoding="utf-8") as f:
                f.write(creds.to_json())
    return build("drive", "v3", credentials=creds)


# ----------------------------------------------------------------------------
# Listagem
# ----------------------------------------------------------------------------
def listar_pasta(servico, pasta_id: str, caminho: str = ""):
    """Retorna lista de dicts com os arquivos da pasta (recursivo)."""
    arquivos = []
    page_token = None
    while True:
        resp = (
            servico.files()
            .list(
                q=f"'{pasta_id}' in parents and trashed = false",
                fields="nextPageToken, files(id, name, mimeType, modifiedTime, size)",
                pageSize=1000,
                pageToken=page_token,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            )
            .execute()
        )
        for item in resp.get("files", []):
            item["caminho"] = caminho
            if item["mimeType"] == MIME_PASTA:
                arquivos.extend(
                    listar_pasta(servico, item["id"], f"{caminho}{item['name']}/")
                )
            else:
                arquivos.append(item)
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return arquivos


# ----------------------------------------------------------------------------
# Download
# ----------------------------------------------------------------------------
def nome_seguro(nome: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "_", nome)


def _baixar(requisicao, destino: Path):
    destino.parent.mkdir(parents=True, exist_ok=True)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, requisicao)
    pronto = False
    while not pronto:
        _, pronto = downloader.next_chunk()
    destino.write_bytes(buffer.getvalue())


def baixar_arquivo(servico, item: dict, pasta_saida: Path):
    """Baixa um arquivo. Retorna o Path salvo ou None se o tipo não for suportado."""
    base = pasta_saida / item["caminho"]
    nome = nome_seguro(item["name"])
    mime = item["mimeType"]

    if mime == MIME_SHEETS:
        # Exporta como XLSX para manter todas as abas (necessário para o analise.py)
        nome_arquivo = nome if nome.lower().endswith(".xlsx") else f"{nome}.xlsx"
        destino = base / nome_arquivo
        req = servico.files().export_media(fileId=item["id"], mimeType=MIME_XLSX)
    elif mime in (MIME_XLSX, MIME_XLS, MIME_CSV) or nome.lower().endswith(
        (".xlsx", ".xls", ".csv")
    ):
        destino = base / nome
        req = servico.files().get_media(fileId=item["id"], supportsAllDrives=True)
    else:
        return None

    _baixar(req, destino)
    return destino


# ----------------------------------------------------------------------------
# Execução Principal
# ----------------------------------------------------------------------------
def coletar(auth: str = "oauth", pasta_id: str = PASTA_ID, saida: Path | str = PASTA_SAIDA_PADRAO):
    servico = autenticar(auth)
    saida = Path(saida)
    saida.mkdir(parents=True, exist_ok=True)

    print("Listando arquivos da pasta do Google Drive...")
    itens = listar_pasta(servico, pasta_id)
    print(f"{len(itens)} arquivo(s) encontrado(s).")

    for item in itens:
        try:
            destino = baixar_arquivo(servico, item, saida)
            status = "baixado" if destino else "ignorado (tipo não suportado)"
        except Exception as e:
            status = f"erro: {e}"
        print(f" - {item['caminho']}{item['name']}: {status}")

    print(f"\nConcluído. Arquivos salvos em '{saida}/'.")


def main():
    ap = argparse.ArgumentParser(description="Coleta dados de uma pasta do Google Drive")
    ap.add_argument("--auth", choices=["oauth", "service"], default="oauth")
    ap.add_argument("--pasta-id", default=PASTA_ID)
    ap.add_argument("--saida", default=str(PASTA_SAIDA_PADRAO), help="Diretório de destino dos downloads")
    args, _ = ap.parse_known_args()
    coletar(args.auth, args.pasta_id, args.saida)


if __name__ == "__main__":
    main()