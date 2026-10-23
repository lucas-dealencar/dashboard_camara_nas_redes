import argparse
from datetime import datetime
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import schedule

PASTA_SCRIPTS = Path(__file__).resolve().parent
RAIZ = PASTA_SCRIPTS.parent
PASTA_PAINEL = RAIZ / "dados_painel"
PASTA_DOCS_DADOS = RAIZ / "docs" / "dados"


def aguardar_internet(tentativas: int = 5, intervalo: int = 2) -> bool:
    """Verifica se há conexão real de rede via socket e HTTP."""
    for i in range(tentativas):
        # 1. Teste de socket direto
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            return True
        except OSError:
            pass

        # 2. Teste HTTP com cabeçalho de navegador
        try:
            req = urllib.request.Request(
                "https://www.google.com",
                headers={"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, timeout=5):
                return True
        except Exception:
            pass

        print(f"[REDE] Aguardando conexão... ({i + 1}/{tentativas})")
        time.sleep(intervalo)
    return False


def rodar_pipeline():
    agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    print(f"\n[{agora}] Iniciando atualização do painel...")

    if not aguardar_internet():
        print("[AVISO] Sem conexão com a internet no momento.")
        return

    try:
        # 1. Download da planilha do Google Drive
        subprocess.run(
            [sys.executable, str(PASTA_SCRIPTS / "coletor.py")],
            cwd=str(PASTA_SCRIPTS),
            check=True,
        )

        # 2. Processamento e cálculo das métricas analíticas
        subprocess.run(
            [sys.executable, str(PASTA_SCRIPTS / "analise.py")],
            cwd=str(PASTA_SCRIPTS),
            check=True,
        )

        # 3. Copia os payloads gerados para a pasta do GitHub Pages (docs/dados/)
        PASTA_DOCS_DADOS.mkdir(parents=True, exist_ok=True)
        shutil.copy2(
            PASTA_PAINEL / "dados_dashboard.json",
            PASTA_DOCS_DADOS / "dados_dashboard.json",
        )
        shutil.copy2(
            PASTA_PAINEL / "dados_dashboard.js",
            PASTA_DOCS_DADOS / "dados_dashboard.js",
        )
        print(
            f"[{datetime.now().strftime('%H:%M:%S')}] Dados do dashboard e pasta docs/ atualizados com sucesso!"
        )

        # 4. Automação do Git: staging, commit condicional e push
        print("[GIT] Verificando alterações para deploy no GitHub Pages...")
        subprocess.run(["git", "add", "docs/dados/"], cwd=str(RAIZ), check=True)

        # Checa se os arquivos de dados realmente mudaram antes de gerar commit vazio
        status = subprocess.run(
            ["git", "diff", "--staged", "--name-only"],
            cwd=str(RAIZ),
            capture_output=True,
            text=True,
            check=True,
        )

        if "docs/dados" in status.stdout:
            hora_commit = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            msg_commit = f"data: atualizacao automatica {hora_commit}"
            subprocess.run(["git", "commit", "-m", msg_commit], cwd=str(RAIZ), check=True)
            subprocess.run(["git", "push", "origin", "main"], cwd=str(RAIZ), check=True)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Deploy disparado no GitHub Pages com sucesso!")
        else:
            print("[GIT] Nenhuma alteração nos dados detectada. Deploy ignorado.")

    except subprocess.CalledProcessError as e:
        print(f"[ERRO] Falha na execução do pipeline (código {e.returncode}).")


def main():
    ap = argparse.ArgumentParser(
        description="Orquestrador do Dashboard Câmara nas Redes"
    )
    ap.add_argument("--manual", action="store_true", help="Roda uma vez e encerra")
    ap.add_argument(
        "--horario",
        default="07:30",
        help="Horário diário para atualização automática",
    )
    args = ap.parse_args()

    rodar_pipeline()

    if args.manual:
        return

    schedule.every().day.at(args.horario).do(rodar_pipeline)
    print(f"Agendador ativo. Próxima execução diária às {args.horario}.")
    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()