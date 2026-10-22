import argparse
from datetime import datetime
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.request
import schedule
import socket


PASTA_SCRIPTS = Path(__file__).resolve().parent
RAIZ = PASTA_SCRIPTS.parent
PASTA_PAINEL = RAIZ / "dados_painel"
PASTA_DOCS_DADOS = RAIZ / "docs" / "dados"


def aguardar_internet(tentativas: int = 5, intervalo: int = 2) -> bool:
    """Verifica se há conexão real de rede via socket e HTTP."""
    for i in range(tentativas):
        # 1. Teste rápido de socket direto (funciona mesmo com proxy/firewall)
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
        # 1. Download do Drive
        subprocess.run(
            [sys.executable, str(PASTA_SCRIPTS / "coletor.py")],
            cwd=str(PASTA_SCRIPTS),
            check=True,
        )

        # 2. Processamento e cálculo de métricas
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