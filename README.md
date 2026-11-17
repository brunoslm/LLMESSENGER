# LLMESSENGER

Um MSN Messenger moderno em que os contatos são IAs locais, rodando no seu computador com o [Ollama](https://ollama.com). Tem emoticons clássicos, "chamar atenção" (nudge), molduras de status e conversas salvas. Os agentes também podem responder com base nos seus PDFs (RAG).

## Contatos

| Agente | Especialidade | Modelo padrão |
| --- | --- | --- |
| Chef Zeca | Culinária (receitas, substituições, segurança alimentar) | `llama3.1` |
| Lia | Acolhimento com base em psicologia (não substitui um profissional) | `llama3.1` |
| Byte | Programação | `qwen2.5-coder:7b` |
| Prof. Téo | Matemática, passo a passo | `llama3.1` |

O modelo de cada agente pode ser trocado na caixinha no topo do chat. A escolha fica salva.

## Como rodar

1. Instale o [Ollama](https://ollama.com/download) e baixe os modelos:
   ```bash
   ollama pull llama3.1
   ollama pull qwen2.5-coder:7b
   ```
2. Instale as dependências do Python (de preferência num ambiente virtual):
   ```bash
   python -m venv .venv
   source .venv/bin/activate      # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. Abra o app:
   ```bash
   python main.py
   ```

Na primeira vez que você sincronizar PDFs, o modelo de embeddings (`paraphrase-multilingual-MiniLM-L12-v2`) é baixado. Pode demorar um pouco.

## Seus documentos (RAG)

Clique em **Documentos > Adicionar PDFs...**. Os arquivos são copiados para `meus_pdfs/`, e o banco vetorial fica em `banco_chroma/`. Se você colocar PDFs direto na pasta, use **Documentos > Sincronizar pasta**. Os trechos relevantes vão junto com a pergunta para qualquer agente. Tudo fica só na sua máquina.

## Estrutura

| Arquivo | O que faz |
| --- | --- |
| `main.py` | Interface PyQt6: contatos, conversas, emoticons, nudge |
| `agentes.py` | Personalidade, modelo e temperatura de cada agente |
| `ia.py` | Monta o prompt e conversa com o Ollama em segundo plano |
| `treinamento.py` | Transforma os `train_*.jsonl` em contexto para a IA |
| `documentos.py` | Leitura dos PDFs e busca no banco vetorial |
| `conversas.py` | Histórico e preferências em SQLite (`conversas.db`) |
| `recursos.py` | Sprites, emoticons e conversão do texto em HTML |
| `test_treinamento.py` | Testes dos arquivos de treino e do `treinamento.py` |
| `assets/` | Imagens: avatares, emoticons, moldura e botões da janela |

## Os arquivos de treino (`train_*.jsonl`)

Cada linha é um exemplo no formato de chat (`{"messages": [...]}`), o mesmo usado em fine-tuning. Linhas começando com `//` são comentários. O app relê os arquivos sozinho quando eles mudam.

- **`train_emoticons.jsonl`**: pares "expressão → emoticon", com gírias regionais do Brasil inteiro (oxe, uai, bah, égua, trem bão, da hora...), e conversas de exemplo. As primeiras expressões de cada emoticon vão sempre no prompt. As demais só entram quando o usuário usa aquela gíria, então o arquivo pode crescer sem deixar o prompt maior.
- **`train_zeca.jsonl`, `train_lia.jsonl`, `train_byte.jsonl`, `train_teo.jsonl`**: conversas de exemplo de cada agente. A cada pergunta, entram no prompt até 6 exemplos: até 3 mais parecidos com ela e, completando as vagas, os primeiros do arquivo.

Depois de editar, rode os testes para conferir se nada quebrou:

```bash
python -m unittest -v
```

## Desempenho

O prompt pede 16384 tokens de contexto ao Ollama (`TAMANHO_CONTEXTO` em `ia.py`). Sem GPU, a primeira resposta de cada conversa demora mais, porque o modelo precisa ler a personalidade, o dicionário de emoticons e os exemplos. As seguintes aproveitam o cache do Ollama.
