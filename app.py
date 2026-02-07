import streamlit as st
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="NBA Draft Board — Blend ADP", layout="wide")
st.title("🏀 NBA Fantasy Draft Board — Blend ADP")

# -------- Cache the PDF parse so it runs once per file --------
@st.cache_data(show_spinner=False)
def parse_pdf_cached(pdf_bytes: bytes) -> pd.DataFrame:
    """Parse Hashtag Basketball ADP PDF; return DataFrame [Player, Team, Pos, Blend, ADP_Rank]."""
    try:
        import pdfplumber
    except Exception:
        return pd.DataFrame(columns=["Player","Team","Pos","Blend","ADP_Rank"])

    def _clean(s: str) -> str:
        return re.sub(r"\s+", " ", s or "").strip()

    rows = []
    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            # 1) Try table extraction first
            for tbl in (page.extract_tables() or []):
                # Find header row that has BL or BLEND
                header_idx = None
                for i, r in enumerate(tbl[:3]):
                    joined = " ".join([_clean(c) for c in r if c])
                    if re.search(r"\bBL(END)?\b", joined, flags=re.I):
                        header_idx = i; break
                if header_idx is not None:
                    headers = [(_clean(c) or f"C{j}") for j, c in enumerate(tbl[header_idx])]
                    colmap = {h.lower(): j for j, h in enumerate(headers)}
                    # locate likely columns
                    blend_idx = None
                    for j, h in enumerate(headers):
                        if re.fullmatch(r"bl(end)?", _clean(h).lower()):
                            blend_idx = j; break
                    player_idx = colmap.get("player", 0)
                    team_idx   = colmap.get("team")
                    pos_idx    = colmap.get("pos")
                    for r in tbl[header_idx+1:]:
                        if not any(r): continue
                        def g(idx):
                            try: return r[idx]
                            except Exception: return None
                        player = _clean(g(player_idx))
                        if not player or len(player.split()) < 2: continue
                        team = _clean(g(team_idx)) if team_idx is not None else ""
                        pos  = _clean(g(pos_idx))  if pos_idx  is not None else ""
                        blend_raw = _clean(g(blend_idx)) if blend_idx is not None else ""
                        # numeric at end of cell
                        m = re.search(r"(\d+(?:\.\d+)?)", blend_raw) if blend_raw else None
                        blend = float(m.group(1)) if m else None
                        rows.append((player, team, pos, blend))

            # 2) Fallback: parse text lines (ignore URLs)
            text = page.extract_text() or ""
            for raw in text.splitlines():
                line = _clean(raw)
                if not line: 
                    continue
                # Skip obvious headers/footers/links
                if re.search(r"(https?://\S+)|(ADP Data|Hashtag Basketball|Season|Updated|\bBL(END)?\b)", line, flags=re.I):
                    continue
                # Last float on line as Blend
                m_end = re.search(r"(\d+(?:\.\d+)?)\s*$", line)
                if not m_end:
                    continue
                blend = float(m_end.group(1))
                body = re.sub(r"(\d+(?:\.\d+)?)\s*$", "", line).strip()
                body = re.sub(r"^\s*\d+[\.\-]?\s*", "", body)  # remove leading index like "12." or "12 -"

                # Try to peel team code (2-4 caps) at end; keep simple pos detection in parentheses
                pos = ""
                m_pos = re.search(r"\(([A-Z/]+)\)", body)
                if m_pos:
                    pos = m_pos.group(1)
                    body = (body[:m_pos.start()] + body[m_pos.end():]).strip()

                parts = body.split()
                team = ""
                if parts and re.fullmatch(r"[A-Z]{2,4}", parts[-1]):
                    team = parts[-1]; parts = parts[:-1]
                player = _clean(" ".join(parts))
                # Also skip anything that looks like a bare link that slipped through
                if re.match(r"^https?://", player, flags=re.I):
                    continue
                if len(player.split()) >= 2:
                    rows.append((player, team, pos, blend))

    if not rows:
        return pd.DataFrame(columns=["Player","Team","Pos","Blend","ADP_Rank"])

    df = pd.DataFrame(rows, columns=["Player","Team","Pos","Blend"])
    df["Blend"] = pd.to_numeric(df["Blend"], errors="coerce")
    # Rank by Blend (lower is earlier)
    df = df.sort_values(["Blend","Player"], ascending=[True, True], na_position="last")
    df = df.drop_duplicates(subset=["Player"], keep="first").reset_index(drop=True)
    # Keep top 300 by Blend
    df = df.head(300).copy()
    df["ADP_Rank"] = (df["Blend"].rank(method="first")).astype("Int64")
    return df[["Player","Team","Pos","Blend","ADP_Rank"]]

def parse_csv(file) -> pd.DataFrame:
    df = pd.read_csv(file)
    cols = {c.lower(): c for c in df.columns}
    def pick(*names):
        for n in names:
            if n in cols: return cols[n]
        return None
    col_player = pick("player","name","player_name")
    col_blend  = pick("blend","adp","avg_draft_position","avgdraftposition")
    col_team   = pick("team","tm")
    col_pos    = pick("pos","position")

    out = pd.DataFrame()
    out["Player"] = df[col_player] if col_player else df.iloc[:,0]
    out["Team"]   = df[col_team] if col_team else ""
    out["Pos"]    = df[col_pos] if col_pos else ""
    out["Blend"]  = pd.to_numeric(df[col_blend], errors="coerce") if col_blend else None
    out = out.sort_values(["Blend","Player"], ascending=[True,True], na_position="last").reset_index(drop=True)
    out = out.head(300).copy()
    out["ADP_Rank"] = (out["Blend"].rank(method="first")).astype("Int64")
    return out[["Player","Team","Pos","Blend","ADP_Rank"]]

# -------- Session State --------
if "players_df" not in st.session_state: st.session_state["players_df"] = None
if "drafted"    not in st.session_state: st.session_state["drafted"] = set()

# -------- Upload --------
st.markdown("### 1) Upload ADP list (PDF or CSV)")
c1, c2 = st.columns(2)
with c1:
    up_pdf = st.file_uploader("PDF (Hashtag Basketball ADP)", type=["pdf"])
with c2:
    up_csv = st.file_uploader("Or CSV with Player, Team, Pos, Blend", type=["csv"])

if up_pdf is not None and st.session_state["players_df"] is None:
    st.session_state["players_df"] = parse_pdf_cached(up_pdf.read())
elif up_csv is not None and st.session_state["players_df"] is None:
    st.session_state["players_df"] = parse_csv(up_csv)

df = st.session_state["players_df"]

if df is None or len(df) == 0:
    st.info("Upload a PDF or CSV to begin. We’ll rank by **Blend** and keep the top 300.")
else:
    # Build Remaining and Drafted
    remaining_df = df[~df["Player"].isin(st.session_state["drafted"])].copy()
    drafted_df   = df[df["Player"].isin(st.session_state["drafted"])].copy()

    # ---- Editable "Draft" checkbox column on the Remaining table ----
    st.markdown("### 2) Remaining Players")
    remaining_df = remaining_df.sort_values(["Blend","Player"], ascending=[True,True]).reset_index(drop=True)
    remaining_df["Draft"] = False  # temp checkbox column (not stored)
    edited = st.data_editor(
        remaining_df[["Draft","ADP_Rank","Player","Team","Pos","Blend"]],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Draft": st.column_config.CheckboxColumn("Draft"),
            "ADP_Rank": st.column_config.NumberColumn("ADP Rank"),
            "Player": st.column_config.TextColumn("Player"),
            "Team": st.column_config.TextColumn("Team"),
            "Pos": st.column_config.TextColumn("Pos"),
            "Blend": st.column_config.NumberColumn("Blend (lower = earlier)"),
        },
        num_rows="fixed",
        key="remaining_editor"
    )

    # Button to move all checked rows → Drafted
    to_draft = edited.loc[edited["Draft"] == True, "Player"].tolist()
    if st.button(f"✅ Move {len(to_draft)} selected to Drafted", type="primary", disabled=(len(to_draft)==0)):
        st.session_state["drafted"].update(to_draft)
        st.rerun()

    # ---- Drafted table (read-only) ----
    st.markdown("### 3) Drafted Players")
    drafted_df = drafted_df.sort_values(["ADP_Rank","Player"], ascending=[True,True]).reset_index(drop=True)
    st.dataframe(
        drafted_df[["ADP_Rank","Player","Team","Pos","Blend"]],
        use_container_width=True,
        hide_index=True
    )

    # ---- Quick actions ----
    cex1, cex2, cex3 = st.columns(3)
    with cex1:
        st.download_button("⬇️ Export Remaining (CSV)",
            remaining_df.drop(columns=["Draft"]).to_csv(index=False).encode(),
            "remaining_players.csv","text/csv"
        )
    with cex2:
        st.download_button("⬇️ Export Drafted (CSV)",
            drafted_df.to_csv(index=False).encode(),
            "drafted_players.csv","text/csv"
        )
    with cex3:
        if st.button("🧹 Reset Drafted"):
            st.session_state["drafted"] = set()
            st.rerun()
