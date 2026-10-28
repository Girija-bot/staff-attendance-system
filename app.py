
import os
import sqlite3
from pathlib import Path
from datetime import date, datetime, time, timedelta
from io import BytesIO

import pandas as pd
import streamlit as st
from sqlalchemy import (
    create_engine, text, Integer, String, Date, Time,
    ForeignKey, UniqueConstraint, inspect
)
from sqlalchemy.orm import (
    DeclarativeBase, Mapped, mapped_column, sessionmaker
)

# --------------------------------------------------
# PAGE CONFIGURATION
# --------------------------------------------------

st.set_page_config(
    page_title="Staff Attendance | Presenze del personale",
    page_icon="📋",
    layout="wide"
)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///attendance.db")

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

Session = sessionmaker(bind=engine, expire_on_commit=False)


def create_sqlite_backup():
    """Create a timestamped backup before deleting records."""
    if engine.dialect.name != "sqlite":
        raise RuntimeError(
            "Automatic backup is configured for SQLite only. "
            "Back up the hosted database through its provider first."
        )

    database_path = engine.url.database

    if not database_path or database_path == ":memory:":
        raise RuntimeError("Could not identify a file-based SQLite database.")

    database_path = Path(database_path)

    if not database_path.is_absolute():
        database_path = Path.cwd() / database_path

    if not database_path.exists():
        raise FileNotFoundError(
            f"Database file not found: {database_path}"
        )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = database_path.with_name(
        f"attendance_backup_before_delete_{timestamp}.db"
    )

    with sqlite3.connect(str(database_path)) as source:
        with sqlite3.connect(str(backup_path)) as destination:
            source.backup(destination)

    return backup_path


# --------------------------------------------------
# DATABASE MODELS
# --------------------------------------------------

class Base(DeclarativeBase):
    pass


class Staff(Base):
    __tablename__ = "staff"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)

    partita_iva: Mapped[str | None] = mapped_column(
        String(30), nullable=True
    )
    email: Mapped[str | None] = mapped_column(
        String(254), nullable=True
    )
    codice_fiscale: Mapped[str | None] = mapped_column(
        String(16), nullable=True
    )
    telefono: Mapped[str | None] = mapped_column(
        String(30), nullable=True
    )

    active: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False
    )


class Attendance(Base):
    __tablename__ = "attendance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    staff_id: Mapped[int] = mapped_column(
        ForeignKey("staff.id"), nullable=False
    )
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        String(40), nullable=False, default="Present"
    )
    start_time: Mapped[time | None] = mapped_column(
        Time, nullable=True
    )
    end_time: Mapped[time | None] = mapped_column(
        Time, nullable=True
    )
    notes: Mapped[str] = mapped_column(String(500), default="")

    __table_args__ = (
        UniqueConstraint("staff_id", "work_date", name="uq_staff_day"),
    )


# Create tables if they do not exist.
Base.metadata.create_all(engine)


# --------------------------------------------------
# SAFE DATABASE MIGRATIONS
# Existing staff and attendance records are preserved.
# --------------------------------------------------

staff_columns = {
    column["name"]
    for column in inspect(engine).get_columns("staff")
}

new_columns = {
    "partita_iva": "VARCHAR(30)",
    "email": "VARCHAR(254)",
    "codice_fiscale": "VARCHAR(16)",
    "telefono": "VARCHAR(30)",
}

for column_name, column_type in new_columns.items():
    if column_name not in staff_columns:
        with engine.begin() as connection:
            connection.execute(
                text(
                    f"ALTER TABLE staff ADD COLUMN "
                    f"{column_name} {column_type}"
                )
            )


# --------------------------------------------------
# TRANSLATIONS
# --------------------------------------------------

TRANSLATIONS = {
    "English": {
        "nav": "Navigation",
        "dashboard": "Dashboard",
        "record": "Record attendance",
        "staff": "Staff management",
        "weekly": "Weekly report",
        "title": "📋 Staff Attendance Management",
        "subtitle": "Daily attendance register and weekly report",
        "privacy": (
            "Use a private account/device. Only collect information "
            "needed for lawful workforce administration."
        ),
        "today": "Today",
        "active_staff": "Active staff",
        "records_today": "Attendance records today",
        "present_today": "Present / attended today",
        "by_category": "Staff by category",
        "today_records": "Today's records",
        "no_today": "No attendance has been recorded for today yet.",
        "staff_management": "Staff management",
        "add_staff": "➕ Add staff member",
        "name": "Staff name",
        "category": "Category",
        "vat": "Partita IVA / VAT number (optional)",
        "email": "Email address (optional)",
        "tax_code": "Codice fiscale (optional)",
        "phone": "Phone number (optional)",
        "contact_details": "Contact details",
        "vat_help": "Enter the VAT number if applicable.",
        "add": "Add staff member",
        "enter_name": "Please enter a staff name.",
        "added": "Added",
        "staff_list": "Current staff list",
        "active": "Active",
        "inactive": "Inactive",
        "deactivate": "Deactivate",
        "reactivate": "Reactivate",
        "deactivate_note": (
            "Deactivating a staff member hides them from new attendance "
            "entries but keeps historical records."
        ),
        "save_details": "Save staff details",
        "details_saved": "Staff details updated successfully.",
        "record_title": "Record daily attendance",
        "attendance_date": "Attendance date",
        "person": "Staff member",
        "status": "Attendance status",
        "start": "Start time",
        "end": "End time",
        "notes": "Notes (optional)",
        "save": "Save attendance",
        "saved": "Attendance saved for",
        "update_note": (
            "Saving the same person and date again updates the existing "
            "record instead of creating a duplicate."
        ),
        "weekly_title": "Weekly attendance report",
        "choose_day": "Choose any day in the week",
        "week": "Week",
        "filter": "Filter category",
        "all": "All categories",
        "no_week": "No attendance records found for this week.",
        "entries": "Attendance entries",
        "attended": "Present / attended",
        "absent": "Absent / not attended",
        "hours": "Recorded hours",
        "totals": "Totals by category",
        "detail": "Attendance details",
        "csv": "Download CSV",
        "excel": "Download Excel",
        "work_date": "Work date",
        "hours_col": "Hours",
        "total": "Total",
        "report_note": (
            "Hours are calculated from start and end times. Breaks are "
            "not deducted. These figures are not a payroll calculation."
        ),
        "empty_category": (
            "No active staff in this category yet. "
            "Add staff in Staff management."
        ),
    },

    "Italiano": {
        "nav": "Navigazione",
        "dashboard": "Riepilogo",
        "record": "Registra presenze",
        "staff": "Gestione del personale",
        "weekly": "Report settimanale",
        "title": "📋 Gestione presenze del personale",
        "subtitle": "Registro giornaliero delle presenze e report settimanale",
        "privacy": (
            "Usa un account e un dispositivo privati. Raccogli solo i dati "
            "necessari per una gestione del personale conforme alla legge."
        ),
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
        "vat": "Partita IVA (facoltativa)",
        "email": "Indirizzo e-mail (facoltativo)",
        "tax_code": "Codice fiscale (facoltativo)",
        "phone": "Numero di telefono (facoltativo)",
        "contact_details": "Dati di contatto",
        "vat_help": "Inserisci la Partita IVA se applicabile.",
        "add": "Aggiungi persona",
        "enter_name": "Inserisci il nome della persona.",
        "added": "Aggiunto/a",
        "staff_list": "Elenco del personale",
        "active": "Attivo",
        "inactive": "Non attivo",
        "deactivate": "Disattiva",
        "reactivate": "Riattiva",
        "deactivate_note": (
            "Disattivando una persona, questa non apparirà nelle nuove "
            "registrazioni, ma lo storico verrà conservato."
        ),
        "save_details": "Salva i dati della persona",
        "details_saved": "Dati del personale aggiornati correttamente.",
        "record_title": "Registra le presenze giornaliere",
        "attendance_date": "Data della presenza",
        "person": "Persona",
        "status": "Stato della presenza",
        "start": "Ora di inizio",
        "end": "Ora di fine",
        "notes": "Note (facoltative)",
        "save": "Salva presenza",
        "saved": "Presenza salvata per",
        "update_note": (
            "Se salvi di nuovo la stessa persona per la stessa data, "
            "la registrazione esistente viene aggiornata e non duplicata."
        ),
        "weekly_title": "Report settimanale delle presenze",
        "choose_day": "Scegli un giorno della settimana",
        "week": "Settimana",
        "filter": "Filtra per categoria",
        "all": "Tutte le categorie",
        "no_week": "Nessuna presenza registrata per questa settimana.",
        "entries": "Registrazioni",
        "attended": "Presenti / intervenuti",
        "absent": "Assenti / non intervenuti",
        "hours": "Ore registrate",
        "totals": "Totali per categoria",
        "detail": "Dettaglio presenze",
        "csv": "Scarica CSV",
        "excel": "Scarica Excel",
        "work_date": "Data",
        "hours_col": "Ore",
        "total": "Totale",
        "report_note": (
            "Le ore sono calcolate tra l'ora di inizio e quella di fine. "
            "Le pause non vengono detratte. Questi dati non costituiscono "
            "un calcolo della retribuzione."
        ),
        "empty_category": (
            "Non ci sono ancora persone attive in questa categoria. "
            "Aggiungile in Gestione del personale."
        ),
    }
}


# --------------------------------------------------
# CATEGORIES AND STATUSES
# --------------------------------------------------

CATEGORIES = [
    "Officially registered",
    "Not officially registered",
    "On-call staff",
]

CATEGORY_IT = {
    "Officially registered": "Personale regolarmente assunto",
    "Not officially registered": "Personale a prestazione occasionale",
    "On-call staff": "Personale a chiamata",
}

STATUSES = [
    "Present",
    "Assente",
    "Absent",
    "Leave",
    "Called in - attended",
    "Called in - did not attend",
]

STATUS_IT = {
    "Present": "Presente",
    "Assente": "Assente",
    "Absent": "Assente",
    "Leave": "Permesso / ferie",
    "Called in - attended": "Chiamato/a - presente",
    "Called in - did not attend": "Chiamato/a - non presente",
}

ZERO_HOUR_STATUSES = {
    "Assente",
    "Absent",
    "Leave",
    "Called in - did not attend",
}


# --------------------------------------------------
# LANGUAGE SELECTOR AND NAVIGATION
# --------------------------------------------------

with st.sidebar:
    language = st.selectbox(
        "Lingua / Language",
        ["Italiano", "English"],
        index=0,
        key="app_language"
    )

    def tr(key):
        return TRANSLATIONS[language][key]

    def category_label(category):
        if language == "Italiano":
            return CATEGORY_IT.get(category, category)
        return category

    def status_label(status):
        if language == "Italiano":
            if status is None or pd.isna(status):
                return status

            normalized = str(status).strip().casefold()

            for original, translated in STATUS_IT.items():
                if original.casefold() == normalized:
                    return translated

        return status

    st.header(tr("nav"))

    page_options = [
        tr("dashboard"),
        tr("record"),
        tr("staff"),
        tr("weekly"),
    ]

    page = st.radio(
        "Menu",
        page_options,
        label_visibility="collapsed"
    )

    st.divider()
    st.caption(tr("privacy"))


# --------------------------------------------------
# DATABASE FUNCTIONS
# --------------------------------------------------

def all_staff(active_only=True):
    with Session() as session:
        query = session.query(Staff)

        if active_only:
            query = query.filter(Staff.active == 1)

        return query.order_by(Staff.category, Staff.name).all()


def get_attendance(staff_id, work_date):
    with Session() as session:
        return session.query(Attendance).filter_by(
            staff_id=staff_id,
            work_date=work_date
        ).first()


def save_attendance(
    staff_id, work_date, status, start_time, end_time, notes
):
    if status in ZERO_HOUR_STATUSES:
        start_time = None
        end_time = None

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

        session.commit()


def attendance_frame(start_date, end_date, category=None):
    with Session() as session:
        rows = session.execute(
            text("""
                SELECT
                    a.work_date,
                    st.name,
                    st.category,
                    a.status,
                    a.start_time,
                    a.end_time,
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

    df["work_date"] = pd.to_datetime(df["work_date"]).dt.date

    def format_time(value):
        if value is None or pd.isna(value):
            return ""

        if hasattr(value, "strftime"):
            return value.strftime("%H:%M")

        value_text = str(value)

        try:
            return datetime.strptime(
                value_text[:8], "%H:%M:%S"
            ).strftime("%H:%M")
        except ValueError:
            try:
                return datetime.strptime(
                    value_text[:5], "%H:%M"
                ).strftime("%H:%M")
            except ValueError:
                return value_text

    df["start_time"] = df["start_time"].apply(format_time)
    df["end_time"] = df["end_time"].apply(format_time)

    def calculate_hours(row):
        status_value = (
            str(row["status"]).strip()
            if pd.notna(row["status"])
            else ""
        )

        zero_hour_lookup = {
            value.casefold() for value in ZERO_HOUR_STATUSES
        }

        if status_value.casefold() in zero_hour_lookup:
            return 0.0

        try:
            start = datetime.strptime(row["start_time"], "%H:%M")
            end = datetime.strptime(row["end_time"], "%H:%M")

            duration = (end - start).total_seconds() / 3600

            if duration < 0:
                duration += 24

            return round(duration, 2)

        except (ValueError, TypeError):
            return 0.0

    df["hours"] = df.apply(calculate_hours, axis=1)

    return df


# --------------------------------------------------
# DISPLAY DATAFRAME
# --------------------------------------------------

def display_dataframe(df):
    result = df.copy()

    if result.empty:
        return result

    for column in ["category", "status"]:
        if column in result.columns:
            result[column] = result[column].apply(
                lambda value: (
                    str(value).strip()
                    if pd.notna(value)
                    else value
                )
            )

    if language == "Italiano":
        category_lookup = {
            key.strip().casefold(): value
            for key, value in CATEGORY_IT.items()
        }

        status_lookup = {
            key.strip().casefold(): value
            for key, value in STATUS_IT.items()
        }

        if "category" in result.columns:
            result["category"] = result["category"].apply(
                lambda value: (
                    category_lookup.get(value.casefold(), value)
                    if isinstance(value, str)
                    else value
                )
            )

        if "status" in result.columns:
            result["status"] = result["status"].apply(
                lambda value: (
                    status_lookup.get(value.casefold(), value)
                    if isinstance(value, str)
                    else value
                )
            )

        if "notes" in result.columns:
            note_translations = {
                "absent": "Assente",
                "assente": "Assente",
                "present": "Presente",
                "leave": "Permesso / ferie",
            }

            result["notes"] = result["notes"].apply(
                lambda value: (
                    note_translations.get(
                        value.strip().casefold(), value
                    )
                    if isinstance(value, str)
                    else value
                )
            )

    result = result.rename(columns={
        "work_date": tr("work_date"),
        "name": (
            "Staff name" if language == "English"
            else "Nome del dipendente"
        ),
        "category": tr("category"),
        "status": tr("status"),
        "start_time": tr("start"),
        "end_time": tr("end"),
        "notes": tr("notes"),
        "hours": tr("hours_col"),
    })

    return result


def make_excel(df):
    output = BytesIO()
    sheet_name = "Attendance" if language == "English" else "Presenze"

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)

    output.seek(0)
    return output.getvalue()


# --------------------------------------------------
# MAIN PAGE HEADER
# --------------------------------------------------

st.title(tr("title"))
st.caption(tr("subtitle"))


# --------------------------------------------------
# DASHBOARD
# --------------------------------------------------

if page == tr("dashboard"):

    today = date.today()
    st.subheader(f"{tr('today')} — {today.strftime('%d/%m/%Y')}")

    people = all_staff()
    today_df = attendance_frame(today, today)

    col1, col2, col3 = st.columns(3)

    col1.metric(tr("active_staff"), len(people))
    col2.metric(
        tr("records_today"),
        0 if today_df.empty else len(today_df)
    )
    col3.metric(
        tr("present_today"),
        0 if today_df.empty else int(
            today_df["status"].fillna("").astype(str).str.strip()
            .str.casefold().isin([
                "present", "called in - attended"
            ]).sum()
        )
    )

    st.markdown(f"### {tr('by_category')}")

    for category in CATEGORIES:
        count = sum(
            1 for person in people if person.category == category
        )
        st.write(f"**{category_label(category)}:** {count}")

    if not today_df.empty:
        st.markdown(f"### {tr('today_records')}")
        st.dataframe(
            display_dataframe(today_df),
            width="stretch",
            hide_index=True
        )
    else:
        st.info(tr("no_today"))


# --------------------------------------------------
# STAFF MANAGEMENT
# --------------------------------------------------

elif page == tr("staff"):

    st.subheader(tr("staff_management"))

    # ADD STAFF
    with st.expander(tr("add_staff"), expanded=True):
        with st.form("add_staff_form", clear_on_submit=True):

            name = st.text_input(tr("name"))

            category = st.selectbox(
                tr("category"),
                CATEGORIES,
                format_func=category_label
            )

            st.markdown(f"**{tr('contact_details')}**")

            partita_iva = st.text_input(
                tr("vat"),
                max_chars=30,
                help=tr("vat_help")
            )

            email = st.text_input(
                tr("email"),
                max_chars=254
            )

            codice_fiscale = st.text_input(
                tr("tax_code"),
                max_chars=16
            )

            telefono = st.text_input(
                tr("phone"),
                max_chars=30
            )

            submitted = st.form_submit_button(
                tr("add"),
                type="primary"
            )

            if submitted:
                if not name.strip():
                    st.error(tr("enter_name"))
                else:
                    with Session() as session:
                        session.add(
                            Staff(
                                name=name.strip(),
                                category=category,
                                partita_iva=partita_iva.strip() or None,
                                email=email.strip() or None,
                                codice_fiscale=(
                                    codice_fiscale.strip().upper() or None
                                ),
                                telefono=telefono.strip() or None,
                                active=1
                            )
                        )
                        session.commit()

                    st.success(f"{tr('added')} {name.strip()}.")
                    st.rerun()

    # --------------------------------------------------
    # DANGER ZONE: PERMANENT DELETION
    # --------------------------------------------------

    st.divider()

    if language == "Italiano":
        st.subheader("Zona pericolosa — Eliminazione definitiva")

        st.warning(
            "Questa operazione eliminerà definitivamente TUTTO il personale "
            "e TUTTE le relative registrazioni delle presenze. "
            "Prima dell'eliminazione verrà creata una copia di sicurezza "
            "del database SQLite. L'operazione non può essere annullata "
            "dall'app."
        )

        confirm_label = (
            "Scrivi ELIMINA TUTTO per confermare l'eliminazione definitiva"
        )
        delete_button_label = (
            "Elimina DEFINITIVAMENTE tutto il personale e tutte le presenze"
        )
        confirm_word = "ELIMINA TUTTO"

    else:
        st.subheader("Danger zone — Permanent deletion")

        st.warning(
            "This permanently deletes ALL staff members and ALL their "
            "attendance records. A local SQLite backup will be created first. "
            "This action cannot be undone from the app."
        )

        confirm_label = "Type DELETE ALL to confirm permanent deletion"
        delete_button_label = (
            "Permanently delete ALL staff and attendance"
        )
        confirm_word = "DELETE ALL"

    confirm_delete_text = st.text_input(
        confirm_label,
        key="confirm_delete_all_staff"
    )

    if st.button(
        delete_button_label,
        type="primary",
        disabled=(confirm_delete_text != confirm_word),
        key="delete_all_staff_button"
    ):
        try:
            backup_path = create_sqlite_backup()

            with Session() as session:
                session.query(Attendance).delete(
                    synchronize_session=False
                )
                session.query(Staff).delete(
                    synchronize_session=False
                )
                session.commit()

            st.success(
                (
                    "Tutto il personale e tutte le presenze sono stati "
                    "eliminati. Copia di sicurezza salvata in: "
                    if language == "Italiano"
                    else "All staff and attendance records were deleted. "
                    "Backup saved at: "
                ) + str(backup_path)
            )
            st.rerun()

        except Exception as exc:
            st.error(
                "Errore durante l'operazione / Error during operation: "
                f"{exc}"
            )

    # --------------------------------------------------
    # STAFF LIST AND EDITABLE CONTACT DETAILS
    # --------------------------------------------------

    people = all_staff(active_only=False)

    if people:
        st.markdown(f"### {tr('staff_list')}")

        for person in people:
            with st.container(border=True):

                col1, col2, col3 = st.columns([2, 2, 2])

                col1.write(f"**{person.name}**")
                col2.write(category_label(person.category))
                col3.write(
                    f"**{tr('vat')}:** "
                    f"{person.partita_iva or '—'}"
                )

                st.write(
                    f"**{tr('email')}:** {person.email or '—'}"
                )
                st.write(
                    f"**{tr('tax_code')}:** "
                    f"{person.codice_fiscale or '—'}"
                )
                st.write(
                    f"**{tr('phone')}:** {person.telefono or '—'}"
                )

                col4, col5 = st.columns([1, 1])

                col4.write(
                    tr("active") if person.active else tr("inactive")
                )

                if person.active:
                    if col5.button(
                        tr("deactivate"),
                        key=f"deactivate_{person.id}"
                    ):
                        with Session() as session:
                            obj = session.get(Staff, person.id)
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
                            obj = session.get(Staff, person.id)
                            if obj:
                                obj.active = 1
                                session.commit()
                        st.rerun()

                with st.expander(
                    f"{tr('contact_details')} — {person.name}"
                ):
                    with st.form(f"staff_details_form_{person.id}"):

                        new_name = st.text_input(
                            tr("name"),
                            value=person.name,
                            key=f"name_{person.id}"
                        )

                        new_category = st.selectbox(
                            tr("category"),
                            CATEGORIES,
                            index=CATEGORIES.index(person.category),
                            format_func=category_label,
                            key=f"category_{person.id}"
                        )

                        new_vat = st.text_input(
                            tr("vat"),
                            value=person.partita_iva or "",
                            max_chars=30,
                            key=f"vat_{person.id}"
                        )

                        new_email = st.text_input(
                            tr("email"),
                            value=person.email or "",
                            max_chars=254,
                            key=f"email_{person.id}"
                        )

                        new_tax_code = st.text_input(
                            tr("tax_code"),
                            value=person.codice_fiscale or "",
                            max_chars=16,
                            key=f"tax_code_{person.id}"
                        )

                        new_phone = st.text_input(
                            tr("phone"),
                            value=person.telefono or "",
                            max_chars=30,
                            key=f"phone_{person.id}"
                        )

                        save_details = st.form_submit_button(
                            tr("save_details")
                        )

                        if save_details:
                            if not new_name.strip():
                                st.error(tr("enter_name"))
                            else:
                                with Session() as session:
                                    obj = session.get(Staff, person.id)

                                    if obj:
                                        obj.name = new_name.strip()
                                        obj.category = new_category
                                        obj.partita_iva = (
                                            new_vat.strip() or None
                                        )
                                        obj.email = (
                                            new_email.strip() or None
                                        )
                                        obj.codice_fiscale = (
                                            new_tax_code.strip().upper()
                                            or None
                                        )
                                        obj.telefono = (
                                            new_phone.strip() or None
                                        )
                                        session.commit()

                                st.success(tr("details_saved"))
                                st.rerun()

        st.caption(tr("deactivate_note"))


# --------------------------------------------------
# DAILY ATTENDANCE
# --------------------------------------------------

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
        person for person in all_staff()
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

        old = get_attendance(chosen.id, work_date)

        if old:
            default_status = old.status
        elif category == "On-call staff":
            default_status = "Called in - did not attend"
        else:
            default_status = "Present"

        normalized_default = str(default_status).strip().casefold()
        normalized_statuses = {
            item.casefold(): item for item in STATUSES
        }

        default_status = normalized_statuses.get(
            normalized_default, "Present"
        )

        status = st.selectbox(
            tr("status"),
            STATUSES,
            index=STATUSES.index(default_status),
            format_func=status_label
        )

        if status in ZERO_HOUR_STATUSES:
            start_time = None
            end_time = None

            if language == "Italiano":
                st.info(
                    "Per questo stato non è necessario inserire "
                    "l'ora di inizio o di fine. Le ore registrate saranno 0."
                )
            else:
                st.info(
                    "Start and end times are not required for this status. "
                    "Recorded hours will be 0."
                )

        else:
            col1, col2 = st.columns(2)

            default_start = (
                old.start_time if old and old.start_time else time(9, 0)
            )
            default_end = (
                old.end_time if old and old.end_time else time(17, 0)
            )

            start_time = col1.time_input(
                tr("start"),
                value=default_start
            )
            end_time = col2.time_input(
                tr("end"),
                value=default_end
            )

        notes = st.text_input(
            tr("notes"),
            value=old.notes if old else "",
            max_chars=500
        )

        if st.button(tr("save"), type="primary"):
            save_attendance(
                chosen.id,
                work_date,
                status,
                start_time,
                end_time,
                notes
            )

            st.success(
                f"{tr('saved')} {chosen.name} "
                f"({work_date.strftime('%d/%m/%Y')})."
            )

        st.caption(tr("update_note"))


# --------------------------------------------------
# WEEKLY REPORT
# --------------------------------------------------

elif page == tr("weekly"):

    st.subheader(tr("weekly_title"))

    selected_day = st.date_input(
        tr("choose_day"),
        value=date.today(),
        format="DD/MM/YYYY"
    )

    monday = selected_day - timedelta(days=selected_day.weekday())
    sunday = monday + timedelta(days=6)

    st.write(
        f"**{tr('week')}:** "
        f"{monday.strftime('%d/%m/%Y')} – "
        f"{sunday.strftime('%d/%m/%Y')}"
    )

    category_options = ["All categories"] + CATEGORIES

    category_filter = st.selectbox(
        tr("filter"),
        category_options,
        format_func=lambda item: (
            tr("all") if item == "All categories"
            else category_label(item)
        )
    )

    df = attendance_frame(
        monday,
        sunday,
        None if category_filter == "All categories"
        else category_filter
    )

    if df.empty:
        st.info(tr("no_week"))

    else:
        total_entries = len(df)

        normalized_statuses = (
            df["status"].fillna("").astype(str).str.strip().str.casefold()
        )

        attended_count = int(
            normalized_statuses.isin([
                "present", "called in - attended"
            ]).sum()
        )

        absent_count = int(
            normalized_statuses.isin([
                "assente",
                "absent",
                "called in - did not attend"
            ]).sum()
        )

        total_hours = float(df["hours"].sum())

        col1, col2, col3, col4 = st.columns(4)

        col1.metric(tr("entries"), total_entries)
        col2.metric(tr("attended"), attended_count)
        col3.metric(tr("absent"), absent_count)
        col4.metric(tr("hours"), f"{total_hours:.2f}")

        # SUMMARY BY CATEGORY AND STATUS
        st.markdown(f"### {tr('totals')}")

        summary_df = df.copy()
        summary_df["category"] = summary_df["category"].apply(
            category_label
        )
        summary_df["status"] = summary_df["status"].apply(status_label)

        summary = (
            summary_df.groupby(["category", "status"])
            .size()
            .unstack(fill_value=0)
        )

        summary[tr("total")] = summary.sum(axis=1)

        st.dataframe(
            summary.reset_index(),
            width="stretch",
            hide_index=True
        )

        # DETAILED WEEKLY REPORT
        st.markdown(f"### {tr('detail')}")

        report_df = display_dataframe(df)

        st.dataframe(
            report_df,
            width="stretch",
            hide_index=True
        )

        csv_data = report_df.to_csv(index=False).encode("utf-8-sig")

        filename_prefix = (
            "attendance" if language == "English" else "presenze"
        )

        col1, col2 = st.columns(2)

        col1.download_button(
            tr("csv"),
            data=csv_data,
            file_name=f"{filename_prefix}_{monday}_{sunday}.csv",
            mime="text/csv"
        )

        col2.download_button(
            tr("excel"),
            data=make_excel(report_df),
            file_name=f"{filename_prefix}_{monday}_{sunday}.xlsx",
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            )
        )

        st.caption(tr("report_note"))
