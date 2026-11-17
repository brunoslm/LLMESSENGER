"""
=============================================================================
ARQUIVO: main.py
OBJETIVO: Ponto de entrada do aplicativo. Gerencia a interface PyQt6 de um
          MSN moderno: lista de contatos (agentes com personalidade), conversas
          salvas e streaming, documentos (RAG única compartilhada) e os efeitos
          clássicos (molduras de status, Nudge e Emoticons).
=============================================================================
"""
import math
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QTextEdit, QPushButton, QLabel, QFrame,
                             QMenu, QScrollArea, QGridLayout, QWidgetAction,
                             QListWidget, QListWidgetItem, QFileDialog, QAbstractButton,
                             QComboBox, QInputDialog, QMessageBox)
from PyQt6.QtCore import Qt, QThread, QTimer, QPoint, QSize, pyqtSignal
from PyQt6.QtGui import QPainter, QTextDocument

# Importando os módulos customizados
from recursos import GerenciadorRecursos
from ia import WorkerIA, WorkerModelos
from documentos import GerenciadorRAG
from agentes import AGENTES
from conversas import BancoConversas

MODELO_PADRAO = "llama3.1:latest"
TITULO_PADRAO = "Nova conversa"
# Intervalo mínimo entre os nudges da IA, para ela não virar um incômodo
INTERVALO_NUDGE_IA = 60
FONTE = "'Segoe UI', 'Noto Sans', 'Cantarell', sans-serif"

ESTILO = f"""
    * {{ font-family: {FONTE}; color: #17324D; }}
    QMainWindow, #raiz {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #CFE6FB, stop:0.5 #EAF4FD, stop:1 #F8FBFF);
    }}
    #sidebar, #painelChat {{ background-color: rgba(255, 255, 255, 170); border: 1px solid #FFFFFF; border-radius: 16px; }}
    #logo {{ font-size: 20px; font-weight: 700; color: #1F6FD6; }}
    #nomeGrande {{ font-size: 16px; font-weight: 600; }}
    #secao {{ font-size: 11px; font-weight: 600; color: #6B87A3; }}
    #fraco {{ font-size: 12px; color: #5F7A95; }}
    #nomeRemetente {{ font-size: 11px; color: #6B87A3; }}
    QListWidget {{ background: transparent; border: none; outline: none; }}
    QListWidget::item {{ border-radius: 10px; }}
    QListWidget::item:hover {{ background-color: rgba(47, 125, 225, 25); }}
    QListWidget::item:selected {{ background-color: rgba(47, 125, 225, 50); }}
    QScrollArea, #areaMensagens {{ background: transparent; border: none; }}
    QScrollBar:vertical {{ background: transparent; width: 8px; }}
    QScrollBar::handle:vertical {{ background: #B9CFE5; border-radius: 4px; min-height: 24px; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
    #bolhaUsuario {{ background-color: #D3E8FF; border-radius: 14px; }}
    #bolhaIA {{ background-color: #FFFFFF; border: 1px solid #DCE7F2; border-radius: 14px; }}
    #bolhaSistema {{ background-color: rgba(23, 50, 77, 18); border-radius: 10px; }}
    #entrada {{ background-color: #FFFFFF; border: 1px solid #C9DBEC; border-radius: 12px; padding: 6px; font-size: 14px; }}
    #entrada:focus {{ border: 1px solid #2F7DE1; }}
    #botaoEnviar {{ background-color: #2F7DE1; color: #FFFFFF; border: none; border-radius: 12px; font-weight: 600; font-size: 14px; }}
    #botaoEnviar:hover {{ background-color: #2569C2; }}
    #botaoEnviar:disabled {{ background-color: #A9C6E8; }}
    #botaoDocumentos {{ background-color: #FFFFFF; border: 1px solid #C9DBEC; border-radius: 10px; padding: 8px; font-weight: 600; }}
    #botaoDocumentos:hover {{ background-color: #EEF5FC; }}
    #botaoDocumentos:disabled {{ color: #9DB2C7; }}
    #listaConversas::item {{ padding: 6px 8px; }}
    #listaConversas::item:selected {{ color: #17324D; }}
    QComboBox {{ background-color: #FFFFFF; border: 1px solid #C9DBEC; border-radius: 8px; padding: 3px 8px; font-size: 12px; }}
    QMenu {{ background-color: #FFFFFF; border: 1px solid #C9DBEC; }}
    QMenu::item {{ padding: 6px 18px; }}
    QMenu::item:selected {{ background-color: #E2ECF5; }}
    QToolTip {{ background-color: #FFFFFF; border: 1px solid #C9DBEC; }}
"""

TEXTO_STATUS = {"online": "Online", "ocupado": "Digitando...", "erro": "Com problema", "offline": "Offline"}

@dataclass(eq=False)
class Conversa:
    agente: str
    id: int | None = None  # Só ganha id ao ser salva, na primeira mensagem
    titulo: str = TITULO_PADRAO
    mensagens: list = field(default_factory=list)

class WorkerIndexacao(QThread):
    """Thread separada para ler PDFs sem travar a janela principal."""
    sinal_concluido = pyqtSignal(int, str)

    def __init__(self, rag_instance):
        super().__init__()
        self.rag = rag_instance

    def run(self):
        try:
            self.sinal_concluido.emit(self.rag.processar_pdfs(), "")
        except Exception as e:
            self.sinal_concluido.emit(0, str(e))

class BotaoSprite(QAbstractButton):
    """Botão desenhado com os três estados (normal, hover, pressionado) da imagem original."""
    def __init__(self, estados):
        super().__init__()
        self.estados = estados
        self.setFixedSize(estados[0].size() if estados else QSize(36, 25))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)

    def paintEvent(self, evento):
        if not self.estados:
            return
        estado = 2 if self.isDown() else 1 if self.underMouse() else 0
        QPainter(self).drawPixmap(0, 0, self.estados[estado])

class CaixaEntrada(QTextEdit):
    """Enter envia; Shift+Enter quebra a linha."""
    sinal_enviar = pyqtSignal()

    def keyPressEvent(self, evento):
        if evento.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not evento.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            self.sinal_enviar.emit()
            return
        super().keyPressEvent(evento)

class Bolha(QWidget):
    """Uma mensagem: nome do remetente em cima e o balão com o texto."""
    def __init__(self, tipo, remetente):
        super().__init__()
        self.tipo = tipo
        self.html = ""
        linha = QVBoxLayout(self)
        linha.setContentsMargins(0, 0, 0, 0)
        linha.setSpacing(2)
        alinhamento = {
            "usuario": Qt.AlignmentFlag.AlignRight,
            "ia": Qt.AlignmentFlag.AlignLeft,
            "sistema": Qt.AlignmentFlag.AlignHCenter,
        }[tipo]

        if remetente:
            nome = QLabel(remetente)
            nome.setObjectName("nomeRemetente")
            linha.addWidget(nome, alignment=alinhamento)

        self.balao = QFrame()
        self.balao.setObjectName({"usuario": "bolhaUsuario", "ia": "bolhaIA", "sistema": "bolhaSistema"}[tipo])
        interno = QVBoxLayout(self.balao)
        interno.setContentsMargins(12, 8, 12, 8)
        self.texto = QLabel()
        self.texto.setTextFormat(Qt.TextFormat.RichText)
        self.texto.setWordWrap(True)
        self.texto.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.texto.setStyleSheet("font-size: 12px;" if tipo == "sistema" else "font-size: 14px;")
        interno.addWidget(self.texto)
        linha.addWidget(self.balao, alignment=alinhamento)

    def definir_html(self, conteudo, largura_maxima):
        self.html = conteudo
        self.texto.setText(conteudo)
        self.ajustar(largura_maxima)

    def ajustar(self, largura_maxima):
        # O QLabel sozinho escolhe uma largura ruim para texto longo; medimos e fixamos
        documento = QTextDocument()
        documento.setDefaultFont(self.texto.font())
        documento.setHtml(self.html)
        largura = min(math.ceil(documento.idealWidth()) + 2, largura_maxima - 24)
        self.texto.setFixedWidth(largura)
        self.texto.setFixedHeight(self.texto.heightForWidth(largura))

class LinhaContato(QWidget):
    """Item da lista: moldura de status, nome e situação do contato."""
    def __init__(self, recursos, contato):
        super().__init__()
        self.res = recursos
        self.contato = contato
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 8, 2)
        self.foto = QLabel()
        self.foto.setFixedSize(70, 66)
        layout.addWidget(self.foto)
        coluna = QVBoxLayout()
        coluna.setSpacing(0)
        coluna.addStretch()
        nome = QLabel(contato.nome)
        nome.setStyleSheet("font-weight: 600; background: transparent;")
        self.situacao = QLabel()
        self.situacao.setObjectName("fraco")
        coluna.addWidget(nome)
        coluna.addWidget(self.situacao)
        coluna.addStretch()
        layout.addLayout(coluna, stretch=1)
        self.atualizar()

    def atualizar(self):
        self.foto.setPixmap(self.res.obter_avatar_com_moldura(self.contato.avatar, self.contato.status, "pequena"))
        self.situacao.setText(f"{self.contato.especialidade} · {TEXTO_STATUS[self.contato.status]}")

class MSNWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MSN Messenger - IA")
        self.resize(1040, 700)
        self.setMinimumSize(860, 680)

        # Inicialização dos Gerenciadores
        self.res = GerenciadorRecursos()
        self.rag = GerenciadorRAG()

        self.banco = BancoConversas()

        self.contatos = {agente.id: agente for agente in AGENTES}
        self.ativo = AGENTES[0]
        # Conversa aberta de cada agente: começa pela mais recente
        self.conversas = {agente.id: self.abrir_mais_recente(agente) for agente in AGENTES}
        self.modelos_disponiveis = []
        self.thread_ia = None
        self.respondendo = False
        self.thread_index = None
        self.thread_modelos = None
        self.bolha_stream = None
        self.texto_stream = ""
        self.nudge_ativo = False
        self.ultimo_nudge_ia = -INTERVALO_NUDGE_IA

        self.setStyleSheet(ESTILO)
        self.construir_interface()
        self.recriar_lista_contatos()
        self.recriar_lista_conversas()
        self.mostrar_conversa()

        # Agrupa os pedaços do streaming para não redesenhar a cada token
        self.timer_stream = QTimer(self)
        self.timer_stream.setSingleShot(True)
        self.timer_stream.setInterval(50)
        self.timer_stream.timeout.connect(self.desenhar_stream)

        # Mantém o status dos contatos atualizado
        self.timer_modelos = QTimer(self)
        self.timer_modelos.timeout.connect(self.consultar_modelos)
        self.timer_modelos.start(15000)
        self.consultar_modelos()

    # --- CONSTRUÇÃO DA INTERFACE ---

    def construir_interface(self):
        """Cria os layouts e widgets da janela."""
        self.raiz = QWidget()
        self.raiz.setObjectName("raiz")
        self.setCentralWidget(self.raiz)
        principal = QHBoxLayout(self.raiz)
        principal.setContentsMargins(12, 12, 12, 12)
        principal.setSpacing(12)
        principal.addWidget(self.construir_sidebar())
        principal.addWidget(self.construir_chat(), stretch=1)
        principal.addLayout(self.construir_coluna_avatares())

    def construir_sidebar(self):
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(250)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(12, 14, 12, 12)
        layout.setSpacing(8)

        logo = QLabel("LLMESSENGER")
        logo.setObjectName("logo")
        layout.addWidget(logo)

        secao = QLabel("CONTATOS")
        secao.setObjectName("secao")
        layout.addWidget(secao)

        self.lista_contatos = QListWidget()
        self.lista_contatos.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.lista_contatos.currentItemChanged.connect(self.trocar_contato)
        self.lista_contatos.setFixedHeight(72 * len(AGENTES) + 4)
        layout.addWidget(self.lista_contatos)

        secao_conversas = QLabel("CONVERSAS")
        secao_conversas.setObjectName("secao")
        layout.addWidget(secao_conversas)

        self.btn_nova_conversa = QPushButton("+ Nova conversa")
        self.btn_nova_conversa.setObjectName("botaoDocumentos")
        self.btn_nova_conversa.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_nova_conversa.clicked.connect(self.nova_conversa)
        layout.addWidget(self.btn_nova_conversa)

        self.lista_conversas = QListWidget()
        self.lista_conversas.setObjectName("listaConversas")
        self.lista_conversas.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.lista_conversas.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.lista_conversas.currentItemChanged.connect(self.trocar_conversa)
        self.lista_conversas.customContextMenuRequested.connect(self.abrir_menu_conversa)
        layout.addWidget(self.lista_conversas, stretch=1)

        self.lbl_documentos = QLabel()
        self.lbl_documentos.setObjectName("fraco")
        self.lbl_documentos.setWordWrap(True)
        layout.addWidget(self.lbl_documentos)
        self.atualizar_lbl_documentos()

        self.btn_documentos = QPushButton("Documentos")
        self.btn_documentos.setObjectName("botaoDocumentos")
        self.btn_documentos.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_documentos.clicked.connect(self.abrir_menu_documentos)
        layout.addWidget(self.btn_documentos)
        return sidebar

    def construir_chat(self):
        painel = QFrame()
        painel.setObjectName("painelChat")
        layout = QVBoxLayout(painel)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        self.lbl_titulo = QLabel()
        self.lbl_titulo.setObjectName("nomeGrande")
        cabecalho = QHBoxLayout()
        cabecalho.addWidget(self.lbl_titulo, stretch=1)
        self.combo_modelo = QComboBox()
        self.combo_modelo.setToolTip("Modelo do Ollama usado por este agente")
        self.combo_modelo.addItem(self.modelo)
        self.combo_modelo.currentTextChanged.connect(self.trocar_modelo)
        cabecalho.addWidget(self.combo_modelo)
        layout.addLayout(cabecalho)

        self.area_mensagens = QScrollArea()
        self.area_mensagens.setWidgetResizable(True)
        self.area_mensagens.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.area_mensagens.viewport().setAutoFillBackground(False)
        self.container_mensagens = QWidget()
        self.container_mensagens.setObjectName("areaMensagens")
        self.layout_mensagens = QVBoxLayout(self.container_mensagens)
        self.layout_mensagens.setContentsMargins(4, 4, 10, 4)
        self.layout_mensagens.setSpacing(10)
        self.layout_mensagens.addStretch()
        self.area_mensagens.setWidget(self.container_mensagens)
        self.area_mensagens.verticalScrollBar().rangeChanged.connect(self.rolar_para_o_fim)
        layout.addWidget(self.area_mensagens, stretch=1)

        # Label de Status (Digitando...)
        self.lbl_status = QLabel("")
        self.lbl_status.setObjectName("fraco")
        layout.addWidget(self.lbl_status)

        barra = QHBoxLayout()
        barra.setSpacing(4)
        self.btn_smiley = BotaoSprite(self.res.obter_estados_botao("smiley"))
        self.btn_smiley.setToolTip("Emoticons")
        self.btn_smiley.clicked.connect(self.abrir_menu_emoticons)
        barra.addWidget(self.btn_smiley)
        self.btn_nudge = BotaoSprite(self.res.obter_estados_botao("nudge"))
        self.btn_nudge.setToolTip("Chamar atenção")
        self.btn_nudge.clicked.connect(self.chamar_atencao)
        barra.addWidget(self.btn_nudge)
        barra.addStretch()
        layout.addLayout(barra)

        # Área de Digitação
        linha_entrada = QHBoxLayout()
        self.chat_input = CaixaEntrada()
        self.chat_input.setObjectName("entrada")
        self.chat_input.setAcceptRichText(False)
        self.chat_input.setFixedHeight(64)
        self.chat_input.setPlaceholderText("Digite uma mensagem. Enter envia, Shift+Enter quebra a linha.")
        self.chat_input.sinal_enviar.connect(self.enviar_ou_parar)
        linha_entrada.addWidget(self.chat_input)
        self.btn_send = QPushButton("Enviar")
        self.btn_send.setObjectName("botaoEnviar")
        self.btn_send.setFixedSize(84, 64)
        self.btn_send.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_send.clicked.connect(self.enviar_ou_parar)
        linha_entrada.addWidget(self.btn_send)
        layout.addLayout(linha_entrada)
        return painel

    def construir_coluna_avatares(self):
        """Fotos grandes com as molduras do chatFrame: contato em cima, usuário embaixo."""
        coluna = QVBoxLayout()
        coluna.setContentsMargins(0, 4, 0, 4)
        self.foto_contato = QLabel()
        self.foto_contato.setFixedSize(126, 126)
        coluna.addWidget(self.foto_contato)
        coluna.addStretch()
        foto_usuario = QLabel()
        foto_usuario.setFixedSize(126, 126)
        foto_usuario.setPixmap(self.res.obter_avatar_com_moldura("user_avatar.png", "online"))
        coluna.addWidget(foto_usuario)
        return coluna

    # --- CONTATOS ---

    def consultar_modelos(self):
        if self.thread_modelos and self.thread_modelos.isRunning():
            return
        self.thread_modelos = WorkerModelos()
        self.thread_modelos.sinal_modelos.connect(self.receber_modelos)
        self.thread_modelos.sinal_offline.connect(lambda: self.receber_modelos([]))
        self.thread_modelos.start()

    def modelo_de(self, agente):
        """Modelo escolhido para o agente; se ele não estiver instalado, o primeiro que estiver."""
        candidatos = [
            self.banco.obter_preferencia(f"modelo_{agente.id}"),
            agente.modelo,
            self.banco.obter_preferencia("modelo"),  # escolha antiga, de quando valia para todos
            MODELO_PADRAO,
        ]
        candidatos = [m for m in candidatos if m]
        if not self.modelos_disponiveis:
            return candidatos[0]
        return next((m for m in candidatos if m in self.modelos_disponiveis), self.modelos_disponiveis[0])

    @property
    def modelo(self):
        return self.modelo_de(self.ativo)

    def receber_modelos(self, modelos):
        if modelos:
            self.modelos_disponiveis = modelos
        self.atualizar_combo_modelos(modelos)
        for contato in self.contatos.values():
            if contato is self.ativo and self.gerando():
                continue
            contato.status = "online" if self.modelo_de(contato) in modelos else "offline"
        self.atualizar_status_visual()

    def atualizar_combo_modelos(self, modelos):
        if not modelos:
            return
        atuais = [self.combo_modelo.itemText(i) for i in range(self.combo_modelo.count())]
        if atuais != modelos:
            self.combo_modelo.blockSignals(True)
            self.combo_modelo.clear()
            self.combo_modelo.addItems(modelos)
            self.combo_modelo.blockSignals(False)
        self.mostrar_modelo_ativo()

    def mostrar_modelo_ativo(self):
        self.combo_modelo.blockSignals(True)
        self.combo_modelo.setCurrentText(self.modelo)
        self.combo_modelo.blockSignals(False)

    def trocar_modelo(self, modelo):
        self.banco.definir_preferencia(f"modelo_{self.ativo.id}", modelo)

    def recriar_lista_contatos(self):
        self.lista_contatos.blockSignals(True)
        self.lista_contatos.clear()
        for contato in self.contatos.values():
            item = QListWidgetItem()
            item.setSizeHint(QSize(0, 72))
            item.setData(Qt.ItemDataRole.UserRole, contato.id)
            self.lista_contatos.addItem(item)
            self.lista_contatos.setItemWidget(item, LinhaContato(self.res, contato))
            if contato is self.ativo:
                self.lista_contatos.setCurrentItem(item)
        self.lista_contatos.blockSignals(False)

    def trocar_contato(self, atual, _anterior):
        if atual is None:
            return
        self.ativo = self.contatos[atual.data(Qt.ItemDataRole.UserRole)]
        self.mostrar_modelo_ativo()
        self.recriar_lista_conversas()
        self.mostrar_conversa()

    def atualizar_status_visual(self):
        for i in range(self.lista_contatos.count()):
            item = self.lista_contatos.item(i)
            self.lista_contatos.itemWidget(item).atualizar()
        self.foto_contato.setPixmap(self.res.obter_avatar_com_moldura(self.ativo.avatar, self.ativo.status))
        self.lbl_titulo.setText(f"{self.ativo.nome}  ·  {TEXTO_STATUS[self.ativo.status]}")

    def definir_status_ativo(self, status):
        self.ativo.status = status
        self.atualizar_status_visual()

    # --- CONVERSAS ---

    @property
    def conversa(self):
        return self.conversas[self.ativo.id]

    def carregar_conversa(self, agente, conversa_id, titulo):
        return Conversa(agente.id, conversa_id, titulo, self.banco.mensagens(conversa_id))

    def abrir_mais_recente(self, agente):
        salvas = self.banco.listar(agente.id)
        if not salvas:
            return Conversa(agente.id)
        return self.carregar_conversa(agente, salvas[0]["id"], salvas[0]["titulo"])

    def recriar_lista_conversas(self):
        self.lista_conversas.blockSignals(True)
        self.lista_conversas.clear()
        # A conversa nova ainda não está no banco, mas aparece na lista
        linhas = [(c["id"], c["titulo"]) for c in self.banco.listar(self.ativo.id)]
        if self.conversa.id is None:
            linhas.insert(0, (None, self.conversa.titulo))
        for conversa_id, titulo in linhas:
            item = QListWidgetItem(titulo)
            item.setToolTip(titulo)
            item.setData(Qt.ItemDataRole.UserRole, conversa_id)
            self.lista_conversas.addItem(item)
            if conversa_id == self.conversa.id:
                self.lista_conversas.setCurrentItem(item)
        self.lista_conversas.blockSignals(False)

    def trocar_conversa(self, atual, _anterior):
        if atual is None:
            return
        conversa_id = atual.data(Qt.ItemDataRole.UserRole)
        if conversa_id is None or conversa_id == self.conversa.id:
            return
        self.conversas[self.ativo.id] = self.carregar_conversa(self.ativo, conversa_id, atual.text())
        self.recriar_lista_conversas()
        self.mostrar_conversa()

    def nova_conversa(self):
        if not self.conversa.mensagens and self.conversa.id is None:
            self.chat_input.setFocus()
            return
        self.conversas[self.ativo.id] = Conversa(self.ativo.id)
        self.recriar_lista_conversas()
        self.mostrar_conversa()
        self.chat_input.setFocus()

    def abrir_menu_conversa(self, posicao):
        item = self.lista_conversas.itemAt(posicao)
        if item is None or item.data(Qt.ItemDataRole.UserRole) is None or not self.lista_conversas.isEnabled():
            return
        conversa_id = item.data(Qt.ItemDataRole.UserRole)
        menu = QMenu(self)
        menu.addAction("Renomear...", lambda: self.renomear_conversa(conversa_id, item.text()))
        menu.addAction("Apagar...", lambda: self.apagar_conversa(conversa_id, item.text()))
        menu.exec(self.lista_conversas.viewport().mapToGlobal(posicao))

    def renomear_conversa(self, conversa_id, titulo):
        novo, confirmou = QInputDialog.getText(self, "Renomear conversa", "Novo nome:", text=titulo)
        novo = novo.strip()
        if not confirmou or not novo:
            return
        self.banco.renomear(conversa_id, novo)
        if conversa_id == self.conversa.id:
            self.conversa.titulo = novo
        self.recriar_lista_conversas()

    def apagar_conversa(self, conversa_id, titulo):
        resposta = QMessageBox.question(self, "Apagar conversa", f"Apagar \"{titulo}\" para sempre?")
        if resposta != QMessageBox.StandardButton.Yes:
            return
        self.banco.apagar(conversa_id)
        if conversa_id == self.conversa.id:
            self.conversas[self.ativo.id] = self.abrir_mais_recente(self.ativo)
            self.mostrar_conversa()
        self.recriar_lista_conversas()

    def registrar(self, mensagem):
        """Guarda a mensagem na conversa ativa. Avisos soltos não criam uma conversa no banco."""
        conversa = self.conversa
        conversa.mensagens.append(mensagem)
        if conversa.id is None:
            if mensagem["role"] == "sistema":
                return
            conversa.id = self.banco.criar(conversa.agente, conversa.titulo)
            for anterior in conversa.mensagens:
                self.banco.adicionar_mensagem(conversa.id, anterior)
        else:
            self.banco.adicionar_mensagem(conversa.id, mensagem)
        # A primeira fala do usuário dá nome à conversa
        if conversa.titulo == TITULO_PADRAO and mensagem["role"] == "user" and not mensagem.get("oculta"):
            conversa.titulo = " ".join(mensagem["content"].split())[:40]
            self.banco.renomear(conversa.id, conversa.titulo)
        self.recriar_lista_conversas()

    # --- MENSAGENS ---

    def largura_bolha(self):
        return max(240, int(self.area_mensagens.viewport().width() * 0.78))

    def adicionar_bolha(self, tipo, remetente, texto):
        bolha = Bolha(tipo, remetente)
        self.layout_mensagens.addWidget(bolha)
        bolha.definir_html(self.res.formatar_mensagem(texto, so_carinhas=tipo == "ia"), self.largura_bolha())
        return bolha

    def desenhar_mensagem(self, mensagem):
        if mensagem["role"] == "user":
            if not mensagem.get("oculta"):
                self.adicionar_bolha("usuario", "Você diz:", mensagem["content"])
        elif mensagem["role"] == "assistant":
            self.adicionar_bolha("ia", f"{self.ativo.nome} diz:", mensagem["content"])
        else:
            self.adicionar_bolha("sistema", "", mensagem["content"])

    def mostrar_conversa(self):
        """Redesenha o chat com as mensagens do contato selecionado."""
        while self.layout_mensagens.count() > 1:
            widget = self.layout_mensagens.takeAt(1).widget()
            widget.setParent(None)
            widget.deleteLater()
        self.adicionar_bolha("sistema", "", f"Sua conversa com {self.ativo.nome} começa aqui!")
        if not self.conversa.mensagens:
            self.adicionar_bolha("ia", f"{self.ativo.nome} diz:", self.ativo.saudacao)
        for mensagem in self.conversa.mensagens:
            self.desenhar_mensagem(mensagem)
        self.atualizar_status_visual()

    def adicionar_sistema(self, texto):
        mensagem = {"role": "sistema", "content": texto}
        self.registrar(mensagem)
        self.desenhar_mensagem(mensagem)

    def rolar_para_o_fim(self, _minimo, maximo):
        self.area_mensagens.verticalScrollBar().setValue(maximo)

    def resizeEvent(self, evento):
        super().resizeEvent(evento)
        for i in range(1, self.layout_mensagens.count()):
            self.layout_mensagens.itemAt(i).widget().ajustar(self.largura_bolha())

    def gerando(self):
        return self.respondendo

    def enviar_ou_parar(self):
        if self.gerando():
            self.thread_ia.requestInterruption()
            self.lbl_status.setText("Parando...")
            return
        if not self.btn_send.isEnabled():
            return
        texto = self.chat_input.toPlainText().strip()
        if not texto:
            return
        self.chat_input.clear()
        mensagem = {"role": "user", "content": texto}
        self.registrar(mensagem)
        self.desenhar_mensagem(mensagem)
        self.iniciar_resposta(consulta=texto)

    def bloquear_navegacao(self, bloquear):
        for widget in (self.lista_contatos, self.lista_conversas, self.btn_nova_conversa, self.btn_documentos):
            widget.setEnabled(not bloquear)

    def iniciar_resposta(self, consulta=None):
        self.lbl_status.setText(f"{self.ativo.nome} está digitando...")
        self.btn_send.setText("Parar")
        self.bloquear_navegacao(True)
        self.combo_modelo.setEnabled(False)
        self.definir_status_ativo("ocupado")
        self.bolha_stream = None
        self.texto_stream = ""

        historico = [{"role": m["role"], "content": m["content"]} for m in self.conversa.mensagens if m["role"] != "sistema"]
        # A thread anterior já avisou que acabou, mas pode levar um instante para encerrar
        if self.thread_ia:
            self.thread_ia.wait()
        self.respondendo = True
        self.thread_ia = WorkerIA(self.modelo, historico, self.rag, self.ativo, consulta)
        self.thread_ia.sinal_parcial.connect(self.receber_parcial)
        self.thread_ia.sinal_resposta.connect(self.receber_resposta)
        self.thread_ia.sinal_erro.connect(self.receber_erro)
        self.thread_ia.start()

    def receber_parcial(self, texto):
        self.texto_stream = texto
        if not self.timer_stream.isActive():
            self.timer_stream.start()

    def desenhar_stream(self):
        if not self.texto_stream:
            return
        if self.bolha_stream is None:
            self.bolha_stream = self.adicionar_bolha("ia", f"{self.ativo.nome} diz:", self.texto_stream)
        else:
            self.bolha_stream.definir_html(self.res.formatar_mensagem(self.texto_stream, so_carinhas=True), self.largura_bolha())

    def finalizar_resposta(self, status):
        self.respondendo = False
        self.timer_stream.stop()
        self.lbl_status.setText("")
        self.btn_send.setText("Enviar")
        self.bloquear_navegacao(False)
        self.combo_modelo.setEnabled(True)
        self.definir_status_ativo(status)
        self.chat_input.setFocus()

    def receber_resposta(self, resposta, nudge):
        self.texto_stream = resposta
        self.desenhar_stream()
        if resposta:
            self.registrar({"role": "assistant", "content": resposta})
        else:
            # Parou antes da primeira palavra: não há resposta para guardar
            self.adicionar_sistema("Resposta interrompida.")
        self.finalizar_resposta("online")
        QApplication.beep()
        # Pisca a janela na barra de tarefas se o usuário estiver em outro programa
        QApplication.alert(self)
        if nudge:
            self.nudge_da_ia()

    def receber_erro(self, erro):
        self.desenhar_stream()
        if self.texto_stream:
            self.registrar({"role": "assistant", "content": self.texto_stream})
        self.adicionar_sistema(f"Não consegui falar com {self.ativo.nome}. Verifique se o Ollama está rodando. Detalhe: {erro}")
        self.finalizar_resposta("erro")
        # Sai do vermelho na próxima consulta, se o Ollama estiver respondendo
        self.ativo.status = "offline"

    # --- EMOTICONS E NUDGE ---

    def abrir_menu_emoticons(self):
        """Abre um menu em grade (Grid) com scroll para os 79 emoticons."""
        menu = QMenu(self)

        # Container do Grid
        container = QWidget()
        grid = QGridLayout(container)
        grid.setSpacing(2)
        grid.setContentsMargins(5, 5, 5, 5)

        colunas_max = 10 # Quantos emoticons por linha

        for i, atalho in enumerate(self.res.mapa_emoticons.keys()):
            btn_emo = QPushButton()
            btn_emo.setIcon(self.res.obter_icone_emoticon(atalho))
            btn_emo.setFixedSize(26, 26)
            btn_emo.setToolTip(atalho)
            btn_emo.setStyleSheet("""
                QPushButton { border: 1px solid transparent; background: transparent; border-radius: 4px; }
                QPushButton:hover { background-color: #E2ECF5; border: 1px solid #99B4D1; }
            """)

            # Conecta o clique: insere texto e fecha menu
            btn_emo.clicked.connect(lambda checked, a=atalho: [self.inserir_texto_input(a), menu.close()])

            grid.addWidget(btn_emo, i // colunas_max, i % colunas_max)

        # Área de Scroll
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedSize(310, 220) # Tamanho fixo da janelinha
        scroll.setWidget(container)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Adiciona o Scroll no Menu
        action = QWidgetAction(menu)
        action.setDefaultWidget(scroll)
        menu.addAction(action)

        # Abre o menu acima do botão Smiley
        pos = self.btn_smiley.mapToGlobal(self.btn_smiley.rect().topLeft())
        menu.exec(pos - QPoint(0, scroll.height() + 10))

    def inserir_texto_input(self, texto):
        self.chat_input.insertPlainText(texto + " ")
        self.chat_input.setFocus()

    def chamar_atencao(self):
        """Treme o conteúdo da janela (o Wayland não deixa o app mover a própria janela)."""
        if self.gerando() or self.nudge_ativo:
            return
        self.adicionar_sistema("Você chamou atenção!")
        QApplication.beep()
        self.tremer([(5, 5), (-10, -10), (10, 0), (0, 10), (-5, -5)] * 6)

        if self.ativo.status == "online" and self.btn_send.isEnabled():
            self.registrar({
                "role": "user", "oculta": True,
                "content": "(O usuário clicou em 'Chamar atenção' para sacudir sua janela. Reaja em uma frase curta.)",
            })
            self.iniciar_resposta()

    def nudge_da_ia(self):
        """O agente pediu atenção: treme a janela e, se ela estiver em segundo plano, notifica."""
        agora = time.monotonic()
        if self.nudge_ativo or agora - self.ultimo_nudge_ia < INTERVALO_NUDGE_IA:
            return
        self.ultimo_nudge_ia = agora
        self.adicionar_sistema(f"{self.ativo.nome} chamou sua atenção!")
        self.tremer([(5, 5), (-10, -10), (10, 0), (0, 10), (-5, -5)] * 6)
        if not self.isActiveWindow() and shutil.which("notify-send"):
            subprocess.Popen(["notify-send", "MSN", f"{self.ativo.nome} chamou sua atenção!"])

    def tremer(self, deslocamentos):
        self.nudge_ativo = True
        origem = self.raiz.pos()
        passos = iter(deslocamentos)

        def proximo():
            passo = next(passos, None)
            if passo is None:
                self.raiz.move(origem)
                self.nudge_ativo = False
                return
            self.raiz.move(origem.x() + passo[0], origem.y() + passo[1])
            QTimer.singleShot(20, proximo)

        proximo()

    # --- DOCUMENTOS (RAG) ---

    def listar_pdfs(self):
        return [a for a in os.listdir(self.rag.diretorio_pdfs) if a.lower().endswith(".pdf")]

    def atualizar_lbl_documentos(self):
        total = len(self.listar_pdfs())
        self.lbl_documentos.setText(f"{total} PDF(s) em meus_pdfs" if total else "Nenhum PDF adicionado")

    def abrir_menu_documentos(self):
        menu = QMenu(self)
        menu.addAction("Adicionar PDFs...", self.adicionar_pdfs)
        menu.addAction("Sincronizar pasta", self.iniciar_indexacao)
        menu.exec(self.btn_documentos.mapToGlobal(QPoint(0, -70)))

    def adicionar_pdfs(self):
        arquivos, _ = QFileDialog.getOpenFileNames(self, "Adicionar PDFs", "", "PDF (*.pdf)")
        if not arquivos:
            return
        for arquivo in arquivos:
            destino = os.path.join(self.rag.diretorio_pdfs, os.path.basename(arquivo))
            if os.path.abspath(arquivo) != os.path.abspath(destino):
                shutil.copy2(arquivo, destino)
        self.iniciar_indexacao()

    def iniciar_indexacao(self):
        self.btn_send.setEnabled(False)
        self.bloquear_navegacao(True)
        self.lbl_status.setText("Sincronizando PDFs...")
        self.thread_index = WorkerIndexacao(self.rag)
        self.thread_index.sinal_concluido.connect(self.finalizar_indexacao)
        self.thread_index.start()

    def finalizar_indexacao(self, pedacos, erro):
        self.btn_send.setEnabled(True)
        self.bloquear_navegacao(False)
        self.lbl_status.setText("")
        self.atualizar_lbl_documentos()
        if erro:
            self.adicionar_sistema(f"Erro ao sincronizar os PDFs: {erro}")
        elif pedacos:
            self.adicionar_sistema("PDFs sincronizados com sucesso!")
            QApplication.beep()
        else:
            self.adicionar_sistema("Nenhum texto legível foi encontrado na pasta meus_pdfs.")

    def closeEvent(self, evento):
        # Não deixa thread rodando enquanto a janela é destruída
        self.timer_modelos.stop()
        for thread in (self.thread_ia, self.thread_index, self.thread_modelos):
            if thread and thread.isRunning():
                thread.requestInterruption()
                if not thread.wait(2000):
                    thread.terminate()
                    thread.wait()
        self.banco.fechar()
        super().closeEvent(evento)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    janela = MSNWindow()
    janela.show()
    sys.exit(app.exec())
