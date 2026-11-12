# Winnings Dashboard

A Streamlit dashboard for the **Gambling Pool** Google Sheet. It reads the sheet live, so new rows appear the next time you open the page (data is cached for 60 seconds, and the **↻ Refresh data** button forces a re-pull).

## Run it on your computer

```bash
pip install -r requirements.txt
streamlit run app.py
```

It opens at http://localhost:8501.

## Put it online (free, open it from any device)

1. Create a GitHub repo and upload this folder's files, including `.streamlit/config.toml`.
2. Go to https://share.streamlit.io, sign in with GitHub, click **Create app**, choose the repo, and set the main file to `app.py`.
3. Deploy. You get a `*.streamlit.app` link.

Note that a Streamlit Cloud app is public by default. To keep it private, open the app's **Settings → Sharing** and limit viewers to your own email.

## Requirements for the sheet

- It must stay shared as **Anyone with the link → Viewer**. Otherwise the app shows an error asking you to fix the sharing.
- The app reads the first tab (`Sheet1`) and uses these columns: `Date`, `Opponent`, `Win` (Win / Loss / Broke Even), `Amount`, `AJD Amount`.
- `AJD Amount` (the signed amount) is what the app totals. If that cell is blank, the amount is worked out from `Win` + `Amount`.
- Opponent names are case-normalized, so `david` and `David` count as the same person.
- Rows without a date are always included in the all-time totals. Uncheck **Include undated** to see only the bets inside the chosen date range.

## Using a different sheet or tab

Set the `SHEET_ID` and `SHEET_GID` environment variables. `SHEET_GID` is the number after `gid=` in the tab's URL.
