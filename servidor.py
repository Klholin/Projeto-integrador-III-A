"""Servidor de consulta de processos — PI III-A (PUC Goiás, ADS EaD).

Disponibiliza, por meio de uma conexão TCP protegida com TLS, a consulta do
andamento de processos para os clientes do escritório parceiro. Cada cliente
se autentica com código + senha e só enxerga os próprios processos.

Uso:
    python servidor.py                 # 127.0.0.1:5050
    python servidor.py --porta 6000
    python servidor.py --host 0.0.0.0  # aceita conexões de outras máquinas da rede
"""
from __future__ import annotations

import argparse
import json
import logging
import socket
import ssl
import sys
import threading
from pathlib import Path

from comum import (
    VERSAO_PROTOCOLO,
    ErroProtocolo,
    enviar,
    gerar_hash_senha,
    receber,
    verificar_senha,
)

PASTA_BASE = Path(__file__).resolve().parent
MAX_TENTATIVAS_LOGIN = 3
TEMPO_LIMITE_INATIVIDADE = 300  # segundos

log = logging.getLogger("servidor")


# --------------------------------------------------------------------------
# Camada de dados (arquivo JSON, sem banco de dados)
# --------------------------------------------------------------------------
class BaseDeDados:
    """Carrega o dados.json e responde às consultas respeitando o dono."""

    CAMPOS_RESUMO = ("numero", "tipo_acao", "fase", "ultima_atualizacao")

    def __init__(self, caminho: Path):
        with open(caminho, encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
        self.clientes = {c["codigo"].upper(): c for c in dados["clientes"]}
        self.processos = {p["numero"]: p for p in dados["processos"]}
        # Hash "falso" usado quando o código não existe, para que a resposta
        # leve o mesmo tempo e não revele quais códigos são válidos.
        self._salt_falso, self._hash_falso = gerar_hash_senha("senha-inexistente")

    def autenticar(self, codigo: str, senha: str) -> dict | None:
        cliente = self.clientes.get(str(codigo).strip().upper())
        if cliente is None:
            verificar_senha(senha, self._salt_falso, self._hash_falso)
            return None
        if verificar_senha(senha, cliente["salt"], cliente["hash_senha"]):
            return cliente
        return None

    def listar_processos(self, cliente: dict) -> list[dict]:
        resumo = []
        for numero in cliente["processos"]:
            processo = self.processos.get(numero)
            if processo:
                resumo.append({campo: processo[campo] for campo in self.CAMPOS_RESUMO})
        return resumo

    def detalhar_processo(self, cliente: dict, numero: str) -> dict | None:
        # Controle de acesso: o processo precisa pertencer ao cliente logado.
        if numero not in cliente["processos"]:
            return None
        return self.processos.get(numero)


# --------------------------------------------------------------------------
# Atendimento de uma conexão
# --------------------------------------------------------------------------
def erro(mensagem: str) -> dict:
    return {"status": "erro", "mensagem": mensagem}


def atender_cliente(conexao: ssl.SSLSocket, endereco, base: BaseDeDados) -> None:
    """Trata todas as requisições de uma conexão TLS já estabelecida."""
    origem = f"{endereco[0]}:{endereco[1]}"
    cliente = None
    tentativas = 0

    log.info("[%s] Conexão segura: %s / %s", origem, conexao.version(), conexao.cipher()[0])
    with conexao, conexao.makefile("r", encoding="utf-8", newline="\n") as leitor:
        while True:
            try:
                requisicao = receber(leitor)
            except ErroProtocolo as e:
                enviar(conexao, erro(str(e)))
                log.warning("[%s] Requisição inválida: %s", origem, e)
                break
            except (socket.timeout, TimeoutError):
                log.info("[%s] Conexão encerrada por inatividade.", origem)
                break
            except (ssl.SSLError, OSError, UnicodeDecodeError) as e:
                log.warning("[%s] Falha na leitura: %s", origem, e)
                break

            if requisicao is None:  # cliente fechou a conexão
                break

            acao = requisicao.get("acao")

            if acao == "login":
                cliente = base.autenticar(requisicao.get("codigo", ""), requisicao.get("senha", ""))
                if cliente:
                    log.info("[%s] Login bem-sucedido: %s", origem, cliente["codigo"])
                    enviar(conexao, {"status": "ok", "nome": cliente["nome"],
                                     "versao_protocolo": VERSAO_PROTOCOLO})
                else:
                    tentativas += 1
                    log.warning("[%s] Falha de login (%d/%d) para o código %r",
                                origem, tentativas, MAX_TENTATIVAS_LOGIN, requisicao.get("codigo"))
                    restantes = MAX_TENTATIVAS_LOGIN - tentativas
                    if restantes <= 0:
                        resposta = erro("Número máximo de tentativas atingido. Conexão encerrada.")
                        resposta["fim_sessao"] = True
                        enviar(conexao, resposta)
                        break
                    enviar(conexao, erro(f"Código ou senha inválidos. Tentativas restantes: {restantes}."))

            elif acao == "sair":
                enviar(conexao, {"status": "ok", "mensagem": "Sessão encerrada."})
                break

            elif cliente is None:
                enviar(conexao, erro("É necessário fazer login antes de consultar."))

            elif acao == "listar_processos":
                enviar(conexao, {"status": "ok", "processos": base.listar_processos(cliente)})
                log.info("[%s] %s listou seus processos.", origem, cliente["codigo"])

            elif acao == "detalhar_processo":
                numero = str(requisicao.get("numero", "")).strip()
                processo = base.detalhar_processo(cliente, numero)
                if processo is None:
                    enviar(conexao, erro("Processo não encontrado entre os seus processos."))
                    log.warning("[%s] %s tentou acessar o processo %r.", origem, cliente["codigo"], numero)
                else:
                    enviar(conexao, {"status": "ok", "processo": processo})
                    log.info("[%s] %s consultou o processo %s.", origem, cliente["codigo"], numero)

            else:
                enviar(conexao, erro(f"Ação desconhecida: {acao!r}."))

    log.info("[%s] Conexão encerrada.", origem)


# --------------------------------------------------------------------------
# Servidor
# --------------------------------------------------------------------------
def criar_contexto_tls(certificado: Path, chave: Path) -> ssl.SSLContext:
    contexto = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    contexto.minimum_version = ssl.TLSVersion.TLSv1_2  # recusa SSL/TLS antigos
    contexto.load_cert_chain(certfile=str(certificado), keyfile=str(chave))
    return contexto


class Servidor:
    def __init__(self, host: str, porta: int, contexto: ssl.SSLContext, base: BaseDeDados):
        self.contexto = contexto
        self.base = base
        self.socket = socket.create_server((host, porta))
        self.socket.settimeout(1.0)  # permite verificar o pedido de parada
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
            threading.Thread(target=self._iniciar_sessao, args=(conexao, endereco),
                             daemon=True).start()
        self.socket.close()

    def _iniciar_sessao(self, conexao: socket.socket, endereco) -> None:
        conexao.settimeout(TEMPO_LIMITE_INATIVIDADE)
        try:
            # O handshake TLS acontece aqui. Conexões sem TLS são recusadas.
            conexao_tls = self.contexto.wrap_socket(conexao, server_side=True)
        except (ssl.SSLError, OSError) as e:
            log.warning("[%s:%s] Handshake TLS recusado: %s", endereco[0], endereco[1], e)
            conexao.close()
            return
        try:
            atender_cliente(conexao_tls, endereco, self.base)
        except Exception:  # noqa: BLE001 - nunca derrubar o servidor por um cliente
            log.exception("[%s:%s] Erro inesperado.", endereco[0], endereco[1])

    def encerrar(self) -> None:
        self._parar.set()


def main() -> None:
    parser = argparse.ArgumentParser(description="Servidor de consulta de processos (TLS).")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--porta", type=int, default=5050)
    parser.add_argument("--dados", type=Path, default=PASTA_BASE / "dados.json")
    parser.add_argument("--cert", type=Path, default=PASTA_BASE / "certs" / "cert.pem")
    parser.add_argument("--chave", type=Path, default=PASTA_BASE / "certs" / "key.pem")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        datefmt="%d/%m/%Y %H:%M:%S")

    for arquivo in (args.cert, args.chave):
        if not arquivo.exists():
            sys.exit(f"Arquivo não encontrado: {arquivo}\n"
                     "Gere o certificado com:  python gerar_certificado.py")

    servidor = Servidor(args.host, args.porta, criar_contexto_tls(args.cert, args.chave),
                        BaseDeDados(args.dados))
    log.info("Servidor ouvindo em %s:%s (TLS). Pressione Ctrl+C para encerrar.", *servidor.endereco[:2])
    try:
        servidor.servir_para_sempre()
    except KeyboardInterrupt:
        log.info("Encerrando servidor...")
        servidor.encerrar()


if __name__ == "__main__":
    main()
