# -*- coding: utf-8 -*-
"""Ditado local: segure Ctrl+Win, fale, solte. O texto aparece onde o cursor esta.

Desenho, e o porque de cada peca:

  1. O modelo carrega UMA vez, no boot (8.4s medidos). Por isso isto e um servico
     que fica de pe, e nao um script que sobe a cada frase -- pagar 8.4s por
     ditado tornaria a ferramenta inutil.
  2. A gravacao acontece enquanto a tecla esta pressionada, sem limite de tempo.
  3. A transcricao roda em thread separada: o listener nunca pode travar, senao
     o proximo atalho se perde.
  4. O texto e injetado por SendInput, nao por Ctrl+V -- seu clipboard fica intacto.
  5. Tudo fica no historico com o audio original, porque injecao vai sempre onde
     o foco esta, e o foco muda.
"""
import os
import sys
import json
import time
import wave
import queue
import threading
import datetime
import traceback
import re

import numpy as np
import sounddevice as sd
from pynput import keyboard

RAIZ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, RAIZ)
import config
from injetar import digitar

HISTORICO = os.path.join(RAIZ, "historico")
os.makedirs(HISTORICO, exist_ok=True)
REGISTRO = os.path.join(HISTORICO, "registro.jsonl")

TAXA_WHISPER = 16000


def montar_atalho(nomes):
    """Converte os nomes do config em teclas do pynput, avisando o que nao existe."""
    teclas = set()
    for n in nomes:
        t = getattr(keyboard.Key, n, None)
        if t is None:
            raise SystemExit("tecla desconhecida no config.ATALHO: %r" % n)
        teclas.add(t)
    return teclas


ATALHO = montar_atalho(getattr(config, "ATALHO", ["ctrl_l", "cmd_l"]))
NOME_ATALHO = " + ".join(n.replace("_l", " esquerdo").replace("ctrl", "Ctrl")
                          .replace("cmd", "Win").replace("alt", "Alt").replace("shift", "Shift")
                         for n in getattr(config, "ATALHO", ["ctrl_l", "cmd_l"]))


ARQUIVO_LOG = os.path.join(HISTORICO, "servico.log")


def log(msg):
    """Escreve no console e em arquivo.

    O arquivo existe porque a janela do console se perde -- fica atras de outras,
    some ao ser fechada sem querer, ou nem aparece quando o servico e lancado de
    dentro de outro programa. Diagnostico que depende de achar uma janela nao e
    diagnostico.
    """
    linha = "[%s] %s" % (datetime.datetime.now().strftime("%H:%M:%S"), msg)
    print(linha, flush=True)
    try:
        with open(ARQUIVO_LOG, "a", encoding="utf-8") as f:
            f.write(linha + "\n")
    except Exception:
        pass


def carregar_vocabulario():
    """Monta as hotwords e a tabela de correcoes.

    O formato das hotwords nao e detalhe. Medido em 31/08/2026, sobre as mesmas
    amostras: 69 termos soltos deram 9/11 de acerto e zeraram a pontuacao -- o
    modelo imita o estilo do que recebe como contexto, e uma lista sem pontuacao
    ensina justamente isso. 15 termos separados por virgula, terminados em ponto,
    deram 11/11 com a melhor pontuacao. Lista curta e pontuada, sempre.
    """
    caminho = os.path.join(RAIZ, "vocabulario.json")
    with open(caminho, encoding="utf-8") as f:
        v = json.load(f)
    termos = v.get("prioritarios", [])
    hotwords = ", ".join(termos) + "." if termos else None
    return hotwords, compilar_correcoes(v.get("correcoes", {}))


def compilar_correcoes(correcoes):
    """Prepara as correcoes como UMA passada de regex.

    Aplicar em cadeia com str.replace corrompe: 'Coinect'->'Coinext' e logo
    depois 'Coinex'->'Coinext' produz 'Coinextt', porque a segunda regra casa
    dentro do resultado da primeira. Uma passada so, com fronteira de palavra e
    as chaves ordenadas da maior para a menor, elimina as duas armadilhas.
    """
    uteis = {k: v for k, v in correcoes.items() if k != v}
    if not uteis:
        return None, {}
    chaves = sorted(uteis, key=len, reverse=True)
    padrao = re.compile("|".join(r"(?<!\w)" + re.escape(k) + r"(?!\w)" for k in chaves))
    return padrao, uteis


def aplicar_correcoes(texto, compiladas):
    """Camada curativa: o que hotwords nao previne, isto conserta depois."""
    padrao, mapa = compiladas
    if padrao is None:
        return texto
    return padrao.sub(lambda m: mapa[m.group(0)], texto)


def reamostrar(audio, de_taxa, para_taxa):
    """Decimacao com media de bloco -- filtro passa-baixa suficiente para voz."""
    if de_taxa == para_taxa:
        return audio
    fator = de_taxa / float(para_taxa)
    n_saida = int(len(audio) / fator)
    if n_saida <= 0:
        return audio
    idx = (np.arange(n_saida) * fator).astype(np.int64)
    largura = max(1, int(fator))
    if largura == 1:
        return audio[idx]
    limite = len(audio) - 1
    janelas = np.stack([audio[np.minimum(idx + k, limite)] for k in range(largura)])
    return janelas.mean(axis=0)


def salvar_wav(caminho, audio, taxa):
    dados = np.clip(audio, -1.0, 1.0)
    with wave.open(caminho, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(taxa)
        w.writeframes((dados * 32767).astype(np.int16).tobytes())


class Ditado(object):
    def __init__(self):
        log("carregando %s em %s/%s..." % (config.MODELO, config.DEVICE, config.COMPUTE_TYPE))
        t0 = time.time()
        from faster_whisper import WhisperModel
        self.modelo = WhisperModel(config.MODELO, device=config.DEVICE,
                                   compute_type=config.COMPUTE_TYPE,
                                   local_files_only=True)
        log("modelo pronto em %.1fs" % (time.time() - t0))

        self.hotwords, self.correcoes = carregar_vocabulario()
        log("vocabulario: %d termos prioritarios, %d correcoes"
            % (self.hotwords.count(",") + 1, len(self.correcoes[1])))

        info = sd.query_devices(kind="input")
        self.dispositivo = None                       # None = padrao do sistema
        self.taxa_captura = int(info["default_samplerate"])
        log("microfone: %s (%d Hz)" % (info["name"], self.taxa_captura))

        self.vocab_mtime = self._mtime_vocab()

        try:
            import servidor
            servidor.subir()
            log("historico em http://127.0.0.1:%d" % servidor.PORTA)
        except Exception as e:
            log("historico indisponivel: %s" % e)

        self.indicador = None
        if getattr(config, "INDICADOR", True):
            from indicador import Indicador
            self.indicador = Indicador()

        self.apertadas = set()
        self.gravando = False
        self.blocos = []
        self.stream = None
        self.inicio = 0.0
        self.fila = queue.Queue()
        threading.Thread(target=self._worker, daemon=True).start()

    def _sinalizar(self, estado):
        if self.indicador:
            self.indicador.pedir(estado)

    def _mtime_vocab(self):
        try:
            return os.path.getmtime(os.path.join(RAIZ, "vocabulario.json"))
        except OSError:
            return 0

    def _recarregar_se_mudou(self):
        """A interface de historico escreve no vocabulario; o servico precisa ver.

        Checar o mtime antes de cada transcricao custa microssegundos e evita ter
        de reiniciar o servico toda vez que voce ensina uma palavra nova."""
        agora = self._mtime_vocab()
        if agora != self.vocab_mtime:
            self.vocab_mtime = agora
            try:
                self.hotwords, self.correcoes = carregar_vocabulario()
                log("vocabulario recarregado: %d correcoes" % len(self.correcoes[1]))
            except Exception as e:
                log("falha ao recarregar vocabulario: %s" % e)

    # ---------- captura ----------
    def _callback(self, indata, frames, tempo, status):
        if self.gravando:
            self.blocos.append(indata[:, 0].copy())

    def comecar(self):
        if self.gravando:
            return
        self.blocos = []
        self.gravando = True
        self.inicio = time.time()
        try:
            self.stream = sd.InputStream(device=self.dispositivo, channels=1,
                                         samplerate=self.taxa_captura,
                                         dtype="float32", callback=self._callback)
            self.stream.start()
            log("gravando...")
            self._sinalizar("gravando")
            self._bip(880)
        except Exception as e:
            self.gravando = False
            log("ERRO ao abrir o microfone: %s" % e)

    def parar(self):
        if not self.gravando:
            return
        self.gravando = False
        dur = time.time() - self.inicio
        try:
            if self.stream:
                self.stream.stop()
                self.stream.close()
        except Exception:
            pass
        self.stream = None
        self._bip(660)
        if not self.blocos or dur < 0.35:
            log("muito curto (%.2fs), descartado" % dur)
            self._sinalizar(None)
            return
        self._sinalizar("transcrevendo")
        audio = np.concatenate(self.blocos)
        log("capturado %.1fs, transcrevendo..." % dur)
        self.fila.put(audio)

    def _bip(self, hz):
        if not getattr(config, "BIPES", True):
            return
        try:
            import winsound
            winsound.Beep(hz, 70)
        except Exception:
            pass

    # ---------- transcricao ----------
    def _worker(self):
        while True:
            audio = self.fila.get()
            try:
                self._processar(audio)
            except Exception:
                log("ERRO na transcricao:\n%s" % traceback.format_exc())
            finally:
                # sem isto o indicador fica ambar para sempre, de erro ou de sucesso
                self._sinalizar(None)

    def _processar(self, audio):
        self._recarregar_se_mudou()
        audio16 = reamostrar(audio, self.taxa_captura, TAXA_WHISPER)
        dur = len(audio16) / float(TAXA_WHISPER)

        t0 = time.time()
        params = dict(config.PARAMETROS)
        params["hotwords"] = self.hotwords
        segs, _ = self.modelo.transcribe(audio16, **params)
        bruto = " ".join(s.text.strip() for s in segs).strip()
        gasto = time.time() - t0

        texto = aplicar_correcoes(bruto, self.correcoes)
        if not texto:
            log("nada reconhecido (%.1fs de audio)" % dur)
            return

        carimbo = datetime.datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
        wav = os.path.join(HISTORICO, carimbo + ".wav")
        salvar_wav(wav, audio16, TAXA_WHISPER)

        with open(REGISTRO, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "quando": datetime.datetime.now().isoformat(timespec="seconds"),
                "audio": os.path.basename(wav),
                "texto": texto,
                "bruto": bruto if bruto != texto else None,
                "segundos_audio": round(dur, 1),
                "segundos_transcricao": round(gasto, 2),
            }, ensure_ascii=False) + "\n")

        time.sleep(0.12)                      # deixa o Ctrl/Win terminarem de subir
        if getattr(config, "MODO_COLAGEM", "digitar") == "clipboard":
            from injetar import colar_por_clipboard
            aceitos, enviados = colar_por_clipboard(texto)
        else:
            aceitos, enviados = digitar(texto,
                                        lote=getattr(config, "LOTE_DIGITACAO", 12),
                                        pausa=getattr(config, "PAUSA_DIGITACAO", 0.006))
        marca = "" if aceitos == enviados else "  [!! %d de %d eventos]" % (aceitos, enviados)
        log("%.1fs de fala -> %.2fs -> %d caracteres%s" % (dur, gasto, len(texto), marca))
        log("   %s" % (texto[:110] + ("..." if len(texto) > 110 else "")))

    # ---------- atalho ----------
    def on_press(self, k):
        self.apertadas.add(k)
        if ATALHO.issubset(self.apertadas):
            self.comecar()

    def on_release(self, k):
        if self.gravando and k in ATALHO:
            self.parar()
        self.apertadas.discard(k)

    def rodar(self):
        """O tkinter so funciona na thread principal, entao ele fica com ela e o
        listener de teclado vai para uma thread. Sem indicador, o listener toma
        a principal de volta e nao ha mainloop nenhum."""
        log("pronto. Segure %s, fale, solte. Feche esta janela para encerrar." % NOME_ATALHO)
        listener = keyboard.Listener(on_press=self.on_press, on_release=self.on_release)
        listener.daemon = True
        listener.start()
        if self.indicador:
            self.indicador.rodar()
        else:
            listener.join()


if __name__ == "__main__":
    try:
        Ditado().rodar()
    except KeyboardInterrupt:
        log("encerrado.")
