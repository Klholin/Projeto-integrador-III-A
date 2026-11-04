"""Define (ou troca) a senha de um cliente no dados.json.

A senha nunca é gravada em texto puro: só o salt e o hash PBKDF2.

Uso:
    python cadastrar_senha.py CLI-1001
"""
from __future__ import annotations

import argparse
import getpass
import json
import sys
from pathlib import Path

from comum import gerar_hash_senha

ARQUIVO_DADOS = Path(__file__).resolve().parent / "dados.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Define a senha de um cliente.")
    parser.add_argument("codigo", help="Código de acesso do cliente (ex.: CLI-1001)")
    parser.add_argument("--dados", type=Path, default=ARQUIVO_DADOS)
    args = parser.parse_args()

    with open(args.dados, encoding="utf-8") as arquivo:
        dados = json.load(arquivo)

    cliente = next((c for c in dados["clientes"]
                    if c["codigo"].upper() == args.codigo.upper()), None)
    if cliente is None:
        sys.exit(f"Cliente {args.codigo} não encontrado.")

    senha = getpass.getpass("Nova senha: ")
    if len(senha) < 6:
        sys.exit("A senha deve ter pelo menos 6 caracteres.")
    if senha != getpass.getpass("Confirme a senha: "):
        sys.exit("As senhas não conferem.")

    cliente["salt"], cliente["hash_senha"] = gerar_hash_senha(senha)
    with open(args.dados, "w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=2)
        arquivo.write("\n")
    print(f"Senha de {cliente['codigo']} atualizada.")


if __name__ == "__main__":
    main()
