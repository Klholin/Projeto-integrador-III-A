"""Fluxos do servidor (seção Flow da especificação) e servidor TLS."""
from __future__ import annotations

import socket
import ssl
import threading

from app.componentes_servidor import (
    ConsultaDeProcessos,
    ControleDeAcesso,
    RegistroDeAuditoria,
    Sessao,
    ValidadorDeCredenciais,
)
from app.documentos import ValidadorDeDocumento
from app.especificacao import Especificacao
from app.intencao import ErroDeIntencao, fluxo
from app.protocolo import CanalDeMensagens
from app.repositorio import RepositorioDeProcessos
from app.seguranca import CanalSeguro, GerenciadorDeSenhas

TEMPO_LIMITE_INATIVIDADE = 300  # segundos


class OrquestradorDeFluxos:
    """Executa os fluxos 'on intenção X'. Cada passo do Flow vira uma linha de código."""

    def __init__(self, espec: Especificacao, repositorio: RepositorioDeProcessos,
                 auditoria: RegistroDeAuditoria | None = None):
        self.espec = espec
        tipos = espec.propriedade("ValidadorDeDocumento", "tipos_aceitos")
        self.validador_documento = ValidadorDeDocumento([t.strip() for t in tipos.split(",")])
        senhas = GerenciadorDeSenhas(espec.propriedade("GerenciadorDeSenhas", "iteracoes"))
        self.validador = ValidadorDeCredenciais(
            repositorio, senhas, espec.propriedade("ValidadorDeCredenciais", "max_tentativas"))
        self.controle = ControleDeAcesso()
        campos = espec.propriedade("ConsultaDeProcessos", "campos_resumo")
        self.consulta = ConsultaDeProcessos(repositorio, [c.strip() for c in campos.split(",")])
        self.auditoria = auditoria or RegistroDeAuditoria()
        self.fluxos = self._descobrir_fluxos()

    def _descobrir_fluxos(self) -> dict:
        fluxos = {}
        for nome in dir(type(self)):
            intencao = getattr(getattr(type(self), nome), "__fluxo_iop__", None)
            if intencao:
                fluxos[intencao] = getattr(self, nome)
        return fluxos

    # ------------------------------------------------------------------ despacho
    def tratar(self, sessao: Sessao, requisicao: dict) -> dict:
        intencao = requisicao.get("intencao")
        try:
            executar = self.fluxos.get(intencao)
            if executar is None:
                raise ErroDeIntencao("intencao_desconhecida", intencao=intencao)
            return executar(sessao, requisicao)
        except ErroDeIntencao as erro:
            return self.resposta_de_erro(erro)

    def resposta_de_erro(self, erro: ErroDeIntencao) -> dict:
        resposta = {"status": "erro", "condicao": erro.condicao,
                    "mensagem": self.espec.mensagem_de_erro(erro.condicao, **erro.dados)}
        if erro.encerrar_sessao:
            resposta["fim_sessao"] = True
        return resposta

    # ------------------------------------------------------------------ fluxos
    @fluxo("autenticar")
    def autenticar(self, sessao: Sessao, requisicao: dict) -> dict:
        documento = self.validador_documento.reconhecer(requisicao.get("documento", ""))
        if documento is None:
            restantes = self._registrar_falha_e_verificar_bloqueio(sessao, "documento inválido")
            raise ErroDeIntencao("documento_invalido", restantes=restantes)
        cliente = self.validador.validar(documento, requisicao.get("senha", ""))
        if cliente:
            sessao.autenticar(cliente, documento)
            self.auditoria.registrar(sessao.origem, f"Login bem-sucedido: {documento.mascarado()}")
            return {"status": "ok", "nome": cliente.nome}
        restantes = self._registrar_falha_e_verificar_bloqueio(sessao, documento.mascarado())
        raise ErroDeIntencao("credenciais_invalidas", restantes=restantes)

    def _registrar_falha_e_verificar_bloqueio(self, sessao: Sessao, descricao: str) -> int:
        """Passos 'registrar falha' e 'verificar condição de bloqueio' do Flow."""
        sessao.registrar_falha()
        self.auditoria.registrar(sessao.origem, f"Falha de login ({sessao.tentativas_falhas}/"
                                 f"{self.validador.max_tentativas}): {descricao}", alerta=True)
        restantes = self.validador.tentativas_restantes(sessao)
        if restantes <= 0:
            raise ErroDeIntencao("bloqueio", encerrar_sessao=True)
        return restantes

    @fluxo("consultar_meus_processos")
    def consultar_meus_processos(self, sessao: Sessao, requisicao: dict) -> dict:
        self.controle.exigir_autenticacao(sessao)
        processos = self.consulta.resumo_de(sessao.cliente)
        self.auditoria.registrar(sessao.origem, f"{sessao.identificacao} consultou seus processos.")
        return {"status": "ok", "processos": processos}

    @fluxo("ver_andamento_do_processo")
    def ver_andamento_do_processo(self, sessao: Sessao, requisicao: dict) -> dict:
        self.controle.exigir_autenticacao(sessao)
        numero = str(requisicao.get("numero", "")).strip()
        if self.controle.possui_processo(sessao, numero):
            detalhes = self.consulta.detalhes_de(numero)
            self.auditoria.registrar(sessao.origem, f"{sessao.identificacao} consultou o processo {numero}.")
            return {"status": "ok", "processo": detalhes}
        self.auditoria.registrar(sessao.origem, f"{sessao.identificacao} tentou acessar o processo "
                                 f"{numero!r} (negado).", alerta=True)
        raise ErroDeIntencao("processo_nao_encontrado")

    @fluxo("encerrar_sessao")
    def encerrar_sessao(self, sessao: Sessao, requisicao: dict) -> dict:
        return {"status": "ok", "mensagem": "Sessão encerrada.", "fim_sessao": True}


class ServidorSeguro:
    """Aceita conexões e executa o fluxo 'on conexão recebida' em uma thread por cliente."""

    def __init__(self, host: str, porta: int, espec: Especificacao, canal: CanalSeguro,
                 orquestrador: OrquestradorDeFluxos):
        self.espec = espec
        self.canal = canal
        self.orquestrador = orquestrador
        self.auditoria = orquestrador.auditoria
        self.tamanho_maximo_kb = espec.propriedade("CanalDeMensagens", "tamanho_maximo_kb")
        self.socket = socket.create_server((host, porta))
        self.socket.settimeout(1.0)
        self.endereco = self.socket.getsockname()
        self._parar = threading.Event()

    def servir_para_sempre(self) -> None:
        while not self._parar.is_set():
            try:
                conexao, endereco = self.socket.accept()
            except (socket.timeout, TimeoutError):
                continue
            except OSError:
                break
            threading.Thread(target=self.conexao_recebida, args=(conexao, endereco),
                             daemon=True).start()
        self.socket.close()

    def encerrar(self) -> None:
        self._parar.set()

    # Flow: on conexão recebida
    def conexao_recebida(self, conexao: socket.socket, endereco) -> None:
        origem = f"{endereco[0]}:{endereco[1]}"
        conexao.settimeout(TEMPO_LIMITE_INATIVIDADE)
        try:
            conexao_tls = self.canal.proteger(conexao)
        except (ssl.SSLError, OSError) as erro:
            self.auditoria.registrar(origem, f"Handshake TLS recusado: {erro}", alerta=True)
            conexao.close()
            return

        sessao = Sessao(origem)
        mensagens = CanalDeMensagens(conexao_tls, self.tamanho_maximo_kb)
        self.auditoria.registrar(origem, f"Conexão segura: {conexao_tls.version()} / "
                                 f"{conexao_tls.cipher()[0]}")
        try:
            self._receber_intencoes(sessao, mensagens)
        except Exception as erro:  # noqa: BLE001 - um cliente nunca derruba o servidor
            self.auditoria.registrar(origem, f"Erro inesperado: {erro!r}", alerta=True)
        finally:
            mensagens.fechar()
            self.auditoria.registrar(origem, "Conexão encerrada.")

    def _receber_intencoes(self, sessao: Sessao, mensagens: CanalDeMensagens) -> None:
        while True:
            try:
                requisicao = mensagens.receber()
            except ErroDeIntencao as erro:
                mensagens.enviar(self.orquestrador.resposta_de_erro(erro))
                self.auditoria.registrar(sessao.origem, "Mensagem inválida recebida.", alerta=True)
                return
            except (socket.timeout, TimeoutError):
                self.auditoria.registrar(sessao.origem, "Encerrada por inatividade.")
                return
            except (ssl.SSLError, OSError, UnicodeDecodeError) as erro:
                self.auditoria.registrar(sessao.origem, f"Falha na leitura: {erro}", alerta=True)
                return
            if requisicao is None:
                return
            resposta = self.orquestrador.tratar(sessao, requisicao)
            mensagens.enviar(resposta)
            if resposta.get("fim_sessao"):
                return
