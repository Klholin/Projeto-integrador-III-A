"""Componente ValidadorDeDocumento: reconhece CPF, CNPJ ou CRM digitados."""
from __future__ import annotations

import re

from app.intencao import componente
from app.modelos import Documento

UFS = {"AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA",
       "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"}
SEPARADORES = re.compile(r"[\s./\-]+")


@componente("ValidadorDeDocumento")
class ValidadorDeDocumento:
    """Intenção: reconhecer o documento com que o cliente se identifica."""

    def __init__(self, tipos_aceitos: list[str]):
        self.tipos_aceitos = set(tipos_aceitos)

    def reconhecer(self, texto: str) -> Documento | None:
        """Devolve o Documento normalizado ou None se for inválido."""
        texto = str(texto or "").strip().upper()
        if not texto:
            return None
        documento = self._crm(texto) if re.search(r"[A-Z]", texto) else self._cpf_ou_cnpj(texto)
        if documento and documento.tipo in self.tipos_aceitos:
            return documento
        return None

    # ------------------------------------------------------------------ CPF / CNPJ
    def _cpf_ou_cnpj(self, texto: str) -> Documento | None:
        digitos = SEPARADORES.sub("", texto)
        if not digitos.isdigit():
            return None
        if len(digitos) == 11 and cpf_valido(digitos):
            return Documento("CPF", digitos)
        if len(digitos) == 14 and cnpj_valido(digitos):
            return Documento("CNPJ", digitos)
        return None

    # ------------------------------------------------------------------ CRM
    def _crm(self, texto: str) -> Documento | None:
        """Aceita número e UF em qualquer ordem: CRM-GO 12345, CRM/GO 12345, 12345/GO, GO12345..."""
        resto = re.sub(r"^CRM", "", texto).strip()
        partes = [p for p in re.split(r"(\d+)|[\s./\-]+", resto) if p]
        letras = [p for p in partes if p.isalpha()]
        numeros = [p for p in partes if p.isdigit()]
        if len(letras) != 1 or len(numeros) != 1 or len(partes) != 2:
            return None
        uf, numero = letras[0], numeros[0]
        if uf not in UFS or not 1 <= len(numero.lstrip("0")) <= 7:
            return None
        return Documento("CRM", f"{uf}-{int(numero)}")


def _digito(base: str, pesos: list[int]) -> str:
    resto = sum(int(d) * p for d, p in zip(base, pesos)) % 11
    return "0" if resto < 2 else str(11 - resto)


def cpf_valido(cpf: str) -> bool:
    if len(cpf) != 11 or not cpf.isdigit() or cpf == cpf[0] * 11:
        return False
    d1 = _digito(cpf[:9], list(range(10, 1, -1)))
    d2 = _digito(cpf[:9] + d1, list(range(11, 1, -1)))
    return cpf[9:] == d1 + d2


def cnpj_valido(cnpj: str) -> bool:
    if len(cnpj) != 14 or not cnpj.isdigit() or cnpj == cnpj[0] * 14:
        return False
    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    d1 = _digito(cnpj[:12], pesos1)
    d2 = _digito(cnpj[:12] + d1, [6] + pesos1)
    return cnpj[12:] == d1 + d2
