"""Modelos de domínio: Documento, Cliente, Processo e Movimentacao."""
from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Documento:
    """Documento de identificação já normalizado.

    numero: só dígitos para CPF e CNPJ; "UF-NUMERO" para CRM (ex.: "GO-12345").
    """

    tipo: str  # "CPF", "CNPJ" ou "CRM"
    numero: str

    @property
    def chave(self) -> tuple[str, str]:
        return self.tipo, self.numero

    def formatado(self) -> str:
        n = self.numero
        if self.tipo == "CPF":
            return f"{n[:3]}.{n[3:6]}.{n[6:9]}-{n[9:]}"
        if self.tipo == "CNPJ":
            return f"{n[:2]}.{n[2:5]}.{n[5:8]}/{n[8:12]}-{n[12:]}"
        uf, numero = n.split("-")
        return f"CRM-{uf} {numero}"

    def mascarado(self) -> str:
        """Versão para logs (LGPD): esconde parte do número."""
        n = self.numero
        if self.tipo == "CPF":
            return f"CPF ***.{n[3:6]}.{n[6:9]}-**"
        if self.tipo == "CNPJ":
            return f"CNPJ **.{n[2:5]}.{n[5:8]}/****-**"
        uf, numero = n.split("-")
        return f"CRM-{uf} {'*' * max(len(numero) - 2, 1)}{numero[-2:]}"


@dataclass(frozen=True)
class Movimentacao:
    data: str
    descricao: str


@dataclass(frozen=True)
class Processo:
    numero: str
    tipo_acao: str
    orgao_julgador: str
    data_distribuicao: str
    fase: str
    ultima_atualizacao: str
    advogado_responsavel: str
    proximo_passo: str
    movimentacoes: tuple[Movimentacao, ...]

    @classmethod
    def de_dict(cls, dados: dict) -> "Processo":
        campos = dict(dados)
        campos["movimentacoes"] = tuple(Movimentacao(**m) for m in dados["movimentacoes"])
        return cls(**campos)

    def resumo(self, campos: list[str]) -> dict:
        return {campo: getattr(self, campo) for campo in campos}

    def detalhes(self) -> dict:
        dados = asdict(self)
        dados["movimentacoes"] = list(dados["movimentacoes"])
        return dados


@dataclass(frozen=True)
class Cliente:
    nome: str
    salt: str
    hash_senha: str
    documentos: tuple[Documento, ...]  # um ou mais; todos levam à mesma conta
    processos: tuple[str, ...]

    @classmethod
    def de_dict(cls, dados: dict) -> "Cliente":
        return cls(dados["nome"], dados["salt"], dados["hash_senha"],
                   tuple(Documento(d["tipo"], d["numero"]) for d in dados["documentos"]),
                   tuple(dados["processos"]))

    def possui_processo(self, numero: str) -> bool:
        return numero in self.processos
