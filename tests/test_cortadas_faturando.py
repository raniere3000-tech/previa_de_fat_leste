# -*- coding: utf-8 -*-
"""Aba Análise > Cortadas faturando: Situação Ligação cortada e valor faturado (água + esgoto) > 0 no mês;
resumo por ciclo (mês atual × anterior), novas × recorrentes e lista por matrícula."""
import json
import os
import re

import pandas as pd
import pytest

from dados_sinteticos import gera_pasta
from faturamento import Sessao
from faturamento.analitico import _norm_situacao
from faturamento.cortadas_faturando import monta_cortadas_faturando


@pytest.fixture(scope="module")
def sessao(tmp_path_factory):
    d = tmp_path_factory.mktemp("cfat") / "dados"
    gera_pasta(str(d), n_ligacoes=200, n_grupos=4)
    s = Sessao(str(d), progresso=lambda pct, desc: None)
    s.preparar()
    s.continuar()
    return s


def _esperado(ctx, ref):
    b = ctx.base_final[ctx.base_final["Referencia de Leitura"] == ref]
    b = b[b["__serv"].isin(["A", "E"])]
    lig = b["N. Ligação"].astype(str).str.strip()
    cort = b["Situacao Ligacao"].map(_norm_situacao).eq("Cortada").groupby(lig.values).any()
    val = pd.to_numeric(b["Valor (R$)"], errors="coerce").fillna(0).groupby(lig.values).sum()
    return set(val[cort & (val.round(2) > 0)].index)


def test_criterio_cortada_com_valor_faturado(sessao):
    ctx = sessao.ctx
    d, ant = monta_cortadas_faturando(ctx)
    assert len(d) and set(d["N. Ligação"]) == _esperado(ctx, ctx.ref_atual)
    assert (d["Valor total (R$)"] > 0).all()
    assert d["Valor total (R$)"].round(2).tolist() == (d["Valor água (R$)"] + d["Valor esgoto (R$)"]).round(2).tolist()
    anteriores = _esperado(ctx, ctx.ref_anterior)
    assert sum(v[0] for v in ant.values()) == len(anteriores)
    rec = d["Cortada faturando"] != "Nova"
    assert set(d.loc[rec, "N. Ligação"]) == set(d["N. Ligação"]) & anteriores    # recorrente = já cortada faturando


def test_quadro_na_aba_analise_abaixo_de_ativas_x_cortadas(sessao):
    html = open(sessao.caminho_html, encoding="utf-8").read()
    assert 'id="cortadas-faturando"' in html and 'id="tabela-cfat-resumo"' in html and 'class="btn-just btn-cfat"' in html
    assert html.index("Economias faturadas por ciclo — ativas x cortadas") < html.index('id="cortadas-faturando"')
    ant = json.loads(re.search(r'<script type="application/json" id="cfat-anterior">(.*?)</script>', html, re.S).group(1))
    assert ant == monta_cortadas_faturando(sessao.ctx)[1]
    assert html.count('<tr data-grupo=') >= len(sessao.ctx.resultados["cortadas_faturando"])


def test_navegador_refaz_com_filtros_e_worker_carrega_o_modulo():
    raiz = os.path.join(os.path.dirname(__file__), "..")
    rel = open(os.path.join(raiz, "faturamento", "assets", "relatorio.js"), encoding="utf-8").read()
    worker = open(os.path.join(raiz, "analisador.worker.js"), encoding="utf-8").read()
    assert "function cfatRecalcular()" in rel and rel.count("cfatRecalcular();") >= 2 and "Cortadas_faturando_" in rel
    assert '"faturamento/cortadas_faturando.py"' in worker
