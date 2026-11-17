# Pipeline de prompts — Interface de preenchimento (intranet)

**Objetivo:** construir `app_intranet/` (Node.js + HTML puro) para preencher as abas `propostas` e `canal_destaque` da planilha qualitativa, sem alterar o pipeline Prefect existente (`main.py`, `src/`).

## Os 4 marcos

| Marco | Arquivo | Modelo | Termina com |
|---|---|---|---|
| 1 | `01_contrato.md` | `claude-opus-5-5`, modo plano | **sua aprovação** do contrato |
| 2 | `02_backend_api.md` | `claude-sonnet-5-5` | API funcionando e testes passando |
| 3 | `03_interface.md` | `claude-sonnet-5-5` | tela validada no navegador |
| 4 | `04_revisao_entrega.md` | parte A `claude-opus-5-5`, parte B `claude-sonnet-5-5` | revisão, deploy e teste ponta a ponta |

## Como executar cada marco
```
/clear
/model <modelo do marco>
Execute @pipeline_prompts/0N_nome.md
```
No marco 1, ative o modo plano (Shift+Tab) antes de enviar. O marco 4 tem dois `/model`: troque no ponto indicado dentro do arquivo.

O contexto passa de um marco ao outro por arquivos, não por conversa: `app_intranet/CLAUDE.md` (regras), `app_intranet/notas/CONTRATO.md` (dados) e `app_intranet/STATUS.md` (andamento). Por isso o `/clear` entre marcos é seguro.

## Regras de economia de tokens (valem para todos os marcos)

1. Leia **somente** o que o marco lista em "Ler". Não explore o repositório.
2. **Nunca leia inteiro** `docs/dados/dados_dashboard.json` (mais de 600 KB), `docs/assets/js/app.js` (70 KB) ou `docs/assets/css/style.css` (79 KB). Extraia só o necessário com `node -e`, `python -c` ou `grep`.
3. Não releia o que acabou de escrever nem repita código no chat.
4. Resposta final de cada marco, no máximo 10 linhas: o que foi feito · um comando para testar · pendências. Registre também em `STATUS.md`.
5. Não faça commit nem push. Sugira a mensagem de commit.
6. Se faltar uma decisão do usuário, registre em `STATUS.md` ("Decisões abertas"), assuma o padrão indicado e siga.
7. O marco diz **o resultado esperado**. Se achar uma estrutura melhor que a sugerida, use-a e registre o motivo em uma linha no `STATUS.md`.

## Segurança dos dados
- Testes de **escrita** só numa **cópia** da planilha: aponte `SPREADSHEET_ID_QUALITATIVO` do `.env` do app para a cópia e compartilhe a cópia com a conta de serviço. Nunca teste escrita na produção.
- Credenciais: `src/credentials.json` (já ignorado pelo git), referenciado por `GOOGLE_APPLICATION_CREDENTIALS`. Nunca copie nem imprima o conteúdo.

## Decisões abertas (padrão assumido)

| Decisão | Padrão |
|---|---|
| Autenticação da intranet | middleware plugável; em desenvolvimento, usuário fixo via `.env` |
| Onde o Node roda | Docker; porta e prefixo de rota configuráveis |
| Coluna YouTube em `canal_destaque` | não existe hoje; o app ignora e avisa |
| Total usado no percentual | campo opcional "Total de manifestações"; sem ele, soma das ocorrências (confirmado no marco 1) |
