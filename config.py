# -*- coding: utf-8 -*-
"""Configuracao decidida por bancada, em 31 de agosto de 2026.

Cada escolha aqui foi medida, nao arbitrada. Os numeros de referencia estao
no README e o metodo em bancada.py. Quem for mudar qualquer valor: remeça.
"""

# --- modelo ---
# large-v3-turbo bateu o medium em velocidade (RTF 0.08 contra 0.16) com qualidade
# igual dentro do ruido -- a diferenca medida de WER foram dois artigos em ~90 palavras.
MODELO = "large-v3-turbo"

# Numa GPU Pascal (compute capability 6.1, ex.: GTX 1050 Ti) nao ha float16 nativo:
# o CTranslate2 so oferece int8_float32, int8 e float32. int8 e o mais rapido.
# GPU medida 9x mais rapida que 12 nucleos de CPU (5.2s contra 46.0s).
DEVICE = "cuda"
COMPUTE_TYPE = "int8"

# --- vocabulario ---
# O vocabulario vivo mora em vocabulario.json (copie vocabulario.example.json).
# A lista abaixo e so o exemplo do formato: curta e de proposito -- medido em
# 31/08/2026, 69 termos como hotwords derrubaram o acerto (9/11) e mataram a
# pontuacao; 15 termos deram 11/11 com a melhor pontuacao. Lista longa dilui o sinal.
HOTWORDS = (
    "OKR NPS CSAT ditar ditado Whisper"
)

# --- parametros de transcricao ---
# condition_on_previous_text=False e a trava anti-loop: sem ela, uma amostra real
# terminou em "E aí E aí E aí E aí" e levou 21.0s; com ela, 9.6s e sem loop.
# O custo e pontuacao mais fraca em audio muito longo -- irrelevante para ditado,
# onde cada disparo tem segundos, e corrigivel pela camada de limpeza.
PARAMETROS = {
    "language": "pt",
    "beam_size": 5,
    "vad_filter": True,
    "condition_on_previous_text": False,
    "hotwords": HOTWORDS,
}

# Medido em 31/08/2026: trechos de 20s de fala -> 2.16s de espera em media
# (minimo 1.87s, maximo 2.77s). Carga do modelo: ~8.4s, uma vez por sessao.


# --- atalho ---
# Nomes de teclas do pynput. Ctrl+Win era o atalho do Wispr Flow; desativado o
# original, o par ficou livre -- e e o que a mao esquerda alcanca sem sair do teclado.
#
#   ["ctrl_l", "cmd_l"]    Ctrl esquerdo + Windows   <- em uso
#   ["ctrl_l", "alt_l"]    Ctrl + Alt esquerdos      <- alternativa livre
#   ["ctrl_l", "shift_l"]  Ctrl + Shift esquerdos    <- livre, mas atrapalha selecao
#
# Testado em 31/08/2026: Ctrl+Win nao abre o menu Iniciar com o listener ativo,
# e os tres disparos do teste foram capturados (0.6s, 0.6s, 0.7s).
ATALHO = ["ctrl_l", "cmd_l"]

# Mostra um ponto no canto da tela enquanto grava e enquanto transcreve.
INDICADOR = True

# Bipes curtos ao comecar e ao terminar de gravar.
BIPES = True


# --- como o texto chega ao app ---
#   "digitar"   SendInput caractere a caractere. Nao toca no clipboard.
#   "clipboard" Ctrl+V, com o clipboard restaurado logo depois. Instantaneo e
#               integro em qualquer app, mas atropela o clipboard por ~200ms.
#
# Medido em 31/08/2026: o Notepad aceita qualquer ritmo; apps Electron perderam
# blocos com lote 400 sem pausa. Dai o lote pequeno com pausa.
# Medido num app Electron em 31/08/2026, com o modo "digitar":
#   lote 400 sem pausa -> 103 chars viraram ~60
#   lote  12 com  6 ms ->  66 chars viraram  25
# Afinar o ritmo nao resolve: o laco de mensagens do Electron descarta eventos
# de teclado sinteticos em bloco, independentemente da velocidade. O clipboard
# entrega tudo de uma vez, e o conteudo anterior volta logo em seguida.
MODO_COLAGEM = "clipboard"
LOTE_DIGITACAO = 12
PAUSA_DIGITACAO = 0.006
