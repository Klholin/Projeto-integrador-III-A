"""Inicia o servidor — System ConsultaDeProcessos (ver intencoes/sistema.iop).

Uso:
    python servidor.py                 # 127.0.0.1:5050
    python servidor.py --porta 6000
    python servidor.py --host 0.0.0.0  # aceita conexões de outras máquinas da rede
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from app.especificacao import CAMINHO_PADRAO, ErroDeEspecificacao, Especificacao
from app.repositorio import RepositorioJSON
from app.seguranca import CanalSeguro
from app.fluxos import OrquestradorDeFluxos, ServidorSeguro

PASTA = Path(__file__).resolve().parent


def configurar_log(arquivo: Path) -> None:
    arquivo.parent.mkdir(exist_ok=True)
    formato = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%d/%m/%Y %H:%M:%S")
    raiz = logging.getLogger()
    raiz.setLevel(logging.INFO)
    for destino in (logging.StreamHandler(), logging.FileHandler(arquivo, encoding="utf-8")):
        destino.setFormatter(formato)
        raiz.addHandler(destino)


def main() -> None:
    parser = argparse.ArgumentParser(description="Servidor de consulta de processos (TLS).")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--porta", type=int, default=5050)
    parser.add_argument("--dados", type=Path, default=PASTA / "dados.json")
    parser.add_argument("--cert", type=Path, default=PASTA / "certs" / "cert.pem")
    parser.add_argument("--chave", type=Path, default=PASTA / "certs" / "key.pem")
    parser.add_argument("--espec", type=Path, default=CAMINHO_PADRAO)
    parser.add_argument("--log", type=Path, default=PASTA / "logs" / "servidor.log")
    args = parser.parse_args()

    for arquivo in (args.cert, args.chave):
        if not arquivo.exists():
            sys.exit(f"Arquivo não encontrado: {arquivo}\nGere o certificado com: python gerar_certificado.py")

    try:
        espec = Especificacao.carregar(args.espec)
        repositorio = RepositorioJSON(args.dados)
    except (ErroDeEspecificacao, ValueError) as erro:
        sys.exit(str(erro))

    configurar_log(args.log)
    log = logging.getLogger("servidor")
    canal = CanalSeguro.para_servidor(args.cert, args.chave,
                                      espec.propriedade("CanalSeguro", "versao_minima"))
    servidor = ServidorSeguro(args.host, args.porta, espec, canal,
                              OrquestradorDeFluxos(espec, repositorio))

    log.info("System %s — intenções: %s", espec.sistema, ", ".join(espec.intencoes))
    log.info("Servidor ouvindo em %s:%s (TLS). Ctrl+C para encerrar.", *servidor.endereco[:2])
    try:
        servidor.servir_para_sempre()
    except KeyboardInterrupt:
        log.info("Encerrando servidor...")
        servidor.encerrar()


if __name__ == "__main__":
    main()
