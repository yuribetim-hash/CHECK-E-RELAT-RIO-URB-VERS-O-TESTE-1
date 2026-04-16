import streamlit as st
import os
import json
from docxtpl import DocxTemplate, RichText
from io import BytesIO
from datetime import datetime

# -------------------------
# LOGIN
# -------------------------
usuarios = {
    "admin": "1234",
    "analista": "abcd"
}

def tela_login():
    st.title("Login do Sistema")

    user = st.text_input("Usuário")
    senha = st.text_input("Senha", type="password")

    if st.button("Entrar"):
        if user in usuarios and usuarios[user] == senha:
            st.session_state["logado"] = True
            st.session_state["usuario"] = user
            st.rerun()
        else:
            st.error("Usuário ou senha inválidos")

if "logado" not in st.session_state:
    st.session_state["logado"] = False

if not st.session_state["logado"]:
    tela_login()
    st.stop()

st.sidebar.write(f"👤 {st.session_state['usuario']}")
if st.sidebar.button("Sair"):
    st.session_state["logado"] = False
    st.rerun()

# -------------------------
# HISTÓRICO
# -------------------------
def get_pasta_protocolo(protocolo):
    return os.path.join("dados", protocolo.replace("/", "-"))

def listar_analises(protocolo):
    pasta = get_pasta_protocolo(protocolo)
    if not os.path.exists(pasta):
        return []
    arquivos = os.listdir(pasta)
    analises = [f for f in arquivos if f.startswith("AN") and f.endswith(".json")]
    analises.sort()
    return analises

def carregar_ultima_analise(protocolo):
    analises = listar_analises(protocolo)
    if not analises:
        return None
    caminho = os.path.join(get_pasta_protocolo(protocolo), analises[-1])
    with open(caminho, "r", encoding="utf-8") as f:
        return json.load(f)

def salvar_historico(dados, respostas, observacoes, conclusao, analista, n_analise, arquivo_docx):
    pasta = get_pasta_protocolo(dados["protocolo"])
    os.makedirs(pasta, exist_ok=True)

    base = f"AN{n_analise}"

    registro = {
        "protocolo": dados["protocolo"],
        "n_analise": n_analise,
        "data": datetime.now().strftime("%d/%m/%Y"),
        "analista": analista,
        "dados": dados,
        "respostas": respostas,
        "observacoes": observacoes,
        "conclusao": conclusao
    }

    with open(os.path.join(pasta, f"{base}.json"), "w", encoding="utf-8") as f:
        json.dump(registro, f, indent=4, ensure_ascii=False)

    with open(os.path.join(pasta, f"{base}.docx"), "wb") as f:
        f.write(arquivo_docx.getvalue())

# -------------------------
# CARREGAR PERGUNTAS
# -------------------------
def carregar_perguntas_txt(caminho):
    if not os.path.exists(caminho):
        st.error("Arquivo perguntas.txt não encontrado")
        st.stop()

    perguntas = []
    bloco = {}

    with open(caminho, "r", encoding="utf-8") as f:
        linhas = f.readlines()

    for linha in linhas:
        linha = linha.strip()

        if not linha:
            if bloco:
                perguntas.append(bloco)
                bloco = {}
            continue

        if linha.startswith("GRUPO:"):
            bloco["grupo"] = linha.replace("GRUPO:", "").strip()

        elif linha.startswith("ID:"):
            bloco["id"] = linha.replace("ID:", "").strip()

        elif linha.startswith("PERGUNTA:"):
            bloco["pergunta"] = linha.replace("PERGUNTA:", "").strip()

        elif linha.startswith("OPCOES:"):
            bloco["opcoes"] = linha.replace("OPCOES:", "").strip().split(";")

        elif linha.startswith("REGRA_"):
            chave, valor = linha.split(":", 1)
            resposta = chave.replace("REGRA_", "").strip()
            bloco.setdefault("regras", {})[resposta] = {"texto": valor.strip()}

    if bloco:
        perguntas.append(bloco)

    return perguntas

perguntas = carregar_perguntas_txt("perguntas.txt")

# -------------------------
# FUNÇÕES
# -------------------------
def definir_conclusao(respostas):
    for p in perguntas:
        if respostas[p["id"]] in p.get("regras", {}):
            return "DESFAVORÁVEL"
    return "FAVORÁVEL"


def gerar_docx(dados, respostas, observacoes, conclusao, analista, matricula, setor, n_analise):

    doc = DocxTemplate("modelo_parecer.docx")

    grupos = {}
    for p in perguntas:
        resp = respostas[p["id"]]
        if resp in p.get("regras", {}):
            grupo = p["grupo"]
            texto = p["regras"][resp]["texto"]
            obs = observacoes[p["id"]]

            if obs.strip():
                texto += f"\nObservação: {obs}"

            grupos.setdefault(grupo, []).append(texto)

    rt = RichText()
    contador = 1

    if grupos:
        for grupo, itens in grupos.items():
            rt.add(grupo.upper(), bold=True)
            rt.add("\n\n")

            for item in itens:
                rt.add(f"{contador}. {item}")
                rt.add("\n\n")
                contador += 1
    else:
        rt.add("Não foram identificadas inconformidades.")

    context = {
        "protocolo": dados["protocolo"],
        "tipo": dados["tipo"],
        "interessado": dados["interessado"],
        "n_lotes": dados["n_lotes"],
        "inconformidades": rt,
        "conclusao": conclusao,
        "data": f"Data: {datetime.now().strftime('%d/%m/%Y')}",
        "analista": f"Analista: {analista}",
        "matricula": matricula,
        "setor": setor,
        "n_analise": n_analise
    }

    doc.render(context)

    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)

    return buffer

# -------------------------
# INTERFACE
# -------------------------
st.title("Sistema de Parecer Urbanístico")

protocolo = st.text_input("N° Protocolo")

# HISTÓRICO
dados_antigos = None
if protocolo:
    ultima = carregar_ultima_analise(protocolo)
    if ultima:
        st.info(f"Última análise: AN{ultima['n_analise']}")
        if st.button("▶️ Continuar análise"):
            st.session_state["dados_antigos"] = ultima
            st.rerun()

dados_antigos = st.session_state.get("dados_antigos")

st.header("Dados do Empreendimento")

tipo = st.selectbox("Tipo", ["Loteamento", "Condomínio fechado de lotes"])
interessado = st.text_input("Requerente", value=dados_antigos["dados"]["interessado"] if dados_antigos else "")
n_lotes = st.number_input("Nº Lotes", min_value=1, value=dados_antigos["dados"]["n_lotes"] if dados_antigos else 1)

st.header("Analista")
analista = st.text_input("Nome")
matricula = st.text_input("Matrícula")
setor = st.text_input("Setor")
n_analise = st.text_input("Nº da Análise")

st.header("Análise")

respostas = {}
observacoes = {}

grupos_ui = {}
for p in perguntas:
    grupos_ui.setdefault(p["grupo"], []).append(p)

for grupo, lista in grupos_ui.items():
    st.subheader(grupo)

    for p in lista:
        valor_padrao = dados_antigos["respostas"].get(p["id"]) if dados_antigos else None
        obs_padrao = dados_antigos["observacoes"].get(p["id"], "") if dados_antigos else ""

        respostas[p["id"]] = st.selectbox(
            p["pergunta"],
            p["opcoes"],
            index=p["opcoes"].index(valor_padrao) if valor_padrao in p["opcoes"] else 0
        )

        observacoes[p["id"]] = st.text_area(
            "Observação",
            value=obs_padrao
        )

# COMPARATIVO
if dados_antigos:
    st.subheader("Alterações")
    for pid in respostas:
        antiga = dados_antigos["respostas"].get(pid)
        atual = respostas[pid]
        if antiga != atual:
            st.warning(f"{pid}: {antiga} → {atual}")

# GERAR
if st.button("Gerar Parecer"):

    dados = {
        "protocolo": protocolo,
        "tipo": tipo,
        "interessado": interessado,
        "n_lotes": n_lotes
    }

    conclusao = definir_conclusao(respostas)

    arquivo = gerar_docx(
        dados, respostas, observacoes,
        conclusao, analista, matricula,
        setor, n_analise
    )

    salvar_historico(
        dados, respostas, observacoes,
        conclusao, analista,
        n_analise, arquivo
    )

    protocolo_limpo = protocolo.replace("/", "-") if protocolo else "sem_protocolo"
    data_arquivo = datetime.now().strftime("%d-%m-%Y")
    analise_str = f"AN{n_analise}" if n_analise else "AN0"

    nome = f"PU_{protocolo_limpo}_{data_arquivo}_{analise_str}.docx"

    st.download_button("📄 Baixar", arquivo, file_name=nome)