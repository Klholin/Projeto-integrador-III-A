"""Testes da especificação de intenção e dos componentes isolados.

Executar a partir da pasta do projeto:
    python -m unittest discover -s tests -v
"""
import sys
import tempfile
import unittest
from pathlib import Path

PASTA = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PASTA))

from app.componentes_servidor import Sessao  # noqa: E402
from app.documentos import ValidadorDeDocumento  # noqa: E402
from app.modelos import Documento  # noqa: E402
from app.especificacao import CAMINHO_PADRAO, ErroDeEspecificacao, Especificacao  # noqa: E402
from app.repositorio import RepositorioJSON  # noqa: E402
from app.seguranca import GerenciadorDeSenhas  # noqa: E402
from app.fluxos import OrquestradorDeFluxos  # noqa: E402
import verificar_intencoes  # noqa: E402


class TestEspecificacao(unittest.TestCase):
    def setUp(self):
        self.espec = Especificacao.carregar()

    def test_sistema_e_secoes(self):
        self.assertEqual(self.espec.sistema, "ConsultaDeProcessos")
        self.assertEqual(len(self.espec.componentes), 11)
        self.assertEqual(self.espec.intencoes, ["autenticar", "consultar_meus_processos",
                                                "ver_andamento_do_processo", "encerrar_sessao"])
        self.assertEqual(len(self.espec.mapas_de_implementacao), 3)

    def test_propriedades_tipadas(self):
        self.assertEqual(self.espec.propriedade("ValidadorDeCredenciais", "max_tentativas"), 3)
        self.assertEqual(self.espec.propriedade("CanalSeguro", "versao_minima"), "TLS 1.2")

    def test_mensagem_de_erro_com_dados(self):
        self.assertIn("Tentativas restantes: 2",
                      self.espec.mensagem_de_erro("credenciais_invalidas", restantes=2))

    def test_condicao_inexistente(self):
        with self.assertRaises(ErroDeEspecificacao):
            self.espec.mensagem_de_erro("nao_existe")

    def test_codigo_alinhado_com_a_especificacao(self):
        falhas = [linha for linha in verificar_intencoes.verificar(self.espec) if not linha[2]]
        self.assertEqual(falhas, [], f"Divergências intenção x código: {falhas}")

    def test_mudar_a_intencao_muda_o_comportamento(self):
        """Fonte da verdade: alterar max_tentativas na especificação altera o sistema."""
        texto = CAMINHO_PADRAO.read_text(encoding="utf-8").replace(
            "max_tentativas: 3", "max_tentativas: 5")
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "sistema.iop"
            caminho.write_text(texto, encoding="utf-8")
            espec = Especificacao.carregar(caminho)
        orquestrador = OrquestradorDeFluxos(espec, RepositorioJSON(PASTA / "dados.json"))
        self.assertEqual(orquestrador.validador.tentativas_restantes(Sessao("teste")), 5)


class TestValidadorDeDocumento(unittest.TestCase):
    def setUp(self):
        tipos = Especificacao.carregar().propriedade("ValidadorDeDocumento", "tipos_aceitos")
        self.validador = ValidadorDeDocumento([t.strip() for t in tipos.split(",")])

    def test_cpf_com_e_sem_pontuacao(self):
        for texto in ("111.444.777-35", "11144477735", " 111 444 777 35 "):
            self.assertEqual(self.validador.reconhecer(texto), Documento("CPF", "11144477735"))

    def test_cpf_invalido(self):
        for texto in ("111.444.777-36", "000.000.000-00", "1114447773", "111.444.777-3X"):
            self.assertIsNone(self.validador.reconhecer(texto), texto)

    def test_cnpj(self):
        self.assertEqual(self.validador.reconhecer("11.222.333/0001-81"),
                         Documento("CNPJ", "11222333000181"))
        self.assertIsNone(self.validador.reconhecer("11.222.333/0001-82"))

    def test_crm_em_qualquer_formato(self):
        for texto in ("CRM-GO 99001", "crm/go 99001", "99001/GO", "GO 99001", "CRM 99001-GO", "CRMGO099001"):
            self.assertEqual(self.validador.reconhecer(texto), Documento("CRM", "GO-99001"), texto)

    def test_crm_invalido(self):
        for texto in ("CRM-XX 99001", "CRM-GO", "CRM 99001", "CRM-GO 99001 SP", "CRM-GO 0"):
            self.assertIsNone(self.validador.reconhecer(texto), texto)

    def test_vazio(self):
        self.assertIsNone(self.validador.reconhecer(""))

    def test_mascara_nao_expoe_documento_completo(self):
        for documento in (Documento("CPF", "11144477735"), Documento("CNPJ", "11222333000181"),
                          Documento("CRM", "GO-99001")):
            self.assertNotIn(documento.numero.split("-")[-1], documento.mascarado())
            self.assertNotIn(documento.formatado(), documento.mascarado())


class TestComponentes(unittest.TestCase):
    def test_gerenciador_de_senhas(self):
        senhas = GerenciadorDeSenhas(iteracoes=1000)
        salt, hash_ = senhas.gerar_hash("segredo")
        self.assertTrue(senhas.verificar("segredo", salt, hash_))
        self.assertFalse(senhas.verificar("outro", salt, hash_))
        self.assertNotIn("segredo", hash_)

    def test_repositorio_json(self):
        repo = RepositorioJSON(PASTA / "dados.json")
        cliente = repo.buscar_cliente(Documento("CPF", "11144477735"))
        self.assertEqual(cliente.nome, "Maria Exemplo da Silva")
        self.assertTrue(cliente.possui_processo("0001001-11.2026.8.09.9999"))
        self.assertFalse(cliente.possui_processo("0001002-22.2026.8.09.9999"))
        self.assertIsNone(repo.buscar_cliente(Documento("CPF", "52998224725")))

    def test_repositorio_documentos_do_mesmo_cliente(self):
        repo = RepositorioJSON(PASTA / "dados.json")
        self.assertIs(repo.buscar_cliente(Documento("CPF", "44477711107")),
                      repo.buscar_cliente(Documento("CRM", "GO-99001")))

    def test_repositorio_arquivo_invalido(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "dados.json"
            caminho.write_text("{ invalido", encoding="utf-8")
            with self.assertRaises(ValueError):
                RepositorioJSON(caminho)


if __name__ == "__main__":
    unittest.main()
