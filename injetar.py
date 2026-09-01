# -*- coding: utf-8 -*-
"""Injeta texto no campo em foco, sem passar pelo clipboard.

Usa SendInput com eventos KEYEVENTF_UNICODE -- o teclado virtual do Windows
digita cada caractere. E o mesmo mecanismo do Wispr Flow, e a razao de o que
voce tem copiado continuar intacto.

Medido em 31/08/2026: 112 eventos (56 caracteres, com acentos) em 0.048s.
"""
import ctypes
import time
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
ULONG_PTR = wintypes.WPARAM
INPUT_KEYBOARD = 1
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_KEYUP = 0x0002


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ULONG_PTR)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD),
                ("wParamH", wintypes.WORD)]


class INPUT(ctypes.Structure):
    class _I(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]
    _anonymous_ = ("i",)
    _fields_ = [("type", wintypes.DWORD), ("i", _I)]


# A INPUT precisa da uniao inteira: em x64 o Windows valida o tamanho (40 bytes)
# e rejeita a chamada em silencio se ele nao bater -- SendInput devolve 0.
assert ctypes.sizeof(INPUT) == 40, "tamanho de INPUT inesperado: %d" % ctypes.sizeof(INPUT)

user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
user32.SendInput.restype = wintypes.UINT

# Ritmo de envio. No Notepad qualquer valor funciona; em app Electron (o Claude,
# o VS Code, o Slack) o laco de mensagens engole eventos que chegam rapido demais.
# Medido em 31/08/2026: lote 400 sem pausa perdeu blocos inteiros no Claude.
LOTE = 12
PAUSA = 0.006

# Virtual-keys dos modificadores que, presos, transformam cada letra em atalho.
MODIFICADORES = [0x11, 0xA2, 0xA3,   # Ctrl, Ctrl esq, Ctrl dir
                 0x12, 0xA4, 0xA5,   # Alt, Alt esq, Alt dir
                 0x10, 0xA0, 0xA1,   # Shift, Shift esq, Shift dir
                 0x5B, 0x5C]         # Win esq, Win dir


def soltar_modificadores():
    """Forca o release de Ctrl/Alt/Shift/Win antes de digitar.

    O atalho e push-to-talk: quando a transcricao termina, a tecla ja foi solta
    ha segundos. Mas o estado do teclado e global e pode ficar presa -- e com
    Ctrl preso cada caractere vira comando em vez de texto, o que aparece como
    'sumiram pedacos do meio'. Soltar antes custa nada e elimina a hipotese.
    """
    eventos = []
    for vk in MODIFICADORES:
        if user32.GetAsyncKeyState(vk) & 0x8000:
            ev = INPUT(type=INPUT_KEYBOARD)
            ev.ki = KEYBDINPUT(wVk=vk, wScan=0, dwFlags=KEYEVENTF_KEYUP,
                               time=0, dwExtraInfo=0)
            eventos.append(ev)
    if eventos:
        arr = (INPUT * len(eventos))(*eventos)
        user32.SendInput(len(eventos), arr, ctypes.sizeof(INPUT))
    return len(eventos)


def _unidades(texto):
    """Converte a string em unidades UTF-16, que e o que SendInput aceita."""
    saida = []
    for ch in texto:
        if ord(ch) > 0xFFFF:              # fora do BMP vira par surrogate
            b = ch.encode("utf-16-le")
            saida.extend([int.from_bytes(b[i:i + 2], "little") for i in (0, 2)])
        else:
            saida.append(ord(ch))
    return saida


def digitar(texto, lote=LOTE, pausa=PAUSA):
    """Digita o texto no campo em foco. Devolve (eventos_aceitos, eventos_enviados)."""
    if not texto:
        return 0, 0
    presos = soltar_modificadores()
    if presos:
        time.sleep(0.03)

    unidades = _unidades(texto)
    aceitos = enviados = 0
    for i in range(0, len(unidades), lote):
        eventos = []
        for u in unidades[i:i + lote]:
            for flags in (KEYEVENTF_UNICODE, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP):
                ev = INPUT(type=INPUT_KEYBOARD)
                ev.ki = KEYBDINPUT(wVk=0, wScan=u, dwFlags=flags, time=0, dwExtraInfo=0)
                eventos.append(ev)
        arr = (INPUT * len(eventos))(*eventos)
        aceitos += user32.SendInput(len(eventos), arr, ctypes.sizeof(INPUT))
        enviados += len(eventos)
        if pausa and i + lote < len(unidades):
            time.sleep(pausa)
    return aceitos, enviados


def colar_por_clipboard(texto):
    """Alternativa: poe no clipboard, manda Ctrl+V, devolve o clipboard de antes.

    Entrega instantanea e integra em qualquer app, mas passa pelo clipboard --
    se voce copiar alguma coisa nesses ~200ms, o que volta e o texto ditado.
    Existe como plano B para app que engula eventos de teclado.
    """
    import pyperclip
    try:
        anterior = pyperclip.paste()
    except Exception:
        anterior = None
    soltar_modificadores()
    time.sleep(0.03)
    pyperclip.copy(texto)
    time.sleep(0.05)
    user32.keybd_event(0x11, 0, 0, 0)          # Ctrl down
    user32.keybd_event(0x56, 0, 0, 0)          # V down
    user32.keybd_event(0x56, 0, KEYEVENTF_KEYUP, 0)
    user32.keybd_event(0x11, 0, KEYEVENTF_KEYUP, 0)
    time.sleep(0.15)
    if anterior is not None:
        try:
            pyperclip.copy(anterior)
        except Exception:
            pass
    return len(texto), len(texto)
