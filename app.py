import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import plotly.express as px
import urllib.parse
import numpy as np

#Autenticação
USERS = st.secrets["users"]

def login():
    st.title("Autenticação necessária")
    with st.form("login"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Entrar")
        if submitted:
            if username in USERS and USERS[username] == password:
                st.session_state["autenticado"] = True
                st.session_state["user"] = username
                st.success(f"Bem-vindo, {username}!")
                st.rerun()
            else:
                st.error("Credenciais inválidas.")

if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

if not st.session_state["autenticado"]:
    login()
    st.stop()

st.set_page_config(layout="wide")

st.markdown("""
    <style>
        .main .block-container {
            padding: 0 2rem;
            max-width: 100% !important;
        }
    </style>
""", unsafe_allow_html=True)

# SQLite local
from sqlalchemy import create_engine

engine = create_engine("sqlite:///presencas.db")

@st.cache_data
def load_data():
    return pd.read_sql("SELECT * FROM presencas", engine)

df = load_data()


# Filtros
st.sidebar.header("Filtros")

def ordenar_turnos(turnos):
    numericos = sorted([t for t in turnos if t.isdigit()], key=int)
    especiais = [t for t in turnos if not t.isdigit()]
    return especiais + numericos  

# Filtro: Ano Letivo
ano_letivo = st.sidebar.multiselect("Ano Letivo", sorted(df['data_ano_letivo'].unique(),reverse=True))

# Filtro: Unidade Orgânica
unidades_opcoes = sorted(df['unidade_nome'].dropna().unique())
unidade = st.sidebar.multiselect("Escola", unidades_opcoes)

# 1º filtro dependente: cursos disponíveis para a(s) unidade(s) selecionada(s)
df_filtrado = df.copy()

if ano_letivo:
    df_filtrado = df_filtrado[df_filtrado['data_ano_letivo'].isin(ano_letivo)]
if unidade:
    df_filtrado = df_filtrado[df_filtrado['unidade_nome'].isin(unidade)]
curso_opcoes = sorted(df_filtrado['curso_nome'].dropna().unique())
curso = st.sidebar.multiselect("Curso", curso_opcoes)

# 2º filtro dependente: UCs e Regimes disponíveis para os cursos selecionados
df_filtrado = df_filtrado[df_filtrado['curso_nome'].isin(curso)] if curso else df_filtrado
regime_opcoes = sorted(df_filtrado['curso_regime'].dropna().unique())
regime = st.sidebar.multiselect("Regime", regime_opcoes)
ucs_opcoes = sorted(df_filtrado['uc_nome'].dropna().unique())
uc = st.sidebar.multiselect("Unidade Curricular", ucs_opcoes)

# 3º filtro dependente: turnos e componentes disponíveis para as UCs selecionadas
df_filtrado = df_filtrado[df_filtrado['uc_nome'].isin(uc)] if uc else df_filtrado
turnos_ordenados = ordenar_turnos(df_filtrado['turno'].dropna().unique())
turno = st.sidebar.multiselect("Turno", turnos_ordenados)
componente_opcoes = sorted(df_filtrado['turno_componente'].dropna().unique())
componente = st.sidebar.multiselect("Componente", componente_opcoes)

# Slider: Semana Letiva (intervalo mínimo e máximo)
semana_min = int(df_filtrado['data_semana_letiva'].min())
semana_max = int(df_filtrado['data_semana_letiva'].max())

st.sidebar.markdown(
    """
    <div style="display: flex; align-items: center; gap: 6px;">
        <label style="font-weight: 600;">Semana Letiva (intervalo)</label>
        <span title="A representação atual das datas académicas está corretamente mapeada apenas para os anos letivos de 2022/23, 2023/24 e 2024/25, pelo que os valores de semanas letivas em anos anteriores poderão não estar corretos." 
      style="color: red; cursor: help; font-size: 18px; font-weight: bold; display: inline-block; border: 1.5px solid red; border-radius: 50%; width: 18px; height: 18px; text-align: center; line-height: 16px;">i</span>

    </div>
    """,
    unsafe_allow_html=True
)

if semana_min < semana_max:
    semana_range = st.sidebar.slider(
        label="Intervalo de Semana Letiva",
        min_value=semana_min,
        max_value=semana_max,
        value=(semana_min, semana_max),
        step=1,
        label_visibility="collapsed"
    )
else:
    st.sidebar.warning("Não há semanas letivas disponíveis para os filtros selecionados.")
    semana_range = (semana_min, semana_max)

excluir_avaliacoes = st.sidebar.checkbox("Excluir avaliações e exames", value=True)

# Aplicar filtros
if ano_letivo:
    df = df[df['data_ano_letivo'].isin(ano_letivo)]
if unidade:
    df = df[df['unidade_nome'].isin(unidade)]
if curso:
    df = df[df['curso_nome'].isin(curso)]
if regime:
    df = df[df['curso_regime'].isin(regime)]
if uc:
    df = df[df['uc_nome'].isin(uc)]
if turno:
    df = df[df['turno'].isin(turno)]
if componente:
    df = df[df['turno_componente'].isin(componente)]
df = df[(df['data_semana_letiva'] >= semana_range[0]) & (df['data_semana_letiva'] <= semana_range[1])]
if excluir_avaliacoes:
    df = df[~(
        (df['data_semana_letiva'] == 0) |
        ((df['turno'] == 'Sem Turno') & (df['turno_componente'] == 'N/A'))
    )]

def gerar_impacto(n_alunos):
    if n_alunos < 10:
        return "🔴"
    elif n_alunos <= 15:
        return "🟡"
    else:
        return "🟢"

df['impacto_presencas'] = df['n_alunos'].apply(gerar_impacto)

# Reordenar colunas para colocar 'impacto_presencas' a seguir a 'n_alunos'
colunas = list(df.columns)
if 'n_alunos' in colunas and 'impacto_presencas' in colunas:
    colunas.remove('impacto_presencas')
    idx = colunas.index('n_alunos') + 1
    colunas.insert(idx, 'impacto_presencas')
    df = df[colunas]

df.drop(columns=["data_ano_letivo"], inplace=True)    

df.rename(columns={
    'n_alunos': 'Presenças',
    'data_completa': 'Data',
    'turno': 'Turno',
    'turno_componente': 'Componente',
    'curso_nome': 'Curso',
    'curso_regime': 'Regime',
    'uc_nome': 'Unidade Curricular',
    'data_semana_letiva': 'Semana Letiva',
    'unidade_nome': 'Escola',
    'impacto_presencas': 'Impacto'
}, inplace=True)

df.sort_values(by='Data', ascending=False, inplace=True)

if not df.empty:
    # Parâmetros da paginação
    linhas_por_pagina = 100
    total_linhas = len(df)
    total_paginas = (total_linhas - 1) // linhas_por_pagina + 1

    pagina_atual = st.sidebar.number_input(
        label="Página",
        min_value=1,
        max_value=total_paginas,
        value=1,
        step=1
    )

    inicio = (pagina_atual - 1) * linhas_por_pagina
    fim = inicio + linhas_por_pagina

    df_pagina = df.iloc[inicio:fim]

    st.subheader("Registos de Presenças por Aula (Filtrados)")
    st.dataframe(df_pagina, use_container_width=True, hide_index=True)

    df['Turno Simples'] = (
        df['Componente'].fillna('') + 
        df['Turno'].astype(str) + 
        ' (' + df['Regime'].astype(str) + ')'
    )

    st.subheader("Evolução Semanal de Presenças por Turno")
    fig = px.line(
        df.groupby(['Semana Letiva', 'Turno Simples'])['Presenças'].sum().reset_index(),
        x='Semana Letiva',
        y='Presenças',
        color='Turno Simples',  
        labels={
            'Turno Simples': 'Turno (Regime)',
            'Semana Letiva': 'Semana Letiva',
            'Presenças': 'Presenças'
        }
    )

    # Modificar o intervalo do eixo X para começar na menor semana presente
    semana_min = df['Semana Letiva'].min()
    semana_max = df['Semana Letiva'].max()
    fig.update_xaxes(range=[semana_min, semana_max])

    fig.add_vline(
        x=5,  # Semana 5
        line_dash="dash",
        line_color="red",
        annotation_text="Controlo de Presenças",
        annotation_position="top left"
    )
    st.plotly_chart(fig, use_container_width=True)


    # Top 10 Turnos com Menor Média de Presenças (considerando apenas aulas válidas)
    df_validas = df[df['Presenças'] > 0]

    df_ranking = df_validas.groupby([
        'Curso',
        'Unidade Curricular',
        'Regime',
        'Turno',
        'Componente'
    ]).agg({'Presenças': 'mean'}).reset_index()

    df_ranking = df_ranking.sort_values('Presenças').head(15)

    df_ranking['Turno Simples'] = (
        df_ranking['Componente'] + 
        df_ranking['Turno'].astype(str) + 
        ' (' + df_ranking['Regime'] + ')'
    )

    st.subheader("Médias de Presenças por turno")
    fig_ranking = px.bar(
        df_ranking,
        x='Presenças',
        y='Turno Simples',
        color='Turno Simples',
        orientation='h',
        labels = {
        'Turno Simples': 'Turno (Regime)',
        'Presenças': 'Média de Presenças'
        },
    )
    st.plotly_chart(fig_ranking, use_container_width=True)

    # Agrupar por turno, ignorando presenças 0
    df_turno_stats = (
        df[df['Presenças'] > 0]
        .groupby('Turno Simples')['Presenças']
        .agg(
            Minimo='min',
            Mediana='median',
            Maximo='max'
        )
        .reset_index()
        .sort_values('Minimo')
    )

    # Mostrar apenas um turno de cada vez, com seletor
    st.subheader("Métricas por Turno")

    # Lista de turnos disponíveis para seleção
    turnos_disponiveis = df_turno_stats['Turno Simples'].tolist()

    # Selectbox para escolher o turno
    turno_escolhido = st.selectbox("Selecione um turno:", turnos_disponiveis)

    # Filtrar os dados para o turno escolhido
    row = df_turno_stats[df_turno_stats['Turno Simples'] == turno_escolhido].iloc[0]

    # Mostrar os dados do turno selecionado
    col1, col2, col3 = st.columns(3)
    col1.metric("Mínimo", int(row['Minimo']))
    col2.metric("Mediana", f"{row['Mediana']:.1f}")
    col3.metric("Máximo", int(row['Maximo']))




else:
    st.warning("Nenhum registo encontrado para os filtros selecionados.")

