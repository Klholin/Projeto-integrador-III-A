"""Componente CanalDeMensagens: uma mensagem JSON por linha sobre TLS."""
from __future__ import annotations

import json

from app.intencao import ErroDeIntencao, componente


@componente("CanalDeMensagens")
class CanalDeMensagens:
    """Intenção: transportar intenções e respostas entre cliente e servidor."""

    def __init__(self, conexao, tamanho_maximo_kb: int):
        self.conexao = conexao
        self.limite = tamanho_maximo_kb * 1024
        self._leitor = conexao.makefile("r", encoding="utf-8", newline="\n")

    def enviar(self, mensagem: dict) -> None:
        dados = json.dumps(mensagem, ensure_ascii=False) + "\n"
        self.conexao.sendall(dados.encode("utf-8"))

    def receber(self) -> dict | None:
        """Devolve a próxima mensagem ou None se a outra ponta encerrou."""
        linha = self._leitor.readline(self.limite + 1)
        if not linha:
            return None
        if len(linha) > self.limite:
            raise ErroDeIntencao("mensagem_invalida", encerrar_sessao=True,
                                 detalhe="tamanho máximo excedido.")
        try:
            mensagem = json.loads(linha)
        except json.JSONDecodeError:
            raise ErroDeIntencao("mensagem_invalida", encerrar_sessao=True,
                                 detalhe="não é um JSON válido.") from None
        if not isinstance(mensagem, dict):
            raise ErroDeIntencao("mensagem_invalida", encerrar_sessao=True,
                                 detalhe="deve ser um objeto JSON.")
        return mensagem

    def fechar(self) -> None:
        for recurso in (self._leitor, self.conexao):
            try:
                recurso.close()
            except OSError:
                pass
