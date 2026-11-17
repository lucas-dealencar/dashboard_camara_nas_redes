---
marco: 4
modelo: parte A claude-opus-5-5; parte B claude-sonnet-5-5
pausa: sim (ao fim da parte A)
---

# Marco 4 — Revisão, deploy e validação ponta a ponta

Pré-requisito: marcos 1 a 3 concluídos. A parte B só roda se a **cópia** da planilha estiver configurada no `.env`.

## Parte A — Revisão crítica (`/model claude-opus-5-5`)

### Ler (somente)
`app_intranet/server/**/*.js`, `app_intranet/public/js/*.js`, `app_intranet/.env.example`, `app_intranet/notas/CONTRATO.md`. Não leia `node_modules` nem os arquivos grandes do site.

### Checklist (revise; corrija só o necessário, sem reescrever)
- **Segredos:** `credentials.json` nunca lido além do caminho em variável de ambiente, nunca em log, resposta ou erro; `.env` ignorado; `.env.example` sem valores reais; logs sem conteúdo de células.
- **Autenticação:** toda rota de escrita passa por `identificarUsuario`; em `AUTH_MODE=header` o cabeçalho só é confiável vindo do proxy (documentar que a porta do Node não fica exposta direto); usuário no log de cada gravação; verificação de `Origin`/`Host` nas rotas de escrita contra requisição forjada; limite de taxa na escrita.
- **Entrada:** validação no servidor para tudo; limites de tamanho; avaliar prefixo seguro para valores iniciados em `=`, `+`, `-`, `@` (se alguém reabrir a aba como fórmula); front sem `innerHTML` com dados externos; CSP sem `unsafe-inline` quando possível.
- **Integridade:** ordem gravar→apagar correta e recuperável; bloco legado só com confirmação; duas pessoas salvando a mesma proposta; conta de serviço sem escopo além de Sheets.

### Saída da parte A
Tabela curta: achado · gravidade · correção aplicada ou recomendada. Corrija agora os de gravidade alta; liste os demais. **Pare para aprovação do usuário.**

## Parte B — Entrega (`/model claude-sonnet-5-5`)

### B1. Empacotamento
- `Dockerfile` (`node:20-alpine`, usuário não-root, `npm ci --omit=dev`, copia só `server/`, `public/`, `package*.json`, `HEALTHCHECK` em `/api/saude`, sem `.env` nem credenciais) e `.dockerignore`. `docker build` só se o Docker estiver instalado; sem push de imagem.
- `notas/DEPLOY.md` (curto, em português): variáveis de ambiente (nome, obrigatória, exemplo); credencial montada como segredo/volume e planilha compartilhada com a conta de serviço como editora; acesso ao JSON do dashboard em `DASHBOARD_JSON` (volume ou cópia periódica do repositório); **integração com a intranet** (prefixo por `BASE_PATH`, iframe por `FRAME_ANCESTORS`, login por `AUTH_MODE=header`); comandos de build/run/logs; alternativa sem Docker (pm2 ou serviço do sistema); checklist de entrada em produção.

### B2. Teste ponta a ponta (somente na **cópia**; se o `.env` não apontar para ela, pare e avise)
1. Suba o app e grave uma proposta de teste com 4 argumentos na semana mais recente (proposta real do ranking). Anote o `id_envio`.
2. Releia a cópia: 4 linhas em `propostas` com o mesmo `id_envio`, percentuais corretos, campos repetidos, 1 linha em `canal_destaque`.
3. Regrave a mesma proposta com 3 argumentos: o bloco deve ser **substituído** (3 linhas, sem duplicata nem sobra).
4. Rode `python main.py --sem-publicar` com `SPREADSHEET_ID_QUALITATIVO` da cópia; procure nos logs avisos de percentual corrigido ou proposta sem correspondência.
5. Extraia do `docs/dados/dados_dashboard.json` **só** o trecho da proposta de teste (`node -e`, saída truncada) e confira argumentos, percentuais, descrição e postagem representativa.
6. **Restaure o JSON publicado:** `git checkout -- docs/dados/dados_dashboard.json` (o passo 4 o sobrescreve com dados da cópia).
7. Apague da cópia as linhas de teste (só as do `id_envio` anotado).

### B3. Fechamento
Escreva `app_intranet/README.md` (até 40 linhas): o que é, como rodar, como testar, onde estão contrato e deploy. Atualize `STATUS.md` (marcos, decisões abertas, pendências). Sugira a mensagem de commit, sem commitar.

### Saída da parte B
Relatório de até 10 linhas: resultado de cada passo de B2 (ok/falhou), divergências, o que falta para a produção.
