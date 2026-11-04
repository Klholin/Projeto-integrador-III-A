"""Gera o certificado autoassinado (cert.pem) e a chave privada (key.pem).

Usa o OpenSSL instalado no computador. No Windows, o OpenSSL que vem com o
Git for Windows é encontrado automaticamente.

Uso:
    python gerar_certificado.py
    python gerar_certificado.py --ip 192.168.0.10   # para acessar por outra máquina da rede
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

PASTA_CERTS = Path(__file__).resolve().parent / "certs"
CAMINHOS_WINDOWS = [
    r"C:\Program Files\Git\usr\bin\openssl.exe",
    r"C:\Program Files\Git\mingw64\bin\openssl.exe",
    r"C:\Program Files\OpenSSL-Win64\bin\openssl.exe",
]


def localizar_openssl() -> str:
    encontrado = shutil.which("openssl")
    if encontrado:
        return encontrado
    for caminho in CAMINHOS_WINDOWS:
        if Path(caminho).exists():
            return caminho
    sys.exit("OpenSSL não encontrado. Instale o Git for Windows (inclui o OpenSSL) "
             "ou o OpenSSL e tente novamente.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera certificado TLS autoassinado.")
    parser.add_argument("--ip", action="append", default=[],
                        help="IP extra do servidor a incluir no certificado (pode repetir).")
    parser.add_argument("--dias", type=int, default=365)
    args = parser.parse_args()

    PASTA_CERTS.mkdir(exist_ok=True)
    cert, chave = PASTA_CERTS / "cert.pem", PASTA_CERTS / "key.pem"

    nomes = ["DNS:localhost", "IP:127.0.0.1"] + [f"IP:{ip}" for ip in args.ip]
    comando = [
        localizar_openssl(), "req", "-x509", "-newkey", "rsa:2048", "-sha256", "-nodes",
        "-days", str(args.dias),
        "-keyout", str(chave), "-out", str(cert),
        "-subj", "/C=BR/ST=Goias/L=Goiania/O=PI III-A Prototipo/CN=localhost",
        "-addext", "subjectAltName=" + ",".join(nomes),
    ]
    resultado = subprocess.run(comando, capture_output=True, text=True)
    if resultado.returncode != 0:
        sys.exit(f"Falha ao gerar o certificado:\n{resultado.stderr}")

    print(f"Certificado gerado: {cert}")
    print(f"Chave privada.....: {chave}  (NÃO envie este arquivo para o GitHub)")
    print(f"Nomes válidos.....: {', '.join(nomes)}")


if __name__ == "__main__":
    main()
