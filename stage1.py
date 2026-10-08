import time
import streamlit as st
import pandas as pd
import plotly.express as px

import parser as p

st.title("📊 Средняя успеваемость направлений")


YEARS = {
    "2026 (1 курс)": "2026",
    "2025 (2 курс)": "2025",
    "2024 (3 курс)": "2024",
    "2023 (4 курс)": "2023",
}

# Колонки, которые НЕ являются баллами — их не трогаем.
# ВАЖНО: "Сумма" тут НЕТ — её нужно приводить к числу.
STRING_COLS = {"Группа", "№", "ФИО", "stud_id", "Семестр"}


# Утилиты
# def finalize_df(df: pd.DataFrame) -> pd.DataFrame:
#     """Приводит все колонки-баллы к числу, строковые оставляет строками."""
#     if df.empty:
#         return df
#     for c in df.columns:
#         if c in STRING_COLS:
#             df[c] = df[c].astype(str)
#         else:
#             df[c] = pd.to_numeric(df[c], errors="coerce")
#     return df


def try_fetch(params_list):
    for params in params_list:
        try:
            html = p.fetch(params)
        except Exception:
            continue
        return html, params
    return None, None


@st.cache_data(ttl=3600, show_spinner=False)
def load_directions_for_year(year: str):
    params = {
        "up": "none", "y": year,
        "k": "1", "f": "1",
        "upp": "all", "sort": "fio", "ball": "hide",
    }
    html, _ = try_fetch([params])
    if html is None:
        return []
    return [o for o in p.get_filter_options(html, "Направление")
            if o.label not in ("Не выбрано",) and "up" in o.params]


@st.cache_data(ttl=1800, show_spinner=False)
def load_groups_and_sems(up_id: str, year: str):
    params = {
        "up": up_id, "y": year,
        "k": "1", "f": "1",
        "g": "all", "upp": "all", "sort": "fio", "ball": "hide",
    }
    html, _ = try_fetch([
        params,
        {k: v for k, v in params.items() if k != "g"},
    ])
    if html is None:
        return None, [], []
    groups = [o for o in p.get_filter_options(html, "Группа")
              if o.label not in ("Не выбрано", "Все группы")]
    sems = p.get_filter_options(html, "Семестр")
    return html, groups, sems


@st.cache_data(ttl=600, show_spinner=False)
def load_group_html(up_id, year, g_id, s_id):
    return p.fetch({
        "up": up_id, "y": year, "k": "1", "f": "1",
        "g": g_id, "s": s_id,
        "upp": "all", "sort": "fio", "ball": "hide",
    })


def load_direction_data(up_id, year, groups, sems, selected_sems, direction_label):
    """Скачивает данные всех групп направления за выбранные семестры."""
    sem_options = {o.label: o for o in sems}
    all_rows = []
    subject_meta = None
    progress = st.progress(0.0, text=f"Загружаем «{direction_label}»…")
    total = len(groups) * len(selected_sems)
    step = 0

    for gopt in groups:
        g_id = gopt.params.get("g")
        for sem_label in selected_sems:
            step += 1
            progress.progress(step / total, text=f"{gopt.label} / {sem_label}")
            s_id = sem_options[sem_label].params.get("s")
            try:
                html = load_group_html(up_id, year, g_id, s_id)
            except Exception:
                continue
            if subject_meta is None:
                subject_meta = p.parse_subjects(html)
            rows = p.parse_students(html, group_name=gopt.label)
            for r in rows:
                r["Семестр"] = sem_label
            all_rows.extend(rows)
            time.sleep(0.2)

    progress.empty()
    df = pd.DataFrame(all_rows)
    if df.empty or subject_meta is None:
        return df, subject_meta or []
    return p.to_numeric_df(df), subject_meta


# ------------------------------------------------------------
# 1. Выбор направления 1
# ------------------------------------------------------------
st.markdown("### 🎯 Направление 1")

col1, col2, col3 = st.columns(3)

with col1:
    y1_label = st.selectbox("Год поступления (1)", list(YEARS.keys()), key="d1_y")
    y1 = YEARS[y1_label]

with col2:
    dirs1 = load_directions_for_year(y1)
    if not dirs1:
        st.error("Не удалось получить направления за выбранный год.")
        st.stop()
    dir1_labels = [o.label for o in dirs1]
    dir1_label = st.selectbox("Направление 1", dir1_labels, key="d1_dir")
    dir1_opt = dirs1[dir1_labels.index(dir1_label)]
    up1 = dir1_opt.params["up"]

with col3:
    _, groups1, sems1 = load_groups_and_sems(up1, y1)
    if not groups1:
        st.warning("Для направления 1 нет групп.")
        st.stop()
    st.caption(f"Группы ({len(groups1)}): {', '.join(g.label for g in groups1)}")


# ------------------------------------------------------------
# 2. Выбор направления 2
# ------------------------------------------------------------
st.markdown("### 🔄 Направление 2 (для сравнения)")

col1, col2, col3 = st.columns(3)

with col1:
    y2_label = st.selectbox("Год поступления (2)", list(YEARS.keys()), key="d2_y")
    y2 = YEARS[y2_label]

with col2:
    dirs2 = load_directions_for_year(y2)
    if not dirs2:
        st.error("Не удалось получить направления за выбранный год.")
        st.stop()
    dir2_labels = [o.label for o in dirs2]
    dir2_label = st.selectbox("Направление 2", dir2_labels, key="d2_dir")
    dir2_opt = dirs2[dir2_labels.index(dir2_label)]
    up2 = dir2_opt.params["up"]

with col3:
    _, groups2, sems2 = load_groups_and_sems(up2, y2)
    if not groups2:
        st.warning("Для направления 2 нет групп.")
        st.stop()
    st.caption(f"Группы ({len(groups2)}): {', '.join(g.label for g in groups2)}")


# ------------------------------------------------------------
# 3. Общий семестр
# ------------------------------------------------------------
common_sems = sorted(set(o.label for o in sems1) & set(o.label for o in sems2))
if not common_sems:
    st.warning("У направлений нет общих семестров.")
    st.stop()

sem_label = st.selectbox("Семестр для сравнения", common_sems, key="d_sem")


# ------------------------------------------------------------
# 4. Загрузка данных
# ------------------------------------------------------------
with st.spinner("Загружаем данные направления 1…"):
    df1, meta1 = load_direction_data(
        up1, y1, groups1, sems1, [sem_label], dir1_label
    )
if df1.empty:
    st.error("Не удалось получить данные направления 1.")
    st.stop()

with st.spinner("Загружаем данные направления 2…"):
    df2, meta2 = load_direction_data(
        up2, y2, groups2, sems2, [sem_label], dir2_label
    )
if df2.empty:
    st.error("Не удалось получить данные направления 2.")
    st.stop()

subject_shorts_1 = [s["short"] for s in meta1]
subject_shorts_2 = [s["short"] for s in meta2]
common_subjects = [s for s in subject_shorts_1 if s in subject_shorts_2]


# ------------------------------------------------------------
# 5. ГРАФИКИ: Направление 1
# ------------------------------------------------------------
st.header("1. Средняя успеваемость направления 1")

col_a, col_b = st.columns(2)

with col_a:
    fig = px.histogram(
        df1, x="Сумма", nbins=20,
        title=f"Распределение суммарного балла — {dir1_label}",
        color_discrete_sequence=["#2E86DE"],
    )
    fig.update_layout(height=420)
    st.plotly_chart(fig, use_container_width=True)

with col_b:
    box = px.box(
        df1, y="Сумма", points="all",
        title=f"Boxplot суммарного балла — {dir1_label}",
        color_discrete_sequence=["#2E86DE"],
    )
    box.update_layout(height=420)
    st.plotly_chart(box, use_container_width=True)

subj_means_1 = df1[subject_shorts_1].mean().round(2).reset_index()
subj_means_1.columns = ["Предмет", "Средний балл"]
fig = px.bar(
    subj_means_1, x="Предмет", y="Средний балл",
    title=f"Средний балл по предметам — {dir1_label}",
    color_discrete_sequence=["#2E86DE"],
)
fig.update_layout(height=460)
st.plotly_chart(fig, use_container_width=True)

avg_total_1 = round(df1["Сумма"].mean(), 2)
median_total_1 = round(df1["Сумма"].median(), 2)
st.caption(
    f"Студентов: **{len(df1)}** | Средний суммарный балл: **{avg_total_1}** | "
    f"Медиана: **{median_total_1}**"
)


# ------------------------------------------------------------
# 6. ГРАФИКИ: Направление 1 vs Направление 2
# ------------------------------------------------------------
st.header("2. Сравнение направлений 1 и 2")

df_all = pd.concat([df1, df2], ignore_index=True)
df_all["Направление"] = [dir1_label] * len(df1) + [dir2_label] * len(df2)

box = px.box(
    df_all, x="Направление", y="Сумма",
    points="all", color="Направление",
    title="Распределение суммарного балла: направления 1 vs 2",
)
box.update_layout(height=460, showlegend=False)
st.plotly_chart(box, use_container_width=True)

if common_subjects:
    means_1 = df1[common_subjects].mean().round(2).to_dict()
    means_2 = df2[common_subjects].mean().round(2).to_dict()

    rows = []
    for s in common_subjects:
        rows.append({"Предмет": s, "Направление 1": means_1.get(s),
                     "Направление 2": means_2.get(s)})
    cmp = pd.DataFrame(rows)

    fig = px.bar(
        cmp.melt(id_vars="Предмет", var_name="Направление",
                 value_name="Средний балл"),
        x="Предмет", y="Средний балл", color="Направление",
        barmode="group",
        title="Средний балл по общим предметам",
    )
    fig.update_layout(height=500)
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(cmp, use_container_width=True, hide_index=True)
else:
    st.info("У направлений нет общих предметов для сравнения по дисциплинам.")


# ------------------------------------------------------------
# 7. Сводная таблица
# ------------------------------------------------------------
st.header("Сводка по направлениям")

summary = pd.DataFrame([
    {
        "Направление": dir1_label,
        "Студентов": len(df1),
        "Средний балл": round(df1["Сумма"].mean(), 2),
        "Медиана": round(df1["Сумма"].median(), 2),
        "Макс": round(df1["Сумма"].max(), 2),
        "Мин": round(df1["Сумма"].min(), 2),
    },
    {
        "Направление": dir2_label,
        "Студентов": len(df2),
        "Средний балл": round(df2["Сумма"].mean(), 2),
        "Медиана": round(df2["Сумма"].median(), 2),
        "Макс": round(df2["Сумма"].max(), 2),
        "Мин": round(df2["Сумма"].min(), 2),
    },
])
st.dataframe(summary, use_container_width=True, hide_index=True)


# ------------------------------------------------------------
# 8. Отладка
# ------------------------------------------------------------
with st.expander("🔍 Отладка"):
    st.write("Направление 1:", dir1_label, "| up:", up1, "| y:", y1)
    st.write("Направление 2:", dir2_label, "| up:", up2, "| y:", y2)
    st.write("Семестр:", sem_label)
    st.write("Группы 1:", [g.label for g in groups1])
    st.write("Группы 2:", [g.label for g in groups2])
    st.write("Общие предметы:", common_subjects)
    st.write("dtypes df1:", df1.dtypes.to_dict())
