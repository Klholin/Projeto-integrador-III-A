"""Testes integrados cliente-servidor sobre TLS, organizados por intenção.

Executar a partir da pasta do projeto:
    python -m unittest discover -s tests -v
"""
import logging
import socket
import ssl
import sys
import threading
import unittest
from pathlib import Path

PASTA = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PASTA))

from app.componentes_cliente import ClienteDeRede  # noqa: E402
from app.especificacao import Especificacao  # noqa: E402
from app.repositorio import RepositorioJSON  # noqa: E402
from app.seguranca import CanalSeguro  # noqa: E402
from app.fluxos import OrquestradorDeFluxos, ServidorSeguro  # noqa: E402

CERT, CHAVE = PASTA / "certs" / "cert.pem", PASTA / "certs" / "key.pem"
PROC_MARIA = "0001001-11.2026.8.09.9999"
PROC_JOAO = "0001002-22.2026.8.09.9999"
PROC_MEDICO = "0001007-77.2025.8.09.9999"
CPF_MARIA = "111.444.777-35"

logging.getLogger("auditoria").setLevel(logging.CRITICAL)  # saída limpa nos testes


@unittest.skipUnless(CERT.exists() and CHAVE.exists(),
                     "Gere o certificado antes: python gerar_certificado.py")
class TestIntegracao(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.espec = Especificacao.carregar()
        versao = cls.espec.propriedade("CanalSeguro", "versao_minima")
        cls.servidor = ServidorSeguro(
            "127.0.0.1", 0, cls.espec, CanalSeguro.para_servidor(CERT, CHAVE, versao),
            OrquestradorDeFluxos(cls.espec, RepositorioJSON(PASTA / "dados.json")))
        cls.porta = cls.servidor.endereco[1]
        cls.canal_cliente = CanalSeguro.para_cliente(CERT, versao)
        threading.Thread(target=cls.servidor.servir_para_sempre, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.servidor.encerrar()

    def conectar(self) -> ClienteDeRede:
        rede = ClienteDeRede("127.0.0.1", self.porta, self.canal_cliente, 64)
        self.addCleanup(rede.fechar)
        return rede

    def logado(self, documento=CPF_MARIA, senha="maria2026") -> ClienteDeRede:
        rede = self.conectar()
        self.assertEqual(rede.autenticar(documento, senha)["status"], "ok")
        return rede

    # --- Component CanalSeguro -----------------------------------------
    def test_canal_seguro_usa_tls_moderno(self):
        self.assertIn(self.conectar().conexao.version(), ("TLSv1.2", "TLSv1.3"))

    def test_canal_seguro_recusa_conexao_sem_tls(self):
        with socket.create_connection(("127.0.0.1", self.porta), timeout=5) as s:
            s.sendall(b'{"intencao": "autenticar", "documento": "11144477735", "senha": "maria2026"}\n')
            try:
                resposta = s.recv(1024)
            except ConnectionResetError:
                resposta = b""
            self.assertNotIn(b"ok", resposta)

    def test_canal_seguro_rejeita_certificado_nao_confiavel(self):
        contexto = ssl.create_default_context()  # sem o nosso cert.pem
        with socket.create_connection(("127.0.0.1", self.porta), timeout=5) as s:
            with self.assertRaises(ssl.SSLCertVerificationError):
                contexto.wrap_socket(s, server_hostname="127.0.0.1")

    # --- Flow: on intenção autenticar ------------------------------------
    def test_autenticar_com_cpf_com_e_sem_pontuacao(self):
        for documento in (CPF_MARIA, "11144477735"):
            resposta = self.conectar().autenticar(documento, "maria2026")
            self.assertEqual(resposta, {"status": "ok", "nome": "Maria Exemplo da Silva"})

    def test_autenticar_com_cnpj(self):
        resposta = self.conectar().autenticar("11.222.333/0001-81", "clinica2026")
        self.assertEqual(resposta["nome"], "Clínica Exemplo Saúde Ltda.")

    def test_autenticar_medico_por_cpf_ou_crm_leva_a_mesma_conta(self):
        processos = []
        for documento in ("444.777.111-07", "CRM-GO 99001", "99001/GO"):
            rede = self.logado(documento, "medico2026")
            processos.append(rede.consultar_meus_processos()["processos"])
        self.assertEqual(processos[0], processos[1])
        self.assertEqual(processos[1], processos[2])
        self.assertEqual([p["numero"] for p in processos[0]], [PROC_MEDICO])

    def test_autenticar_documento_invalido_conta_como_tentativa(self):
        rede = self.conectar()
        resposta = rede.autenticar("123.456.789-00", "qualquer")
        self.assertEqual(resposta["condicao"], "documento_invalido")
        self.assertEqual(resposta["mensagem"],
                         self.espec.mensagem_de_erro("documento_invalido", restantes=2))

    def test_autenticar_nao_registra_documento_completo_no_log(self):
        with self.assertLogs("auditoria", level="INFO") as registro:
            self.conectar().autenticar(CPF_MARIA, "maria2026")
            self.conectar().autenticar("CRM-GO 99001", "errada")
        texto = "\n".join(registro.output)
        self.assertIn("***.444.777-**", texto)
        for trecho in ("11144477735", CPF_MARIA, "99001", "maria2026", "errada"):
            self.assertNotIn(trecho, texto)

    def test_autenticar_invalido_usa_mensagem_da_especificacao(self):
        resposta = self.conectar().autenticar(CPF_MARIA, "errada")
        self.assertEqual(resposta["condicao"], "credenciais_invalidas")
        self.assertEqual(resposta["mensagem"],
                         self.espec.mensagem_de_erro("credenciais_invalidas", restantes=2))

    def test_autenticar_bloqueia_apos_max_tentativas(self):
        rede = self.conectar()
        maximo = self.espec.propriedade("ValidadorDeCredenciais", "max_tentativas")
        for _ in range(maximo):
            resposta = rede.autenticar("documento-qualquer", "Y")
        self.assertEqual(resposta["condicao"], "bloqueio")
        self.assertTrue(resposta.get("fim_sessao"))
        with self.assertRaises((ConnectionError, OSError)):
            rede.autenticar(CPF_MARIA, "maria2026")

    # --- Flow: on intenção consultar_meus_processos ----------------------
    def test_consultar_meus_processos_exige_login(self):
        resposta = self.conectar().consultar_meus_processos()
        self.assertEqual(resposta["condicao"], "login_necessario")

    def test_consultar_meus_processos_somente_os_proprios(self):
        resposta = self.logado().consultar_meus_processos()
        numeros = {p["numero"] for p in resposta["processos"]}
        self.assertEqual(numeros, {PROC_MARIA, "0001003-33.2025.8.09.9999"})

    def test_consultar_meus_processos_expoe_so_campos_do_resumo(self):
        resposta = self.logado().consultar_meus_processos()
        campos = self.espec.propriedade("ConsultaDeProcessos", "campos_resumo")
        esperados = {c.strip() for c in campos.split(",")}
        for processo in resposta["processos"]:
            self.assertEqual(set(processo), esperados)

    # --- Flow: on intenção ver_andamento_do_processo ---------------------
    def test_ver_andamento_do_processo_proprio(self):
        resposta = self.logado().ver_andamento_do_processo(PROC_MARIA)
        self.assertEqual(resposta["status"], "ok")
        self.assertTrue(resposta["processo"]["movimentacoes"])

    def test_ver_andamento_do_processo_de_outro_cliente_e_negado(self):
        resposta = self.logado().ver_andamento_do_processo(PROC_JOAO)
        self.assertEqual(resposta["condicao"], "processo_nao_encontrado")

    def test_ver_andamento_do_processo_exige_login(self):
        resposta = self.conectar().ver_andamento_do_processo(PROC_MARIA)
        self.assertEqual(resposta["condicao"], "login_necessario")

    # --- Flow: on intenção encerrar_sessao -------------------------------
    def test_encerrar_sessao(self):
        resposta = self.logado().encerrar_sessao()
        self.assertEqual(resposta["status"], "ok")
        self.assertTrue(resposta["fim_sessao"])

    # --- ErrorHandling ---------------------------------------------------
    def test_intencao_desconhecida(self):
        rede = self.logado()
        rede.mensagens.enviar({"intencao": "apagar_tudo"})
        self.assertEqual(rede.mensagens.receber()["condicao"], "intencao_desconhecida")

    def test_mensagem_invalida(self):
        rede = self.conectar()
        rede.conexao.sendall(b"isto nao e json\n")
        resposta = rede.mensagens.receber()
        self.assertEqual(resposta["condicao"], "mensagem_invalida")
        self.assertTrue(resposta["fim_sessao"])


if __name__ == "__main__":
    unittest.main()
