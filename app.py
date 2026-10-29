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
    """Create a timestamped backup before destructive database changes."""

    if engine.dialect.name != "sqlite":
        raise RuntimeError(
            "Automatic backup is configured for SQLite only. "
            "Back up your hosted database through its provider first."
        )

    database_path = engine.url.database

    if not database_path or database_path == ":memory:":
        raise RuntimeError(
            "Could not identify a file-based SQLite database."
        )

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
    codice_fiscale: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )
    email: Mapped[str | None] = mapped_column(
        String(150), nullable=True
    )
    phone: Mapped[str | None] = mapped_column(
        String(30), nullable=True
    )

    active: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


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
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    notes: Mapped[str] = mapped_column(String(500), default="")

    __table_args__ = (
        UniqueConstraint("staff_id", "work_date", name="uq_staff_day"),
    )


# Create tables that do not exist yet.
Base.metadata.create_all(engine)


# Add any missing staff columns without deleting existing records.
staff_columns = {
    column["name"] for column in inspect(engine).get_columns("staff")
}

new_columns = {
    "partita_iva": "VARCHAR(30)",
    "codice_fiscale": "VARCHAR(20)",
    "email": "VARCHAR(150)",
    "phone": "VARCHAR(30)",
}

with engine.begin() as connection:
    for column_name, column_type in new_columns.items():
        if column_name not in staff_columns:
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
        "language": "Language / Lingua",
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
        "vat_help": "Enter the VAT number if applicable. Leave blank if not applicable.",
        "tax_code": "Codice Fiscale (optional)",
        "email": "Email address (optional)",
        "phone": "Phone number (optional)",
        "save_details": "Save staff details",
        "edit_details": "Edit staff details",
        "details_saved": "Staff details updated successfully.",
        "not_provided": "Not provided",
        "save_vat": "Save Partita IVA",
        "edit_vat": "Edit Partita IVA",
        "no_vat": "Not provided",
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
        "vat_saved": "Partita IVA updated successfully.",
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
            "No active staff in this category yet. Add staff in Staff management."
        ),
        "called_absent_default": "Called in - did not attend",
        "present_default": "Present",
    },

    "Italiano": {
        "nav": "Navigazione",
        "language": "Lingua / Language",
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
        "vat_help": "Inserisci la Partita IVA se applicabile. Lascia vuoto se non applicabile.",
        "tax_code": "Codice Fiscale (facoltativo)",
        "email": "Indirizzo e-mail (facoltativo)",
        "phone": "Numero di telefono (facoltativo)",
        "save_details": "Salva i dati",
        "edit_details": "Modifica i dati",
        "details_saved": "Dati aggiornati correttamente.",
        "not_provided": "Non inserito",
        "save_vat": "Salva Partita IVA",
        "edit_vat": "Modifica Partita IVA",
        "no_vat": "Non inserita",
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
        "vat_saved": "Partita IVA aggiornata correttamente.",
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
        "called_absent_default": "Chiamato/a - non presente",
        "present_default": "Presente",
    }
}


CATEGORIES = [
    "Officially registered",
    "Not officially registered",
    "On-call staff",
]

CATEGORY_IT = {
    "Officially registered": "Personale regolarmente assunto",
    "Not officially registered": "Personale non regolarmente registrato",
    "On-call staff": "Personale a chiamata",
}

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
            return STATUS_IT.get(status, status)
        return status

    st.header(tr("nav"))

    page_options = [
        tr("dashboard"),
        tr("record"),
        tr("staff"),
        tr("weekly"),
        "Magazzino"
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

    df["start_time"] = df["start_time"].apply(
        lambda value: (
            value.strftime("%H:%M")
            if hasattr(value, "strftime")
            else str(value)[:5] if value else ""
        )
    )

    df["end_time"] = df["end_time"].apply(
        lambda value: (
            value.strftime("%H:%M")
            if hasattr(value, "strftime")
            else str(value)[:5] if value else ""
        )
    )

    def calculate_hours(row):
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


def display_dataframe(df):
    result = df.copy()

    if result.empty:
        return result

    result["category"] = result["category"].apply(category_label)
    result["status"] = result["status"].apply(status_label)

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

if page == "Magazzino":
    from inventory import render_inventory
    render_inventory()
    st.stop()


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
            today_df["status"].isin([
                "Present", "Called in - attended"
            ]).sum()
        )
    )

    st.markdown(f"### {tr('by_category')}")

    for category in CATEGORIES:
        count = sum(1 for person in people if person.category == category)
        st.write(f"**{category_label(category)}:** {count}")

    if not today_df.empty:
        st.markdown(f"### {tr('today_records')}")
        st.dataframe(
            display_dataframe(today_df),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info(tr("no_today"))


# --------------------------------------------------
# STAFF MANAGEMENT
# --------------------------------------------------

elif page == tr("staff"):

    st.subheader(tr("staff_management"))

    # ADD STAFF MEMBER
    with st.expander(tr("add_staff"), expanded=True):
        with st.form("add_staff_form", clear_on_submit=True):

            name = st.text_input(tr("name"))

            category = st.selectbox(
                tr("category"),
                CATEGORIES,
                format_func=category_label
            )

            partita_iva = st.text_input(
                tr("vat"),
                max_chars=30,
                help=tr("vat_help")
            )

            codice_fiscale = st.text_input(
                tr("tax_code"),
                max_chars=20
            )

            email = st.text_input(
                tr("email")
            )

            phone = st.text_input(
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
                                codice_fiscale=codice_fiscale.strip() or None,
                                email=email.strip() or None,
                                phone=phone.strip() or None
                            )
                        )
                        session.commit()

                    st.success(f"{tr('added')} {name.strip()}.")
                    st.rerun()

    # --------------------------------------------------
    # DELETE ONE STAFF MEMBER
    # --------------------------------------------------

    st.divider()

    if language == "Italiano":
        st.subheader("🗑️ Elimina una persona")
        st.warning(
            "Seleziona una sola persona. Verranno eliminate anche tutte "
            "le sue presenze registrate. Questa operazione è definitiva."
        )
        selection_prompt = "Seleziona la persona da eliminare:"
        confirm_label = "Confermo di voler eliminare questa persona"
        delete_button_label = "Elimina la persona selezionata"
        backup_warning = (
            "Il database PostgreSQL non viene salvato automaticamente da "
            "questa app. Prima di procedere, assicurati di avere un backup."
        )
        success_message = "La persona e le sue presenze sono state eliminate."
        missing_message = "La persona selezionata non è stata trovata."
        backup_label = "Backup creato: "
    else:
        st.subheader("🗑️ Delete one staff member")
        st.warning(
            "Select exactly one person. All attendance records belonging "
            "to that person will also be deleted. This cannot be undone."
        )
        selection_prompt = "Check the box next to the person to delete:"
        confirm_label = "I confirm that I want to delete this person"
        delete_button_label = "Delete selected person"
        backup_warning = (
            "This app does not automatically back up PostgreSQL. "
            "Make sure you have a database backup before proceeding."
        )
        success_message = "The person and their attendance records were deleted."
        missing_message = "The selected person could not be found."
        backup_label = "Backup created: "

    people_to_delete = all_staff(active_only=False)

    if not people_to_delete:
        st.info(
            "Nessuna persona presente nell'elenco."
            if language == "Italiano"
            else "There are no staff members to display."
        )
    else:
        st.write(selection_prompt)
        selected_staff_ids = []

        for person_to_delete in people_to_delete:
            checkbox_label = (
                f"{person_to_delete.name} — "
                f"{category_label(person_to_delete.category)}"
            )
            if st.checkbox(
                checkbox_label,
                key=f"delete_staff_checkbox_{person_to_delete.id}"
            ):
                selected_staff_ids.append(person_to_delete.id)

        if len(selected_staff_ids) > 1:
            st.warning(
                "Seleziona una sola persona alla volta."
                if language == "Italiano"
                else "Please select only one person at a time."
            )

        confirm_delete = st.checkbox(
            confirm_label,
            key="confirm_delete_selected_staff"
        )

        if st.button(
            delete_button_label,
            type="primary",
            key="delete_selected_staff_button",
            disabled=(len(selected_staff_ids) != 1 or not confirm_delete)
        ):
            selected_staff_id = selected_staff_ids[0]
            try:
                backup_path = None
                if engine.dialect.name == "sqlite":
                    backup_path = create_sqlite_backup()
                else:
                    st.warning(backup_warning)

                with Session() as session:
                    person = session.get(Staff, selected_staff_id)
                    if person is None:
                        st.error(missing_message)
                    else:
                        session.query(Attendance).filter(
                            Attendance.staff_id == selected_staff_id
                        ).delete(synchronize_session=False)
                        session.delete(person)
                        session.commit()

                        st.success(success_message)
                        if backup_path:
                            st.info(f"{backup_label}{backup_path}")
                        st.rerun()

            except Exception as exc:
                st.error(
                    "Errore durante l'eliminazione / Error while deleting: "
                    f"{type(exc).__name__}: {exc}"
                )

    # --------------------------------------------------
    # STAFF LIST AND EDIT DETAILS
    # --------------------------------------------------

    people = all_staff(active_only=False)

    if people:
        st.markdown(f"### {tr('staff_list')}")

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
                    f"{tr('edit_details')} — {person.name}"
                ):
                    with st.form(f"staff_details_form_{person.id}"):

                        new_vat = st.text_input(
                            tr("vat"),
                            value=person.partita_iva or "",
                            max_chars=30,
                            key=f"vat_input_{person.id}",
                            help=tr("vat_help")
                        )

                        new_tax_code = st.text_input(
                            tr("tax_code"),
                            value=person.codice_fiscale or "",
                            max_chars=20,
                            key=f"tax_code_input_{person.id}"
                        )

                        new_email = st.text_input(
                            tr("email"),
                            value=person.email or "",
                            key=f"email_input_{person.id}"
                        )

                        new_phone = st.text_input(
                            tr("phone"),
                            value=person.phone or "",
                            max_chars=30,
                            key=f"phone_input_{person.id}"
                        )

                        save_details = st.form_submit_button(
                            tr("save_details")
                        )

                        if save_details:
                            with Session() as session:
                                obj = session.get(Staff, person.id)

                                if obj:
                                    obj.partita_iva = new_vat.strip() or None
                                    obj.codice_fiscale = (
                                        new_tax_code.strip() or None
                                    )
                                    obj.email = new_email.strip() or None
                                    obj.phone = new_phone.strip() or None

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

        status = st.selectbox(
            tr("status"),
            STATUSES,
            index=STATUSES.index(default_status),
            format_func=status_label
        )

        col1, col2 = st.columns(2)

        default_start = (
            old.start_time if old and old.start_time else time(9, 0)
        )
        default_end = (
            old.end_time if old and old.end_time else time(17, 0)
        )

        start_time = col1.time_input(tr("start"), value=default_start)
        end_time = col2.time_input(tr("end"), value=default_end)

        notes = st.text_input(
            tr("notes"),
            value=old.notes if old else "",
            max_chars=500
        )

        if st.button(tr("save"), type="primary"):
            save_attendance(
                chosen.id, work_date, status,
                start_time, end_time, notes
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

        attended_count = int(
            df["status"].isin([
                "Present", "Called in - attended"
            ]).sum()
        )

        absent_count = int(
            df["status"].isin([
                "Absent", "Called in - did not attend"
            ]).sum()
        )

        total_hours = float(df["hours"].sum())

        col1, col2, col3, col4 = st.columns(4)
        col1.metric(tr("entries"), total_entries)
        col2.metric(tr("attended"), attended_count)
        col3.metric(tr("absent"), absent_count)
        col4.metric(tr("hours"), f"{total_hours:.2f}")

        st.markdown(f"### {tr('totals')}")

        summary_df = df.copy()
        summary_df["category"] = summary_df["category"].apply(category_label)
        summary_df["status"] = summary_df["status"].apply(status_label)

        summary = (
            summary_df.groupby(["category", "status"])
            .size()
            .unstack(fill_value=0)
        )

        summary[tr("total")] = summary.sum(axis=1)

        st.dataframe(
            summary.reset_index(),
            use_container_width=True,
            hide_index=True
        )

        st.markdown(f"### {tr('detail')}")
        report_df = display_dataframe(df)

        st.dataframe(
            report_df,
            use_container_width=True,
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