"""Elos explícitos entre a especificação de intenção e o código.

- @componente("Nome")  liga uma classe a um item de Components.
- @fluxo("intencao")   liga um método a um gatilho 'on intenção X' do Flow.
- ErroDeIntencao       representa uma condição declarada em ErrorHandling;
                       a mensagem exibida vem da especificação.

O verificador (verificar_intencoes.py) usa esses elos para provar que
intenção e implementação continuam alinhadas (princípio da Transparência).
"""
from __future__ import annotations

REGISTRO_DE_COMPONENTES: dict[str, type] = {}


def componente(nome: str):
    """Marca a classe como implementação do componente `nome` da especificação."""

    def registrar(classe: type) -> type:
        classe.__componente_iop__ = nome
        REGISTRO_DE_COMPONENTES[nome] = classe
        return classe

    return registrar


def fluxo(intencao: str):
    """Marca o método como implementação do gatilho 'on intenção <intencao>'."""

    def marcar(funcao):
        funcao.__fluxo_iop__ = intencao
        return funcao

    return marcar


class ErroDeIntencao(Exception):
    """Condição de erro declarada no ErrorHandling da especificação."""

    def __init__(self, condicao: str, encerrar_sessao: bool = False, **dados):
        super().__init__(condicao)
        self.condicao = condicao
        self.encerrar_sessao = encerrar_sessao
        self.dados = dados
