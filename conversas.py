"""
=============================================================================
ARQUIVO: conversas.py
OBJETIVO: Salvar as conversas de cada agente e as preferências em um banco
          SQLite local (conversas.db, na pasta do projeto).
=============================================================================
"""
import os
import sqlite3
import time

DIR_PROJETO = os.path.dirname(os.path.abspath(__file__))

class BancoConversas:
    def __init__(self, caminho=os.path.join(DIR_PROJETO, "conversas.db")):
        self.conexao = sqlite3.connect(caminho)
        self.conexao.row_factory = sqlite3.Row
        self.conexao.execute("PRAGMA foreign_keys = ON")
        with self.conexao:
            self.conexao.executescript("""
                CREATE TABLE IF NOT EXISTS conversas (
                    id INTEGER PRIMARY KEY,
                    agente TEXT NOT NULL,
                    titulo TEXT NOT NULL,
                    atualizada REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS mensagens (
                    id INTEGER PRIMARY KEY,
                    conversa INTEGER NOT NULL REFERENCES conversas(id) ON DELETE CASCADE,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    oculta INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS preferencias (
                    chave TEXT PRIMARY KEY,
                    valor TEXT NOT NULL
                );
            """)

    def listar(self, agente):
        """Conversas do agente, da mais recente para a mais antiga."""
        return self.conexao.execute(
            "SELECT id, titulo FROM conversas WHERE agente = ? ORDER BY atualizada DESC, id DESC", (agente,)
        ).fetchall()

    def mensagens(self, conversa):
        linhas = self.conexao.execute(
            "SELECT role, content, oculta FROM mensagens WHERE conversa = ? ORDER BY id", (conversa,)
        ).fetchall()
        return [{"role": l["role"], "content": l["content"], "oculta": bool(l["oculta"])} for l in linhas]

    def criar(self, agente, titulo):
        with self.conexao:
            return self.conexao.execute(
                "INSERT INTO conversas (agente, titulo, atualizada) VALUES (?, ?, ?)", (agente, titulo, time.time())
            ).lastrowid

    def adicionar_mensagem(self, conversa, mensagem):
        with self.conexao:
            self.conexao.execute(
                "INSERT INTO mensagens (conversa, role, content, oculta) VALUES (?, ?, ?, ?)",
                (conversa, mensagem["role"], mensagem["content"], int(mensagem.get("oculta", False))),
            )
            self.conexao.execute("UPDATE conversas SET atualizada = ? WHERE id = ?", (time.time(), conversa))

    def renomear(self, conversa, titulo):
        with self.conexao:
            self.conexao.execute("UPDATE conversas SET titulo = ? WHERE id = ?", (titulo, conversa))

    def apagar(self, conversa):
        with self.conexao:
            self.conexao.execute("DELETE FROM conversas WHERE id = ?", (conversa,))

    def obter_preferencia(self, chave, padrao=None):
        linha = self.conexao.execute("SELECT valor FROM preferencias WHERE chave = ?", (chave,)).fetchone()
        return linha["valor"] if linha else padrao

    def definir_preferencia(self, chave, valor):
        with self.conexao:
            self.conexao.execute("INSERT OR REPLACE INTO preferencias (chave, valor) VALUES (?, ?)", (chave, valor))

    def fechar(self):
        self.conexao.close()
