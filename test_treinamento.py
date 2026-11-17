"""
=============================================================================
ARQUIVO: test_treinamento.py
OBJETIVO: Conferir os arquivos train_*.jsonl e as funções que os transformam
          em contexto para a IA. Rode com:  python -m unittest -v
=============================================================================
"""
import json
import unittest
from pathlib import Path

from ia import separar_nudge
from recursos import ATALHOS
from treinamento import (ARQUIVO_EMOTICONS, carregar_jsonl, explicar_emoticons,
                         girias_da_mensagem, glossario_emoticons)

PASTA = Path(__file__).resolve().parent
ARQUIVOS = sorted(PASTA.glob("train_*.jsonl"))


class TestArquivosDeTreino(unittest.TestCase):
    def test_toda_linha_e_json_valido(self):
        for arquivo in ARQUIVOS:
            for numero, linha in enumerate(arquivo.read_text(encoding="utf-8").splitlines(), 1):
                linha = linha.strip()
                if not linha or linha.startswith("//"):
                    continue
                with self.subTest(arquivo=arquivo.name, linha=numero):
                    mensagens = json.loads(linha)["messages"]
                    papeis = [m["role"] for m in mensagens]
                    self.assertEqual(papeis[0], "system")
                    # Depois do system, sempre usuário e assistente se alternando
                    self.assertEqual(papeis[1:], ["user", "assistant"] * ((len(papeis) - 1) // 2))
                    self.assertTrue(all(m["content"].strip() for m in mensagens))

    def test_perguntas_nao_se_repetem(self):
        for arquivo in ARQUIVOS:
            vistas = set()
            for mensagens in carregar_jsonl(arquivo):
                chave = tuple(m["content"].strip().lower() for m in mensagens if m["role"] == "user")
                with self.subTest(arquivo=arquivo.name, pergunta=chave[0]):
                    self.assertNotIn(chave, vistas)
                vistas.add(chave)

    def test_pares_de_emoticons_usam_atalhos_validos(self):
        sistema_par = "Traduza o sentimento ou ação para o atalho do MSN Messenger."
        for mensagens in carregar_jsonl(PASTA / ARQUIVO_EMOTICONS):
            if mensagens[0]["content"] != sistema_par:
                continue
            with self.subTest(expressao=mensagens[1]["content"]):
                self.assertIn(mensagens[2]["content"].strip().lower(), ATALHOS)

    def test_respostas_do_zeca_sao_json_com_mensagem_chat(self):
        for mensagens in carregar_jsonl(PASTA / "train_zeca.jsonl"):
            for m in mensagens:
                if m["role"] == "assistant":
                    with self.subTest(pergunta=mensagens[1]["content"][:40]):
                        self.assertIsInstance(json.loads(m["content"])["mensagem_chat"], str)


class TestContexto(unittest.TestCase):
    def test_glossario_nao_cresce_com_o_arquivo(self):
        # Vai em todo prompt: precisa continuar pequeno mesmo com milhares de pares
        self.assertLess(len(glossario_emoticons()), 5000)

    def test_girias_da_mensagem(self):
        self.assertIn("oxe → :o", girias_da_mensagem("oxe, que história é essa?"))
        self.assertIn("trem bão", girias_da_mensagem("esse pão de queijo é trem bão"))
        self.assertEqual(girias_da_mensagem("qual a derivada de x^2?"), "")
        # Só palavra inteira: "nó" não pode casar dentro de "nós"
        self.assertNotIn("nó →", girias_da_mensagem("nós vamos sair"))

    def test_explicar_emoticons(self):
        self.assertEqual(explicar_emoticons("cadê o (um)?"), "cadê o ☂️?")
        self.assertEqual(explicar_emoticons("oi :)"), "oi :)")

    def test_separar_nudge(self):
        self.assertEqual(separar_nudge("**[NUDGE]** Ei! :o"), ("Ei! :o", True))
        self.assertEqual(separar_nudge("Oi :)"), ("Oi :)", False))


if __name__ == "__main__":
    unittest.main()
