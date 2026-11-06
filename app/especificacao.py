"""Leitura da especificação de intenção (intencoes/sistema.iop).

A especificação é a fonte da verdade do sistema. Este módulo a interpreta para
que o programa use, em tempo de execução, as propriedades dos componentes e as
mensagens de ErrorHandling, e para que o verificador compare intenção e código.

O formato segue o esquema IOP (System, Components, Flow, ErrorHandling,
ImplementationMap), com indentação de 2 espaços por nível.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

CAMINHO_PADRAO = Path(__file__).resolve().parent.parent / "intencoes" / "sistema.iop"
PREFIXO_INTENCAO = "intenção "


class ErroDeEspecificacao(Exception):
    """A especificação está malformada ou incompleta."""


@dataclass
class ComponenteEspecificado:
    nome: str
    campos: dict[str, object] = field(default_factory=dict)
    propriedades: dict[str, object] = field(default_factory=dict)


@dataclass
class Especificacao:
    sistema: str
    descricao: str
    propriedades: dict[str, object]
    componentes: dict[str, ComponenteEspecificado]
    fluxos: dict[str, list[str]]  # gatilho -> passos
    erros: dict[str, str]  # condição -> mensagem
    mapas_de_implementacao: list[str]

    # ------------------------------------------------------------------ consulta
    def propriedade(self, componente: str, nome: str):
        try:
            return self.componentes[componente].propriedades[nome]
        except KeyError as erro:
            raise ErroDeEspecificacao(
                f"Propriedade '{nome}' do componente '{componente}' não está na especificação."
            ) from erro

    def mensagem_de_erro(self, condicao: str, **dados) -> str:
        if condicao not in self.erros:
            raise ErroDeEspecificacao(f"Condição de erro '{condicao}' não está no ErrorHandling.")
        return self.erros[condicao].format(**dados)

    @property
    def intencoes(self) -> list[str]:
        """Nomes das intenções declaradas no Flow (gatilhos 'on intenção X')."""
        return [g[len(PREFIXO_INTENCAO):] for g in self.fluxos if g.startswith(PREFIXO_INTENCAO)]

    # ------------------------------------------------------------------ leitura
    @classmethod
    def carregar(cls, caminho: Path = CAMINHO_PADRAO) -> "Especificacao":
        try:
            texto = Path(caminho).read_text(encoding="utf-8")
        except FileNotFoundError as erro:
            raise ErroDeEspecificacao(f"Especificação não encontrada: {caminho}") from erro
        return _Interpretador(texto).interpretar()


def _valor(texto: str):
    texto = texto.strip()
    if len(texto) >= 2 and texto[0] == texto[-1] == '"':
        return texto[1:-1]
    if re.fullmatch(r"-?\d+", texto):
        return int(texto)
    return texto


def _chave_valor(linha: str, numero: int) -> tuple[str, str]:
    if ":" not in linha:
        raise ErroDeEspecificacao(f"Linha {numero}: esperado 'chave: valor' em {linha!r}.")
    chave, valor = linha.split(":", 1)
    return chave.strip(), valor


class _Interpretador:
    """Interpretador simples, por indentação, do subconjunto usado no projeto."""

    SECOES = {"properties", "Components", "Flow", "ErrorHandling", "ImplementationMap"}

    def __init__(self, texto: str):
        self.linhas = texto.splitlines()

    def interpretar(self) -> Especificacao:
        sistema, descricao = None, ""
        propriedades: dict = {}
        componentes: dict[str, ComponenteEspecificado] = {}
        fluxos: dict[str, list[str]] = {}
        erros: dict[str, str] = {}
        mapas: list[str] = []

        secao = None
        componente = None
        em_propriedades = False
        gatilho = None

        for numero, bruta in enumerate(self.linhas, start=1):
            if not bruta.strip() or bruta.lstrip().startswith("#"):
                continue
            recuo = len(bruta) - len(bruta.lstrip(" "))
            linha = bruta.strip()

            if recuo == 0:
                encontrado = re.fullmatch(r"System (\w+):", linha)
                if not encontrado:
                    raise ErroDeEspecificacao(f"Linha {numero}: esperado 'System <Nome>:'.")
                sistema = encontrado.group(1)
                continue

            if recuo == 2:
                if linha.startswith("description:"):
                    descricao = _valor(linha.split(":", 1)[1])
                    secao = None
                elif linha.endswith(":") and linha[:-1] in self.SECOES:
                    secao = linha[:-1]
                    if secao == "ImplementationMap":
                        mapas.append("")
                else:
                    raise ErroDeEspecificacao(f"Linha {numero}: seção desconhecida {linha!r}.")
                continue

            if secao == "properties":
                chave, valor = _chave_valor(linha, numero)
                propriedades[chave] = _valor(valor)

            elif secao == "Components":
                if recuo == 4:
                    encontrado = re.fullmatch(r"- (\w+):", linha)
                    if not encontrado:
                        raise ErroDeEspecificacao(f"Linha {numero}: esperado '- <Componente>:'.")
                    componente = ComponenteEspecificado(encontrado.group(1))
                    componentes[componente.nome] = componente
                    em_propriedades = False
                elif recuo == 8:
                    chave, valor = _chave_valor(linha, numero)
                    em_propriedades = chave == "properties"
                    if not em_propriedades:
                        componente.campos[chave] = _valor(valor)
                elif em_propriedades:
                    chave, valor = _chave_valor(linha, numero)
                    componente.propriedades[chave] = _valor(valor)

            elif secao == "Flow":
                if recuo == 4:
                    gatilho = linha.rstrip(":")
                    if gatilho.startswith("on "):
                        gatilho = gatilho[3:]
                    fluxos[gatilho] = []
                else:
                    fluxos[gatilho].append(linha)

            elif secao == "ErrorHandling":
                if "→" not in linha:
                    raise ErroDeEspecificacao(f"Linha {numero}: esperado '<condição> → \"mensagem\"'.")
                condicao, mensagem = linha.split("→", 1)
                erros[condicao.strip()] = _valor(mensagem)

            elif secao == "ImplementationMap":
                mapas[-1] += bruta + "\n"

        if sistema is None:
            raise ErroDeEspecificacao("Definição 'System <Nome>:' não encontrada.")
        return Especificacao(sistema, descricao, propriedades, componentes, fluxos, erros, mapas)
