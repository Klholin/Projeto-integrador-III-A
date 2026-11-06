"""Componentes de segurança: CanalSeguro (TLS) e GerenciadorDeSenhas."""
from __future__ import annotations

import hashlib
import hmac
import secrets
import socket
import ssl
from pathlib import Path

from app.intencao import componente

VERSOES_TLS = {"TLS 1.2": ssl.TLSVersion.TLSv1_2, "TLS 1.3": ssl.TLSVersion.TLSv1_3}


@componente("CanalSeguro")
class CanalSeguro:
    """Intenção: estabelecer a conexão criptografada e garantir a identidade do servidor."""

    def __init__(self, contexto: ssl.SSLContext):
        self.contexto = contexto

    @classmethod
    def para_servidor(cls, certificado: Path, chave: Path, versao_minima: str) -> "CanalSeguro":
        contexto = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        contexto.minimum_version = VERSOES_TLS[versao_minima]
        contexto.load_cert_chain(certfile=str(certificado), keyfile=str(chave))
        return cls(contexto)

    @classmethod
    def para_cliente(cls, certificado_ca: Path, versao_minima: str) -> "CanalSeguro":
        # create_default_context exige certificado válido e confere o nome do host.
        contexto = ssl.create_default_context(cafile=str(certificado_ca))
        contexto.minimum_version = VERSOES_TLS[versao_minima]
        return cls(contexto)

    def proteger(self, conexao: socket.socket) -> ssl.SSLSocket:
        """Lado servidor: handshake TLS; conexões sem TLS falham aqui."""
        return self.contexto.wrap_socket(conexao, server_side=True)

    def conectar(self, host: str, porta: int, tempo_limite: float = 15) -> ssl.SSLSocket:
        """Lado cliente: conecta e valida o certificado do servidor."""
        bruto = socket.create_connection((host, porta), timeout=tempo_limite)
        try:
            return self.contexto.wrap_socket(bruto, server_hostname=host)
        except Exception:
            bruto.close()
            raise


@componente("GerenciadorDeSenhas")
class GerenciadorDeSenhas:
    """Intenção: proteger as senhas armazenadas (nunca em texto puro)."""

    def __init__(self, iteracoes: int):
        self.iteracoes = iteracoes

    def gerar_hash(self, senha: str, salt_hex: str | None = None) -> tuple[str, str]:
        salt = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(16)
        derivada = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), salt, self.iteracoes)
        return salt.hex(), derivada.hex()

    def verificar(self, senha: str, salt_hex: str, hash_hex: str) -> bool:
        _, calculado = self.gerar_hash(senha, salt_hex)
        return hmac.compare_digest(calculado, hash_hex)  # tempo constante
