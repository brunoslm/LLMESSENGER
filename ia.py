"""
=============================================================================
ARQUIVO: ia.py
OBJETIVO: Conectar ao Ollama e rodar a IA em segundo plano (Multithreading).
=============================================================================
"""
import re
from PyQt6.QtCore import QThread, pyqtSignal
import ollama
from treinamento import glossario_emoticons, exemplos_agente, explicar_emoticons

# Quantas mensagens anteriores acompanham cada pergunta
LIMITE_HISTORICO = 20

SYSTEM_PROMPT_BASE = """
Você está conversando em um MSN Messenger moderno. Responda em português, de forma natural,
a menos que o usuário escreva em outro idioma. Mantenha sempre a sua personalidade.

EMOTICONS: use pelo menos um em toda resposta, sem exagerar (de 1 a 3), combinando com o tom
da conversa. Eles aparecem como os emoticons clássicos do MSN. Escreva os atalhos separados
por espaços: :) feliz | :d rindo | ;) piscando | :o surpreso | :p mostrando a língua
| :@ com raiva | :s confuso | :( triste | :'( chorando | :$ envergonhado | 8-) revirando os olhos.
Também pode usar estes emoji: ❤️ 👍 👎 ⭐ 💡 🍕 ☕ 🍽️ 🎂 🎁 💻 📷 📞 🎵 🌈 😴

FORMATO: o chat só entende **negrito**, `código` e blocos ```. Não use títulos com #.
"""

PROMPT_NUDGE = """
CHAMAR ATENÇÃO: a marcação [NUDGE] sacode a janela do usuário, como o "chamar atenção" do MSN.
Regra: NÃO a use em respostas normais; perguntas, pedidos de ajuda e conversa comum nunca levam
[NUDGE]. Comece a resposta com [NUDGE] somente nestes casos:
1. O usuário pediu para você chamar a atenção dele ou sacudir a janela. Aí é obrigatório.
Exemplo de resposta a "me chama atenção!": [NUDGE] Ei! Acorda aí! :d
2. Há um perigo que ele precisa ver agora, como comida insegura ou um comando que apaga dados.
3. O usuário sacudiu a sua janela e você quer devolver a brincadeira.
Nunca explique nem mencione essa marcação.
"""

# Aceita variações comuns do modelo, como **[NUDGE]** e [nudge]
PADRAO_NUDGE = re.compile(r"[ \t]*\*{0,2}\[\s*nudge\s*\]\*{0,2}[ \t]*\n?", re.IGNORECASE)
# Marcação ainda chegando pelo streaming: "[", "[NU", "**[NUDG"...
PADRAO_NUDGE_INCOMPLETO = re.compile(r"\*{0,2}\[(?:n(?:u(?:d(?:g(?:e)?)?)?)?)?$", re.IGNORECASE)

RESPOSTA_SO_NUDGE = "Ei, olha aqui! :o"

def separar_nudge(texto):
    """Devolve o texto sem a marcação [NUDGE] e se ela estava presente."""
    limpo, quantidade = PADRAO_NUDGE.subn("", texto)
    return limpo.strip(), quantidade > 0

class WorkerIA(QThread):
    sinal_parcial = pyqtSignal(str)
    sinal_resposta = pyqtSignal(str, bool)
    sinal_erro = pyqtSignal(str)

    def __init__(self, modelo, historico, rag_instance, agente, consulta):
        super().__init__()
        self.modelo = modelo
        # O modelo não conhece os atalhos do MSN, então as mensagens do usuário vão traduzidas
        self.historico = [
            {**m, "content": explicar_emoticons(m["content"])} if m["role"] == "user" else m
            for m in historico[-LIMITE_HISTORICO:]
        ]
        self.rag = rag_instance # Usa a instância compartilhada
        self.agente = agente
        self.consulta = consulta

    def _montar_prompt(self):
        prompt = f"{self.agente.personalidade}\n{SYSTEM_PROMPT_BASE}"
        glossario = glossario_emoticons()
        if glossario:
            prompt += (
                "\nDICIONÁRIO DE EMOTICONS: escolha o emoticon pelo sentimento ou assunto, "
                "inclusive pelas gírias brasileiras de cada linha:\n" + glossario + "\n"
            )
        exemplos = exemplos_agente(self.agente, self.consulta)
        if exemplos:
            # Sem o [NUDGE]: nos exemplos ele faria o modelo sacudir a janela à toa
            dialogos = "\n\n".join(
                "\n".join(f"Usuário: {pergunta}\nVocê: {separar_nudge(resposta)[0]}" for pergunta, resposta in conversa)
                for conversa in exemplos
            )
            prompt += (
                "\nEXEMPLOS DO SEU JEITO DE RESPONDER (são só referência de estilo e não fazem "
                "parte desta conversa; não copie frases deles e varie o jeito de começar):\n" + dialogos + "\n"
            )
        if self.agente.pode_nudge:
            prompt += PROMPT_NUDGE
        # Sem consulta (ex.: reação ao "chamar atenção") não há o que buscar nos PDFs
        contexto = self.rag.buscar_contexto(self.consulta) if self.consulta else ""
        if not contexto:
            return prompt
        return (
            f"{prompt}\n\nTRECHOS DOS ARQUIVOS DO USUÁRIO:\n{contexto}\n\n"
            "Se a pergunta for sobre esses arquivos, responda com base neles e diga quando "
            "a resposta não estiver nos trechos. Se for outro assunto, ignore os trechos "
            "sem mencioná-los e converse normalmente."
        )

    def run(self):
        try:
            mensagens = [{'role': 'system', 'content': self._montar_prompt()}] + self.historico
            opcoes = {} if self.agente.temperatura is None else {"temperature": self.agente.temperatura}
            resposta = ""
            for parte in ollama.chat(model=self.modelo, messages=mensagens, stream=True, options=opcoes):
                if self.isInterruptionRequested():
                    break
                resposta += parte['message']['content']
                self.sinal_parcial.emit(separar_nudge(PADRAO_NUDGE_INCOMPLETO.sub("", resposta))[0])
            texto, nudge = separar_nudge(resposta)
            if nudge and not texto:
                texto = RESPOSTA_SO_NUDGE
            self.sinal_resposta.emit(texto, nudge and self.agente.pode_nudge)
        except Exception as e:
            self.sinal_erro.emit(str(e))

class WorkerModelos(QThread):
    """Consulta o Ollama para saber quais modelos estão disponíveis."""
    sinal_modelos = pyqtSignal(list)
    sinal_offline = pyqtSignal()

    def run(self):
        try:
            resposta = ollama.Client(timeout=5).list()
            nomes = [m.model for m in resposta.models if 'embed' not in m.model]
            self.sinal_modelos.emit(nomes)
        except Exception:
            self.sinal_offline.emit()
