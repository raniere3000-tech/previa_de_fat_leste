# -*- coding: utf-8 -*-
"""Grandes Clientes (GC): lista de matrículas da pasta + adicionadas, Excel com faturamento/consumo/vencimento mês a mês."""
import io
import os

import pandas as pd
import pytest

from dados_sinteticos import gera_pasta
from faturamento import Sessao
from faturamento.grandes_clientes import chave_matricula, gera_xlsx_gc, monta_gc
from faturamento.leitura import identifica_tipo


@pytest.fixture(scope="module")
def sessao_gc(tmp_path_factory):
    destino = tmp_path_factory.mktemp("gc") / "dados"
    gera_pasta(str(destino), n_ligacoes=120, n_grupos=4, n_meses=3)
    # mesmo formato da planilha "Matriculas lest GC": Matricula | TIPO (uma matrícula com zero à esquerda, uma inexistente)
    pd.DataFrame({"Matricula": ["100003", "0100007", "999999999"], "TIPO": ["GC", "gc", "GC"]}).to_excel(
        destino / "Matriculas lest GC.xlsx", index=False)
    s = Sessao(str(destino), progresso=lambda pct, desc: None)
    s.preparar()
    s.continuar()
    return s


def test_reconhece_a_planilha_de_matriculas():
    assert identifica_tipo(["Matricula", "TIPO"]) == "matriculas_gc"
    assert identifica_tipo(["Matrícula", "Tipo"]) == "matriculas_gc"
    assert chave_matricula("0102340199") == chave_matricula("102340199.0") == "102340199"


def test_lista_da_pasta_entra_no_contexto_e_na_aba_dados(sessao_gc):
    ctx = sessao_gc.ctx
    assert [i["mat"] for i in ctx.gc_lista] == ["100003", "100007", "999999999"]
    assert {i["tipo"] for i in ctx.gc_lista} == {"GC"}
    assert any(i["tipo"] == "Matrículas GC" for i in ctx.bases_info)
    assert not any("Matriculas lest GC" in ig["arquivo"] for ig in ctx.classificacao["ignorados"])
    html = open(sessao_gc.caminho_html, encoding="utf-8").read()
    assert 'id="gcBaixar"' in html and 'id="gc-dados"' in html and "Matriculas lest GC.xlsx" in html


def test_valores_batem_com_a_base_em_todos_os_meses(sessao_gc):
    ctx = sessao_gc.ctx
    an, refs, cad = monta_gc(ctx, [{"mat": "100003", "tipo": "GC"}, {"mat": "100050", "tipo": "PUBLICO"}])
    assert len(refs) == 3
    b = ctx.base_completa
    for lig in ("100003", "100050"):
        for ref in refs:
            linhas = b[(b["N. Ligação"] == lig) & (b["Referencia de Leitura"] == ref)]
            if not len(linhas):
                continue
            r = an[(an["Matrícula"] == lig) & (an["Referência"] == ref)].iloc[0]
            assert r["Faturado Total (R$)"] == pytest.approx(pd.to_numeric(linhas["Valor (R$)"]).sum(), abs=0.01)
            agua = linhas[linhas["__serv"] == "A"]
            assert r["Consumo Faturado Água (m³)"] == pytest.approx(pd.to_numeric(agua["Consumo Faturado"]).sum())
            assert r["Data de Vencimento"] is not None
    assert list(cad["Tipo"]) == ["GC", "PUBLICO"]


def test_excel_tem_as_abas_por_mes_e_marca_as_nao_encontradas(sessao_gc):
    lista = [{"mat": i["mat"], "tipo": i["tipo"]} for i in sessao_gc.ctx.gc_lista] + [{"mat": "100010", "tipo": "GC"}]
    conteudo, nome, info = gera_xlsx_gc(sessao_gc.ctx, lista)
    assert nome.startswith("GC_Faturamento_Consumo_") and nome.endswith(".xlsx")
    assert info == {"nome": nome, "matriculas": 4, "encontradas": 3, "meses": 3}
    abas = pd.read_excel(io.BytesIO(conteudo), sheet_name=None, dtype={"Matrícula": str})
    assert list(abas) == ["Faturamento (R$)", "Consumo (m³)", "Vencimento", "Analítico"]
    fat = abas["Faturamento (R$)"]
    assert list(fat["Matrícula"]) == ["100003", "100007", "999999999", "100010"]
    assert fat.loc[2, "Nome Cliente"] == "NÃO ENCONTRADA NA BASE"
    assert {"Média", "Total"}.issubset(fat.columns) and len([c for c in fat.columns if "/" in c]) == 3
    assert abas["Vencimento"].iloc[0, 5:].notna().any()


def test_site_e_worker_ligam_o_botao_ao_python():
    raiz = os.path.join(os.path.dirname(__file__), "..")
    site = open(os.path.join(raiz, "index.html"), encoding="utf-8").read()
    worker = open(os.path.join(raiz, "analisador.worker.js"), encoding="utf-8").read()
    rel = open(os.path.join(raiz, "faturamento", "assets", "relatorio.js"), encoding="utf-8").read()
    executor = open(os.path.join(raiz, "executor_web.py"), encoding="utf-8").read()
    assert "window.baixarGC = async (lista)" in site and 'fase: "gc"' in site
    assert '"faturamento/grandes_clientes.py"' in worker and 'fase === "gc"' in worker
    assert "def grandes_clientes(lista_json, caminho)" in executor
    assert "criaSync('gc'" in rel and "window.parent.baixarGC" in rel and "await syncGC.empurrar()" in rel
