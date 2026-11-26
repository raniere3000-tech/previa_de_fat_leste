# -*- coding: utf-8 -*-
"""Aviso na aba Dados quando a pasta tem arquivos com o mesmo nome ("Fatura de ciclo 10-2026" e
"Fatura de ciclo 10-2026 (1)"): só avisa, nenhum arquivo é excluído."""
import shutil

import pandas as pd

from dados_sinteticos import gera_pasta
from faturamento import Sessao
from faturamento.leitura import arquivos_com_mesmo_nome, nome_sem_copia


def test_nome_sem_o_sufixo_da_copia():
    base = nome_sem_copia("Fatura de ciclo 10-2026.xlsx")
    for nome in ("Fatura de ciclo 10-2026 (1).xlsx", "fatura de ciclo 10-2026(2).csv", "Fatura de ciclo 10-2026 - Cópia.xlsx",
                 "Fatura de ciclo 10-2026 - Copia (2).xlsx", "sub/FATURA DE CICLO 10-2026 - Copy.xlsx"):
        assert nome_sem_copia(nome) == base, nome
    assert nome_sem_copia("Fatura de ciclo 11-2026.xlsx") != base
    assert nome_sem_copia("Consumo 10-2026.csv") != nome_sem_copia("Consumo 10-2025.csv")


def test_grupos_de_mesmo_nome():
    caminhos = ["/p/Fatura 10-2026.xlsx", "/p/Fatura 10-2026 (1).xlsx", "/p/Leste/Fatura 10-2026.csv", "/p/Consumo 10-2026.csv"]
    assert arquivos_com_mesmo_nome(caminhos, "/p") == [["Fatura 10-2026 (1).xlsx", "Fatura 10-2026.xlsx", "Leste/Fatura 10-2026.csv"]]


def _avisos(s):
    return [a for a in s.ctx.avisos_base if a.startswith("Arquivos com o mesmo nome")]


def test_aviso_na_aba_dados_sem_excluir_nada(tmp_path):
    d = tmp_path / "dados"
    gera_pasta(str(d), n_ligacoes=60, n_grupos=3)
    f = pd.read_excel(d / "Fatura.xlsx", dtype=str)
    f.iloc[:5].to_excel(d / "Fatura (1).xlsx", index=False)           # baixado de novo, com conteúdo diferente
    s = Sessao(str(d), progresso=lambda pct, desc: None)
    s.preparar()
    s.continuar()
    av = _avisos(s)
    assert av == ['Arquivos com o mesmo nome encontrados na pasta: "Fatura (1).xlsx" e "Fatura.xlsx" — se forem a mesma '
                  'informação (arquivo baixado duas vezes), os valores entram em dobro: confira e deixe só um na pasta.']
    assert len(s.ctx.classificacao["fatura"]) == 2                     # nada excluído
    assert "Arquivos com o mesmo nome encontrados na pasta" in open(s.caminho_html, encoding="utf-8").read()


def test_copia_identica_diz_que_contou_uma_vez(tmp_path):
    d = tmp_path / "dados"
    gera_pasta(str(d), n_ligacoes=60, n_grupos=3)
    shutil.copy(d / "Fatura.xlsx", d / "Fatura (1).xlsx")
    s = Sessao(str(d), progresso=lambda pct, desc: None)
    s.preparar()
    s.continuar()
    assert _avisos(s) == ['Arquivos com o mesmo nome encontrados na pasta: "Fatura (1).xlsx" e "Fatura.xlsx" — o conteúdo '
                          'é idêntico e foi contado uma vez só.']


def test_sem_nomes_repetidos_sem_aviso(tmp_path):
    d = tmp_path / "dados"
    gera_pasta(str(d), n_ligacoes=60, n_grupos=3)
    s = Sessao(str(d), progresso=lambda pct, desc: None)
    s.preparar()
    assert _avisos(s) == []
