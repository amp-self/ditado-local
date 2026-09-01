# -*- coding: utf-8 -*-
"""Bancada de medicao: roda cada modelo sobre as suas amostras de voz e mede
tempo de espera, taxa de erro de palavra e acerto dos termos do seu vocabulario.

Grave 2 ou 3 amostras suas com gravar.cmd (fale ~60s, citando os termos que a
transcricao costuma errar) e edite GLOSSARIO e TERMOS abaixo com o SEU mundo:
nomes de empresa, de pessoa e siglas que voce dita todo dia."""
import os, sys, time, json, wave, io

RAIZ = os.path.dirname(os.path.abspath(__file__))
AMOSTRAS = os.path.join(RAIZ, "amostras")

# O glossario entra como initial_prompt: o Whisper o le como se fosse o texto
# imediatamente anterior, e passa a esperar esse vocabulario.
GLOSSARIO = (
    "Conversa de trabalho sobre a empresa Exemplo, o produto Exemplar, "
    "sucesso do cliente, OKR, NPS, CSAT. Pessoas: Maria Souza, Joao Pereira."
)

# Termos que a transcricao costuma errar no seu uso, mais os nomes proprios.
TERMOS = ["Exemplo", "Exemplar", "Maria Souza", "OKR", "NPS", "CSAT"]

CONFIGS = [
    ("large-v3-turbo", "cuda", "int8"),
    ("medium",         "cuda", "int8"),
]


def duracao_wav(caminho):
    with wave.open(caminho, "rb") as w:
        return w.getnframes() / float(w.getframerate())


def normalizar(t):
    import re, unicodedata
    t = unicodedata.normalize("NFKD", t.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def termos_acertados(texto):
    n = normalizar(texto)
    return [t for t in TERMOS if normalizar(t) in n]


def main():
    from faster_whisper import WhisperModel

    wavs = sorted(f for f in os.listdir(AMOSTRAS) if f.endswith(".wav"))
    if not wavs:
        print("Nenhuma amostra em %s -- rode gravar.cmd primeiro." % AMOSTRAS)
        return

    ref = None
    cam_ref = os.path.join(AMOSTRAS, "referencia-01.txt")
    if os.path.exists(cam_ref):
        with io.open(cam_ref, encoding="utf-8") as f:
            ref = f.read()

    print("amostras encontradas:")
    for w in wavs:
        print("   %-18s %5.1fs" % (w, duracao_wav(os.path.join(AMOSTRAS, w))))
    print()

    linhas, transcricoes = [], {}
    for modelo, device, ct in CONFIGS:
        rotulo = "%s/%s" % (modelo, device)
        try:
            t0 = time.time()
            kw = {"device": device, "compute_type": ct, "local_files_only": True}
            if device == "cpu":
                kw["cpu_threads"] = 12
            m = WhisperModel(modelo, **kw)
            carga = time.time() - t0
        except Exception as e:
            print("FALHA ao carregar %s: %s" % (rotulo, str(e)[:200]))
            continue
        print("== %s (carga %.1fs) ==" % (rotulo, carga), flush=True)

        for wav in wavs:
            caminho = os.path.join(AMOSTRAS, wav)
            dur = duracao_wav(caminho)
            for usa_glossario in (False, True):
                t0 = time.time()
                segs, info = m.transcribe(
                    caminho, language="pt", beam_size=5,
                    initial_prompt=GLOSSARIO if usa_glossario else None,
                    vad_filter=True,
                )
                texto = " ".join(s.text.strip() for s in segs).strip()
                gasto = time.time() - t0

                reg = {"modelo": modelo, "device": device, "amostra": wav,
                       "glossario": usa_glossario, "segundos": round(gasto, 2),
                       "duracao_audio": round(dur, 1),
                       "rtf": round(gasto / dur, 2) if dur else None,
                       "acertos": termos_acertados(texto), "texto": texto}

                if wav.startswith("amostra-1") and ref:
                    try:
                        import jiwer
                        reg["wer"] = round(jiwer.wer(normalizar(ref), normalizar(texto)) * 100, 1)
                    except Exception:
                        pass

                linhas.append(reg)
                transcricoes["%s|%s|%s" % (rotulo, wav, usa_glossario)] = texto
                g = "com glossario" if usa_glossario else "sem glossario "
                extra = ""
                if "wer" in reg:
                    extra += "  WER %5.1f%%" % reg["wer"]
                if wav.startswith("amostra-1"):
                    extra += "  termos %d/%d" % (len(reg["acertos"]), len(TERMOS))
                print("   %-16s %s  %6.1fs  (RTF %.2f)%s"
                      % (wav, g, gasto, reg["rtf"] or 0, extra), flush=True)
        m = None
        print(flush=True)

    with io.open(os.path.join(RAIZ, "resultados.json"), "w", encoding="utf-8") as f:
        json.dump(linhas, f, ensure_ascii=False, indent=2)
    print("resultados salvos em resultados.json (%d medicoes)" % len(linhas))


if __name__ == "__main__":
    main()
