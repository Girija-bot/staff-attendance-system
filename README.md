# Staff Attendance Management System

A small Streamlit app for recording daily attendance and exporting weekly reports.

## Features
- Three staff categories: officially registered, not officially registered, and on-call staff.
- Add, deactivate, and reactivate staff.
- One attendance record per staff member per date; re-saving updates the record.
- Attendance statuses, start/end times, optional notes.
- Weekly summary by category and status.
- CSV and Excel downloads.
- SQLite database for local use; PostgreSQL for a persistent hosted deployment.

## 1. Run locally in VS Code (Windows)

1. Install Python 3.12 from https://www.python.org/downloads/ and select **Add Python to PATH**.
2. Extract this ZIP and open the `staff_attendance_system` folder in VS Code.
3. Open **Terminal → New Terminal**.
4. Run these commands:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

If PowerShell blocks activation, run this once in that terminal and retry activation:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

The app opens in your browser. Your local records are stored in `attendance.db` in this folder. Back up that file regularly. Do not delete it if you need your records.

## 2. Deploy online for free

**Important:** do not rely on SQLite (`attendance.db`) for a hosted app. Free app hosts can restart or replace local files. Use a hosted PostgreSQL database so daily records persist.

1. Create a free PostgreSQL project with a provider that currently offers a free tier (for example, Supabase; free-tier limits and availability can change).
2. Copy its PostgreSQL connection string/URI. Use the provider's connection pooler URL if its instructions recommend that for app hosting. Keep the password private.
3. Upload this project to a **private GitHub repository**. Do not upload database passwords or secrets.
4. Deploy `app.py` as a Streamlit app using Streamlit Community Cloud (check current free-tier availability and limits).
5. In the app's deployment settings, add a secret/environment variable named `DATABASE_URL` with your PostgreSQL connection string. For example:

```text
DATABASE_URL = "postgresql+psycopg://USER:PASSWORD@HOST:PORT/DATABASE"
```

If your provider gives a URI starting with `postgres://` or `postgresql://`, change the prefix to `postgresql+psycopg://` and keep the rest of the URI as provided. URL-encode special characters in the password if needed.
6. Deploy/redeploy. The app creates the required tables automatically on first start.

**Test before using for real:** add a test staff member, record attendance, download a report, restart/reopen the app, and confirm the record is still present.

## Data protection and responsible use
- This app is a basic attendance register, not payroll, time-clock verification, or legal advice.
- Restrict access to the app and database. A public URL without login protection is not suitable for confidential employee data. Use the host's access controls or add authentication before entering real records.
- Collect only information you need, keep backups, and follow applicable employment, privacy, and recordkeeping rules.
- The category “Not officially registered” is provided because it was requested, but this software does not register employment or make unregistered work lawful. Do not use it to conceal employment or avoid legal obligations.
- Staff names and attendance records are personal data. Use a private repository and secure database credentials.

## Notes
- One staff member can have only one attendance entry per date. If split shifts are common, this design will need to be expanded to support multiple shifts per day.
- Weekly reports run Monday through Sunday.
- Hours are calculated from start and end times; overnight shifts are supported. Breaks are not deducted.
