"""
=============================================================================
ARQUIVO: treinamento.py
OBJETIVO: Ler os arquivos train_*.jsonl e transformá-los em contexto para a IA:
          - train_emoticons.jsonl vira um dicionário "gíria -> emoticon" no prompt;
          - train_<agente>.jsonl vira exemplos de conversa (few-shot) do agente.
          Os arquivos são relidos sempre que forem salvos de novo.
=============================================================================
"""
import json
import os
import re
from functools import lru_cache

from recursos import ATALHOS, APELIDOS, EMOJIS

DIR_PROJETO = os.path.dirname(os.path.abspath(__file__))
ARQUIVO_EMOTICONS = "train_emoticons.jsonl"

# Quantos exemplos do agente acompanham cada conversa (cada um gasta contexto do modelo)
MAX_EXEMPLOS = 6

# Para "(b)", "(pi)"... a IA escreve o emoji, porque na fala dela o atalho entre
# parênteses não é desenhado (seria confundido com itens de lista, ver recursos.py)
EMOJI_DO_ATALHO = {}
for _emoji, _atalho in EMOJIS.items():
    EMOJI_DO_ATALHO.setdefault(_atalho, _emoji)

def _caminho(nome):
    return os.path.join(DIR_PROJETO, nome)

def _mtime(caminho):
    try:
        return os.path.getmtime(caminho)
    except OSError:
        return None

def carregar_jsonl(caminho):
    """Devolve a lista de conversas do arquivo, ignorando linhas vazias e comentários //."""
    exemplos = []
    if not os.path.exists(caminho):
        return exemplos
    with open(caminho, encoding="utf-8") as arquivo:
        for numero, linha in enumerate(arquivo, 1):
            linha = linha.strip()
            if not linha or linha.startswith("//"):
                continue
            try:
                mensagens = json.loads(linha)["messages"]
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                print(f"{os.path.basename(caminho)}:{numero} ignorada ({e})")
                continue
            exemplos.append(mensagens)
    return exemplos

def _texto_do_assistente(conteudo):
    """Se a resposta de treino for um JSON com 'mensagem_chat', usa só a fala do chat."""
    try:
        dados = json.loads(conteudo)
    except (json.JSONDecodeError, TypeError):
        return conteudo
    if isinstance(dados, dict) and isinstance(dados.get("mensagem_chat"), str):
        return dados["mensagem_chat"]
    return conteudo

@lru_cache(maxsize=None)
def _glossario(caminho, _mtime):
    grupos = {}
    for mensagens in carregar_jsonl(caminho):
        usuario = next((m["content"] for m in mensagens if m.get("role") == "user"), None)
        atalho = next((m["content"].strip().lower() for m in mensagens if m.get("role") == "assistant"), None)
        if not usuario or atalho not in ATALHOS:
            continue
        if re.fullmatch(r"\(.+\)", atalho):
            atalho = EMOJI_DO_ATALHO.get(atalho)
            if not atalho:
                continue  # Sem emoji equivalente, a IA não teria como desenhá-lo
        grupos.setdefault(atalho, []).append(usuario.strip())
    return "\n".join(f"{atalho}  {', '.join(palavras)}" for atalho, palavras in grupos.items())

def glossario_emoticons():
    """Texto com cada emoticon e as expressões que combinam com ele."""
    caminho = _caminho(ARQUIVO_EMOTICONS)
    return _glossario(caminho, _mtime(caminho))

# Carinhas que qualquer modelo já entende; as outras recebem uma explicação
CARINHAS_CONHECIDAS = {":)", ":d", ";)", ":o", ":p", ":(", ":'(", ":@", ":s", ":$", ":|"}

@lru_cache(maxsize=None)
def _significados(caminho, _mtime):
    """Primeira expressão de cada atalho nos pares "palavra -> atalho" do treino."""
    significados = {}
    for mensagens in carregar_jsonl(caminho):
        usuario = next((m["content"] for m in mensagens if m.get("role") == "user"), None)
        atalho = next((m["content"].strip().lower() for m in mensagens if m.get("role") == "assistant"), None)
        if usuario and atalho in ATALHOS:
            significados.setdefault(atalho, usuario.strip())
    return significados

def explicar_emoticons(texto):
    """
    Troca os atalhos que o usuário mandou por algo que o modelo entenda:
    "(um)" vira "☂️", "(ci)" vira "[emoticon: cigarro]" e "^o)" ganha a explicação ao lado.
    """
    caminho = _caminho(ARQUIVO_EMOTICONS)
    significados = _significados(caminho, _mtime(caminho))
    pedacos = []
    for token in re.split(r"(\s+)", texto):
        nucleo = token.rstrip(".,!?")
        atalho = APELIDOS.get(nucleo.lower(), nucleo.lower())
        if atalho not in ATALHOS or atalho in CARINHAS_CONHECIDAS:
            pedacos.append(token)
            continue
        resto = token[len(nucleo):]
        significado = significados.get(atalho)
        if re.fullmatch(r"\(.+\)", atalho) and atalho in EMOJI_DO_ATALHO:
            pedacos.append(EMOJI_DO_ATALHO[atalho] + resto)
        elif significado:
            pedacos.append(f"{nucleo} [emoticon: {significado}]{resto}")
        else:
            pedacos.append(token)
    return "".join(pedacos)

# Palavras comuns demais para dizer se um exemplo tem a ver com a pergunta
PALAVRAS_VAZIAS = set("""
que pra para com não nao meu minha meus minhas uma uns umas por como isso esse essa este esta
tem vou vai dos das mas mais mesmo você voce ele ela eles elas aqui ali quando qual quais tá ta
sem sobre até ate foi ser está esta estou tô fazer faz fiz muito pouco porque por que onde
""".split())

def _palavras(texto):
    return {p for p in re.findall(r"\w+", texto.lower()) if len(p) >= 3 and p not in PALAVRAS_VAZIAS}

@lru_cache(maxsize=None)
def _conversas(caminho, _mtime):
    """Cada conversa do arquivo como uma tupla de pares (pergunta, resposta)."""
    conversas = []
    for mensagens in carregar_jsonl(caminho):
        pares = []
        pergunta = None
        for m in mensagens:
            if m.get("role") == "user":
                pergunta = m.get("content")
            elif m.get("role") == "assistant" and pergunta:
                pares.append((pergunta, _texto_do_assistente(m.get("content"))))
                pergunta = None
        if pares:
            conversas.append(tuple(pares))
    return tuple(conversas)

def exemplos_agente(agente, consulta=None):
    """
    Até MAX_EXEMPLOS conversas de exemplo do agente, cada uma como lista de (pergunta, resposta).
    As que mais têm a ver com a consulta entram por último, mais perto da conversa real;
    o resto das vagas fica com as primeiras do arquivo.
    """
    if not agente.treino:
        return []
    caminho = _caminho(agente.treino)
    conversas = _conversas(caminho, _mtime(caminho))
    relevantes = []
    if consulta:
        alvo = _palavras(consulta)
        notas = {c: len(alvo & _palavras(" ".join(p for p, _ in c))) for c in conversas}
        relevantes = sorted((c for c in conversas if notas[c]), key=notas.get, reverse=True)[:MAX_EXEMPLOS // 2]
    resto = [c for c in conversas if c not in relevantes][:MAX_EXEMPLOS - len(relevantes)]
    return [list(c) for c in resto + relevantes[::-1]]
