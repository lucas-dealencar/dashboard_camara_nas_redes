---
marco: 2
modelo: claude-sonnet-5-5
pausa: não
---

# Marco 2 — Backend, API e testes

Modelo: `/model claude-sonnet-5-5`. Pré-requisito: marco 1 aprovado.

## Ler (somente)
`app_intranet/CLAUDE.md`, `app_intranet/notas/CONTRATO.md`, `app_intranet/STATUS.md`.

## Resultado esperado

**Acesso à planilha**
- Autenticação por conta de serviço (`googleapis`, escopo `spreadsheets`). Leitura com `UNFORMATTED_VALUE`, gravação com `RAW`. Retentativa com recuo em erros 429/5xx.
- Colunas mapeadas **pelo nome do cabeçalho**, nunca por posição (sem acento/maiúscula; `x(twitter)` e `twitter` valem como X). Coluna ausente é relatada, não inventada.
- Leitura normalizada: `ffill` de `semana`, trim, remoção de `\r\n`. Funções para ler o bloco existente de uma proposta, listar propostas já preenchidas na semana e ler os canais.
- Cálculo de percentuais (frações 0–1, 4 casas; sem total ou total menor que a soma → usa a soma; divisão por zero → 0).
- Montagem das linhas conforme o contrato (repetição de campos, formato de `texto`, `id_envio` único, `atualizado_em` ISO).
- Escrita `salvarAnalise`: relê a aba antes de gravar; **grava as novas linhas, depois apaga as antigas** (índices decrescentes); mesma lógica para `canal_destaque`; exclusão mútua por (`semana`, `proposta`); bloco legado só com `substituirLegado`.

**API** (montada em `BASE_PATH`; `helmet` com `frame-ancestors` de `FRAME_ANCESTORS`; JSON limitado a 256 KB; serve `public/`)

| Método | Rota | Função |
|---|---|---|
| GET | `/api/saude` | `{ ok: true }` sem tocar na planilha |
| GET | `/api/semanas` | semanas, padrão e período |
| GET | `/api/semanas/:n/propostas` | ranking com descrição, autor, canais e selo `preenchida` |
| GET | `/api/analise?semana=&proposta=` | análise gravada (ou vazia) e se é legada |
| PUT | `/api/analise` | valida, calcula, grava e devolve percentuais e `id_envio` |

- Dados do dashboard: extrair só `opcoes_semanas`, `semana_padrao` e, por semana, `proposals[]` (`id`, `description`, `author`, `channels`); cache invalidado por `mtime`; nunca devolver o JSON inteiro.
- Validação com zod conforme o contrato; proposta fora do ranking da semana → 422; bloco legado sem confirmação → 409; erros em português; 500 sem detalhe interno.
- **Autenticação em um único ponto** (`identificarUsuario`), com modos `dev` (usuário fixo) e `header` (cabeçalho injetado pelo proxy/SSO da intranet; sem usuário → 401). Comentário explicando que é o ponto a trocar quando a intranet definir o login real.
- Log de cada gravação: usuário, semana, proposta, `id_envio` (sem conteúdo das células).

## Testes
- **Unitários** (`node --test`, sem rede): percentuais (soma = total, total maior, ausente, zero, 100%, arredondamento); montagem do bloco; escrita com **cliente de planilha simulado** (ordem gravar→apagar, índices decrescentes, legado rejeitado sem confirmação, exclusão mútua); validação; cada caso de borda do contrato vira um teste com o número no nome.
- **Compatibilidade com o pipeline Python:** um script Node gera as linhas exatamente como seriam gravadas em JSON temporário; `test_compat.py` (rodar com `.venv\Scripts\python`) monta DataFrames com os cabeçalhos reais e passa por `src.transformacao._montar_analise` e `_montar_canal`. Verifica: percentuais iguais (tolerância 0,05 ponto, incluindo 0%, 100% e valores pequenos); `descricao` e `postagem_representativa` separadas; `posts_analisados` e `comentarios_analisados` corretos; **`_reconciliar_percentuais` não corrige nada**; canais corretos. Sem rede nem planilha.
- Se um teste falhar por regra do pipeline que o contrato não previa, corrija o app, **não `src/`**, e registre em `STATUS.md`.

## Verificação
`npm test` e o teste de compatibilidade passando. Suba o servidor e confira com `curl` (saída truncada com `| head -c 600`) `/api/saude`, `/api/semanas` e `/api/semanas/<padrão>/propostas`. O PUT real **só na cópia** da planilha.

## Fim do marco
Relatório de até 10 linhas e atualização de `STATUS.md`.
