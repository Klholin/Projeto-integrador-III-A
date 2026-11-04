"""Define (ou troca) a senha de um cliente no dados.json.

Usa o componente GerenciadorDeSenhas com as propriedades da especificação:
a senha nunca é gravada em texto puro, só o salt e o hash.

Uso:
    python cadastrar_senha.py 111.444.777-35
    python cadastrar_senha.py "CRM-GO 99001"
"""
from __future__ import annotations

import argparse
import getpass
import json
import sys
from pathlib import Path

from app.documentos import ValidadorDeDocumento
from app.especificacao import Especificacao
from app.seguranca import GerenciadorDeSenhas

ARQUIVO_DADOS = Path(__file__).resolve().parent / "dados.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Define a senha de um cliente.")
    parser.add_argument("documento", help='CPF, CNPJ ou CRM do cliente (ex.: 111.444.777-35 ou "CRM-GO 99001")')
    parser.add_argument("--dados", type=Path, default=ARQUIVO_DADOS)
    args = parser.parse_args()

    espec = Especificacao.carregar()
    senhas = GerenciadorDeSenhas(espec.propriedade("GerenciadorDeSenhas", "iteracoes"))
    tipos = espec.propriedade("ValidadorDeDocumento", "tipos_aceitos")
    documento = ValidadorDeDocumento([t.strip() for t in tipos.split(",")]).reconhecer(args.documento)
    if documento is None:
        sys.exit("Documento inválido. Informe CPF, CNPJ ou CRM com UF.")

    with open(args.dados, encoding="utf-8") as arquivo:
        dados = json.load(arquivo)

    cliente = next((c for c in dados["clientes"]
                    if {"tipo": documento.tipo, "numero": documento.numero} in c["documentos"]), None)
    if cliente is None:
        sys.exit(f"Nenhum cliente com o documento {documento.formatado()}.")

    senha = getpass.getpass("Nova senha: ")
    if len(senha) < 6:
        sys.exit("A senha deve ter pelo menos 6 caracteres.")
    if senha != getpass.getpass("Confirme a senha: "):
        sys.exit("As senhas não conferem.")

    cliente["salt"], cliente["hash_senha"] = senhas.gerar_hash(senha)
    with open(args.dados, "w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=2)
        arquivo.write("\n")
    print(f"Senha de {cliente['nome']} atualizada (vale para todos os seus documentos).")


if __name__ == "__main__":
    main()
