import time
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

import parser as p

st.title("🎓 Целевой студент vs направления")


# ============================================================
# ГОДЫ
# ============================================================
YEARS = {
    "2026 (1 курс)": "2026",
    "2025 (2 курс)": "2025",
    "2024 (3 курс)": "2024",
    "2023 (4 курс)": "2023",
}

# Колонки, которые НЕ являются баллами — их не трогаем.
STRING_COLS = {"Группа", "№", "ФИО", "stud_id", "Семестр"}


# ------------------------------------------------------------
# Утилиты
# ------------------------------------------------------------
def _finalize_df(df: pd.DataFrame) -> pd.DataFrame:
    """Приводит все колонки-баллы к числу, строковые оставляет строками."""
    if df.empty:
        return df
    for c in df.columns:
        if c in STRING_COLS:
            df[c] = df[c].astype(str)
        else:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


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


@st.cache_data(ttl=600, show_spinner=False)
def load_one_group(up_id, year, g_id, s_id, group_name):
    html = load_group_html(up_id, year, g_id, s_id)
    meta = p.parse_subjects(html)
    rows = p.parse_students(html, group_name=group_name)
    df = pd.DataFrame(rows)
    return _finalize_df(df), meta


def load_direction_data(up_id, year, groups, sems, sem_label, direction_label,
                        progress_prefix=""):
    sem_options = {o.label: o for o in sems}
    s_opt = sem_options.get(sem_label)
    s_id = s_opt.params.get("s") if s_opt else None

    all_rows = []
    subject_meta = None
    total = len(groups)
    progress = st.progress(0.0, text=f"Загружаем «{direction_label}»…")

    for i, gopt in enumerate(groups):
        progress.progress((i + 1) / total, text=f"{progress_prefix}{gopt.label}")
        try:
            html = load_group_html(up_id, year, gopt.params.get("g"), s_id)
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
    return _finalize_df(df), subject_meta


# ------------------------------------------------------------
# 1. Целевой студент (направление 1)
# ------------------------------------------------------------
st.markdown("### 🎯 Направление 1 — целевое")

col1, col2, col3 = st.columns(3)

with col1:
    y1_label = st.selectbox("Год поступления (1)", list(YEARS.keys()), key="s2_y1")
    y1 = YEARS[y1_label]

with col2:
    dirs1 = load_directions_for_year(y1)
    if not dirs1:
        st.error("Не удалось получить направления за выбранный год.")
        st.stop()
    dir1_labels = [o.label for o in dirs1]
    dir1_label = st.selectbox("Направление 1", dir1_labels, key="s2_dir1")
    dir1_opt = dirs1[dir1_labels.index(dir1_label)]
    up1 = dir1_opt.params["up"]

with col3:
    _, groups1, sems1 = load_groups_and_sems(up1, y1)
    if not groups1:
        st.warning("Для направления 1 нет групп.")
        st.stop()
    group1_labels = [g.label for g in groups1]
    group1_label = st.selectbox("Группа целевого студента", group1_labels, key="s2_g1")

group1_opt = next(g for g in groups1 if g.label == group1_label)
sem_labels_1 = [o.label for o in sems1]
sem_label_1 = st.selectbox("Семестр (направление 1)", sem_labels_1,
                            index=len(sem_labels_1) - 1, key="s2_sem1")
sem1_opt = next(o for o in sems1 if o.label == sem_label_1)

with st.spinner("Загружаем целевую группу…"):
    df_target_group, _ = load_one_group(
        up1, y1, group1_opt.params.get("g"), sem1_opt.params.get("s"), group1_label
    )

if df_target_group.empty:
    st.error("Не удалось получить список студентов целевой группы.")
    st.stop()

student_names = df_target_group["ФИО"].dropna().tolist()
target_name = st.selectbox("ФИО целевого студента", student_names, key="s2_student")
row_target = df_target_group[df_target_group["ФИО"] == target_name].iloc[0]


# ------------------------------------------------------------
# 2. Направление 2
# ------------------------------------------------------------
st.markdown("### 🔄 Направление 2 — для сравнения")

col1, col2, col3 = st.columns(3)

with col1:
    y2_label = st.selectbox("Год поступления (2)", list(YEARS.keys()), key="s2_y2")
    y2 = YEARS[y2_label]

with col2:
    dirs2 = load_directions_for_year(y2)
    if not dirs2:
        st.error("Не удалось получить направления за выбранный год.")
        st.stop()
    dir2_labels = [o.label for o in dirs2]
    dir2_label = st.selectbox("Направление 2", dir2_labels, key="s2_dir2")
    dir2_opt = dirs2[dir2_labels.index(dir2_label)]
    up2 = dir2_opt.params["up"]

with col3:
    _, groups2, sems2 = load_groups_and_sems(up2, y2)
    if not groups2:
        st.warning("Для направления 2 нет групп.")
        st.stop()
    sem_labels_2 = [o.label for o in sems2]
    sem_label_2 = st.selectbox("Семестр (направление 2)", sem_labels_2,
                                index=len(sem_labels_2) - 1, key="s2_sem2")


# ------------------------------------------------------------
# 3. Загружаем направления
# ------------------------------------------------------------
with st.spinner("Загружаем направление 1…"):
    df1, meta1 = load_direction_data(
        up1, y1, groups1, sems1, sem_label_1, dir1_label, progress_prefix="Н1: "
    )
if df1.empty:
    st.error("Данные направления 1 не получены.")
    st.stop()

with st.spinner("Загружаем направление 2…"):
    df2, meta2 = load_direction_data(
        up2, y2, groups2, sems2, sem_label_2, dir2_label, progress_prefix="Н2: "
    )
if df2.empty:
    st.error("Данные направления 2 не получены.")
    st.stop()

subject_shorts_1 = [s["short"] for s in meta1]
subject_shorts_2 = [s["short"] for s in meta2]
common_subjects = [s for s in subject_shorts_1 if s in subject_shorts_2]


# ------------------------------------------------------------
# 4. Сводка
# ------------------------------------------------------------
st.subheader("Сводка")

target_total = row_target.get("Сумма", pd.NA)
target_total = float(target_total) if pd.notna(target_total) else 0

avg1 = round(df1["Сумма"].mean(), 2)
avg2 = round(df2["Сумма"].mean(), 2)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Суммарный балл студента", f"{target_total:.2f}")
c2.metric("Средний по направлению 1", f"{avg1:.2f}",
          delta=f"{target_total - avg1:+.2f}")
c3.metric("Средний по направлению 2", f"{avg2:.2f}",
          delta=f"{target_total - avg2:+.2f}")
c4.metric("Студентов", f"Н1: {len(df1)} / Н2: {len(df2)}")


# ------------------------------------------------------------
# 5. ГРАФИК 3: Студент vs направление 1
# ------------------------------------------------------------
st.header("3. Целевой студент vs средняя по направлению 1")

means_1 = df1[subject_shorts_1].mean().round(2).to_dict()
target_by_subj = {s: row_target.get(s, pd.NA) for s in subject_shorts_1}

df3 = pd.DataFrame({
    "Предмет": subject_shorts_1,
    "Студент": [float(target_by_subj[s]) if pd.notna(target_by_subj[s]) else None
                for s in subject_shorts_1],
    "Средний по направлению 1": [means_1.get(s) for s in subject_shorts_1],
})

fig3 = px.bar(
    df3.melt(id_vars="Предмет", var_name="Серия", value_name="Балл"),
    x="Предмет", y="Балл", color="Серия", barmode="group",
    title=f"{target_name} vs средний по «{dir1_label}»",
)
fig3.update_layout(height=500)
st.plotly_chart(fig3, use_container_width=True)

fig_radar_3 = go.Figure()
fig_radar_3.add_trace(go.Scatterpolar(
    r=[float(target_by_subj[s]) if pd.notna(target_by_subj[s]) else 0
       for s in subject_shorts_1],
    theta=subject_shorts_1, fill="toself",
    name=target_name, line_color="#2E86DE",
))
fig_radar_3.add_trace(go.Scatterpolar(
    r=[means_1.get(s, 0) for s in subject_shorts_1],
    theta=subject_shorts_1, fill="toself",
    name="Средний по направлению 1", line_color="#BDC3C7",
))
fig_radar_3.update_layout(
    polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
    height=500,
    title="Профиль: студент vs средний по направлению 1",
)
st.plotly_chart(fig_radar_3, use_container_width=True)


# ------------------------------------------------------------
# 6. ГРАФИК 4: Студент vs направление 2
# ------------------------------------------------------------
st.header("4. Целевой студент vs средняя по направлению 2")

if not common_subjects:
    st.info(
        "У направлений нет общих предметов (по коротким именам). "
        "Сравнение по предметам недоступно."
    )
else:
    means_2 = df2[common_subjects].mean().round(2).to_dict()
    target_common = {s: row_target.get(s, pd.NA) for s in common_subjects}

    df4 = pd.DataFrame({
        "Предмет": common_subjects,
        "Студент": [float(target_common[s]) if pd.notna(target_common[s]) else None
                    for s in common_subjects],
        "Средний по направлению 2": [means_2.get(s) for s in common_subjects],
    })

    fig4 = px.bar(
        df4.melt(id_vars="Предмет", var_name="Серия", value_name="Балл"),
        x="Предмет", y="Балл", color="Серия", barmode="group",
        title=f"{target_name} vs средний по «{dir2_label}» (по общим предметам)",
    )
    fig4.update_layout(height=500)
    st.plotly_chart(fig4, use_container_width=True)

    fig_radar_4 = go.Figure()
    fig_radar_4.add_trace(go.Scatterpolar(
        r=[float(target_common[s]) if pd.notna(target_common[s]) else 0
           for s in common_subjects],
        theta=common_subjects, fill="toself",
        name=target_name, line_color="#2E86DE",
    ))
    fig_radar_4.add_trace(go.Scatterpolar(
        r=[means_2.get(s, 0) for s in common_subjects],
        theta=common_subjects, fill="toself",
        name="Средний по направлению 2", line_color="#EE5A24",
    ))
    fig_radar_4.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        height=500,
        title="Профиль: студент vs средний по направлению 2",
    )
    st.plotly_chart(fig_radar_4, use_container_width=True)


# ------------------------------------------------------------
# 7. Отладка
# ------------------------------------------------------------
with st.expander("🔍 Отладка"):
    st.write("Целевой студент:", target_name)
    st.write("Направление 1:", dir1_label, "| up:", up1, "| y:", y1)
    st.write("Направление 2:", dir2_label, "| up:", up2, "| y:", y2)
    st.write("Семестр 1:", sem_label_1, "| Семестр 2:", sem_label_2)
    st.write("Предметы направления 1:", subject_shorts_1)
    st.write("Предметы направления 2:", subject_shorts_2)
    st.write("Общие предметы:", common_subjects)
    st.write("dtypes df1:", df1.dtypes.to_dict())
    st.write("dtypes df2:", df2.dtypes.to_dict())
