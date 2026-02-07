
# NBA Draft Board — Blend ADP (Local)

This Streamlit app lets you upload a **Hashtag Basketball ADP** PDF (or CSV), extracts the **Blend** values, sorts players from **ADP 1..N (lowest Blend first)**, and gives you a **Drafted** checkbox to mark picks as they happen. You can filter, search, and export remaining players during the draft.

> If the PDF structure is unusual, export a CSV from the site and upload it. The app accepts CSV with columns like: `Player, Team, Pos, Blend`.

## Quick Start

1. **Create & activate a virtual environment** (recommended).  
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the app:
   ```bash
   streamlit run app.py
   ```
4. In the sidebar, upload your **PDF** (preferred) *or* a **CSV**. The app assigns ADP ranks by **Blend** and shows a live-updating board.

## Tips
- You can **download a snapshot** of your board and **reload** it later (keeps your Drafted checkboxes).
- Use **Search**, **Team**, **Pos**, and **Max ADP Rank** to keep only the pool you care about.
- Remaining/Drafted/Full board **CSV exports** are available at any time.
