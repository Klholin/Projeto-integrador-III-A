"""Verifica se o código continua fiel à especificação de intenção.

Princípio IOP da Transparência: a relação intenção → implementação deve
permanecer visível e verificável. Este script confere:

  1. Components      → cada componente tem uma classe com @componente("Nome")
  2. Flow            → cada 'on intenção X' tem um método com @fluxo("X")
  3. ErrorHandling   → cada ErroDeIntencao("cond") usado no código existe na especificação
  4. Rastreabilidade → cada intenção é exercitada por pelo menos um teste

Uso:
    python verificar_intencoes.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

PASTA = Path(__file__).resolve().parent
sys.path.insert(0, str(PASTA))

import app.componentes_cliente  # noqa: E402,F401  (importar registra os componentes)
import app.componentes_servidor  # noqa: E402,F401
import app.documentos  # noqa: E402,F401
import app.protocolo  # noqa: E402,F401
import app.repositorio  # noqa: E402,F401
import app.seguranca  # noqa: E402,F401
from app.especificacao import Especificacao  # noqa: E402
from app.intencao import REGISTRO_DE_COMPONENTES  # noqa: E402
from app.fluxos import OrquestradorDeFluxos  # noqa: E402

PADRAO_ERRO = re.compile(r'ErroDeIntencao\(\s*"(\w+)"')
PADRAO_MENSAGEM = re.compile(r"mensagem_de_erro\(\s*'(\w+)'")


def verificar(espec: Especificacao) -> list[tuple[str, str, bool, str]]:
    """Devolve linhas (categoria, item, ok, detalhe)."""
    resultado = []

    # 1. Componentes
    especificados, implementados = set(espec.componentes), set(REGISTRO_DE_COMPONENTES)
    for nome in sorted(especificados | implementados):
        if nome in especificados and nome in implementados:
            classe = REGISTRO_DE_COMPONENTES[nome]
            resultado.append(("Component", nome, True, f"{classe.__module__}.{classe.__qualname__}"))
        elif nome in especificados:
            resultado.append(("Component", nome, False, "sem classe @componente no código"))
        else:
            resultado.append(("Component", nome, False, "classe no código sem intenção na especificação"))

    # 2. Fluxos
    implementados = {getattr(getattr(OrquestradorDeFluxos, n), "__fluxo_iop__", None)
                     for n in dir(OrquestradorDeFluxos)} - {None}
    for intencao in sorted(set(espec.intencoes) | implementados):
        if intencao in espec.intencoes and intencao in implementados:
            resultado.append(("Flow", intencao, True, f"OrquestradorDeFluxos.{intencao}"))
        elif intencao in espec.intencoes:
            resultado.append(("Flow", intencao, False, "sem método @fluxo no código"))
        else:
            resultado.append(("Flow", intencao, False, "fluxo no código sem intenção na especificação"))

    # 3. Erros
    codigo_fonte = "\n".join(p.read_text(encoding="utf-8") for p in
                             [*(PASTA / "app").glob("*.py"), PASTA / "cliente.py", PASTA / "servidor.py"])
    usados = set(PADRAO_ERRO.findall(codigo_fonte)) | set(PADRAO_MENSAGEM.findall(codigo_fonte))
    for condicao in sorted(set(espec.erros) | usados):
        if condicao in espec.erros and condicao in usados:
            resultado.append(("ErrorHandling", condicao, True, "declarado e usado"))
        elif condicao in espec.erros:
            resultado.append(("ErrorHandling", condicao, False, "declarado, mas nunca usado no código"))
        else:
            resultado.append(("ErrorHandling", condicao, False, "usado no código, mas não declarado"))

    # 4. Rastreabilidade intenção → teste
    testes = "\n".join(p.read_text(encoding="utf-8") for p in (PASTA / "tests").glob("test_*.py"))
    for intencao in espec.intencoes:
        coberto = intencao in testes
        resultado.append(("Teste", intencao, coberto,
                          "coberta por teste" if coberto else "nenhum teste exercita esta intenção"))
    return resultado


def main() -> int:
    espec = Especificacao.carregar()
    linhas = verificar(espec)
    print(f"Verificação de intenções — System {espec.sistema}\n")
    print(f"{'':2}{'Seção':<14}{'Item':<28}Detalhe")
    print("-" * 90)
    for categoria, item, ok, detalhe in linhas:
        print(f"{'OK' if ok else 'XX':<2}  {categoria:<14}{item:<28}{detalhe}")
    falhas = sum(1 for linha in linhas if not linha[2])
    print("-" * 90)
    print(f"{len(linhas) - falhas}/{len(linhas)} verificações OK"
          + ("" if not falhas else f" — {falhas} divergência(s) entre intenção e código"))
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
