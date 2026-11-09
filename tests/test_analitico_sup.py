# -*- coding: utf-8 -*-
"""Analítico por matrícula com a Superintendência escolhida: a matrícula entra pela SUP do GRUPO dela (a mesma das
tabelas da tela, pela Localidade do cronograma), não só pela cidade da matrícula. Antes, um grupo do cronograma da
Interior com matrículas de cidade da Leste baixava o analítico vazio enquanto a tabela da tela tinha números."""
import json
import os
import re

import pandas as pd
import pytest

from dados_sinteticos import gera_pasta
from faturamento import Sessao
from faturamento.analitico import monta_analitico


@pytest.fixture(scope="module")
def sessao(tmp_path_factory):
    d = tmp_path_factory.mktemp("analitico_sup") / "dados"
    gera_pasta(str(d), n_ligacoes=120, n_grupos=4)
    f = pd.read_excel(d / "Fatura.xlsx", dtype=str)
    f["Nome da Localidade"] = "Marica"                                   # todas as matrículas em cidade da Leste...
    f.loc[(f["Grupo"] == "03") & (f["N. da Ligacao"].astype(int) % 7 == 0), "Nome da Localidade"] = "Aperibe"
    f.to_excel(d / "Fatura.xlsx", index=False)
    c = pd.read_csv(d / "Cronograma.csv", sep=";", dtype=str, encoding="utf-8-sig")
    c["Localidade"] = c["Grupo"].map(lambda g: "Interior" if int(g) <= 2 else "Leste")   # ...mas grupos 01 e 02 da Interior
    c.to_csv(d / "Cronograma.csv", sep=";", index=False, encoding="utf-8-sig")
    s = Sessao(str(d), progresso=lambda pct, desc: None)
    s.preparar()
    s.continuar()
    return s


def test_grupo_da_interior_com_matriculas_de_cidade_da_leste(sessao):
    html = open(sessao.caminho_html, encoding="utf-8").read()
    info = json.loads(re.search(r'<script type="application/json" id="info-filtros">(.*?)</script>', html, re.S).group(1))
    assert info["grupoSup"]["01"] == "INTERIOR" and info["grupoSup"]["02"] == "INTERIOR"
    an = monta_analitico(sessao.ctx)
    do_grupo = an[an["Grupo"].astype(str).isin(["01", "02"])]
    assert len(do_grupo) and set(do_grupo["Superintendência"]) == {"LESTE"}    # pela cidade: nenhuma é da Interior


def test_relatorio_js_filtra_a_sup_pelo_grupo():
    rel = open(os.path.join(os.path.dirname(__file__), "..", "faturamento", "assets", "relatorio.js"), encoding="utf-8").read()
    assert "function linhaDaSup(v, sup, colsGrupo)" in rel and "grupoSup" in rel
    assert "v('Superintendência') === sup) && sit" not in rel and "v('Superintendência') !== sup) return" not in rel
    assert rel.count("linhaDaSup(v, sup, [") + rel.count("linhaDaSup(v, sup, (") == 2                      # setas do analítico e Bases analíticas
    assert "Nenhuma matrícula nesta tabela com os filtros da tela" in rel     # vazio: avisa em vez de baixar só o cabeçalho
