"""Componentes de regra de negócio do servidor."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from app.intencao import ErroDeIntencao, componente
from app.modelos import Cliente, Documento
from app.repositorio import RepositorioDeProcessos
from app.seguranca import GerenciadorDeSenhas


@dataclass
class Sessao:
    """Estado de uma conexão: começa não autenticada."""

    origem: str
    cliente: Cliente | None = None
    documento: Documento | None = None  # documento usado no login
    tentativas_falhas: int = 0

    @property
    def autenticada(self) -> bool:
        return self.cliente is not None

    @property
    def identificacao(self) -> str:
        """Identificação segura para logs (documento mascarado)."""
        return self.documento.mascarado() if self.documento else "não autenticado"

    def autenticar(self, cliente: Cliente, documento: Documento) -> None:
        self.cliente = cliente
        self.documento = documento

    def registrar_falha(self) -> None:
        self.tentativas_falhas += 1


@componente("ValidadorDeCredenciais")
class ValidadorDeCredenciais:
    """Intenção: confirmar a identidade do cliente."""

    def __init__(self, repositorio: RepositorioDeProcessos, senhas: GerenciadorDeSenhas,
                 max_tentativas: int):
        self.repositorio = repositorio
        self.senhas = senhas
        self.max_tentativas = max_tentativas
        # Hash fictício: documento não cadastrado leva o mesmo tempo (resposta_uniforme).
        self._salt_falso, self._hash_falso = senhas.gerar_hash("documento-nao-cadastrado")

    def validar(self, documento: Documento, senha: str) -> Cliente | None:
        cliente = self.repositorio.buscar_cliente(documento)
        if cliente is None:
            self.senhas.verificar(senha, self._salt_falso, self._hash_falso)
            return None
        return cliente if self.senhas.verificar(senha, cliente.salt, cliente.hash_senha) else None

    def tentativas_restantes(self, sessao: Sessao) -> int:
        return self.max_tentativas - sessao.tentativas_falhas


@componente("ControleDeAcesso")
class ControleDeAcesso:
    """Intenção: garantir que cada cliente veja somente o que é seu."""

    def exigir_autenticacao(self, sessao: Sessao) -> None:
        if not sessao.autenticada:
            raise ErroDeIntencao("login_necessario")

    def possui_processo(self, sessao: Sessao, numero: str) -> bool:
        return sessao.cliente.possui_processo(numero)


@componente("ConsultaDeProcessos")
class ConsultaDeProcessos:
    """Intenção: montar as informações de acompanhamento processual."""

    def __init__(self, repositorio: RepositorioDeProcessos, campos_resumo: list[str]):
        self.repositorio = repositorio
        self.campos_resumo = campos_resumo

    def resumo_de(self, cliente: Cliente) -> list[dict]:
        processos = (self.repositorio.buscar_processo(n) for n in cliente.processos)
        return [p.resumo(self.campos_resumo) for p in processos if p]

    def detalhes_de(self, numero: str) -> dict:
        return self.repositorio.buscar_processo(numero).detalhes()


@componente("RegistroDeAuditoria")
class RegistroDeAuditoria:
    """Intenção: manter rastro dos acessos (senhas nunca são registradas)."""

    def __init__(self, logger: logging.Logger | None = None):
        self.log = logger or logging.getLogger("auditoria")

    def registrar(self, origem: str, evento: str, alerta: bool = False) -> None:
        (self.log.warning if alerta else self.log.info)("[%s] %s", origem, evento)
