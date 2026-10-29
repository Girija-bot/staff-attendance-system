
import os
import sqlite3
from pathlib import Path
from datetime import date, time

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load the Neon connection from the .env file beside this script.
folder = Path(__file__).parent
load_dotenv(folder / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is missing from .env.")

# Use the installed psycopg 3 driver.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace(
        "postgres://", "postgresql+psycopg://", 1
    )
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace(
        "postgresql://", "postgresql+psycopg://", 1
    )

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

if engine.dialect.name != "postgresql":
    raise RuntimeError("Stopped: database is not PostgreSQL.")

main_file = folder / "attendance.db"
backup_file = folder / "attendance_backup_2026-10-28.db"


def read_table(db_path, table):
    with sqlite3.connect(db_path) as con:
        con.row_factory = sqlite3.Row
        return [
            dict(row)
            for row in con.execute(f"SELECT * FROM {table}").fetchall()
        ]


if not main_file.exists() or not backup_file.exists():
    raise FileNotFoundError("A required SQLite database file is missing.")

staff_rows = read_table(main_file, "staff")
main_attendance = read_table(main_file, "attendance")
backup_staff = read_table(backup_file, "staff")
backup_attendance = read_table(backup_file, "attendance")

if len(staff_rows) != 3 or len(main_attendance) != 3:
    raise RuntimeError("Unexpected record counts in attendance.db.")

if len(backup_attendance) != 2:
    raise RuntimeError("Unexpected record count in the backup.")

# Use backup staff IDs only to identify the names for review.
backup_staff_names = {
    row["id"]: row["name"] for row in backup_staff
}

with engine.begin() as conn:
    # Stop if the main Neon tables already contain data.
    staff_count = conn.execute(
        text("SELECT COUNT(*) FROM staff")
    ).scalar_one()

    attendance_count = conn.execute(
        text("SELECT COUNT(*) FROM attendance")
    ).scalar_one()

    if staff_count != 0 or attendance_count != 0:
        raise RuntimeError(
            f"Stopped safely: Neon has {staff_count} staff and "
            f"{attendance_count} attendance records. Nothing imported."
        )

    # Keep backup entries in a separate review table.
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS attendance_import_review (
            id BIGSERIAL PRIMARY KEY,
            original_staff_id INTEGER,
            staff_name VARCHAR(255),
            work_date DATE,
            status VARCHAR(100),
            start_time TIME,
            end_time TIME,
            notes TEXT,
            source_file VARCHAR(255)
        )
    """))

    review_count = conn.execute(
        text("SELECT COUNT(*) FROM attendance_import_review")
    ).scalar_one()

    if review_count != 0:
        raise RuntimeError(
            f"Stopped safely: review table already has {review_count} "
            "records. Nothing imported."
        )

    # Import the three selected staff members.
    staff_id_map = {}

    for staff in staff_rows:
        result = conn.execute(text("""
            INSERT INTO staff
                (name, category, partita_iva, email,
                 codice_fiscale, telefono, active)
            VALUES
                (:name, :category, :partita_iva, :email,
                 :codice_fiscale, :telefono, :active)
            RETURNING id
        """), {
            "name": staff["name"],
            "category": staff["category"],
            "partita_iva": staff.get("partita_iva"),
            "email": staff.get("email"),
            "codice_fiscale": staff.get("codice_fiscale"),
            "telefono": staff.get("telefono"),
            "active": staff.get("active", 1),
        })

        staff_id_map[staff["id"]] = result.scalar_one()

    # Import the three main attendance records.
    for record in main_attendance:
        conn.execute(text("""
            INSERT INTO attendance
                (staff_id, work_date, status, start_time, end_time, notes)
            VALUES
                (:staff_id, :work_date, :status, :start_time, :end_time, :notes)
        """), {
            "staff_id": staff_id_map[record["staff_id"]],
            "work_date": date.fromisoformat(str(record["work_date"])),
            "status": record["status"],
            "start_time": time.fromisoformat(str(record["start_time"])),
            "end_time": (
                time.fromisoformat(str(record["end_time"]))
                if record.get("end_time") else None
            ),
            "notes": record.get("notes") or "",
        })

    # Preserve both backup entries separately for comparison.
    for record in backup_attendance:
        conn.execute(text("""
            INSERT INTO attendance_import_review
                (original_staff_id, staff_name, work_date, status,
                 start_time, end_time, notes, source_file)
            VALUES
                (:original_staff_id, :staff_name, :work_date, :status,
                 :start_time, :end_time, :notes, :source_file)
        """), {
            "original_staff_id": record["staff_id"],
            "staff_name": backup_staff_names.get(
                record["staff_id"], "Unknown"
            ),
            "work_date": date.fromisoformat(str(record["work_date"])),
            "status": record["status"],
            "start_time": time.fromisoformat(str(record["start_time"])),
            "end_time": (
                time.fromisoformat(str(record["end_time"]))
                if record.get("end_time") else None
            ),
            "notes": record.get("notes") or "",
            "source_file": backup_file.name,
        })

# Print counts after the transaction commits.
with engine.connect() as conn:
    final_staff = conn.execute(
        text("SELECT COUNT(*) FROM staff")
    ).scalar_one()
    final_attendance = conn.execute(
        text("SELECT COUNT(*) FROM attendance")
    ).scalar_one()
    final_review = conn.execute(
        text("SELECT COUNT(*) FROM attendance_import_review")
    ).scalar_one()

print("Import completed successfully.")
print("Staff records:", final_staff)
print("Main attendance records:", final_attendance)
print("Backup records saved for review:", final_review)
