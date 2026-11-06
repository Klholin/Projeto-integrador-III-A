"""Componentes do lado cliente: ClienteDeRede e InterfaceDoCliente."""
from __future__ import annotations

import getpass

from app.intencao import componente
from app.protocolo import CanalDeMensagens
from app.seguranca import CanalSeguro

LINHA = "-" * 64
AJUDA_IDENTIFICACAO = """Identifique-se com um dos documentos abaixo (com ou sem pontuação):
  CPF   ex.: 111.444.777-35
  CNPJ  ex.: 11.222.333/0001-81
  CRM   ex.: CRM-GO 12345   ou   12345/GO
"""


@componente("ClienteDeRede")
class ClienteDeRede:
    """Intenção: representar o servidor no lado do cliente (uma função por intenção)."""

    def __init__(self, host: str, porta: int, canal: CanalSeguro, tamanho_maximo_kb: int):
        self.conexao = canal.conectar(host, porta)
        self.mensagens = CanalDeMensagens(self.conexao, tamanho_maximo_kb)

    def _enviar_intencao(self, intencao: str, **dados) -> dict:
        self.mensagens.enviar({"intencao": intencao, **dados})
        resposta = self.mensagens.receber()
        if resposta is None:
            raise ConnectionError("O servidor encerrou a conexão.")
        return resposta

    def autenticar(self, documento: str, senha: str) -> dict:
        return self._enviar_intencao("autenticar", documento=documento, senha=senha)

    def consultar_meus_processos(self) -> dict:
        return self._enviar_intencao("consultar_meus_processos")

    def ver_andamento_do_processo(self, numero: str) -> dict:
        return self._enviar_intencao("ver_andamento_do_processo", numero=numero)

    def encerrar_sessao(self) -> dict:
        return self._enviar_intencao("encerrar_sessao")

    def descricao_seguranca(self) -> str:
        return f"{self.conexao.version()} | {self.conexao.cipher()[0]}"

    def fechar(self) -> None:
        self.mensagens.fechar()


@componente("InterfaceDoCliente")
class InterfaceDoCliente:
    """Intenção: conversar com o usuário no terminal."""

    def __init__(self, rede: ClienteDeRede, entrada=input, ler_senha=getpass.getpass):
        self.rede = rede
        self.entrada = entrada
        self.ler_senha = ler_senha  # senha digitada sem eco

    def executar(self) -> None:
        if self.autenticar():
            self.menu()

    def autenticar(self) -> bool:
        print(AJUDA_IDENTIFICACAO)
        while True:
            documento = self.entrada("Documento (CPF, CNPJ ou CRM): ").strip()
            senha = self.ler_senha("Senha (não aparece ao digitar): ")
            resposta = self.rede.autenticar(documento, senha)
            if resposta["status"] == "ok":
                print(f"\nBem-vindo(a), {resposta['nome']}!")
                return True
            print(f"\n{resposta['mensagem']}\n")
            if resposta.get("fim_sessao"):
                return False

    def menu(self) -> None:
        opcoes = {"1": self.consultar_meus_processos, "2": self.ver_andamento_do_processo}
        while True:
            print("\n=== MENU ===")
            print("1 - Meus processos")
            print("2 - Andamento de um processo")
            print("0 - Sair")
            escolha = self.entrada("Opção: ").strip()
            if escolha == "0":
                print(self.rede.encerrar_sessao().get("mensagem", "Até logo!"))
                return
            acao = opcoes.get(escolha)
            if acao:
                acao()
            else:
                print("Opção inválida.")

    def consultar_meus_processos(self) -> list[dict]:
        resposta = self.rede.consultar_meus_processos()
        if resposta["status"] != "ok":
            print(resposta["mensagem"])
            return []
        self.mostrar_lista(resposta["processos"])
        return resposta["processos"]

    def ver_andamento_do_processo(self) -> None:
        processos = self.consultar_meus_processos()
        if not processos:
            return
        escolha = self.entrada("Digite o nº da lista (ex.: 1) ou o número do processo: ").strip()
        if escolha.isdigit() and 1 <= int(escolha) <= len(processos):
            escolha = processos[int(escolha) - 1]["numero"]
        if not escolha:
            return
        resposta = self.rede.ver_andamento_do_processo(escolha)
        if resposta["status"] == "ok":
            self.mostrar_detalhes(resposta["processo"])
        else:
            print(f"\n{resposta['mensagem']}")

    # ------------------------------------------------------------------ telas
    @staticmethod
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

    @staticmethod
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
