"""
=============================================================================
ARQUIVO: recursos.py
OBJETIVO: Gerenciar e fatiar todas as imagens, botões, molduras e emoticons,
          além de converter o texto das mensagens em HTML seguro.
=============================================================================
"""
import html
import os
import re
from PyQt6.QtGui import QPixmap, QIcon, QPainter, QPainterPath
from PyQt6.QtCore import Qt, QRect, QRectF, QByteArray, QBuffer, QIODevice

# Atalhos na ordem em que aparecem na fita emoticons.png (19px cada, 79 no total)
ATALHOS = [
    ":)", ":d", ";)", ":o", ":p", "(h)", ":@", ":$", ":s", ":(",
    ":'(", ":|", "(6)", "(a)", "(l)", "(u)", "(m)", "(@)", "(&)", "(s)",
    "(*)", "(~)", "(8)", "(e)", "(f)", "(w)", "(o)", "(k)", "(g)", "(^)",
    "(p)", "(i)", "(c)", "(t)", "({)", "(})", "(b)", "(d)", "(z)", "(x)",
    "(y)", "(n)", ":[", "(nah)", "(%)", "(#)", "(r)", ":-#", "8o|", "8-|",
    "^o)", ":-*", "+o(", "(sn)", "(tu)", "(pl)", "(||)", "(pi)", "(so)", "(au)",
    "(ap)", "(um)", "(ip)", "(co)", "(mp)", "(brb)", "(st)", "(yn)", "(h5)", "(mo)",
    "(bah)", "8-)", "*-)", "(li)", "<:o)", ":^)", "(ci)", "|-)", "(xx)",
]

# Formas alternativas que também viram emoticon, mas não aparecem no menu
APELIDOS = {":-)": ":)", ":-d": ":d", ";-)": ";)", ":-o": ":o", ":-p": ":p", ":-(": ":(", ":-s": ":s", ":-|": ":|"}

# Emoji que a IA costuma escrever e têm um emoticon clássico equivalente
EMOJIS = {
    "🙂": ":)", "😊": ":)", "😀": ":d", "😃": ":d", "😄": ":d", "😁": ":d", "😂": ":d", "🤣": ":d", "😉": ";)",
    "😮": ":o", "😲": ":o", "😛": ":p", "😜": ":p", "😎": "(h)", "😠": ":@", "😡": ":@", "😳": ":$", "😕": ":s",
    "😟": ":s", "🙁": ":(", "😔": ":(", "😞": ":(", "😢": ":'(", "😭": ":'(", "😐": ":|", "😇": "(a)", "😈": "(6)",
    "❤️": "(l)", "❤": "(l)", "💔": "(u)", "🐱": "(@)", "🐶": "(&)", "🌙": "(s)", "⭐": "(*)", "🎬": "(~)", "🎵": "(8)",
    "🎶": "(8)", "✉️": "(e)", "✉": "(e)", "🌹": "(f)", "🥀": "(w)", "🕒": "(o)", "💋": "(k)", "🎁": "(g)", "🎂": "(^)",
    "📷": "(p)", "💡": "(i)", "☕": "(c)", "📞": "(t)", "🍺": "(b)", "🍹": "(d)", "👍": "(y)", "👎": "(n)", "🌈": "(r)",
    "🍽️": "(pl)", "🍽": "(pl)", "🍕": "(pi)", "⚽": "(so)", "🚗": "(au)", "✈️": "(ap)", "✈": "(ap)", "☂️": "(um)", "☂": "(um)",
    "💻": "(co)", "📱": "(mp)", "🌧️": "(st)", "🌧": "(st)", "💰": "(mo)", "⚡": "(li)", "😴": "|-)",
}
PADRAO_EMOJIS = re.compile("|".join(sorted(map(re.escape, EMOJIS), key=len, reverse=True)))

# Recortes de chatFrame.png: status -> (x, largura, deslocamento do furo em x)
MOLDURAS_GRANDES = {"offline": (10, 116, 9), "erro": (150, 116, 9), "ocupado": (289, 117, 10), "online": (428, 119, 11)}
MOLDURAS_PEQUENAS = {"offline": (660, 60, 8), "erro": (728, 60, 8), "ocupado": (796, 62, 8), "online": (864, 66, 8)}

# Tela, posição do furo e altura do recorte de cada tamanho de moldura
GEOMETRIA = {
    "grande": {"tela": (126, 126), "furo": (15, 11), "lado": 96, "altura": 126, "molduras": MOLDURAS_GRANDES},
    "pequena": {"tela": (70, 66), "furo": (8, 7), "lado": 46, "altura": 66, "molduras": MOLDURAS_PEQUENAS},
}

class GerenciadorRecursos:
    def __init__(self):
        # Caminho absoluto da pasta do projeto, para funcionar de qualquer diretório
        self.dir_path = os.path.dirname(os.path.abspath(__file__))

        self.sheet_emoticons = self._carregar("emoticons.png")
        self.sheet_buttons = self._carregar("chatWindowButtons.png")
        self.sheet_molduras = self._carregar("chatFrame.png")

        self.mapa_emoticons = {atalho: i for i, atalho in enumerate(ATALHOS)}
        self._cache_base64 = {}
        self._cache_avatares = {}
        self._cache_molduras = {}

    def _carregar(self, nome):
        return QPixmap(os.path.join(self.dir_path, "assets", nome))

    def _indice_emoticon(self, atalho):
        atalho = atalho.lower()
        return self.mapa_emoticons.get(APELIDOS.get(atalho, atalho))

    def _recortar_emoticon(self, indice):
        h = self.sheet_emoticons.height()
        return self.sheet_emoticons.copy(QRect(indice * h, 0, h, h))

    def obter_emoticon_base64(self, atalho):
        """Fatia o emoticon e converte para Base64 para o HTML."""
        indice = self._indice_emoticon(atalho)
        if indice is None or self.sheet_emoticons.isNull():
            return None
        if indice not in self._cache_base64:
            byte_array = QByteArray()
            buffer = QBuffer(byte_array)
            buffer.open(QIODevice.OpenModeFlag.WriteOnly)
            self._recortar_emoticon(indice).save(buffer, "PNG")
            self._cache_base64[indice] = byte_array.toBase64().data().decode()
        return self._cache_base64[indice]

    def obter_icone_emoticon(self, atalho):
        """Retorna o QIcon para aparecer no menu do botão Smiley."""
        indice = self._indice_emoticon(atalho)
        if indice is None or self.sheet_emoticons.isNull():
            return QIcon()
        return QIcon(self._recortar_emoticon(indice))

    def obter_estados_botao(self, tipo):
        """Fatia chatWindowButtons.png: 3 colunas (normal, hover, pressionado) e 2 linhas."""
        if self.sheet_buttons.isNull():
            return []
        bw = self.sheet_buttons.width() // 3
        bh = self.sheet_buttons.height() // 2
        linha = 0 if tipo == "smiley" else 1
        return [self.sheet_buttons.copy(QRect(coluna * bw, linha * bh, bw, bh)) for coluna in range(3)]

    def _avatar(self, nome_arquivo, lado):
        """Devolve o avatar reduzido; sem arquivo, usa a silhueta padrão de chatFrame.png."""
        chave = (nome_arquivo, lado)
        if chave not in self._cache_avatares:
            if nome_arquivo:
                original = self._carregar(nome_arquivo)
            else:
                original = self.sheet_molduras.copy(QRect(560, 0, 98, 98))
            self._cache_avatares[chave] = original.scaled(
                lado, lado,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        return self._cache_avatares[chave]

    def obter_avatar_com_moldura(self, nome_arquivo, status, tamanho="grande"):
        """Desenha o avatar por baixo da moldura de chatFrame.png da cor do status."""
        chave = (nome_arquivo, status, tamanho)
        if chave in self._cache_molduras:
            return self._cache_molduras[chave]

        g = GEOMETRIA[tamanho]
        x, largura, deslocamento = g["molduras"][status]
        furo_x, furo_y = g["furo"]
        lado = g["lado"]

        tela = QPixmap(*g["tela"])
        tela.fill(Qt.GlobalColor.transparent)
        pintor = QPainter(tela)
        pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
        pintor.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        # A foto invade 1px sob a moldura para não sobrar fresta nos cantos
        recorte = QPainterPath()
        recorte.addRoundedRect(QRectF(furo_x - 1, furo_y - 1, lado + 2, lado + 2), 5, 5)
        pintor.setClipPath(recorte)
        pintor.drawPixmap(furo_x - 1, furo_y - 1, self._avatar(nome_arquivo, lado + 2))
        pintor.setClipping(False)

        moldura = self.sheet_molduras.copy(QRect(x, 0, largura, g["altura"]))
        pintor.drawPixmap(furo_x - deslocamento, 0, moldura)
        pintor.end()

        self._cache_molduras[chave] = tela
        return tela

    def _img_emoticon(self, atalho):
        b64 = self.obter_emoticon_base64(atalho)
        return f"<img src='data:image/png;base64,{b64}' width='19' height='19'>" if b64 else None

    def _trecho_para_html(self, trecho, so_carinhas):
        """Escapa o texto comum, trocando atalhos por emoticons e aplicando **negrito** e `código`."""
        pedacos = []
        for token in re.split(r"(\s+)", trecho):
            # A pontuação colada não impede o emoticon: "legal :)." também vale
            nucleo = token.rstrip(".,!?")
            # Na fala da IA, "(a)" e "(x)" costumam ser itens de lista ou contas, não emoticons;
            # para esses desenhos ela usa emoji
            ignorar = so_carinhas and re.fullmatch(r"\(.+\)", nucleo)
            img = None if ignorar else self._img_emoticon(nucleo)
            if img:
                pedacos.append(img + html.escape(token[len(nucleo):]))
            else:
                pedacos.append(html.escape(token))
        texto = PADRAO_EMOJIS.sub(lambda m: self._img_emoticon(EMOJIS[m.group()]) or m.group(), "".join(pedacos))
        texto = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", texto)
        texto = re.sub(
            r"`([^`\n]+)`",
            r"<span style='font-family: monospace; background-color: #EAF0F7;'>\1</span>",
            texto,
        )
        return texto.replace("\n", "<br>")

    def formatar_mensagem(self, texto, so_carinhas=False):
        """Converte a mensagem em HTML; blocos ``` ainda abertos (durante o streaming) também valem."""
        partes = re.split(r"```[^\n]*\n?(.*?)(?:```|$)", texto, flags=re.DOTALL)
        saida = []
        for i, parte in enumerate(partes):
            if i % 2:
                codigo = html.escape(parte.rstrip("\n"))
                saida.append(
                    "<pre style='font-family: monospace; background-color: #EAF0F7; "
                    f"white-space: pre-wrap;'>{codigo}</pre>"
                )
            else:
                saida.append(self._trecho_para_html(parte, so_carinhas))
        return "".join(saida)
