"""Inicia o cliente — System ConsultaDeProcessos (ver intencoes/sistema.iop).

Uso:
    python cliente.py
    python cliente.py --host 192.168.0.10 --porta 5050
"""
from __future__ import annotations

import argparse
import ssl
import sys
from pathlib import Path

from app.componentes_cliente import LINHA, ClienteDeRede, InterfaceDoCliente
from app.especificacao import CAMINHO_PADRAO, ErroDeEspecificacao, Especificacao
from app.seguranca import CanalSeguro

PASTA = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser(description="Cliente de consulta de processos (TLS).")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--porta", type=int, default=5050)
    parser.add_argument("--ca", type=Path, default=PASTA / "certs" / "cert.pem",
                        help="Certificado do servidor usado para validar a conexão.")
    parser.add_argument("--espec", type=Path, default=CAMINHO_PADRAO)
    args = parser.parse_args()

    try:
        espec = Especificacao.carregar(args.espec)
    except ErroDeEspecificacao as erro:
        sys.exit(str(erro))

    print(LINHA)
    print("ALMEIDA CAMPOS ADVOGADOS ASSOCIADOS — Consulta de Processos")
    print("(protótipo acadêmico — dados fictícios)")
    print(LINHA)

    if not args.ca.exists():
        sys.exit(f"Certificado não encontrado: {args.ca}\nGere-o com: python gerar_certificado.py")

    canal = CanalSeguro.para_cliente(args.ca, espec.propriedade("CanalSeguro", "versao_minima"))
    try:
        rede = ClienteDeRede(args.host, args.porta, canal,
                             espec.propriedade("CanalDeMensagens", "tamanho_maximo_kb"))
    except ssl.SSLCertVerificationError as erro:
        sys.exit(f"{espec.mensagem_de_erro('certificado_nao_confiavel')}\nDetalhe: {erro}")
    except OSError as erro:
        sys.exit(f"{espec.mensagem_de_erro('servidor_indisponivel', endereco=f'{args.host}:{args.porta}')}"
                 f"\nDetalhe: {erro}")

    print(f"Conexão segura estabelecida com {args.host}:{args.porta} ({rede.descricao_seguranca()})\n")
    try:
        InterfaceDoCliente(rede).executar()
    except (ConnectionError, OSError):
        print(f"\n{espec.mensagem_de_erro('conexao_perdida')}")
    except (KeyboardInterrupt, EOFError):
        print("\nEncerrando...")
    finally:
        rede.fechar()


if __name__ == "__main__":
    main()
