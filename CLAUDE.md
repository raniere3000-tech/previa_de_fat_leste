# Regras do repositório

- **Toda atualização muda a versão do cabeçalho do site.** Em `index.html`, aumente `VERSAO_SITE`
  (ex.: `"v16-20261006"` → `"v17-AAAAMMDD"`, com a data do dia) e o texto do `<span id="versao">`
  para o mesmo número. A mensagem do commit começa com essa versão (ex.: `v17: ...`).
- Rode `python -m pytest tests -q` antes de enviar.
- Arquivo novo no pacote `faturamento/` precisa entrar em `ARQUIVOS_PY` no `analisador.worker.js`.
- **Publicação autorizada:** o dono do repositório autorizou mesclar sempre. Depois de validar
  (testes passando), abra o PR da branch de trabalho para a `main` e mescle — a `main` é o que o
  GitHub Pages publica. Antes de mesclar, confira que o PR já contém o último commit enviado.

## Replicação do painel original (mão única)

- O painel original (`raniere3000-tech/analise-faturamento-agua-esgoto`) é a fonte: **tudo o que entra nele é replicado
  aqui**; nada daqui volta para lá. O que só existe aqui (Grandes Clientes, modelos de orçado sem a coluna Sup,
  cronograma sem Qts. Dias e filtrado pela `sup_do_painel`, prefixo do armazenamento) continua só aqui.
  O ícone da aba leva **PL** (Prévia Leste) em azul-marinho numa gota branca sobre fundo laranja (#E2671B) aqui, no `index.html` e no `faturamento/relatorio.py`; no original é PI na gota azul sobre fundo azul-marinho. As cores diferentes são o que separa os dois painéis na aba do navegador: não replique o ícone do original.
- Para replicar: `git cherry-pick -n` dos commits do original, na ordem, a partir do hash em
  `.github/replicacao-original.txt`. Nos conflitos, fica a numeração de versão daqui e o que os dois lados acrescentaram.
  Chave nova do navegador que vier do original ganha o prefixo do site (`LS_PREFIXO +` no `relatorio.js`,
  `ESCOPO + ":..."` no `index.html`) — o teste `test_armazenamento_do_navegador_separado_por_site` confere.
- Depois de publicar, troque a primeira linha de `.github/replicacao-original.txt` pelo hash completo do último commit
  replicado. O aviso (`.github/workflows/avisar-replicacao.yml`, a cada 2 horas) mantém a issue `replicar-original`
  com o que falta e a fecha quando tudo estiver replicado.
