
import os
import math
import uuid
import boto3
from botocore.config import Config
from datetime import date, datetime, time
from io import BytesIO

from dotenv import load_dotenv

load_dotenv()

import bcrypt
import pandas as pd
import streamlit as st

from sqlalchemy import (
    create_engine, text, Integer, String, Date, Time, DateTime, Float,
    ForeignKey, UniqueConstraint, inspect
)
from sqlalchemy.orm import (
    DeclarativeBase, Mapped, mapped_column, sessionmaker
)


# ==================================================
# PAGE CONFIGURATION
# ==================================================

st.set_page_config(
    page_title="Staff Attendance | Presenze del personale",
    page_icon="📋",
    layout="wide"
)


# ==================================================
# LOGIN
# ==================================================

def verify_password(password, stored_hash):
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"),
            stored_hash.encode("utf-8")
        )
    except (ValueError, TypeError, AttributeError):
        return False


USERS = {
    "Girija": os.getenv("GIRIJA_PASSWORD_HASH", ""),
    "Signor Paolo": os.getenv("PAOLO_PASSWORD_HASH", ""),
}

if "authenticated_user" not in st.session_state:
    st.session_state.authenticated_user = None

if st.session_state.authenticated_user not in USERS:

    st.title("🔐 Staff Attendance Login")
    st.caption("Please sign in to access the application.")

    if not all(USERS.values()):
        st.error(
            "Login is not configured. Please contact the administrator."
        )
        st.stop()

    with st.form("login_form"):

        username = st.selectbox(
            "Username",
            list(USERS.keys())
        )

        password = st.text_input(
            "Password",
            type="password"
        )

        login_clicked = st.form_submit_button(
            "Login",
            type="primary"
        )

        if login_clicked:

            if verify_password(password, USERS[username]):
                st.session_state.authenticated_user = username
                st.rerun()

            else:
                st.error("Incorrect password. Please try again.")

    st.stop()


# ==================================================
# DATABASE CONNECTION
# ==================================================

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///attendance.db"
)

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace(
        "postgres://",
        "postgresql+psycopg://",
        1
    )

elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace(
        "postgresql://",
        "postgresql+psycopg://",
        1
    )

connect_args = (
    {"check_same_thread": False}
    if DATABASE_URL.startswith("sqlite")
    else {}
)

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True
)

Session = sessionmaker(
    bind=engine,
    expire_on_commit=False
)


# ==================================================
# DATABASE MODELS
# ==================================================

class Base(DeclarativeBase):
    pass


class Staff(Base):

    __tablename__ = "staff"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    name: Mapped[str] = mapped_column(
        String(120),
        nullable=False
    )

    category: Mapped[str] = mapped_column(
        String(80),
        nullable=False
    )

    partita_iva: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True
    )

    codice_fiscale: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True
    )

    email: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True
    )

    phone: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True
    )

    identity_doc_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True
    )

    identity_doc_number: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    identity_doc_expiry: Mapped[date | None] = mapped_column(
        Date,
        nullable=True
    )

    active: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False
    )


class Attendance(Base):

    __tablename__ = "attendance"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    staff_id: Mapped[int] = mapped_column(
        ForeignKey("staff.id"),
        nullable=False
    )

    work_date: Mapped[date] = mapped_column(
        Date,
        nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="Present"
    )

    start_time: Mapped[time | None] = mapped_column(
        Time,
        nullable=True
    )

    end_time: Mapped[time | None] = mapped_column(
        Time,
        nullable=True
    )

    work_location: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True
    )

    notes: Mapped[str] = mapped_column(
        String(500),
        default=""
    )

    __table_args__ = (
        UniqueConstraint(
            "staff_id",
            "work_date",
            name="uq_staff_day"
        ),
    )


# Payment model: keep a snapshot so payment history remains available.
class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    # Nullable so payment history survives staff deletion.
    staff_id: Mapped[int | None] = mapped_column(
        ForeignKey("staff.id", ondelete="SET NULL"),
        nullable=True
    )

    # Keep a snapshot of the employee's details.
    staff_name: Mapped[str] = mapped_column(
        String(120),
        nullable=False
    )

    category: Mapped[str] = mapped_column(
        String(80),
        nullable=False
    )

    period_start: Mapped[date] = mapped_column(
        Date,
        nullable=False
    )

    period_end: Mapped[date] = mapped_column(
        Date,
        nullable=False
    )

    hours_worked: Mapped[float] = mapped_column(
        Float,
        default=0,
        nullable=False
    )

    work_locations: Mapped[str] = mapped_column(
        String(1000),
        default="",
        nullable=False
    )

    amount: Mapped[float] = mapped_column(
        Float,
        nullable=False
    )

    payment_date: Mapped[date] = mapped_column(
        Date,
        nullable=False
    )

    notes: Mapped[str] = mapped_column(
        String(500),
        default=""
    )



class StaffDocument(Base):
    """Metadata for a file stored in the private Neon Object Storage bucket."""

    __tablename__ = "staff_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    staff_id: Mapped[int] = mapped_column(
        ForeignKey("staff.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    original_filename: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    object_key: Mapped[str] = mapped_column(
        String(500), nullable=False, unique=True
    )
    content_type: Mapped[str] = mapped_column(
        String(100), nullable=False
    )
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    uploaded_by: Mapped[str] = mapped_column(
        String(80), nullable=False
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )


class StaffDocumentAccessLog(Base):
    """Records when an authenticated user is issued a document download link."""

    __tablename__ = "staff_document_access_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("staff_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    username: Mapped[str] = mapped_column(String(80), nullable=False)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    accessed_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )


# Create missing tables without deleting or replacing existing tables.
# This is intentionally after Payment is declared so SQLAlchemy registers it.
Base.metadata.create_all(engine)


# ==================================================
# PRIVATE STAFF DOCUMENT STORAGE
# ==================================================

DOCUMENT_BUCKET = os.getenv("NEON_STORAGE_BUCKET", "uploads")
MAX_DOCUMENT_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_DOCUMENT_TYPES = {
    ".pdf": ("application/pdf", lambda data: data.startswith(b"%PDF-")),
    ".jpg": ("image/jpeg", lambda data: data.startswith(b"\xff\xd8\xff")),
    ".jpeg": ("image/jpeg", lambda data: data.startswith(b"\xff\xd8\xff")),
    ".png": (
        "image/png",
        lambda data: data.startswith(b"\x89PNG\r\n\x1a\n")
    ),
}


def get_private_storage_client():
    """Create an S3-compatible client for the private Neon bucket."""
    required = [
        "AWS_ENDPOINT_URL_S3",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_REGION",
    ]
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError(
            "Private document storage is not configured. Missing: "
            + ", ".join(missing)
        )

    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        region_name=os.environ["AWS_REGION"],
        endpoint_url=os.environ["AWS_ENDPOINT_URL_S3"],
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            connect_timeout=10,
            read_timeout=30,
            retries={"max_attempts": 3, "mode": "standard"},
        ),
    )


def validate_staff_document(filename, content):
    """Allow only small PDF/JPEG/PNG files whose signatures match extensions."""
    safe_name = str(filename or "document").replace("\\", "/").split("/")[-1]
    safe_name = "".join(ch for ch in safe_name if ch.isprintable())[:255]
    extension = os.path.splitext(safe_name)[1].lower()

    if not safe_name or extension not in ALLOWED_DOCUMENT_TYPES:
        raise ValueError("Allowed file types: PDF, JPG, JPEG and PNG.")
    if not content:
        raise ValueError("The selected file is empty.")
    if len(content) > MAX_DOCUMENT_SIZE:
        raise ValueError("The maximum file size is 10 MB.")

    content_type, signature_check = ALLOWED_DOCUMENT_TYPES[extension]
    if not signature_check(content):
        raise ValueError(
            "The file content does not match its extension. Please select a valid document."
        )
    return safe_name, content_type


# ==================================================

staff_columns = {
    column["name"]
    for column in inspect(engine).get_columns("staff")
}

attendance_columns = {
    column["name"]
    for column in inspect(engine).get_columns("attendance")
}

staff_new_columns = {
    "partita_iva": "VARCHAR(30)",
    "codice_fiscale": "VARCHAR(20)",
    "email": "VARCHAR(150)",
    "phone": "VARCHAR(30)",
    "identity_doc_type": "VARCHAR(50)",
    "identity_doc_number": "VARCHAR(100)",
    "identity_doc_expiry": "DATE",
}

with engine.begin() as connection:

    for column_name, column_type in staff_new_columns.items():

        if column_name not in staff_columns:

            connection.execute(
                text(
                    f"ALTER TABLE staff ADD COLUMN "
                    f"{column_name} {column_type}"
                )
            )

    if "work_location" not in attendance_columns:

        connection.execute(
            text(
                "ALTER TABLE attendance "
                "ADD COLUMN work_location VARCHAR(150)"
            )
        )


# ==================================================
# STAFF CATEGORIES
# ==================================================

CATEGORIES = [
    "Officially registered",
    "Not officially registered",
    "On-call staff",
    "Personale a chiamata full-time",
    "Personale a chiamata part-time",
    "Personale a chiamata partita IVA",
]

CATEGORY_IT = {
    "Officially registered":
        "Personale regolarmente assunto",

    "Not officially registered":
        "Personale non regolarmente registrato",

    "On-call staff":
        "Personale a chiamata",

    "Personale a chiamata full-time":
        "Personale a chiamata full-time",

    "Personale a chiamata part-time":
        "Personale a chiamata part-time",

    "Personale a chiamata partita IVA":
        "Personale a chiamata partita IVA",
}


# ==================================================
# ATTENDANCE STATUSES
# ==================================================

STATUSES = [
    "Present",
    "Absent",
    "Leave",
    "Called in - attended",
    "Called in - did not attend",
]

STATUS_IT = {
    "Present": "Presente",
    "Absent": "Assente",
    "Leave": "Permesso / ferie",
    "Called in - attended": "Chiamato/a - presente",
    "Called in - did not attend": "Chiamato/a - non presente",
}


# ==================================================
# IDENTITY DOCUMENT TYPES
# ==================================================

DOCUMENT_TYPES = [
    "Carta d'identità",
    "Passaporto",
    "Permesso di soggiorno",
    "Altro",
]


# ==================================================
# TRANSLATIONS
# ==================================================

TRANSLATIONS = {

    "English": {
        "nav": "Navigation",
        "dashboard": "Dashboard",
        "record": "Record attendance",
        "staff": "Staff management",
        "weekly": "Attendance report",
        "documents": "Staff documents",
        "title": "📋 Staff Attendance Management",
        "subtitle": "Staff register and attendance management",
        "today": "Today",
        "active_staff": "Active staff",
        "records_today": "Attendance records today",
        "present_today": "Present / attended today",
        "by_category": "Staff by category",
        "today_records": "Today's records",
        "no_today": "No attendance has been recorded for today.",
        "staff_management": "Staff management",
        "add_staff": "➕ Add staff member",
        "name": "Staff name",
        "category": "Category",
        "vat": "Partita IVA / VAT number",
        "tax_code": "Codice Fiscale",
        "email": "Email address",
        "phone": "Phone number",
        "document_type": "Identity document type",
        "document_number": "Identity document number",
        "document_expiry": "Document expiry date",
        "add": "Add staff member",
        "enter_name": "Please enter a staff name.",
        "added": "Added",
        "staff_list": "Current staff list",
        "active": "Active",
        "inactive": "Inactive",
        "deactivate": "Deactivate",
        "reactivate": "Reactivate",
        "edit_details": "Edit staff details",
        "save_details": "Save staff details",
        "details_saved": "Staff details updated successfully.",
        "not_provided": "Not provided",
        "record_title": "Record daily attendance",
        "attendance_date": "Attendance date",
        "person": "Staff member",
        "status": "Attendance status",
        "start": "Start time",
        "end": "End time",
        "work_location": "Work location / City",
        "location_placeholder": "Example: Catania, Augusta, Palermo",
        "notes": "Notes",
        "save": "Save attendance",
        "saved": "Attendance saved for",
        "update_note": "Saving the same person and date updates the existing record.",
        "report_title": "Attendance date-range report",
        "start_date": "Start date",
        "end_date": "End date",
        "filter": "Filter category",
        "all": "All categories",
        "no_records": "No attendance records found for this period.",
        "entries": "Attendance entries",
        "attended": "Present / attended",
        "absent": "Absent / not attended",
        "hours": "Recorded hours",
        "totals": "Totals by category",
        "details": "Attendance details",
        "csv": "Download CSV",
        "excel": "Download Excel",
        "work_date": "Date",
        "hours_col": "Hours",
        "total": "Total",
        "report_note": "Hours are calculated from start and end times. Breaks are not deducted. These figures are not a payroll calculation.",
        "empty_category": "No active staff in this category. Add staff in Staff management.",
        "privacy": "Use this application only for authorised workforce administration. Staff documents are stored in a private bucket and are available only to authenticated Girija and Signor Paolo accounts.",
        "logout": "Logout",
        "logged_in": "Logged in as",
        "document_warning": "Upload only staff documents that you are authorised to store. Allowed: PDF, JPG and PNG, maximum 10 MB.",
        "delete_title": "Delete a staff member",
        "delete_warning": "Deleting a person also deletes their attendance history. Staff with stored documents cannot be deleted; deactivate them instead.",
        "confirm_delete": "I understand and confirm deletion",
        "delete_button": "Delete selected person",
        "deleted": "Staff member and attendance history deleted.",
        "delete_error": "Select exactly one person and confirm deletion.",
    },

    "Italiano": {
        "nav": "Navigazione",
        "dashboard": "Riepilogo",
        "record": "Registra presenze",
        "staff": "Gestione del personale",
        "weekly": "Report presenze",
        "documents": "Documenti del personale",
        "title": "📋 Gestione presenze del personale",
        "subtitle": "Gestione del personale e registro delle presenze",
        "today": "Oggi",
        "active_staff": "Personale attivo",
        "records_today": "Registrazioni di oggi",
        "present_today": "Presenti / intervenuti oggi",
        "by_category": "Personale per categoria",
        "today_records": "Registrazioni di oggi",
        "no_today": "Non sono ancora state registrate presenze per oggi.",
        "staff_management": "Gestione del personale",
        "add_staff": "➕ Aggiungi una persona",
        "name": "Nome del dipendente",
        "category": "Categoria",
        "vat": "Partita IVA",
        "tax_code": "Codice Fiscale",
        "email": "Indirizzo e-mail",
        "phone": "Numero di telefono",
        "document_type": "Tipo di documento",
        "document_number": "Numero del documento",
        "document_expiry": "Data di scadenza del documento",
        "add": "Aggiungi persona",
        "enter_name": "Inserisci il nome della persona.",
        "added": "Aggiunto/a",
        "staff_list": "Elenco del personale",
        "active": "Attivo",
        "inactive": "Non attivo",
        "deactivate": "Disattiva",
        "reactivate": "Riattiva",
        "edit_details": "Modifica i dati",
        "save_details": "Salva i dati",
        "details_saved": "Dati aggiornati correttamente.",
        "not_provided": "Non inserito",
        "record_title": "Registra le presenze giornaliere",
        "attendance_date": "Data della presenza",
        "person": "Persona",
        "status": "Stato della presenza",
        "start": "Ora di inizio",
        "end": "Ora di fine",
        "work_location": "Luogo di lavoro / Città",
        "location_placeholder": "Es. Catania, Augusta, Palermo",
        "notes": "Note",
        "save": "Salva presenza",
        "saved": "Presenza salvata per",
        "update_note": "Se salvi di nuovo la stessa persona per la stessa data, la registrazione esistente viene aggiornata.",
        "report_title": "Report presenze per intervallo di date",
        "start_date": "Data iniziale",
        "end_date": "Data finale",
        "filter": "Filtra per categoria",
        "all": "Tutte le categorie",
        "no_records": "Nessuna presenza registrata in questo periodo.",
        "entries": "Registrazioni",
        "attended": "Presenti / intervenuti",
        "absent": "Assenti / non intervenuti",
        "hours": "Ore registrate",
        "totals": "Totali per categoria",
        "details": "Dettaglio presenze",
        "csv": "Scarica CSV",
        "excel": "Scarica Excel",
        "work_date": "Data",
        "hours_col": "Ore",
        "total": "Totale",
        "report_note": "Le ore sono calcolate tra l'ora di inizio e quella di fine. Le pause non vengono detratte. Questi dati non costituiscono un calcolo della retribuzione.",
        "empty_category": "Non ci sono persone attive in questa categoria. Aggiungile in Gestione del personale.",
        "privacy": "Usa questa applicazione solo per la gestione autorizzata del personale. I documenti sono conservati in un archivio privato e sono accessibili solo agli account autenticati di Girija e Signor Paolo.",
        "logout": "Esci",
        "logged_in": "Accesso effettuato come",
        "document_warning": "Carica solo documenti del personale che sei autorizzato a conservare. Formati consentiti: PDF, JPG e PNG, massimo 10 MB.",
        "delete_title": "Elimina una persona",
        "delete_warning": "L'eliminazione di una persona cancella anche lo storico delle presenze. Non è possibile eliminare persone con documenti archiviati: disattivale invece.",
        "confirm_delete": "Ho capito e confermo l'eliminazione",
        "delete_button": "Elimina la persona selezionata",
        "deleted": "Persona e storico delle presenze eliminati.",
        "delete_error": "Seleziona esattamente una persona e conferma l'eliminazione.",
    }
}


# ==================================================
# LANGUAGE AND NAVIGATION
# ==================================================

with st.sidebar:

    language = st.selectbox(
        "Lingua / Language",
        ["Italiano", "English"],
        index=0,
        key="app_language"
    )

    tr = lambda key: TRANSLATIONS[language][key]

    st.caption(
        f"{tr('logged_in')}: "
        f"{st.session_state.authenticated_user}"
    )

    if st.button(tr("logout")):
        st.session_state.authenticated_user = None
        st.rerun()

    st.divider()
    st.header(tr("nav"))

    page_options = [
        tr("dashboard"),
        tr("record"),
        tr("staff"),
        tr("weekly"),
        tr("documents"),
        "Magazzino",
        "Pagamenti"
    ]

    page = st.radio(
        "Menu",
        page_options,
        label_visibility="collapsed"
    )

    st.divider()
    st.caption(tr("privacy"))


def category_label(category):

    if language == "Italiano":
        return CATEGORY_IT.get(category, category)

    return category


def status_label(status):

    if language == "Italiano":
        return STATUS_IT.get(status, status)

    return status


# ==================================================
# DATABASE FUNCTIONS
# ==================================================

def all_staff(active_only=True):

    with Session() as session:

        query = session.query(Staff)

        if active_only:
            query = query.filter(Staff.active == 1)

        return query.order_by(
            Staff.category,
            Staff.name
        ).all()


def get_attendance(staff_id, work_date):

    with Session() as session:

        return session.query(Attendance).filter_by(
            staff_id=staff_id,
            work_date=work_date
        ).first()


def save_attendance(
    staff_id,
    work_date,
    status,
    start_time,
    end_time,
    notes,
    work_location
):

    with Session() as session:

        item = session.query(Attendance).filter_by(
            staff_id=staff_id,
            work_date=work_date
        ).first()

        if item is None:

            item = Attendance(
                staff_id=staff_id,
                work_date=work_date
            )

            session.add(item)

        item.status = status
        item.start_time = start_time
        item.end_time = end_time
        item.notes = notes.strip()
        item.work_location = work_location.strip() or None

        session.commit()


# ==================================================
# ATTENDANCE REPORT DATA
# ==================================================

def attendance_frame(start_date, end_date, category=None):

    with Session() as session:

        rows = session.execute(
            text("""
                SELECT
                    a.staff_id,
                    a.work_date,
                    st.name,
                    st.category,
                    a.start_time,
                    a.end_time,
                    a.status,
                    a.work_location,
                    a.notes
                FROM attendance a
                JOIN staff st ON st.id = a.staff_id
                WHERE a.work_date >= :start_date
                  AND a.work_date <= :end_date
                ORDER BY a.work_date, st.category, st.name
            """),
            {
                "start_date": start_date,
                "end_date": end_date
            }
        ).mappings().all()

    df = pd.DataFrame(rows)

    if df.empty:
        return df

    if category:
        df = df[df["category"] == category].copy()

    if df.empty:
        return df

    df["work_date"] = pd.to_datetime(
        df["work_date"]
    ).dt.date

    def format_time(value):

        if hasattr(value, "strftime"):
            return value.strftime("%H:%M")

        if value:
            return str(value)[:5]

        return ""

    df["start_time"] = df["start_time"].apply(format_time)
    df["end_time"] = df["end_time"].apply(format_time)

    df["work_location"] = df["work_location"].fillna("")

    def calculate_hours(row):

        try:

            start = datetime.strptime(
                row["start_time"],
                "%H:%M"
            )

            end = datetime.strptime(
                row["end_time"],
                "%H:%M"
            )

            duration = (
                end - start
            ).total_seconds() / 3600

            if duration < 0:
                duration += 24

            return round(duration, 2)

        except (ValueError, TypeError):

            return 0.0

    df["hours"] = df.apply(
        calculate_hours,
        axis=1
    )

    return df


# ==================================================
# DISPLAY AND EXPORT
# ==================================================

def display_dataframe(df):

    result = df.copy()

    if result.empty:
        return result

    result["category"] = result["category"].apply(
        category_label
    )

    result["status"] = result["status"].apply(
        status_label
    )

    result = result.rename(columns={
        "category": tr("category"),
        "start_time": tr("start"),
        "name": tr("name"),
        "end_time": tr("end"),
        "status": tr("status"),
        "work_date": tr("work_date"),
        "work_location": tr("work_location"),
        "hours": tr("hours_col"),
        "notes": tr("notes"),
    })

    # Exact requested column order.
    result = result[[
        tr("category"),
        tr("start"),
        tr("name"),
        tr("end"),
        tr("status"),
        tr("work_date"),
        tr("work_location"),
        tr("hours_col"),
        tr("notes"),
    ]]

    return result


def make_excel(df):

    output = BytesIO()

    sheet_name = (
        "Attendance"
        if language == "English"
        else "Presenze"
    )

    with pd.ExcelWriter(
        output,
        engine="openpyxl"
    ) as writer:

        df.to_excel(
            writer,
            index=False,
            sheet_name=sheet_name
        )

        worksheet = writer.sheets[sheet_name]

        worksheet.freeze_panes = "A2"
        worksheet.auto_filter.ref = worksheet.dimensions

        # Make columns easier to read in Excel.
        for column_cells in worksheet.columns:

            max_length = 0
            column_letter = column_cells[0].column_letter

            for cell in column_cells:

                value = str(cell.value or "")
                max_length = max(max_length, len(value))

            worksheet.column_dimensions[column_letter].width = min(
                max(max_length + 2, 12),
                35
            )

    output.seek(0)

    return output.getvalue()


# ==================================================
# MAIN PAGE HEADER
# ==================================================

st.title(tr("title"))
st.caption(tr("subtitle"))


# ==================================================
# INVENTORY
# ==================================================

if page == "Magazzino":

    from inventory import render_inventory

    render_inventory()
    st.stop()


# ==================================================
# STAFF DOCUMENTS
# ==================================================

if page == tr("documents"):

    st.subheader(tr("documents"))
    st.caption(
        "Private staff files. Both Girija and Signor Paolo can view, upload "
        "and download documents for every staff member."
        if language == "English"
        else "Documenti privati del personale. Sia Girija sia Signor Paolo "
             "possono visualizzare, caricare e scaricare i documenti di tutto il personale."
    )
    st.info(
        "Files stay in the private Neon bucket. Downloads use temporary "
        "links that expire after 60 seconds."
        if language == "English"
        else "I file restano nel bucket privato Neon. I link di download "
             "temporanei scadono dopo 60 secondi."
    )

    people_for_documents = all_staff(active_only=False)

    if not people_for_documents:
        st.info("No staff members found." if language == "English" else "Nessun dipendente trovato.")
    else:
        staff_by_label = {
            f"{person.name} — {category_label(person.category)} (ID {person.id})": person
            for person in people_for_documents
        }
        selected_staff_label = st.selectbox(
            "Staff member / Dipendente",
            list(staff_by_label.keys()),
            key="staff_document_person"
        )
        selected_staff = staff_by_label[selected_staff_label]

        st.markdown("#### Upload a document / Carica un documento")
        uploaded_document = st.file_uploader(
            "Choose a PDF, JPG or PNG file / Scegli un file PDF, JPG o PNG",
            type=["pdf", "jpg", "jpeg", "png"],
            key=f"staff_document_upload_{selected_staff.id}"
        )

        if st.button(
            "Upload document / Carica documento",
            type="primary",
            disabled=uploaded_document is None,
            key=f"upload_staff_document_{selected_staff.id}"
        ):
            try:
                file_bytes = uploaded_document.getvalue()
                safe_filename, detected_content_type = validate_staff_document(
                    uploaded_document.name,
                    file_bytes
                )
                storage = get_private_storage_client()
                object_key = (
                    f"staff-documents/{selected_staff.id}/"
                    f"{uuid.uuid4().hex}{os.path.splitext(safe_filename)[1].lower()}"
                )

                # Upload first; if the database insert fails, remove the orphaned object.
                storage.put_object(
                    Bucket=DOCUMENT_BUCKET,
                    Key=object_key,
                    Body=file_bytes,
                    ContentType=detected_content_type,
                )

                try:
                    with Session() as session:
                        document_record = StaffDocument(
                            staff_id=selected_staff.id,
                            original_filename=safe_filename,
                            object_key=object_key,
                            content_type=detected_content_type,
                            file_size=len(file_bytes),
                            uploaded_by=st.session_state.authenticated_user,
                        )
                        session.add(document_record)
                        session.commit()
                except Exception:
                    try:
                        storage.delete_object(Bucket=DOCUMENT_BUCKET, Key=object_key)
                    except Exception:
                        pass
                    raise

                st.success(
                    "Document uploaded successfully." if language == "English"
                    else "Documento caricato correttamente."
                )
                st.rerun()

            except ValueError as exc:
                st.error(str(exc))
            except Exception:
                st.error(
                    "Upload failed. Check the private storage configuration and try again."
                    if language == "English"
                    else "Caricamento non riuscito. Verifica la configurazione dell'archivio privato e riprova."
                )

        st.divider()
        st.markdown("#### Stored documents / Documenti archiviati")

        with Session() as session:
            stored_documents = (
                session.query(StaffDocument)
                .filter(StaffDocument.staff_id == selected_staff.id)
                .order_by(StaffDocument.uploaded_at.desc())
                .all()
            )
            # Detach simple values before closing the session.
            document_rows = [
                {
                    "id": item.id,
                    "filename": item.original_filename,
                    "object_key": item.object_key,
                    "content_type": item.content_type,
                    "file_size": item.file_size,
                    "uploaded_by": item.uploaded_by,
                    "uploaded_at": item.uploaded_at,
                }
                for item in stored_documents
            ]

        if not document_rows:
            st.info("No documents uploaded for this person yet." if language == "English" else "Nessun documento caricato per questa persona.")
        else:
            for document_row in document_rows:
                left, middle, right = st.columns([4, 2, 1])
                left.write(f"**{document_row['filename']}**")
                left.caption(
                    f"{document_row['file_size'] / 1024:.1f} KB · "
                    f"Uploaded by {document_row['uploaded_by']} · "
                    f"{document_row['uploaded_at'].strftime('%d/%m/%Y %H:%M')}"
                )
                middle.write(document_row["content_type"])

                try:
                    storage = get_private_storage_client()
                    safe_download_name = document_row["filename"].replace('"', "")
                    temporary_url = storage.generate_presigned_url(
                        "get_object",
                        Params={
                            "Bucket": DOCUMENT_BUCKET,
                            "Key": document_row["object_key"],
                            "ResponseContentDisposition": (
                                f'attachment; filename="{safe_download_name}"'
                            ),
                        },
                        ExpiresIn=60,
                    )
                    audit_state_key = (
                        f"document_link_logged_{document_row['id']}_"
                        f"{st.session_state.authenticated_user}"
                    )
                    if not st.session_state.get(audit_state_key, False):
                        with Session() as session:
                            session.add(StaffDocumentAccessLog(
                                document_id=document_row["id"],
                                username=st.session_state.authenticated_user,
                                action="download_link_created",
                            ))
                            session.commit()
                        st.session_state[audit_state_key] = True

                    right.link_button(
                        "Download" if language == "English" else "Scarica",
                        temporary_url,
                    )
                except Exception:
                    right.error(
                        "Unavailable" if language == "English" else "Non disponibile"
                    )
                    st.warning(
                        "A download link could not be created. Check the storage settings."
                        if language == "English"
                        else "Impossibile creare il link di download. Verifica le impostazioni dell'archivio."
                    )

    st.stop()


# ==================================================
# DASHBOARD
# ==================================================

# ==================================================
# PAGAMENTI
# ==================================================

if page == "Pagamenti":

    st.subheader("💶 Gestione dei pagamenti")

    st.caption(
        "Seleziona il personale, controlla le ore "
        "registrate e inserisci manualmente l'importo."
    )

    people = all_staff(active_only=True)

    if not people:

        st.info("Nessun dipendente attivo registrato.")

    else:

        # CATEGORY SELECTION

        selected_category = st.selectbox(
            "Categoria",
            CATEGORIES,
            format_func=category_label,
            key="payment_category"
        )

        # EMPLOYEE SELECTION

        category_people = [
            person for person in people
            if person.category == selected_category
        ]

        if not category_people:

            st.info(
                "Nessun dipendente attivo in questa categoria."
            )

        else:

            selected_person = st.selectbox(
                "Nome del dipendente",
                category_people,
                format_func=lambda person: person.name,
                key="payment_employee"
            )

            st.divider()

            # DATE RANGE

            st.markdown("### Periodo di lavoro")

            col1, col2 = st.columns(2)

            period_start = col1.date_input(
                "Data iniziale",
                value=date.today().replace(day=1),
                format="DD/MM/YYYY",
                key="payment_start"
            )

            period_end = col2.date_input(
                "Data finale",
                value=date.today(),
                format="DD/MM/YYYY",
                key="payment_end"
            )

            if period_start > period_end:

                st.error(
                    "La data iniziale deve precedere "
                    "quella finale."
                )

            else:

                # GET ATTENDANCE FOR SELECTED EMPLOYEE

                employee_df = attendance_frame(
                    period_start,
                    period_end,
                    selected_category
                )

                if not employee_df.empty:

                    employee_df = employee_df[employee_df["staff_id"] == selected_person.id
                    ].copy()

                    employee_df = employee_df[
                        employee_df["status"].isin([
                            "Present",
                            "Called in - attended"
                        ])
                    ].copy()

                # CALCULATE ATTENDED HOURS ONLY

                total_hours = (
                    float(employee_df["hours"].sum())
                    if not employee_df.empty
                    else 0.0
                )

                # GET WORK LOCATIONS

                locations = []

                if not employee_df.empty:

                    locations = sorted({
                        str(location).strip()
                        for location in employee_df[
                            "work_location"
                        ].fillna("").tolist()
                        if str(location).strip()
                    })

                st.markdown("### Riepilogo presenze")

                col1, col2 = st.columns(2)

                col1.metric(
                    "Ore lavorate",
                    f"{total_hours:.2f}"
                )

                col2.metric(
                    "Giornate lavorate",
                    (
                        employee_df["work_date"].nunique()
                        if not employee_df.empty
                        else 0
                    )
                )

                st.markdown("**Luoghi di lavoro**")

                if locations:

                    for location in locations:
                        st.write(f"📍 {location}")

                else:

                    st.info(
                        "Nessun luogo di lavoro registrato "
                        "per questo periodo."
                    )

                st.divider()

                # MANUAL PAYMENT ENTRY

                st.markdown("### Inserisci pagamento")

                with st.form("new_payment_form"):

                    amount_input = st.text_input(
                        "Importo da pagare (€)",
                        placeholder="Es. 500,00"
                    )

                    payment_date = st.date_input(
                        "Data del pagamento",
                        value=date.today(),
                        format="DD/MM/YYYY"
                    )

                    payment_notes = st.text_area(
                        "Note",
                        placeholder=(
                            "Eventuali informazioni "
                            "aggiuntive..."
                        ),
                        max_chars=500
                    )

                    save_payment = st.form_submit_button(
                        "💾 Salva pagamento",
                        type="primary"
                    )

                    if save_payment:

                        # Accept Italian decimal commas.
                        cleaned_amount = (
                            amount_input
                            .strip()
                            .replace("€", "")
                            .replace(" ", "")
                        )

                        if (
                            "," in cleaned_amount
                            and "." in cleaned_amount
                        ):
                            cleaned_amount = (
                                cleaned_amount
                                .replace(".", "")
                                .replace(",", ".")
                            )

                        else:
                            cleaned_amount = (
                                cleaned_amount.replace(",", ".")
                            )

                        try:

                            amount = float(cleaned_amount)

                            if not math.isfinite(amount) or amount <= 0:
                                raise ValueError()

                        except (ValueError, TypeError):

                            st.error(
                                "Inserisci un importo valido, "
                                "ad esempio 500,00."
                            )

                        else:

                            with Session() as session:

                                payment = Payment(
                                    staff_id=selected_person.id,
                                    staff_name=selected_person.name,
                                    category=selected_person.category,
                                    period_start=period_start,
                                    period_end=period_end,
                                    hours_worked=total_hours,
                                    work_locations="; ".join(locations),
                                    amount=amount,
                                    payment_date=payment_date,
                                    notes=payment_notes.strip()
                                )

                                session.add(payment)
                                session.commit()

                            st.success(
                                "Pagamento registrato correttamente!"
                            )

                            st.rerun()

    # ==================================================
    # PAYMENT HISTORY
    # ==================================================

    st.divider()

    st.markdown("### 📚 Storico dei pagamenti")

    with Session() as session:

        payment_records = (
            session.query(Payment)
            .order_by(
                Payment.payment_date.desc(),
                Payment.id.desc()
            )
            .all()
        )

        history_data = [
            {
                "Dipendente": p.staff_name,
                "Categoria": category_label(p.category),
                "Dal": p.period_start.strftime("%d/%m/%Y"),
                "Al": p.period_end.strftime("%d/%m/%Y"),
                "Ore lavorate": round(p.hours_worked, 2),
                "Luoghi": p.work_locations,
                "Importo (€)": f"{p.amount:.2f}",
                "Data pagamento": p.payment_date.strftime("%d/%m/%Y"),
                "Note": p.notes or ""
            }
            for p in payment_records
        ]

    if history_data:

        history_df = pd.DataFrame(history_data)

        st.dataframe(
            history_df,
            use_container_width=True,
            hide_index=True
        )

        csv_payments = history_df.to_csv(
            index=False
        ).encode("utf-8-sig")

        st.download_button(
            "📥 Scarica storico pagamenti CSV",
            data=csv_payments,
            file_name="storico_pagamenti.csv",
            mime="text/csv"
        )

    else:

        st.info("Nessun pagamento registrato.")

    st.stop()

if page == tr("dashboard"):

    today = date.today()

    st.subheader(
        f"{tr('today')} — {today.strftime('%d/%m/%Y')}"
    )

    people = all_staff()

    today_df = attendance_frame(
        today,
        today
    )

    col1, col2, col3 = st.columns(3)

    col1.metric(
        tr("active_staff"),
        len(people)
    )

    col2.metric(
        tr("records_today"),
        0 if today_df.empty else len(today_df)
    )

    col3.metric(
        tr("present_today"),
        0 if today_df.empty else int(
            today_df["status"].isin([
                "Present",
                "Called in - attended"
            ]).sum()
        )
    )

    st.markdown(
        f"### {tr('by_category')}"
    )

    for category in CATEGORIES:

        count = sum(
            1 for person in people
            if person.category == category
        )

        st.write(
            f"**{category_label(category)}:** {count}"
        )

    if not today_df.empty:

        st.markdown(
            f"### {tr('today_records')}"
        )

        st.dataframe(
            display_dataframe(today_df),
            use_container_width=True,
            hide_index=True
        )

    else:

        st.info(tr("no_today"))


# ==================================================
# STAFF MANAGEMENT
# ==================================================

elif page == tr("staff"):

    st.subheader(tr("staff_management"))

    # ADD STAFF

    with st.expander(
        tr("add_staff"),
        expanded=True
    ):

        with st.form(
            "add_staff_form",
            clear_on_submit=True
        ):

            name = st.text_input(tr("name"))

            category = st.selectbox(
                tr("category"),
                CATEGORIES,
                format_func=category_label
            )

            partita_iva = st.text_input(
                tr("vat"),
                max_chars=30
            )

            codice_fiscale = st.text_input(
                tr("tax_code"),
                max_chars=20
            )

            email = st.text_input(tr("email"))

            phone = st.text_input(
                tr("phone"),
                max_chars=30
            )

            st.divider()

            st.markdown(
                "#### Identity document / Documento d'identità"
            )

            document_type = st.selectbox(
                tr("document_type"),
                [""] + DOCUMENT_TYPES
            )

            document_number = st.text_input(
                tr("document_number"),
                max_chars=100
            )

            document_expiry = st.date_input(
                tr("document_expiry"),
                value=None,
                format="DD/MM/YYYY"
            )
            uploaded_staff_document = st.file_uploader(
    "Allega documento / Attach document (PDF, JPG, PNG)",
    type=["pdf", "jpg", "jpeg", "png"],
    key="new_staff_document_upload"
)

            st.warning(tr("document_warning"))

            submitted = st.form_submit_button(
                tr("add"),
                type="primary"
            )

            if submitted:

               if not name.strip():

                 st.error(tr("enter_name"))

               else:

                new_staff_id = None

        try:
            prepared_document = None

            # Validate the attachment before saving the staff member.
            if uploaded_staff_document is not None:

                file_bytes = uploaded_staff_document.getvalue()

                safe_filename, detected_content_type = (
                    validate_staff_document(
                        uploaded_staff_document.name,
                        file_bytes
                    )
                )

                prepared_document = (
                    file_bytes,
                    safe_filename,
                    detected_content_type
                )

            # Save the staff member first.
            with Session() as session:

                new_staff = Staff(
                    name=name.strip(),
                    category=category,
                    partita_iva=partita_iva.strip() or None,
                    codice_fiscale=codice_fiscale.strip() or None,
                    email=email.strip() or None,
                    phone=phone.strip() or None,
                    identity_doc_type=document_type or None,
                    identity_doc_number=document_number.strip() or None,
                    identity_doc_expiry=document_expiry
                )

                session.add(new_staff)
                session.commit()

                new_staff_id = new_staff.id

        except ValueError as exc:

            st.error(str(exc))

        except Exception:

            st.error(
                "Could not save the staff member. Please try again."
            )

        else:

            # Upload the attachment using the existing private storage.
            if prepared_document is not None:

                file_bytes, safe_filename, detected_content_type = (
                    prepared_document
                )

                object_key = (
                    f"staff-documents/{new_staff_id}/"
                    f"{uuid.uuid4().hex}"
                    f"{os.path.splitext(safe_filename)[1].lower()}"
                )

                try:

                    storage = get_private_storage_client()

                    storage.put_object(
                        Bucket=DOCUMENT_BUCKET,
                        Key=object_key,
                        Body=file_bytes,
                        ContentType=detected_content_type,
                    )

                    try:

                        with Session() as session:

                            document_record = StaffDocument(
                                staff_id=new_staff_id,
                                original_filename=safe_filename,
                                object_key=object_key,
                                content_type=detected_content_type,
                                file_size=len(file_bytes),
                                uploaded_by=(
                                    st.session_state.authenticated_user
                                ),
                            )

                            session.add(document_record)
                            session.commit()

                    except Exception:

                        try:
                            storage.delete_object(
                                Bucket=DOCUMENT_BUCKET,
                                Key=object_key
                            )
                        except Exception:
                            pass

                        raise

                    st.success(
                        "Staff member and document saved successfully."
                        if language == "English"
                        else "Persona e documento salvati correttamente."
                    )

                except Exception:

                    st.warning(
                        "The staff member was saved, but the document "
                        "upload failed. You can upload it later from "
                        "Staff documents."
                        if language == "English"
                        else "La persona è stata salvata, ma il caricamento "
                             "del documento non è riuscito. Puoi caricarlo "
                             "successivamente da Documenti del personale."
                    )

            else:

                st.success(
                    f"{tr('added')} {name.strip()}."
                )


    # STAFF LIST AND EDITING

    people = all_staff(active_only=False)

    if people:

        st.markdown(
            f"### {tr('staff_list')}"
        )

        for person in people:

            with st.container(border=True):

                col1, col2 = st.columns([2, 2])

                col1.write(f"**{person.name}**")
                col2.write(category_label(person.category))

                detail1, detail2 = st.columns(2)

                detail1.write(
                    f"**{tr('vat')}:** "
                    f"{person.partita_iva or tr('not_provided')}"
                )

                detail2.write(
                    f"**{tr('tax_code')}:** "
                    f"{person.codice_fiscale or tr('not_provided')}"
                )

                detail3, detail4 = st.columns(2)

                detail3.write(
                    f"**{tr('email')}:** "
                    f"{person.email or tr('not_provided')}"
                )

                detail4.write(
                    f"**{tr('phone')}:** "
                    f"{person.phone or tr('not_provided')}"
                )

                st.write(
                    f"**{tr('document_type')}:** "
                    f"{person.identity_doc_type or tr('not_provided')}"
                )

                st.write(
                    f"**{tr('document_number')}:** "
                    f"{person.identity_doc_number or tr('not_provided')}"
                )

                expiry_text = (
                    person.identity_doc_expiry.strftime("%d/%m/%Y")
                    if person.identity_doc_expiry
                    else tr("not_provided")
                )

                st.write(
                    f"**{tr('document_expiry')}:** {expiry_text}"
                )

                col4, col5 = st.columns(2)

                col4.write(
                    tr("active")
                    if person.active
                    else tr("inactive")
                )

                if person.active:

                    if col5.button(
                        tr("deactivate"),
                        key=f"deactivate_{person.id}"
                    ):

                        with Session() as session:

                            obj = session.get(
                                Staff,
                                person.id
                            )

                            if obj:
                                obj.active = 0
                                session.commit()

                        st.rerun()

                else:

                    if col5.button(
                        tr("reactivate"),
                        key=f"reactivate_{person.id}"
                    ):

                        with Session() as session:

                            obj = session.get(
                                Staff,
                                person.id
                            )

                            if obj:
                                obj.active = 1
                                session.commit()

                        st.rerun()

                # EDIT STAFF DETAILS

                with st.expander(
                    f"{tr('edit_details')} — {person.name}"
                ):

                    with st.form(
                        f"staff_details_form_{person.id}"
                    ):

                        new_name = st.text_input(
                            tr("name"),
                            value=person.name,
                            key=f"name_{person.id}"
                        )

                        new_category = st.selectbox(
                            tr("category"),
                            CATEGORIES,
                            index=(
                                CATEGORIES.index(person.category)
                                if person.category in CATEGORIES
                                else 0
                            ),
                            format_func=category_label,
                            key=f"category_{person.id}"
                        )

                        new_vat = st.text_input(
                            tr("vat"),
                            value=person.partita_iva or "",
                            max_chars=30,
                            key=f"vat_{person.id}"
                        )

                        new_tax_code = st.text_input(
                            tr("tax_code"),
                            value=person.codice_fiscale or "",
                            max_chars=20,
                            key=f"tax_{person.id}"
                        )

                        new_email = st.text_input(
                            tr("email"),
                            value=person.email or "",
                            key=f"email_{person.id}"
                        )

                        new_phone = st.text_input(
                            tr("phone"),
                            value=person.phone or "",
                            max_chars=30,
                            key=f"phone_{person.id}"
                        )

                        current_doc_type = (
                            person.identity_doc_type
                            if person.identity_doc_type in DOCUMENT_TYPES
                            else ""
                        )

                        new_doc_type = st.selectbox(
                            tr("document_type"),
                            [""] + DOCUMENT_TYPES,
                            index=(
                                [""] + DOCUMENT_TYPES
                            ).index(current_doc_type),
                            key=f"doc_type_{person.id}"
                        )

                        new_doc_number = st.text_input(
                            tr("document_number"),
                            value=person.identity_doc_number or "",
                            key=f"doc_number_{person.id}"
                        )

                        new_doc_expiry = st.date_input(
                            tr("document_expiry"),
                            value=person.identity_doc_expiry,
                            format="DD/MM/YYYY",
                            key=f"doc_expiry_{person.id}"
                        )

                        save_details = st.form_submit_button(
                            tr("save_details")
                        )

                        if save_details:

                            if not new_name.strip():

                                st.error(tr("enter_name"))

                            else:

                                with Session() as session:

                                    obj = session.get(
                                        Staff,
                                        person.id
                                    )

                                    if obj:

                                        obj.name = new_name.strip()
                                        obj.category = new_category
                                        obj.partita_iva = new_vat.strip() or None
                                        obj.codice_fiscale = new_tax_code.strip() or None
                                        obj.email = new_email.strip() or None
                                        obj.phone = new_phone.strip() or None
                                        obj.identity_doc_type = new_doc_type or None
                                        obj.identity_doc_number = new_doc_number.strip() or None
                                        obj.identity_doc_expiry = new_doc_expiry

                                        session.commit()

                                st.success(tr("details_saved"))
                                st.rerun()

    # OPTIONAL DELETE SECTION

    with st.expander(tr("delete_title")):

        st.warning(tr("delete_warning"))

        delete_people = all_staff(active_only=False)

        delete_choices = {
            f"{p.name} — {category_label(p.category)}": p.id
            for p in delete_people
        }

        if delete_choices:

            selected_person = st.selectbox(
                tr("delete_title"),
                list(delete_choices.keys()),
                key="delete_person_choice"
            )

            confirm_delete = st.checkbox(
                tr("confirm_delete"),
                key="confirm_staff_delete"
            )

            if st.button(
                tr("delete_button"),
                disabled=not confirm_delete,
                key="delete_staff_button"
            ):

                selected_id = delete_choices[selected_person]

                with Session() as session:
                    has_documents = session.query(StaffDocument.id).filter(
                        StaffDocument.staff_id == selected_id
                    ).first()

                    if has_documents:
                        st.error(
                            "This staff member has stored documents. Deactivate the person instead of deleting them."
                            if language == "English"
                            else "Questa persona ha documenti archiviati. Disattivala invece di eliminarla."
                        )
                    else:
                        session.query(Attendance).filter(
                            Attendance.staff_id == selected_id
                        ).delete(
                            synchronize_session=False
                        )
                        session.query(Payment).filter(
                            Payment.staff_id == selected_id
                        ).update(
                            {Payment.staff_id: None},
                            synchronize_session=False
                        )

                        obj = session.get(Staff, selected_id)
                        if obj:
                            session.delete(obj)
                            session.commit()

                        st.success(tr("deleted"))
                        st.rerun()


# ==================================================
# DAILY ATTENDANCE
# ==================================================

elif page == tr("record"):

    st.subheader(tr("record_title"))

    work_date = st.date_input(
        tr("attendance_date"),
        value=date.today(),
        format="DD/MM/YYYY"
    )

    category = st.selectbox(
        tr("category"),
        CATEGORIES,
        format_func=category_label
    )

    people = [
        person
        for person in all_staff()
        if person.category == category
    ]

    if not people:

        st.info(tr("empty_category"))

    else:

        chosen = st.selectbox(
            tr("person"),
            people,
            format_func=lambda person: person.name
        )

        old = get_attendance(
            chosen.id,
            work_date
        )

        if old:

            default_status = old.status

        elif category in [
            "On-call staff",
            "Personale a chiamata full-time",
            "Personale a chiamata part-time",
            "Personale a chiamata partita IVA",
        ]:

            default_status = "Called in - did not attend"

        else:

            default_status = "Present"

        status = st.selectbox(
            tr("status"),
            STATUSES,
            index=STATUSES.index(default_status),
            format_func=status_label
        )

        col1, col2 = st.columns(2)

        default_start = (
            old.start_time
            if old and old.start_time
            else time(9, 0)
        )

        default_end = (
            old.end_time
            if old and old.end_time
            else time(17, 0)
        )

        start_time = col1.time_input(
            tr("start"),
            value=default_start
        )

        end_time = col2.time_input(
            tr("end"),
            value=default_end
        )

        work_location = st.text_input(
            tr("work_location"),
            value=(
                old.work_location
                if old and old.work_location
                else ""
            ),
            placeholder=tr("location_placeholder")
        )

        notes = st.text_input(
            tr("notes"),
            value=old.notes if old else "",
            max_chars=500
        )

        if st.button(
            tr("save"),
            type="primary"
        ):

            save_attendance(
                chosen.id,
                work_date,
                status,
                start_time,
                end_time,
                notes,
                work_location
            )

            st.success(
                f"{tr('saved')} {chosen.name} "
                f"({work_date.strftime('%d/%m/%Y')})."
            )

            st.rerun()

        st.caption(tr("update_note"))


# ==================================================
# DATE-RANGE ATTENDANCE REPORT
# ==================================================

elif page == tr("weekly"):

    st.subheader(tr("report_title"))

    st.write(
        "Select the beginning and ending dates of the report."
        if language == "English"
        else "Seleziona la data iniziale e quella finale del report."
    )

    col1, col2 = st.columns(2)

    start_date = col1.date_input(
        tr("start_date"),
        value=date(2026, 10, 30),
        format="DD/MM/YYYY",
        key="report_start_date"
    )

    end_date = col2.date_input(
        tr("end_date"),
        value=date(2026, 11, 7),
        format="DD/MM/YYYY",
        key="report_end_date"
    )

    if start_date > end_date:

        st.error(
            "The start date must be before the end date."
            if language == "English"
            else "La data iniziale deve precedere la data finale."
        )

        st.stop()

    st.write(
        f"**{tr('start_date')}:** "
        f"{start_date.strftime('%d/%m/%Y')} "
        f" — "
        f"**{tr('end_date')}:** "
        f"{end_date.strftime('%d/%m/%Y')}"
    )

    category_options = [
        "All categories"
    ] + CATEGORIES

    category_filter = st.selectbox(
        tr("filter"),
        category_options,
        format_func=lambda item: (
            tr("all")
            if item == "All categories"
            else category_label(item)
        )
    )

    df = attendance_frame(
        start_date,
        end_date,
        None if category_filter == "All categories"
        else category_filter
    )

    if df.empty:

        st.info(tr("no_records"))

    else:

        total_entries = len(df)

        attended_count = int(
            df["status"].isin([
                "Present",
                "Called in - attended"
            ]).sum()
        )

        absent_count = int(
            df["status"].isin([
                "Absent",
                "Called in - did not attend"
            ]).sum()
        )

        total_hours = float(df["hours"].sum())

        col1, col2, col3, col4 = st.columns(4)

        col1.metric(tr("entries"), total_entries)
        col2.metric(tr("attended"), attended_count)
        col3.metric(tr("absent"), absent_count)
        col4.metric(tr("hours"), f"{total_hours:.2f}")

        # TOTALS BY CATEGORY

        st.markdown(
            f"### {tr('totals')}"
        )

        summary_df = df.copy()

        summary_df["category"] = (
            summary_df["category"].apply(category_label)
        )

        summary_df["status"] = (
            summary_df["status"].apply(status_label)
        )

        summary = (
            summary_df.groupby([
                "category",
                "status"
            ])
            .size()
            .unstack(fill_value=0)
        )

        summary[tr("total")] = summary.sum(axis=1)

        st.dataframe(
            summary.reset_index(),
            use_container_width=True,
            hide_index=True
        )

        # ATTENDANCE DETAILS

        st.markdown(
            f"### {tr('details')}"
        )

        report_df = display_dataframe(df)

        st.dataframe(
            report_df,
            use_container_width=True,
            hide_index=True
        )

        # EXPORT CSV AND EXCEL

        csv_data = report_df.to_csv(
            index=False
        ).encode("utf-8-sig")

        filename_prefix = (
            "attendance"
            if language == "English"
            else "presenze"
        )

        date_suffix = f"{start_date}_{end_date}"

        col1, col2 = st.columns(2)

        col1.download_button(
            tr("csv"),
            data=csv_data,
            file_name=f"{filename_prefix}_{date_suffix}.csv",
            mime="text/csv"
        )

        col2.download_button(
            tr("excel"),
            data=make_excel(report_df),
            file_name=f"{filename_prefix}_{date_suffix}.xlsx",
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            )
        )

        st.caption(tr("report_note"))