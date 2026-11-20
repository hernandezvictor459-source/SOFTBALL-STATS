import sqlite3
from pathlib import Path
from datetime import date
import pandas as pd
import streamlit as st
import plotly.express as px

DB_PATH = Path(__file__).with_name("softball_stats.db")

st.set_page_config(
    page_title="Softball Stats",
    page_icon="🥎",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------- DATABASE ----------
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            jersey_number TEXT,
            position TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY(team_id) REFERENCES teams(id),
            UNIQUE(team_id, name)
        );

        CREATE TABLE IF NOT EXISTS games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_date TEXT NOT NULL,
            home_team_id INTEGER NOT NULL,
            away_team_id INTEGER NOT NULL,
            innings INTEGER NOT NULL DEFAULT 7,
            status TEXT NOT NULL DEFAULT 'En curso',
            notes TEXT,
            FOREIGN KEY(home_team_id) REFERENCES teams(id),
            FOREIGN KEY(away_team_id) REFERENCES teams(id)
        );

        CREATE TABLE IF NOT EXISTS plays (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id INTEGER NOT NULL,
            batting_team_id INTEGER NOT NULL,
            inning INTEGER NOT NULL,
            player_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            runs_scored INTEGER NOT NULL DEFAULT 0,
            rbi INTEGER NOT NULL DEFAULT 0,
            stolen_bases INTEGER NOT NULL DEFAULT 0,
            outs_recorded INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(game_id) REFERENCES games(id) ON DELETE CASCADE,
            FOREIGN KEY(batting_team_id) REFERENCES teams(id),
            FOREIGN KEY(player_id) REFERENCES players(id)
        );
        """)
        conn.commit()

init_db()

# ---------- DATA HELPERS ----------
def read_df(query, params=()):
    with get_conn() as conn:
        return pd.read_sql_query(query, conn, params=params)

def team_options():
    df = read_df("SELECT id, name FROM teams ORDER BY name")
    return df

def player_options(team_id):
    return read_df(
        "SELECT id, name, jersey_number, position FROM players "
        "WHERE team_id=? AND active=1 ORDER BY name",
        (int(team_id),)
    )

def game_score(game_id, team_id):
    df = read_df(
        "SELECT COALESCE(SUM(runs_scored),0) AS runs FROM plays "
        "WHERE game_id=? AND batting_team_id=?",
        (int(game_id), int(team_id))
    )
    return int(df.iloc[0]["runs"])

def stat_totals(game_id=None):
    where = ""
    params = ()
    if game_id is not None:
        where = "WHERE pl.game_id=?"
        params = (int(game_id),)
    return read_df(f"""
        SELECT p.id AS player_id, p.name AS jugador, t.name AS equipo,
               COUNT(pl.id) AS apariciones,
               SUM(CASE WHEN pl.event_type IN
                   ('Sencillo','Doble','Triple','Jonrón') THEN 1 ELSE 0 END) AS hits,
               SUM(CASE WHEN pl.event_type IN
                   ('Sencillo','Doble','Triple','Jonrón','Ponche','Out por roletazo',
                    'Out por elevado','Llegó por error') THEN 1 ELSE 0 END) AS turnos,
               SUM(pl.runs_scored) AS carreras,
               SUM(pl.rbi) AS CE,
               SUM(pl.stolen_bases) AS BR,
               SUM(pl.outs_recorded) AS outs
        FROM plays pl
        JOIN players p ON p.id=pl.player_id
        JOIN teams t ON t.id=p.team_id
        {where}
        GROUP BY p.id, p.name, t.name
        ORDER BY t.name, p.name
    """, params)

# ---------- HEADER / SIDEBAR ----------
st.title("🥎 Softball Stats")
st.caption("Anotación jugada por jugada · Ambos equipos · Estadísticas históricas")

teams = team_options()
menu = st.sidebar.radio(
    "Navegación",
    ["Resumen", "Equipos y jugadores", "Crear partido", "Anotar jugadas", "Historial y estadísticas"],
)

if menu == "Resumen":
    st.subheader("Panel general")
    games = read_df("SELECT * FROM games ORDER BY game_date DESC, id DESC")
    players = read_df("SELECT * FROM players WHERE active=1")
    plays = read_df("SELECT * FROM plays")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Partidos", len(games))
    c2.metric("Jugadores activos", len(players))
    c3.metric("Jugadas registradas", len(plays))
    c4.metric("Carreras anotadas", int(plays["runs_scored"].sum()) if not plays.empty else 0)

    if not games.empty:
        st.markdown("#### Partidos recientes")
        view = games.merge(
            teams.rename(columns={"id":"home_team_id", "name":"local"}),
            on="home_team_id", how="left"
        )
        view = view.merge(
            teams.rename(columns={"id":"away_team_id", "name":"visitante"}),
            on="away_team_id", how="left"
        )
        view["Marcador"] = view.apply(
            lambda r: f'{game_score(r["id"], r["away_team_id"])} - {game_score(r["id"], r["home_team_id"])}',
            axis=1
        )
        st.dataframe(
            view[["game_date", "visitante", "local", "Marcador", "status"]],
            use_container_width=True, hide_index=True
        )
    else:
        st.info("Todavía no hay partidos. Registra equipos y jugadores para comenzar.")

elif menu == "Equipos y jugadores":
    st.subheader("Administrar equipos y jugadores")
    left, right = st.columns(2)
    with left:
        st.markdown("#### Crear equipo")
        with st.form("team_form", clear_on_submit=True):
            team_name = st.text_input("Nombre del equipo")
            add_team = st.form_submit_button("Guardar equipo", use_container_width=True)
            if add_team:
                if not team_name.strip():
                    st.error("Escribe el nombre del equipo.")
                else:
                    try:
                        with get_conn() as conn:
                            conn.execute("INSERT INTO teams(name) VALUES (?)", (team_name.strip(),))
                            conn.commit()
                        st.success("Equipo guardado.")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("Ese equipo ya existe.")

    teams = team_options()
    with right:
        st.markdown("#### Registrar jugador")
        if teams.empty:
            st.info("Primero debes crear al menos un equipo.")
        else:
            with st.form("player_form", clear_on_submit=True):
                team_map = dict(zip(teams["name"], teams["id"]))
                selected_team_name = st.selectbox("Equipo", list(team_map.keys()))
                player_name = st.text_input("Nombre del jugador")
                jersey = st.text_input("Número")
                position = st.selectbox(
                    "Posición",
                    ["","Lanzador (P)","Receptor (C)","Primera base (1B)",
                     "Segunda base (2B)","Tercera base (3B)","Campo corto (SS)",
                     "Jardín izquierdo (LF)","Jardín central (CF)","Jardín derecho (RF)",
                     "Bateador designado (BD)","Otra"]
                )
                add_player = st.form_submit_button("Guardar jugador", use_container_width=True)
                if add_player:
                    if not player_name.strip():
                        st.error("Escribe el nombre del jugador.")
                    else:
                        try:
                            with get_conn() as conn:
                                conn.execute(
                                    "INSERT INTO players(team_id,name,jersey_number,position) VALUES (?,?,?,?)",
                                    (int(team_map[selected_team_name]), player_name.strip(), jersey.strip(), position)
                                )
                                conn.commit()
                            st.success("Jugador guardado.")
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("Ese jugador ya está registrado en ese equipo.")

    st.markdown("#### Plantillas registradas")
    roster = read_df("""
        SELECT p.id AS ID, p.team_id, t.name AS Equipo,
               p.jersey_number AS Número, p.name AS Jugador,
               p.position AS Posición
        FROM players p JOIN teams t ON t.id=p.team_id
        WHERE p.active=1 ORDER BY t.name, p.name
    """)
    st.dataframe(roster[["ID", "Equipo", "Número", "Jugador", "Posición"]], use_container_width=True, hide_index=True)

    st.markdown("#### Editar jugador")
    if not roster.empty:
        ids = roster["ID"].astype(int).tolist()
        pid = st.selectbox("Jugador que deseas editar", ids,
            format_func=lambda x: f'ID {x} · {roster.loc[roster.ID == x, "Jugador"].iloc[0]} ({roster.loc[roster.ID == x, "Equipo"].iloc[0]})')
        row = roster[roster.ID == pid].iloc[0]
        team_map_edit = dict(zip(teams["name"], teams["id"]))
        pos_options = ["", "Lanzador (P)", "Receptor (C)", "Primera base (1B)", "Segunda base (2B)", "Tercera base (3B)", "Campo corto (SS)", "Jardín izquierdo (LF)", "Jardín central (CF)", "Jardín derecho (RF)", "Bateador designado (BD)", "Otra"]
        old_pos = "" if pd.isna(row["Posición"]) else str(row["Posición"])
        with st.form("edit_player_form"):
            new_team = st.selectbox("Equipo", list(team_map_edit), index=list(team_map_edit.values()).index(int(row.team_id)))
            new_name = st.text_input("Nombre", str(row.Jugador))
            new_number = st.text_input("Número", "" if pd.isna(row["Número"]) else str(row["Número"]))
            new_pos = st.selectbox("Posición", pos_options, index=pos_options.index(old_pos) if old_pos in pos_options else 0)
            if st.form_submit_button("Guardar cambios del jugador"):
                try:
                    with get_conn() as conn:
                        conn.execute("UPDATE players SET team_id=?, name=?, jersey_number=?, position=? WHERE id=?", (int(team_map_edit[new_team]), new_name.strip(), new_number.strip(), new_pos, int(pid)))
                        conn.commit()
                    st.success("Jugador actualizado.")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("Ya existe un jugador con ese nombre en el equipo seleccionado.")

    st.markdown("#### Editar equipo")
    if not teams.empty:
        tid = st.selectbox("Equipo que deseas editar", teams["id"].astype(int).tolist(), format_func=lambda x: teams.loc[teams.id == x, "name"].iloc[0])
        old_team_name = teams.loc[teams.id == tid, "name"].iloc[0]
        with st.form("edit_team_form"):
            new_team_name = st.text_input("Nombre del equipo", old_team_name)
            if st.form_submit_button("Guardar cambios del equipo"):
                try:
                    with get_conn() as conn:
                        conn.execute("UPDATE teams SET name=? WHERE id=?", (new_team_name.strip(), int(tid)))
                        conn.commit()
                    st.success("Equipo actualizado.")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("Ya existe un equipo con ese nombre.")

elif menu == "Crear partido":
    st.subheader("Crear un partido")
    teams = team_options()
    if len(teams) < 2:
        st.warning("Necesitas registrar al menos dos equipos antes de crear un partido.")
    else:
        team_map = dict(zip(teams["name"], teams["id"]))
        names = list(team_map.keys())
        with st.form("game_form", clear_on_submit=True):
            game_date = st.date_input("Fecha del partido", value=date.today())
            away_name = st.selectbox("Equipo visitante", names, index=0)
            home_candidates = [n for n in names if n != away_name]
            home_name = st.selectbox("Equipo local", home_candidates)
            innings = st.selectbox("Entradas programadas", [5, 6, 7, 8, 9], index=2)
            notes = st.text_area("Notas (opcional)")
            create_game = st.form_submit_button("Crear partido", use_container_width=True)
            if create_game:
                with get_conn() as conn:
                    cur = conn.execute(
                        """INSERT INTO games(game_date,home_team_id,away_team_id,innings,notes)
                           VALUES (?,?,?,?,?)""",
                        (game_date.isoformat(), int(team_map[home_name]),
                         int(team_map[away_name]), int(innings), notes.strip())
                    )
                    conn.commit()
                    st.success(f"Partido #{cur.lastrowid} creado correctamente.")

elif menu == "Anotar jugadas":
    st.subheader("Anotación jugada por jugada")
    games = read_df("""
        SELECT g.id, g.game_date, g.innings, g.status,
               h.name AS local, a.name AS visitante,
               g.home_team_id, g.away_team_id
        FROM games g
        JOIN teams h ON h.id=g.home_team_id
        JOIN teams a ON a.id=g.away_team_id
        WHERE g.status='En curso'
        ORDER BY g.game_date DESC, g.id DESC
    """)
    if games.empty:
        st.info("No hay partidos en curso. Crea un partido primero.")
    else:
        game_labels = {
            f'#{r.id} · {r.visitante} vs {r.local} · {r.game_date}': int(r.id)
            for r in games.itertuples()
        }
        chosen_label = st.selectbox("Selecciona el partido", list(game_labels.keys()))
        game_id = game_labels[chosen_label]
        game = games[games["id"] == game_id].iloc[0]
        away_id, home_id = int(game["away_team_id"]), int(game["home_team_id"])
        away_runs, home_runs = game_score(game_id, away_id), game_score(game_id, home_id)

        score1, score2 = st.columns(2)
        score1.metric(f'Visitante · {game["visitante"]}', away_runs)
        score2.metric(f'Local · {game["local"]}', home_runs)

        team_choice = st.radio(
            "Equipo que está bateando",
            [f'Visitante: {game["visitante"]}', f'Local: {game["local"]}'],
            horizontal=True
        )
        batting_team_id = away_id if team_choice.startswith("Visitante") else home_id
        batting_team_name = game["visitante"] if batting_team_id == away_id else game["local"]
        roster = player_options(batting_team_id)

        if roster.empty:
            st.warning(f"Registra jugadores para {batting_team_name} antes de anotar.")
        else:
            player_labels = {
                f'{r.name} · #{r.jersey_number or "s/n"} · {r.position or "Sin posición"}': int(r.id)
                for r in roster.itertuples()
            }
            event_types = [
                "Sencillo", "Doble", "Triple", "Jonrón", "Base por bolas",
                "Golpeado", "Ponche", "Out por roletazo", "Out por elevado",
                "Llegó por error", "Toque de sacrificio", "Elevado de sacrificio",
                "Otro"
            ]
            with st.form("play_form", clear_on_submit=True):
                col1, col2 = st.columns(2)
                with col1:
                    inning = st.number_input("Entrada", min_value=1, max_value=20, value=1, step=1)
                    player_label = st.selectbox("Bateador", list(player_labels.keys()))
                    event_type = st.selectbox("Resultado de la jugada", event_types)
                with col2:
                    runs = st.number_input("Carreras anotadas en la jugada", min_value=0, max_value=4, value=0, step=1)
                    rbi = st.number_input("Carreras empujadas (CE)", min_value=0, max_value=4, value=0, step=1)
                    stolen = st.number_input("Bases robadas en la jugada", min_value=0, max_value=4, value=0, step=1)
                    outs = st.number_input("Outs registrados en la jugada", min_value=0, max_value=3, value=0, step=1)
                save_play = st.form_submit_button("Guardar jugada", use_container_width=True)
                if save_play:
                    with get_conn() as conn:
                        conn.execute("""
                            INSERT INTO plays
                            (game_id, batting_team_id, inning, player_id, event_type,
                             runs_scored, rbi, stolen_bases, outs_recorded)
                            VALUES (?,?,?,?,?,?,?,?,?)
                        """, (game_id, batting_team_id, int(inning),
                              int(player_labels[player_label]), event_type,
                              int(runs), int(rbi), int(stolen), int(outs)))
                        conn.commit()
                    st.success("Jugada guardada correctamente.")
                    st.rerun()

        st.markdown("#### Jugadas registradas en este partido")
        log = read_df("""
            SELECT pl.id, pl.inning AS Entrada, t.name AS Equipo,
                   p.name AS Bateador, pl.event_type AS Jugada,
                   pl.runs_scored AS Carreras, pl.rbi AS CE,
                   pl.stolen_bases AS BR, pl.outs_recorded AS Outs
            FROM plays pl
            JOIN teams t ON t.id=pl.batting_team_id
            JOIN players p ON p.id=pl.player_id
            WHERE pl.game_id=?
            ORDER BY pl.id DESC
        """, (game_id,))
        st.dataframe(log, use_container_width=True, hide_index=True)

        if not log.empty:
            st.markdown("#### Editar jugada registrada")
            play_ids = log["id"].astype(int).tolist()
            selected_play = st.selectbox("Selecciona la jugada", play_ids,
                format_func=lambda x: f'ID {x} · Entrada {log.loc[log.id == x, "Entrada"].iloc[0]} · {log.loc[log.id == x, "Bateador"].iloc[0]} · {log.loc[log.id == x, "Jugada"].iloc[0]}')
            old_play = read_df("SELECT * FROM plays WHERE id=?", (int(selected_play),)).iloc[0]
            edit_roster = player_options(int(old_play.batting_team_id))
            edit_player_labels = {f'{r.name} · #{r.jersey_number or "s/n"}': int(r.id) for r in edit_roster.itertuples()}
            old_label = next((k for k,v in edit_player_labels.items() if v == int(old_play.player_id)), list(edit_player_labels)[0])
            with st.form("edit_play_form"):
                e_inning = st.number_input("Entrada", min_value=1, max_value=20, value=int(old_play.inning))
                e_player = st.selectbox("Bateador", list(edit_player_labels), index=list(edit_player_labels).index(old_label))
                e_event = st.selectbox("Resultado", event_types, index=event_types.index(old_play.event_type) if old_play.event_type in event_types else 0)
                a,b,c,d = st.columns(4)
                e_runs = a.number_input("Carreras", min_value=0, max_value=4, value=int(old_play.runs_scored))
                e_rbi = b.number_input("CE", min_value=0, max_value=4, value=int(old_play.rbi))
                e_sb = c.number_input("BR", min_value=0, max_value=4, value=int(old_play.stolen_bases))
                e_outs = d.number_input("Outs", min_value=0, max_value=3, value=int(old_play.outs_recorded))
                if st.form_submit_button("Guardar corrección"):
                    with get_conn() as conn:
                        conn.execute("UPDATE plays SET inning=?, player_id=?, event_type=?, runs_scored=?, rbi=?, stolen_bases=?, outs_recorded=? WHERE id=?", (int(e_inning), int(edit_player_labels[e_player]), e_event, int(e_runs), int(e_rbi), int(e_sb), int(e_outs), int(selected_play)))
                        conn.commit()
                    st.success("Jugada corregida.")
                    st.rerun()

            delete_id = st.selectbox("Jugada que deseas eliminar", play_ids, key="delete_play_select")
            if st.button("Eliminar jugada seleccionada", type="secondary"):
                with get_conn() as conn:
                    conn.execute("DELETE FROM plays WHERE id=? AND game_id=?", (int(delete_id), game_id))
                    conn.commit()
                st.success("Jugada eliminada.")
                st.rerun()

        if st.button("Finalizar partido", type="primary"):
            with get_conn() as conn:
                conn.execute("UPDATE games SET status='Finalizado' WHERE id=?", (game_id,))
                conn.commit()
            st.success("Partido finalizado.")
            st.rerun()

elif menu == "Historial y estadísticas":
    st.subheader("Historial y estadísticas")
    games = read_df("""
        SELECT g.id, g.game_date, g.status, a.name AS Visitante, h.name AS Local,
               g.away_team_id, g.home_team_id
        FROM games g
        JOIN teams h ON h.id=g.home_team_id
        JOIN teams a ON a.id=g.away_team_id
        ORDER BY g.game_date DESC, g.id DESC
    """)
    if not games.empty:
        games["Resultado"] = games.apply(
            lambda r: f'{game_score(r["id"], r["away_team_id"])} - {game_score(r["id"], r["home_team_id"])}',
            axis=1
        )
        st.markdown("#### Partidos")
        st.dataframe(
            games[["game_date", "Visitante", "Local", "Resultado", "status"]],
            use_container_width=True, hide_index=True
        )

        st.markdown("#### Editar partido")
        game_ids = games["id"].astype(int).tolist()
        edit_gid = st.selectbox("Partido que deseas editar", game_ids,
            format_func=lambda x: f'#{x} · {games.loc[games.id == x, "Visitante"].iloc[0]} vs {games.loc[games.id == x, "Local"].iloc[0]}')
        game_row = read_df("SELECT * FROM games WHERE id=?", (int(edit_gid),)).iloc[0]
        all_teams = team_options()
        team_map_all = dict(zip(all_teams["name"], all_teams["id"]))
        team_names_all = list(team_map_all)
        away_old = all_teams.loc[all_teams.id == int(game_row.away_team_id), "name"].iloc[0]
        home_old = all_teams.loc[all_teams.id == int(game_row.home_team_id), "name"].iloc[0]
        with st.form("edit_game_form"):
            e_date = st.date_input("Fecha", value=date.fromisoformat(str(game_row.game_date)))
            e_away = st.selectbox("Visitante", team_names_all, index=team_names_all.index(away_old))
            home_options = [x for x in team_names_all if x != e_away]
            home_default = home_old if home_old in home_options else home_options[0]
            e_home = st.selectbox("Local", home_options, index=home_options.index(home_default))
            inning_options = [5,6,7,8,9]
            e_innings = st.selectbox("Entradas programadas", inning_options, index=inning_options.index(int(game_row.innings)) if int(game_row.innings) in inning_options else 2)
            statuses = ["En curso", "Finalizado"]
            e_status = st.selectbox("Estado", statuses, index=statuses.index(game_row.status) if game_row.status in statuses else 0)
            e_notes = st.text_area("Notas", value=game_row.notes or "")
            if st.form_submit_button("Guardar cambios del partido"):
                with get_conn() as conn:
                    conn.execute("UPDATE games SET game_date=?, away_team_id=?, home_team_id=?, innings=?, status=?, notes=? WHERE id=?", (e_date.isoformat(), int(team_map_all[e_away]), int(team_map_all[e_home]), int(e_innings), e_status, e_notes.strip(), int(edit_gid)))
                    conn.commit()
                st.success("Partido actualizado.")
                st.rerun()

        selected_game = st.selectbox(
            "Filtrar estadísticas por partido",
            ["Toda la temporada"] + [
                f'#{r.id} · {r.Visitante} vs {r.Local} · {r.game_date}'
                for r in games.itertuples()
            ]
        )
        if selected_game == "Toda la temporada":
            stats = stat_totals()
        else:
            selected_id = int(selected_game.split("·")[0].replace("#","").strip())
            stats = stat_totals(selected_id)
    else:
        st.info("Todavía no hay partidos registrados.")
        stats = pd.DataFrame()

    st.markdown("#### Estadísticas individuales")
    if not stats.empty:
        stats = stats.fillna(0)
        stats["AVG (referencial)"] = stats.apply(
            lambda r: round(r["hits"] / r["turnos"], 3) if r["turnos"] else 0,
            axis=1000
        )
        st.dataframe(stats, use_container_width=True, hide_index=True)
        chart = px.bar(stats, x="jugador", y="CE", color="equipo",
                       title="Carreras empujadas por jugador")
        st.plotly_chart(chart, use_container_width=True)
        st.download_button(
            "Descargar estadísticas CSV",
            stats.to_csv(index=False).encode("utf-8-sig"),
            "estadisticas_softball.csv",
            "text/csv"
        )
    else:
        st.info("Las estadísticas aparecerán cuando registres jugadas.")

st.sidebar.divider()
st.sidebar.caption("Versión inicial · Los datos se guardan en softball_stats.db")
