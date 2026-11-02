"""Testes integrados cliente-servidor sobre TLS.

Executar a partir da pasta do projeto:
    python -m unittest discover -s tests -v
"""
import socket
import ssl
import sys
import threading
import unittest
from pathlib import Path

PASTA = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PASTA))

from cliente import ConexaoServidor  # noqa: E402
from servidor import BaseDeDados, Servidor, criar_contexto_tls  # noqa: E402

CERT, CHAVE = PASTA / "certs" / "cert.pem", PASTA / "certs" / "key.pem"
PROC_MARIA = "0001001-11.2026.8.09.9999"
PROC_JOAO = "0001002-22.2026.8.09.9999"


@unittest.skipUnless(CERT.exists() and CHAVE.exists(),
                     "Gere o certificado antes: python gerar_certificado.py")
class TestIntegracao(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.servidor = Servidor("127.0.0.1", 0, criar_contexto_tls(CERT, CHAVE),
                                BaseDeDados(PASTA / "dados.json"))
        cls.porta = cls.servidor.endereco[1]
        threading.Thread(target=cls.servidor.servir_para_sempre, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.servidor.encerrar()

    def conectar(self):
        conexao = ConexaoServidor("127.0.0.1", self.porta, CERT)
        self.addCleanup(conexao.fechar)
        return conexao

    def logar(self, codigo="CLI-1001", senha="maria2026"):
        conexao = self.conectar()
        self.assertEqual(conexao.requisitar({"acao": "login", "codigo": codigo,
                                             "senha": senha})["status"], "ok")
        return conexao

    # --- Segurança da comunicação -------------------------------------
    def test_conexao_usa_tls_moderno(self):
        self.assertIn(self.conectar().sock.version(), ("TLSv1.2", "TLSv1.3"))

    def test_conexao_sem_tls_e_recusada(self):
        with socket.create_connection(("127.0.0.1", self.porta), timeout=5) as s:
            s.sendall(b'{"acao": "login", "codigo": "CLI-1001", "senha": "maria2026"}\n')
            try:
                resposta = s.recv(1024)
            except ConnectionResetError:
                resposta = b""
            self.assertNotIn(b"ok", resposta)

    def test_certificado_nao_confiavel_e_rejeitado(self):
        contexto = ssl.create_default_context()  # sem o nosso cert.pem
        with socket.create_connection(("127.0.0.1", self.porta), timeout=5) as s:
            with self.assertRaises(ssl.SSLCertVerificationError):
                contexto.wrap_socket(s, server_hostname="127.0.0.1")

    # --- Autenticação --------------------------------------------------
    def test_login_valido(self):
        resposta = self.conectar().requisitar(
            {"acao": "login", "codigo": "cli-1001", "senha": "maria2026"})
        self.assertEqual(resposta["status"], "ok")
        self.assertEqual(resposta["nome"], "Maria Exemplo da Silva")

    def test_login_invalido(self):
        resposta = self.conectar().requisitar(
            {"acao": "login", "codigo": "CLI-1001", "senha": "errada"})
        self.assertEqual(resposta["status"], "erro")

    def test_bloqueio_apos_tres_tentativas(self):
        conexao = self.conectar()
        for _ in range(3):
            resposta = conexao.requisitar({"acao": "login", "codigo": "X", "senha": "Y"})
        self.assertTrue(resposta.get("fim_sessao"))
        with self.assertRaises((ConnectionError, OSError)):
            conexao.requisitar({"acao": "login", "codigo": "CLI-1001", "senha": "maria2026"})

    def test_consulta_exige_login(self):
        resposta = self.conectar().requisitar({"acao": "listar_processos"})
        self.assertEqual(resposta["status"], "erro")

    # --- Consultas e controle de acesso ---------------------------------
    def test_lista_somente_processos_do_cliente(self):
        resposta = self.logar().requisitar({"acao": "listar_processos"})
        numeros = {p["numero"] for p in resposta["processos"]}
        self.assertEqual(numeros, {PROC_MARIA, "0001003-33.2025.8.09.9999"})

    def test_detalhes_do_proprio_processo(self):
        resposta = self.logar().requisitar({"acao": "detalhar_processo", "numero": PROC_MARIA})
        self.assertEqual(resposta["status"], "ok")
        self.assertTrue(resposta["processo"]["movimentacoes"])

    def test_nao_acessa_processo_de_outro_cliente(self):
        resposta = self.logar().requisitar({"acao": "detalhar_processo", "numero": PROC_JOAO})
        self.assertEqual(resposta["status"], "erro")

    def test_acao_desconhecida(self):
        resposta = self.logar().requisitar({"acao": "apagar_tudo"})
        self.assertEqual(resposta["status"], "erro")

    def test_sair(self):
        self.assertEqual(self.logar().requisitar({"acao": "sair"})["status"], "ok")


if __name__ == "__main__":
    unittest.main()
