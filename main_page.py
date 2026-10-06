import streamlit as st

st.set_page_config(
    page_title="Аналитика БРС СПбГЭУ",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

pages = [
    st.Page("stage1.py", title="1 — Успеваемость направлений"),
    st.Page("stage2.py", title="2 — Целевой студент"),
]

pg = st.navigation(pages)
pg.run()
