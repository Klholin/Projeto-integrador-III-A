"""Componente RepositorioDeProcessos: abstração + implementação em arquivo JSON."""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path

from app.intencao import componente
from app.modelos import Cliente, Documento, Processo


@componente("RepositorioDeProcessos")
class RepositorioDeProcessos(ABC):
    """Intenção: fornecer os dados de clientes e processos (somente leitura).

    Classe abstrata: outra fonte (CSV, banco de dados) pode ser usada criando
    uma nova subclasse, sem alterar o restante do sistema.
    """

    @abstractmethod
    def buscar_cliente(self, documento: Documento) -> Cliente | None: ...

    @abstractmethod
    def buscar_processo(self, numero: str) -> Processo | None: ...


class RepositorioJSON(RepositorioDeProcessos):
    """Lê clientes e processos do arquivo dados.json."""

    def __init__(self, caminho: Path):
        try:
            with open(caminho, encoding="utf-8") as arquivo:
                dados = json.load(arquivo)
            clientes = [Cliente.de_dict(c) for c in dados["clientes"]]
            self._processos = {p["numero"]: Processo.de_dict(p) for p in dados["processos"]}
        except FileNotFoundError as erro:
            raise ValueError(f"Arquivo de dados não encontrado: {caminho}") from erro
        except (json.JSONDecodeError, KeyError, TypeError) as erro:
            raise ValueError(f"Arquivo de dados inválido ({caminho}): {erro}") from erro

        # Índice por documento: todos os documentos de um cliente levam à mesma conta.
        self._clientes: dict[tuple[str, str], Cliente] = {}
        for cliente in clientes:
            if not cliente.documentos:
                raise ValueError(f"Cliente {cliente.nome} não tem documento cadastrado.")
            for documento in cliente.documentos:
                if documento.chave in self._clientes:
                    raise ValueError(f"Documento repetido no cadastro: {documento.mascarado()}")
                self._clientes[documento.chave] = cliente
            for numero in cliente.processos:
                if numero not in self._processos:
                    raise ValueError(f"Cliente {cliente.nome} referencia processo inexistente: {numero}")

    def buscar_cliente(self, documento: Documento) -> Cliente | None:
        return self._clientes.get(documento.chave)

    def buscar_processo(self, numero: str) -> Processo | None:
        return self._processos.get(numero)
