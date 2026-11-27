# -*- coding: utf-8 -*-
"""Aba Análise, abaixo de "Economias faturadas por ciclo — ativas x cortadas": ligações CORTADAS que FATURARAM.

Critério: no mês, Situação Ligação "CORT…" (mesma leitura da tabela ativas × cortadas) e valor faturado de água +
esgoto > 0. Uma linha por ligação. Mostra:
  - cards e resumo por ciclo (mês atual × anterior: ligações, economias e valor);
  - novas × recorrentes (recorrente = já estava cortada e faturando no mês anterior);
  - a lista por matrícula do mês atual, com Excel.
O filtro de grupos e o de Superintendência (pela SUP do grupo, como as tabelas da tela) são refeitos no navegador
(cfatRecalcular, relatorio.js).
"""
import html
import json

import numpy as np
import pandas as pd

from .analitico import _norm_situacao
from .formatacao import fmt_num


def _num(s):
    return pd.to_numeric(s, errors="coerce").fillna(0)


def _por_ligacao(ctx, ref):
    """Uma linha por ligação cortada com valor faturado (água + esgoto) > 0 no mês `ref`."""
    b = ctx.base_final
    if b is None or not len(b) or "Situacao Ligacao" not in b.columns:
        return pd.DataFrame()
    b = b[b["Referencia de Leitura"] == ref]
    serv = b["__serv"] if "__serv" in b.columns else b["Rubrica"].astype(str).str.upper().map(
        lambda r: "E" if "ESGOTO" in r else "A" if "AGUA" in r else "")
    b = b[serv.isin(["A", "E"])]
    serv = serv[b.index]
    if not len(b):
        return pd.DataFrame()
    lig = b["N. Ligação"].astype(str).str.strip()
    sit = b["Situacao Ligacao"].map({v: _norm_situacao(v) for v in b["Situacao Ligacao"].dropna().unique()})
    cortada = (sit == "Cortada").groupby(lig.values).any()
    valor = _num(b["Valor (R$)"])
    a = (serv == "A").values
    t = pd.DataFrame({
        "valor_agua": valor.where(a, 0).groupby(lig.values).sum(),
        "valor_esgoto": valor.where(~a, 0).groupby(lig.values).sum(),
        "consumo_fat": _num(b["Consumo Faturado"]).where(a, 0).groupby(lig.values).sum(),
    })
    t["consumo_med"] = (_num(b["Consumo Medido"]).where(a, 0).groupby(lig.values).sum()
                        if "Consumo Medido" in b.columns else np.nan)
    t["valor"] = t["valor_agua"] + t["valor_esgoto"]
    t = t[cortada.reindex(t.index).fillna(False) & (t["valor"].round(2) > 0)]
    if not len(t):
        return pd.DataFrame()
    # dados descritivos: a linha de água (se houver) vem primeiro
    cols = [c for c in ("Grupo", "Nome Cliente", "Categoria", "__sup", "Situacao Ligacao", "Situacao Lancamento",
                        "Economias_Totais", "Nome da Localidade") if c in b.columns]
    ordem = np.argsort(~a, kind="stable")
    desc = b.iloc[ordem][cols].assign(__lig=lig.values[ordem]).drop_duplicates("__lig").set_index("__lig")
    return t.join(desc, how="left")


def monta_cortadas_faturando(ctx):
    """(lista do mês atual, resumo por grupo do mês anterior {grupo: [ligações, economias, valor]})."""
    ra, rn = ctx.ref_atual, ctx.ref_anterior
    at, an = _por_ligacao(ctx, ra), _por_ligacao(ctx, rn)
    ant = {}
    if len(an):
        g = an.assign(eco=_num(an.get("Economias_Totais", 0)), n=1).groupby(an["Grupo"].astype(str))[["n", "eco", "valor"]].sum()
        ant = {str(k): [int(r.n), float(r.eco), round(float(r.valor), 2)] for k, r in g.iterrows()}
    if not len(at):
        return pd.DataFrame(), ant
    d = pd.DataFrame(index=at.index)
    d.index.name = "N. Ligação"
    d["Nome Cliente"] = at.get("Nome Cliente")
    d["Categoria"] = at.get("Categoria")
    d["Superintendência"] = at.get("__sup")
    d["Localidade"] = at.get("Nome da Localidade")
    d["Grupo"] = at.get("Grupo")
    d["Situação Ligação"] = at.get("Situacao Ligacao")
    d["Situação Lançamento"] = at.get("Situacao Lancamento")
    d["Economias"] = _num(at["Economias_Totais"]) if "Economias_Totais" in at.columns else 0
    d["Consumo medido água (m³)"] = at["consumo_med"]
    d["Consumo faturado água (m³)"] = at["consumo_fat"]
    d["Valor água (R$)"] = at["valor_agua"].round(2)
    d["Valor esgoto (R$)"] = at["valor_esgoto"].round(2)
    d["Valor total (R$)"] = at["valor"].round(2)
    d[f"Valor total {rn} (R$)"] = an["valor"].round(2).reindex(d.index) if len(an) else np.nan
    d["Cortada faturando"] = np.where(d.index.isin(an.index), f"Recorrente (já em {ctx.mes_anterior})", "Nova")
    return d.sort_values("Valor total (R$)", ascending=False).reset_index(), ant


def gera_cortadas_faturando_html(ctx):
    d, ant = monta_cortadas_faturando(ctx)
    ctx.resultados["cortadas_faturando"] = d
    ra, rn = ctx.ref_atual, ctx.ref_anterior
    titulo = f"Cortadas faturando — {ctx.mes_atual}"
    if not len(d) and not ant:
        return (f"<div class='card' id='cortadas-faturando'><h2>{titulo}</h2>"
                f"<p>Nenhuma ligação com Situação Ligação cortada e valor faturado em {ctx.mes_atual} nem em {ctx.mes_anterior}.</p></div>")
    e = lambda v: html.escape("" if v is None or (isinstance(v, float) and np.isnan(v)) else str(v), quote=True)
    num = lambda v, dec=0: "—" if v is None or pd.isna(v) else fmt_num(v, dec)
    rot = "Baixar a lista (Excel), com os filtros de grupo e Superintendência"
    dl = (f'<button type="button" class="btn-just btn-cfat" data-mes="{e(ctx.mes_atual.replace("/", "-"))}" '
          f'title="{rot}" aria-label="{rot}">&#11015;&#8801;</button>')
    linhas = []
    for _, r in d.iterrows():
        rec = r["Cortada faturando"] != "Nova"
        linhas.append(
            f'<tr data-grupo="{e(r["Grupo"])}" data-sup="{e(r["Superintendência"])}" data-eco="{r["Economias"]}" '
            f'data-val="{r["Valor total (R$)"]}" data-rec="{int(rec)}">'
            f'<td>{e(r["N. Ligação"])}</td><td style="text-align:left">{e(r["Nome Cliente"])}</td><td>{e(r["Grupo"])}</td>'
            f'<td style="text-align:left">{e(r["Localidade"])}</td><td style="text-align:left">{e(r["Categoria"])}</td>'
            f'<td style="text-align:left">{e(r["Situação Ligação"])}</td><td style="text-align:left">{e(r["Situação Lançamento"])}</td>'
            f'<td>{num(r["Economias"])}</td><td>{num(r["Consumo medido água (m³)"], 1)}</td>'
            f'<td>{num(r["Consumo faturado água (m³)"], 1)}</td><td>R$ {num(r["Valor água (R$)"], 2)}</td>'
            f'<td>R$ {num(r["Valor esgoto (R$)"], 2)}</td><td style="font-weight:700">R$ {num(r["Valor total (R$)"], 2)}</td>'
            f'<td>{"—" if pd.isna(r[f"Valor total {rn} (R$)"]) else "R$ " + num(r[f"Valor total {rn} (R$)"], 2)}</td>'
            f'<td{" style=\'color:#C2560C;font-weight:700\'" if rec else ""}>{e(r["Cortada faturando"])}</td></tr>')
    dados_ant = ('<script type="application/json" id="cfat-anterior">'
                 + json.dumps(ant, ensure_ascii=False).replace("</", "<\\/") + "</script>")
    card = lambda rotulo, ident: f'<div class="cort-card"><span>{rotulo}</span><b id="{ident}">—</b></div>'
    return f"""
    <div class="card" id="cortadas-faturando" data-ra="{e(ctx.mes_atual)}" data-rn="{e(ctx.mes_anterior)}">
    <h2 style="display:flex; align-items:center; gap:12px; flex-wrap:wrap;">{titulo} {dl}</h2>
    <p class="nota-secao">Ligações com Situação Ligação <b>cortada</b> no mês e valor faturado (água + esgoto) &gt; 0.
    <b>Recorrente</b> (em <span style="color:#C2560C;font-weight:700">laranja</span>): já estava cortada e faturando em {e(ctx.mes_anterior)};
    <b>nova</b>: passou a faturar cortada neste mês. Segue os filtros de Superintendência e grupo.</p>
    <div class="cort-cards" style="display:flex; gap:12px; flex-wrap:wrap; margin:8px 0 12px;">
      {card("Ligações cortadas faturando", "cfat-qtd")}{card("Economias", "cfat-eco")}{card("Valor faturado", "cfat-val")}
      {card(f"Novas em {ctx.mes_atual}", "cfat-novas")}{card(f"Recorrentes (já em {ctx.mes_anterior})", "cfat-rec")}
      {card(f"Ligações em {ctx.mes_anterior}", "cfat-qtd-ant")}
    </div>
    <h3 style="margin:6px 0">Resumo por ciclo</h3>
    <div class="table-wrap">
    <table class="tabela-cortadas" id="tabela-cfat-resumo">
    <thead><tr><th>Ciclo</th><th>Ligações {e(ctx.mes_atual)}</th><th>Ligações {e(ctx.mes_anterior)}</th><th>Dif. ligações</th>
    <th>Novas</th><th>Recorrentes</th><th>Economias {e(ctx.mes_atual)}</th><th>Valor {e(ctx.mes_atual)}</th><th>Valor {e(ctx.mes_anterior)}</th>
    <th>Dif. valor</th></tr></thead><tbody></tbody></table></div>
    <h3 style="margin:12px 0 6px">Lista por matrícula — {ctx.mes_atual}</h3>
    <div class="table-wrap" style="max-height:520px; overflow:auto;">
    <table class="tabela-cortadas" id="tabela-cfat">
    <thead><tr><th>Ligação</th><th>Cliente</th><th>Grupo</th><th>Localidade</th><th>Categoria</th><th>Situação ligação</th>
    <th>Situação lançamento</th><th>Economias</th><th>Medido água (m³)</th><th>Faturado água (m³)</th><th>Valor água</th>
    <th>Valor esgoto</th><th>Valor total</th><th>Valor total {e(ctx.mes_anterior)}</th><th>Cortada faturando</th></tr></thead>
    <tbody>{"".join(linhas)}</tbody></table></div>{dados_ant}
    </div>"""
