# -*- coding: utf-8 -*-
"""Servidor do historico: a pagina que mostra o que voce ditou.

Existe porque a injecao vai sempre onde o foco esta, e o foco muda. Quando o
texto cai na caixa errada, ele nao se perdeu -- esta aqui, com o audio do lado.

Roda em thread dentro do proprio servico de ditado, para nao haver um segundo
processo carregando nada. So biblioteca padrao.
"""
import os
import io
import json
import re
import difflib
import threading
import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

RAIZ = os.path.dirname(os.path.abspath(__file__))
HISTORICO = os.path.join(RAIZ, "historico")
REGISTRO = os.path.join(HISTORICO, "registro.jsonl")
VOCABULARIO = os.path.join(RAIZ, "vocabulario.json")
PORTA = 4772

_trava = threading.Lock()


def ler_registros(limite=60):
    """Le o jsonl de tras para frente: o ditado mais recente primeiro."""
    if not os.path.exists(REGISTRO):
        return []
    saida = []
    with io.open(REGISTRO, encoding="utf-8") as f:
        for linha in f:
            linha = linha.strip()
            if not linha:
                continue
            try:
                saida.append(json.loads(linha))
            except ValueError:
                continue
    saida.reverse()
    return saida[:limite]


PONTUACAO = ".,;:!?\"'()"
MAX_PALAVRAS = 3        # termo composto vai ate aqui; alem disso e frase
RAZAO_MIN = 0.45        # o certo nao pode encolher demais em relacao ao errado
RAZAO_MAX = 2.2         # nem inchar demais


def _aceitavel(errado, certo):
    """Isto e troca de termo, ou reescrita disfarcada?

    A regra e o comprimento: um termo corrigido tem tamanho parecido com o
    errado, porque e a mesma palavra escrita de outro jeito. Reescrita muda o
    tamanho. Sem esta trava, corrigir o sentido de uma frase viraria uma regra
    de substituicao aplicada a todo texto futuro.
    """
    if not errado or not certo or errado == certo:
        return False
    if len(errado) < 2:
        return False
    return RAZAO_MIN <= len(certo) / float(len(errado)) <= RAZAO_MAX


def palavras_trocadas(antes, depois):
    """Descobre o que mudou entre o texto transcrito e o texto corrigido.

    Devolve pares (errado, certo) prontos para virar entrada de correcao.

    Trata dois casos, e o segundo existe porque o primeiro nao bastava:

      1. Troca palavra a palavra -- 'Substek' -> 'Substack'. Cada par e julgado
         sozinho.
      2. Troca de termo COMPOSTO, em que a contagem de palavras muda --
         'Whisperflow' -> 'Wispr Flow'. E o caso mais comum de nome proprio:
         o modelo junta o que e separado, ou separa o que e junto. A primeira
         versao desta funcao exigia contagem igual dos dois lados e recusava
         justamente esses (31/08/2026, na primeira correcao real de uso).
    """
    a, b = antes.split(), depois.split()
    pares = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b).get_opcodes():
        if tag != "replace":
            continue
        na, nb = i2 - i1, j2 - j1

        if na == nb:
            for k in range(na):
                e = a[i1 + k].strip(PONTUACAO)
                c = b[j1 + k].strip(PONTUACAO)
                if _aceitavel(e, c):
                    pares.append((e, c))
        elif na <= MAX_PALAVRAS and nb <= MAX_PALAVRAS:
            e = " ".join(a[i1:i2]).strip(PONTUACAO)
            c = " ".join(b[j1:j2]).strip(PONTUACAO)
            if _aceitavel(e, c):
                pares.append((e, c))
    return pares


def gravar_correcoes(pares):
    """Acrescenta pares ao vocabulario.json, sem duplicar e sem perder o resto."""
    with _trava:
        with io.open(VOCABULARIO, encoding="utf-8") as f:
            v = json.load(f)
        corr = v.setdefault("correcoes", {})
        novos = []
        for errado, certo in pares:
            if corr.get(errado) == certo:
                continue
            corr[errado] = certo
            novos.append((errado, certo))
        if novos:
            with io.open(VOCABULARIO, "w", encoding="utf-8") as f:
                json.dump(v, f, ensure_ascii=False, indent=2)
        return novos


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass                                # silencia o log de acesso do http.server

    def _responder(self, codigo, corpo, tipo="application/json; charset=utf-8"):
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(corpo)

    def do_GET(self):
        caminho = self.path.split("?")[0]
        if caminho in ("/", "/index.html"):
            try:
                with io.open(os.path.join(RAIZ, "painel.html"), "rb") as f:
                    self._responder(200, f.read(), "text/html; charset=utf-8")
            except IOError:
                self._responder(404, b"painel.html nao encontrado", "text/plain")
            return

        if caminho == "/api/historico":
            dados = json.dumps(ler_registros(), ensure_ascii=False).encode("utf-8")
            self._responder(200, dados)
            return

        if caminho.startswith("/audio/"):
            nome = os.path.basename(caminho[len("/audio/"):])
            # so serve .wav de dentro do historico -- nada de subir arvore
            if not re.match(r"^[\w\-T]+\.wav$", nome):
                self._responder(400, b"nome invalido", "text/plain")
                return
            alvo = os.path.join(HISTORICO, nome)
            if not os.path.exists(alvo):
                self._responder(404, b"audio nao encontrado", "text/plain")
                return
            with io.open(alvo, "rb") as f:
                self._responder(200, f.read(), "audio/wav")
            return

        self._responder(404, b"nao encontrado", "text/plain")

    def do_POST(self):
        if self.path.split("?")[0] != "/api/correcao":
            self._responder(404, b"nao encontrado", "text/plain")
            return
        try:
            n = int(self.headers.get("Content-Length", 0))
            corpo = json.loads(self.rfile.read(n).decode("utf-8"))
            antes = corpo.get("antes", "")
            depois = corpo.get("depois", "")
        except Exception:
            self._responder(400, json.dumps({"erro": "json invalido"}).encode("utf-8"))
            return

        pares = palavras_trocadas(antes, depois)
        if not pares:
            self._responder(200, json.dumps({
                "novos": [],
                "aviso": "nenhuma troca de palavra reconhecida -- o vocabulario aprende "
                         "troca de termo, nao reescrita de frase"
            }, ensure_ascii=False).encode("utf-8"))
            return

        novos = gravar_correcoes(pares)
        self._responder(200, json.dumps({
            "novos": [{"errado": e, "certo": c} for e, c in novos]
        }, ensure_ascii=False).encode("utf-8"))


def subir(ao_recarregar=None):
    """Sobe o servidor em thread. ao_recarregar avisa o servico que o vocabulario mudou."""
    global _avisar
    _avisar = ao_recarregar
    servidor = ThreadingHTTPServer(("127.0.0.1", PORTA), Handler)
    t = threading.Thread(target=servidor.serve_forever, daemon=True)
    t.start()
    return servidor


_avisar = None
