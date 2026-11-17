---
marco: 1
modelo: claude-opus-5-5
modo: plano
pausa: sim
---

# Marco 1 — Estrutura e contrato de dados

Modelo: `/model claude-opus-5-5`, em modo plano. Entregáveis: base do projeto + `app_intranet/notas/CONTRATO.md` (máx. 150 linhas), aprovado pelo usuário antes de qualquer código de negócio. Erro aqui contamina tudo, então confirme cada fato contra o código.

## Ler (somente)
- `src/transformacao.py`, linhas 176–470 (qualitativo, percentuais, montagem, alinhamento);
- `src/config.py`;
- 3 blocos reais da aba `propostas`, só leitura (ver "Verificação").

## Parte A — Base do projeto
Crie `app_intranet/` com: `package.json` (ES modules, Node ≥ 20; `express`, `googleapis`, `dotenv`, `zod`, `helmet`; testes com `node --test`; sem framework de front nem bundler), `.env.example`, `.gitignore` (`node_modules/`, `.env`, `*.log`), `server/`, `public/`, `test/`, `notas/`. A divisão interna de `server/` é sua; sugestão: `config.js`, `middleware/`, `sheets/` (cliente, esquema, leitura, escrita), `dominio/` (percentual, bloco), `rotas/`. Rode `npm install`.

`.env.example` deve conter: `PORT`, `BASE_PATH=/`, `GOOGLE_APPLICATION_CREDENTIALS=../src/credentials.json`, `SPREADSHEET_ID_QUALITATIVO`, `DASHBOARD_JSON=../docs/dados/dados_dashboard.json`, `ABA_PROPOSTAS=propostas`, `ABA_CANAL=canal_destaque`, `AUTH_MODE=dev`, `AUTH_DEV_USER`, `FRAME_ANCESTORS`.

Crie `app_intranet/CLAUDE.md` (até 40 linhas, em português): propósito e stack; comandos `npm run dev` e `npm test`; erros em português; nenhum segredo em log; credenciais só por variável de ambiente; **não ler inteiros** o JSON do dashboard, `app.js` e `style.css`; escrita só na cópia da planilha; fonte de verdade em `notas/CONTRATO.md`; não alterar `main.py` nem `src/`; não commitar.

Crie `app_intranet/STATUS.md`: tabela `Marco | Estado | Observação` (4 linhas), seções "Decisões abertas" e "Pendências".

## Parte B — Fatos já levantados (confirme, não redescubra)

**Planilha:** id em `SPREADSHEET_ID_QUALITATIVO`. Aba `propostas`: `proposta, argumentos, percentual, ocorrencias, post, comentario, o_que_mobilizou, texto, semana, id_envio, atualizado_em`. Aba `canal_destaque`: `proposta, Instagram, Facebook, x(twitter), Bluesky, semana` (sem YouTube).

**Como o pipeline lê:**
- `UNFORMATTED_VALUE`; colunas sem cabeçalho são ignoradas; cabeçalho comparado em minúsculas; `semana` preenchida para baixo (`ffill`).
- **Bloco** = linhas consecutivas com mesmo (`semana`, `o_que_mobilizou`); nome oficial = primeira linha do bloco; `post` e `comentario` = máximo do bloco.
- `texto` = `<descrição>` + `Postagem representativa:` + `<exemplo>` (regex sem diferenciar maiúsculas).
- `proposta` pode ter `\r\n` ao final; `chave_proposta` ignora espaços e maiúsculas e junta as abas.
- `_alinhar_qualitativo` reescreve o nome pelo ranking da semana: o app grava o **id oficial** (`dados_semanas[semana].proposals[].id` do JSON do dashboard).

**Percentual (`_para_percentual`):** inteiro > 1 é tratado como vírgula perdida (÷10); número ≤ 1 vira fração (×100); texto com `%` já está em pontos. **Decisão proposta:** o app grava `ocorrencias / total` como **número entre 0 e 1**, sem texto. Confirme que 0, 1 e valores como 0.415 passam intactos.

**Total do percentual:** hipótese: é o campo "Total de manifestações (opcional)" do antigo Form (aba `Form Responses 1`); no PLP 108/2021, 59/142 = 41,5%. Sem o total, usar a soma das ocorrências. O total **não é gravado**; serve só para calcular o percentual.

**`canal_destaque`:** uma linha por proposta, inteiros por rede, `semana` às vezes vazia.

**JSON do dashboard:** `opcoes_semanas[]` (`id`, `rotulo`, `periodo`), `semana_padrao`, `dados_semanas[semana].proposals[]` com `id`, `description`, `author`, `channels[]` (`name`, `value`).

## Verificação (somente leitura)
Com `.venv\Scripts\python` e `gspread`, imprima no máximo 30 linhas da aba `propostas` (3 blocos recentes) e teste a hipótese do total: `ocorrencias / percentual_em_fração` deve ser constante por bloco. Não grave nada nem imprima a credencial.

## Conteúdo do CONTRATO.md
1. Esquema das duas abas (colunas, tipos, quem escreve).
2. Regras de escrita de uma proposta: ordem das linhas; repetição de `semana`, `post`, `comentario`, `o_que_mobilizou`; formato de `texto` e de `percentual`; `id_envio` (UUID por envio) e `atualizado_em` (ISO 8601).
3. **Substituição de bloco:** por `id_envio`; bloco legado sem `id_envio` por (`semana`, `chave_proposta`), só com confirmação explícita. Gravar as linhas novas **antes** de apagar as antigas (falha no meio gera duplicata, nunca perda).
4. Normalizações na leitura e na escrita.
5. Resposta ao total do percentual e à coluna YouTube.
6. Limites de validação (ocorrências inteiras ≥ 0, título obrigatório, 1 a 10 argumentos, tamanho máximo dos textos).
7. **Casos de borda numerados** que os testes do marco 2 devem cobrir.

## Fim do marco
Apresente o plano e o contrato e **pare para aprovação**. Liste as decisões que o usuário precisa confirmar (total do percentual, YouTube, regra de substituição). Atualize `STATUS.md`.
