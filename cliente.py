"""Cliente de consulta de processos — PI III-A (PUC Goiás, ADS EaD).

Conecta-se ao servidor por TLS (verificando o certificado), faz o login do
cliente do escritório e oferece um menu em linha de comando para consultar
o andamento dos seus processos.

Uso:
    python cliente.py
    python cliente.py --host 192.168.0.10 --porta 5050
"""
from __future__ import annotations

import argparse
import getpass
import socket
import ssl
import sys
from pathlib import Path

from comum import enviar, receber

PASTA_BASE = Path(__file__).resolve().parent
LINHA = "-" * 64


class ConexaoServidor:
    """Encapsula a conexão TLS e o envio de requisições."""

    def __init__(self, host: str, porta: int, certificado_ca: Path):
        contexto = ssl.create_default_context(cafile=str(certificado_ca))
        contexto.minimum_version = ssl.TLSVersion.TLSv1_2
        # create_default_context já exige certificado válido (CERT_REQUIRED)
        # e confere se o nome do host bate com o certificado.
        bruto = socket.create_connection((host, porta), timeout=15)
        self.sock = contexto.wrap_socket(bruto, server_hostname=host)
        self.leitor = self.sock.makefile("r", encoding="utf-8", newline="\n")

    def requisitar(self, mensagem: dict) -> dict:
        enviar(self.sock, mensagem)
        resposta = receber(self.leitor)
        if resposta is None:
            raise ConnectionError("O servidor encerrou a conexão.")
        return resposta

    def descricao_seguranca(self) -> str:
        return f"{self.sock.version()} | {self.sock.cipher()[0]}"

    def fechar(self) -> None:
        try:
            self.leitor.close()
            self.sock.close()
        except OSError:
            pass


# --------------------------------------------------------------------------
# Exibição
# --------------------------------------------------------------------------
def mostrar_lista(processos: list[dict]) -> None:
    if not processos:
        print("\nVocê não possui processos cadastrados.")
        return
    print(f"\n{LINHA}\nMEUS PROCESSOS\n{LINHA}")
    for i, p in enumerate(processos, start=1):
        print(f"[{i}] {p['numero']}")
        print(f"    Ação: {p['tipo_acao']}")
        print(f"    Fase: {p['fase']}  |  Atualizado em: {p['ultima_atualizacao']}")
    print(LINHA)


def mostrar_detalhes(p: dict) -> None:
    print(f"\n{LINHA}\nPROCESSO {p['numero']}\n{LINHA}")
    print(f"Tipo de ação ........: {p['tipo_acao']}")
    print(f"Órgão julgador ......: {p['orgao_julgador']}")
    print(f"Distribuído em ......: {p['data_distribuicao']}")
    print(f"Fase atual ..........: {p['fase']}")
    print(f"Advogado responsável : {p['advogado_responsavel']}")
    print(f"Próximo passo .......: {p['proximo_passo']}")
    print("\nÚltimas movimentações:")
    for mov in p["movimentacoes"]:
        print(f"  {mov['data']}  {mov['descricao']}")
    print(LINHA)


# --------------------------------------------------------------------------
# Fluxo do programa
# --------------------------------------------------------------------------
def fazer_login(conexao: ConexaoServidor) -> bool:
    while True:
        codigo = input("Código de acesso: ").strip()
        senha = getpass.getpass("Senha (não aparece ao digitar): ")
        resposta = conexao.requisitar({"acao": "login", "codigo": codigo, "senha": senha})
        if resposta["status"] == "ok":
            print(f"\nBem-vindo(a), {resposta['nome']}!")
            return True
        print(f"\n{resposta['mensagem']}\n")
        if resposta.get("fim_sessao"):
            return False


def escolher_processo(conexao: ConexaoServidor) -> str | None:
    resposta = conexao.requisitar({"acao": "listar_processos"})
    processos = resposta.get("processos", [])
    mostrar_lista(processos)
    if not processos:
        return None
    escolha = input("Digite o nº da lista (ex.: 1) ou o número do processo: ").strip()
    if escolha.isdigit() and 1 <= int(escolha) <= len(processos):
        return processos[int(escolha) - 1]["numero"]
    return escolha or None


def menu(conexao: ConexaoServidor) -> None:
    while True:
        print("\n=== MENU ===")
        print("1 - Meus processos")
        print("2 - Detalhes de um processo")
        print("0 - Sair")
        opcao = input("Opção: ").strip()

        if opcao == "1":
            resposta = conexao.requisitar({"acao": "listar_processos"})
            if resposta["status"] == "ok":
                mostrar_lista(resposta["processos"])
            else:
                print(resposta["mensagem"])
        elif opcao == "2":
            numero = escolher_processo(conexao)
            if not numero:
                continue
            resposta = conexao.requisitar({"acao": "detalhar_processo", "numero": numero})
            if resposta["status"] == "ok":
                mostrar_detalhes(resposta["processo"])
            else:
                print(f"\n{resposta['mensagem']}")
        elif opcao == "0":
            resposta = conexao.requisitar({"acao": "sair"})
            print(resposta.get("mensagem", "Até logo!"))
            return
        else:
            print("Opção inválida.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Cliente de consulta de processos (TLS).")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--porta", type=int, default=5050)
    parser.add_argument("--ca", type=Path, default=PASTA_BASE / "certs" / "cert.pem",
                        help="Certificado do servidor usado para validar a conexão.")
    args = parser.parse_args()

    print(LINHA)
    print("ALMEIDA CAMPOS ADVOGADOS ASSOCIADOS — Consulta de Processos")
    print("(protótipo acadêmico — dados fictícios)")
    print(LINHA)

    if not args.ca.exists():
        sys.exit(f"Certificado não encontrado: {args.ca}\nGere-o com: python gerar_certificado.py")

    try:
        conexao = ConexaoServidor(args.host, args.porta, args.ca)
    except ssl.SSLCertVerificationError as e:
        sys.exit(f"Certificado do servidor NÃO é confiável — conexão abortada.\nDetalhe: {e}")
    except (ConnectionError, OSError) as e:
        sys.exit(f"Não foi possível conectar a {args.host}:{args.porta}. "
                 f"O servidor está em execução?\nDetalhe: {e}")

    print(f"Conexão segura estabelecida com {args.host}:{args.porta} "
          f"({conexao.descricao_seguranca()})\n")
    try:
        if fazer_login(conexao):
            menu(conexao)
    except (ConnectionError, OSError) as e:
        print(f"\nConexão perdida com o servidor: {e}")
    except (KeyboardInterrupt, EOFError):
        print("\nEncerrando...")
    finally:
        conexao.fechar()


if __name__ == "__main__":
    main()
