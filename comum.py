"""Funções compartilhadas entre servidor e cliente.

- Protocolo de mensagens: cada mensagem é um objeto JSON em UMA linha,
  terminada por "\\n" (JSON Lines), trafegando dentro do canal TLS.
- Senhas: armazenadas como hash PBKDF2-HMAC-SHA256 com salt aleatório.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets

CODIFICACAO = "utf-8"
TAMANHO_MAX_MENSAGEM = 64 * 1024  # 64 KB: evita mensagens gigantes (DoS simples)
ITERACOES_PBKDF2 = 200_000
VERSAO_PROTOCOLO = 1


class ErroProtocolo(Exception):
    """Mensagem malformada ou fora do padrão do protocolo."""


# --------------------------------------------------------------------------
# Envio e recebimento de mensagens
# --------------------------------------------------------------------------
def enviar(conexao, mensagem: dict) -> None:
    """Serializa a mensagem em JSON e envia como uma linha."""
    dados = json.dumps(mensagem, ensure_ascii=False) + "\n"
    conexao.sendall(dados.encode(CODIFICACAO))


def receber(leitor) -> dict | None:
    """Lê uma linha do leitor (socket.makefile) e devolve o dicionário.

    Retorna None quando a outra ponta encerrou a conexão.
    """
    linha = leitor.readline(TAMANHO_MAX_MENSAGEM + 1)
    if not linha:
        return None
    if len(linha) > TAMANHO_MAX_MENSAGEM:
        raise ErroProtocolo("Mensagem excede o tamanho máximo permitido.")
    try:
        mensagem = json.loads(linha)
    except json.JSONDecodeError as erro:
        raise ErroProtocolo("Mensagem não é um JSON válido.") from erro
    if not isinstance(mensagem, dict):
        raise ErroProtocolo("Mensagem deve ser um objeto JSON.")
    return mensagem


# --------------------------------------------------------------------------
# Senhas (hash com salt)
# --------------------------------------------------------------------------
def gerar_hash_senha(senha: str, salt_hex: str | None = None) -> tuple[str, str]:
    """Gera (salt, hash) em hexadecimal para a senha informada."""
    salt = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(16)
    derivada = hashlib.pbkdf2_hmac(
        "sha256", senha.encode(CODIFICACAO), salt, ITERACOES_PBKDF2
    )
    return salt.hex(), derivada.hex()


def verificar_senha(senha: str, salt_hex: str, hash_hex: str) -> bool:
    """Compara a senha com o hash armazenado em tempo constante."""
    _, calculado = gerar_hash_senha(senha, salt_hex)
    return hmac.compare_digest(calculado, hash_hex)
