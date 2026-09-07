# ditado-local

Hold Ctrl+Win, speak, release. The text lands wherever your cursor is.

I dictate almost everything I write, and I was doing it with Wispr Flow, a product I admire and would still be paying for if I could. When the subscription stopped fitting my budget, I built my own in one afternoon: Whisper running locally on a GTX 1050 Ti. This is the Wispr for whoever cannot pay for Wispr yet.

Everything stays on your machine. There is no account and no quota, and the audio of what you dictate never leaves a local folder that git ignores.

## What running it feels like

Twenty seconds of speech become text in about 2.2 seconds on average, measured on the 1050 Ti (minimum 1.87s, maximum 2.77s). The model loads once, in about 8.4 seconds, and the service stays up. Accuracy came out well above what I expected, and the vocabulary layer covers what the model cannot guess.

## The design, and why each piece exists

Every choice below came out of a measuring bench (`bancada.py`), so the numbers are from samples of my own voice.

**A service, never a script.** Loading the model costs 8.4 seconds. Paying that per sentence would make the tool useless, so the model loads once and a keyboard listener waits. Recording runs while the shortcut is held, with no time limit, and transcription runs on a separate thread so the listener never blocks.

**A two-layer vocabulary.** Proper nouns are one error the model cannot guess: the name of your company does not exist in the Portuguese it was trained on. Layer one is a short hotwords list, and short is the point. On the same samples, 69 terms dropped accuracy to 9/11 and killed the punctuation entirely, while 15 comma-separated terms scored 11/11 with the best punctuation of the bench. Layer two is literal corrections, applied after transcription in a single regex pass. You never edit that layer by hand: when you fix a text in the history page, the tool diffs your correction against the transcript and learns the term.

**A history page with the audio next to each text** (`http://127.0.0.1:4772`). Injection follows keyboard focus, and focus moves. When your text lands in the wrong box, it is not lost.

**Clipboard paste instead of synthetic typing.** Electron apps drop synthetic keystrokes in bulk: in a measured test, a 400-character batch arrived as about 60 characters, and slowing down does not fix it. Pasting delivers everything at once, and your previous clipboard content is restored right after.

**An anti-loop flag.** With `condition_on_previous_text` enabled, one real sample ended in a repetition loop and took 21.0s; disabled, 9.6s and clean. The cost is weaker punctuation on very long audio, which dictation never produces.

**int8 on the GPU.** A Pascal card has no native float16, and int8 was the fastest compute type available. The GPU measured 9x faster than 12 CPU cores (5.2s against 46.0s), and `large-v3-turbo` beat `medium` at equal quality (RTF 0.08 against 0.16).

## Install (Windows)

1. Clone and enter the folder:

   ```
   git clone https://github.com/amp-self/ditado-local
   cd ditado-local
   ```

2. Python 3.10 or newer, with a virtual environment:

   ```
   python -m venv .venv
   .venv\Scripts\pip install -r requirements.txt
   ```

3. A CUDA-capable GPU is recommended. CPU works with the same code, 9x slower on my bench; set `DEVICE = "cpu"` in `config.py`.

4. Pre-fetch the model, one time, connected to the internet (the service itself runs offline, with `local_files_only=True`):

   ```
   .venv\Scripts\python -c "from faster_whisper import download_model; download_model('large-v3-turbo')"
   ```

5. Copy `vocabulario.example.json` to `vocabulario.json` and put your own terms in it.

6. Run `ditado.cmd`. Hold Ctrl+Win, speak, release.

## Teach it your vocabulary

`extrair_vocabulario.py` scans a folder of markdown notes and returns the proper nouns and acronyms you actually use, ranked by frequency, ready to curate into `vocabulario.json`:

```
python extrair_vocabulario.py "C:\path\to\your\notes"
```

The measuring bench is reusable too: record two or three samples of your own voice with `gravar.cmd`, edit the terms at the top of `bancada.py`, and it will measure wait time, word error rate and vocabulary hits for each model on your hardware.

## Notes

Built for Brazilian Portuguese dictation (`language: "pt"` in `config.py`; change it for yours). The code and comments are in Portuguese: I built this for my own daily use, and I am publishing it as it runs on my machine.

## License

MIT. Use it, change it, ship it; keep the notice.
