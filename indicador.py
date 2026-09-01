# -*- coding: utf-8 -*-
"""Indicador visual de gravacao: um ponto no canto da tela.

  vermelho pulsando = gravando
  ambar             = transcrevendo
  invisivel         = ocioso

Roda em tkinter, que vem com o Python -- nenhuma dependencia nova. A janela e
sem borda, sempre no topo e com fundo transparente, entao o que aparece na tela
e so o circulo.

IMPORTANTE: tkinter exige a thread principal. Por isso o servico inverte a
ordem natural -- o mainloop fica no principal e o listener de teclado roda em
thread. Quem mexer aqui: nao chame nada de tkinter de outra thread; use
`pedir()`, que enfileira a mudanca para o proprio mainloop aplicar.
"""
import queue
import tkinter as tk

LADO = 34               # tamanho da janela, em pixels
RAIO = 11               # raio do circulo
MARGEM_X = 26           # distancia da borda direita
MARGEM_Y = 90           # distancia da borda inferior (acima da barra de tarefas)
CHAVE = "#010203"       # cor tratada como transparente pelo Windows

CORES = {
    "gravando": ("#ff3b30", "#ff8a80"),      # vermelho, e o tom do halo
    "transcrevendo": ("#ff9500", "#ffcc80"),  # ambar
}


class Indicador(object):
    def __init__(self):
        self.pedidos = queue.Queue()
        self.estado = None
        self.fase = 0.0
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=CHAVE)
        try:
            self.root.attributes("-transparentcolor", CHAVE)
        except tk.TclError:
            pass                                   # sem transparencia, o quadrado aparece
        self.root.geometry(self._posicao())
        self.canvas = tk.Canvas(self.root, width=LADO, height=LADO,
                                bg=CHAVE, highlightthickness=0)
        self.canvas.pack()
        self.root.withdraw()
        self.root.after(60, self._tique)

    def _posicao(self):
        larg = self.root.winfo_screenwidth()
        alt = self.root.winfo_screenheight()
        return "%dx%d+%d+%d" % (LADO, LADO, larg - LADO - MARGEM_X, alt - LADO - MARGEM_Y)

    # --- API para as outras threads ---
    def pedir(self, estado):
        """Chamavel de qualquer thread. estado: 'gravando', 'transcrevendo' ou None."""
        self.pedidos.put(estado)

    def encerrar(self):
        self.pedidos.put("__fim__")

    # --- so o mainloop roda daqui para baixo ---
    def _tique(self):
        try:
            while True:
                p = self.pedidos.get_nowait()
                if p == "__fim__":
                    self.root.destroy()
                    return
                self.estado = p
                if p is None:
                    self.root.withdraw()
                else:
                    self.fase = 0.0
                    self.root.deiconify()
                    self.root.attributes("-topmost", True)
        except queue.Empty:
            pass

        if self.estado:
            self.fase += 0.16
            self._desenhar()
        self.root.after(60, self._tique)

    def _desenhar(self):
        import math
        self.canvas.delete("all")
        cor, halo = CORES.get(self.estado, CORES["gravando"])
        c = LADO / 2.0
        # o halo respira; o nucleo fica firme, para o olho achar o ponto sem esforco
        pulso = (math.sin(self.fase) + 1) / 2.0
        r_halo = RAIO + 4 + pulso * 4
        self.canvas.create_oval(c - r_halo, c - r_halo, c + r_halo, c + r_halo,
                                fill=halo, outline="")
        self.canvas.create_oval(c - RAIO, c - RAIO, c + RAIO, c + RAIO,
                                fill=cor, outline="#ffffff", width=2)

    def rodar(self):
        self.root.mainloop()
