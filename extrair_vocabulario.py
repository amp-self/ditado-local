# -*- coding: utf-8 -*-
"""Varre o seu vault de notas (markdown) atras dos nomes proprios e termos que
a transcricao erra.

Nomes proprios sao o unico erro que o modelo nao consegue adivinhar: o nome da
sua empresa nao existe no portugues que ele viu treinando. Suas notas ja sabem
todos eles.

Uso:  python extrair_vocabulario.py "C:\\caminho\\do\\seu\\vault"
      (ou defina a variavel de ambiente VAULT_DIR)
"""
import os, re, sys, json, collections
sys.stdout.reconfigure(encoding="utf-8")

VAULT = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("VAULT_DIR", "")
if not VAULT or not os.path.isdir(VAULT):
    raise SystemExit("informe a pasta do vault: python extrair_vocabulario.py <pasta>")

# subpastas/arquivos mais densos em nome proprio; vazio = varre o vault inteiro
FONTES = [""]

# palavras capitalizadas que sao portugues comum, nao nome proprio
RUIDO = set("""A O E Os As Um Uma Ele Ela Eles Elas Eu Voce Nos Isso Isto Aquilo Que Quando Onde Como
Porque Por Para Com Sem Sobre Entre Depois Antes Ainda Sempre Nunca Mais Menos Muito Pouco Todo Toda
Todos Todas Cada Outro Outra Ou Mas Se Nao Sim Ja Aqui Ali La Hoje Ontem Amanha Agora Entao Assim
Tambem Apenas Mesmo Mesma So Ate Desde Durante Contra Segundo Primeiro Segunda Terceira Ver Fazer Ter
Ser Estar Dizer Dar Ir Vir Poder Querer Saber Ficar Deixar Passar Levar Trazer Achar Falar Escrever
Ler Pensar Trabalho Trabalhar Sistema Sistemas Pessoa Pessoas Empresa Empresas Time Times Cliente
Clientes Texto Textos Peca Pecas Edicao Edicoes Nota Notas Regra Regras Lei Leis Modelo Modelos
Arquivo Arquivos Documento Documentos Data Datas Dia Dias Semana Semanas Mes Meses Ano Anos Hora
Horas Minuto Minutos Valor Valores Ideia Ideias Conceito Conceitos Caso Casos Ponto Pontos Parte
Partes Forma Formas Modo Modos Tipo Tipos Nome Nomes Fonte Fontes Base Bases Nivel Niveis Etapa
Etapas Passo Passos Item Itens Lista Listas Bloco Blocos Linha Linhas Campo Campos
Sessao Sessoes Conversa Conversas Resposta Respostas Pergunta Perguntas Decisao Decisoes
Leitura Leituras Escrita Analise Projeto Projetos Trecho Frase Frases Versao
Versoes Pagina Paginas Titulo Marca Papel Rotulo Etiqueta Registro Registros Achado Achados""".split())

def arquivos():
    for f in FONTES:
        p = os.path.join(VAULT, f) if f else VAULT
        if os.path.isfile(p):
            yield p
        elif os.path.isdir(p):
            for raiz, _, nomes in os.walk(p):
                for n in nomes:
                    if n.endswith(".md"):
                        yield os.path.join(raiz, n)

cont = collections.Counter()
siglas = collections.Counter()
for caminho in arquivos():
    try:
        txt = open(caminho, encoding="utf-8", errors="ignore").read()
    except Exception:
        continue
    # nome proprio: capitalizada nao no inicio de frase
    for m in re.finditer(r"(?<![.!?]\s)(?<![.!?]\s\s)(?<!^)\b([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][a-záàâãéêíóôõúç]{2,})\b", txt, re.M):
        p = m.group(1)
        if p not in RUIDO:
            cont[p] += 1
    # siglas: 2 a 6 maiusculas
    for m in re.finditer(r"\b([A-Z]{2,6})\b", txt):
        siglas[m.group(1)] += 1

MIN_NOME, MIN_SIGLA = 8, 6
nomes = [p for p, c in cont.most_common(160) if c >= MIN_NOME]
sigs = [s for s, c in siglas.most_common(60) if c >= MIN_SIGLA and s not in ("MD", "PS")]

print("=== nomes proprios recorrentes (>= %d ocorrencias) ===" % MIN_NOME)
print(", ".join(nomes[:80]))
print()
print("=== siglas (>= %d) ===" % MIN_SIGLA)
print(", ".join(sigs[:40]))
json.dump({"nomes": nomes, "siglas": sigs},
          open("_vocab_bruto.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print()
print("candidatos: %d nomes, %d siglas" % (len(nomes), len(sigs)))
