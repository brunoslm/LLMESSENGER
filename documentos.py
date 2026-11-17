"""
=============================================================================
ARQUIVO: documentos.py
OBJETIVO: Processar PDFs, criar banco de dados vetorial e buscar contexto (RAG).
=============================================================================
"""
import os
import threading

DIR_PROJETO = os.path.dirname(os.path.abspath(__file__))

# Abaixo desta relevância (0 a 1) o trecho é considerado sem relação com a pergunta
RELEVANCIA_MINIMA = 0.15

class GerenciadorRAG:
    def __init__(self, diretorio_pdfs=os.path.join(DIR_PROJETO, "meus_pdfs")):
        """
        Inicializa o sistema RAG apontando para a pasta com seus PDFs.
        As bibliotecas pesadas só são carregadas quando forem realmente usadas.
        """
        self.diretorio_pdfs = diretorio_pdfs
        os.makedirs(self.diretorio_pdfs, exist_ok=True)

        self.caminho_banco = os.path.join(DIR_PROJETO, "banco_chroma")
        self.embeddings = None
        self.banco_vetorial = None
        self._trava = threading.Lock()

    def _obter_embeddings(self):
        # Modelo de embeddings leve, open-source e muito bom em português
        if self.embeddings is None:
            from langchain_community.embeddings import HuggingFaceEmbeddings
            # Vetores normalizados são necessários para a relevância ficar entre 0 e 1
            self.embeddings = HuggingFaceEmbeddings(
                model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
                encode_kwargs={"normalize_embeddings": True},
            )
        return self.embeddings

    def processar_pdfs(self):
        """Lê todos os PDFs da pasta e recria o banco. Retorna quantos pedaços foram salvos."""
        from langchain_community.document_loaders import PyPDFDirectoryLoader
        from langchain_community.vectorstores import Chroma
        from langchain_text_splitters import RecursiveCharacterTextSplitter

        with self._trava:
            print("Lendo PDFs...")
            documentos = PyPDFDirectoryLoader(self.diretorio_pdfs).load()
            if not documentos:
                print(f"Nenhum PDF encontrado na pasta '{self.diretorio_pdfs}'.")
                return 0

            print(f"Dividindo {len(documentos)} páginas em pedaços...")
            # Divide o texto em blocos de 1000 caracteres, com uma sobreposição de 200
            # Isso garante que um parágrafo importante não seja cortado no meio
            divisor = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
            pedacos_texto = [p for p in divisor.split_documents(documentos) if p.page_content.strip()]
            if not pedacos_texto:
                print("Os PDFs não têm texto legível.")
                return 0

            print("Criando banco de dados vetorial. Isso pode demorar na primeira vez...")
            # Apaga a coleção anterior para não duplicar trechos a cada sincronização
            if self._banco_existe():
                Chroma(persist_directory=self.caminho_banco, embedding_function=self._obter_embeddings()).delete_collection()
            self.banco_vetorial = Chroma.from_documents(
                documents=pedacos_texto,
                embedding=self._obter_embeddings(),
                persist_directory=self.caminho_banco,
            )
            print("Banco de dados pronto e salvo!")
            return len(pedacos_texto)

    def _banco_existe(self):
        return os.path.exists(os.path.join(self.caminho_banco, "chroma.sqlite3"))

    def carregar_banco(self):
        """Carrega o banco de dados se ele já existir."""
        if not self._banco_existe():
            return False
        from langchain_community.vectorstores import Chroma
        self.banco_vetorial = Chroma(persist_directory=self.caminho_banco, embedding_function=self._obter_embeddings())
        return True

    def buscar_contexto(self, pergunta, k=3):
        """
        Busca os 3 pedaços de texto mais parecidos com a pergunta, descartando
        os que não têm relação com ela. Sem nada relevante, retorna vazio.
        """
        with self._trava:
            if not self.banco_vetorial and not self.carregar_banco():
                return ""
            resultados = self.banco_vetorial.similarity_search_with_relevance_scores(pergunta, k=k)

        textos = [doc.page_content for doc, nota in resultados if nota >= RELEVANCIA_MINIMA]
        return "\n\n---\n\n".join(textos)
