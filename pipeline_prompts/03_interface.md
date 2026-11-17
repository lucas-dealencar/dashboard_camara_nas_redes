---
marco: 3
modelo: claude-sonnet-5-5
pausa: não
---

# Marco 3 — Interface (HTML/JS puro)

Modelo: `/model claude-sonnet-5-5`. Sem framework nem build, com módulos ES nativos: a intranet precisa conseguir incorporar a tela sem ferramentas extras. Pré-requisito: marco 2 concluído.

## Ler (somente)
`app_intranet/CLAUDE.md`, `app_intranet/notas/CONTRATO.md`. Para o visual: `grep -n -- "--[a-z-]*:" docs/assets/css/style.css | head -20` (paleta `--ink #07333a`, `--mint #36c7a6`, `--paper`, `--pale`, `--line`, `--red`; fontes DM Sans e Manrope). Não leia `app.js` nem o CSS inteiro.

## Conceito: tela de edição, não formulário rígido
Duas colunas. À esquerda, seletor de semana e a lista de propostas do ranking com selo `preenchida` ou `pendente`. À direita, a análise da proposta escolhida, editável como uma planilha.

## Requisitos para reduzir digitação
1. **Semana** já vem na `semana_padrao`; **proposta** é um clique na lista (nome oficial do ranking).
2. Cabeçalho da proposta mostra descrição e autor, para conferência.
3. **Canais** (Instagram, Facebook, X, Bluesky) já vêm preenchidos pelo ranking e são editáveis.
4. **Contexto digitado uma vez:** `o_que_mobilizou`, posts analisados, comentários analisados e, opcional, total de manifestações.
5. **Grade de argumentos** (1 a 10 linhas livres): título, ocorrências, **% calculado e somente leitura**, descrição, postagem representativa. Adicionar, remover e reordenar. Tab e Enter navegam; Enter na última célula cria nova linha.
6. **Colar do Excel/Sheets:** um bloco com tabulações colado na primeira célula distribui nas colunas e cria as linhas necessárias.
7. **Rascunho automático** em `localStorage` por (semana, proposta), com aviso ao restaurar; tudo em `try/catch`.
8. **Validação inline** antes de salvar (título vazio, ocorrências negativas, soma maior que o total) e confirmação clara de sucesso ou erro, mostrando os percentuais devolvidos pela API.
9. Ao abrir proposta já gravada, carregar a análise. Se for legada (sem `id_envio`), avisar e exigir confirmação antes de substituir.
10. Confirmar antes de trocar de proposta com alterações não salvas.

## Qualidade
- Caminhos **relativos** (funcionar sob qualquer prefixo da intranet); nada de URL absoluta.
- Nada de `innerHTML` com texto do usuário (`textContent`).
- Acessível por teclado, rótulos associados, `aria-live` nas mensagens, foco visível, contraste AA, responsivo.
- O cálculo local do % deve ser igual ao do servidor (reaproveite a mesma regra do contrato).

## Verificação
No navegador integrado: abrir uma proposta, colar 3 linhas de teste, conferir o % calculado, salvar **na cópia da planilha** e confirmar as linhas gravadas. No máximo 2 capturas (desktop e 375 px de largura).

## Fim do marco
Relatório de até 10 linhas e atualização de `STATUS.md`.
