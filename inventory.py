
import os
from io import BytesIO
from datetime import date, datetime

import streamlit as st
import pandas as pd
from sqlalchemy import (
    create_engine, String, Integer, Float, Date, DateTime,
    ForeignKey, Text, func
)
from sqlalchemy.orm import (
    DeclarativeBase, Mapped, mapped_column, relationship,
    sessionmaker
)
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
)


# --------------------------------------------------
# DATABASE: USA LO STESSO DATABASE_URL DI app.py
# --------------------------------------------------

DATABASE_URL = os.getenv(
    "DATABASE_URL", "sqlite:///attendance.db"
)

# Compatibilità con il driver PostgreSQL già usato nel progetto.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace(
        "postgres://", "postgresql+psycopg://", 1
    )
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace(
        "postgresql://", "postgresql+psycopg://", 1
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

InventorySession = sessionmaker(
    bind=engine, expire_on_commit=False
)


class InventoryBase(DeclarativeBase):
    pass


class Product(InventoryBase):
    __tablename__ = "inventory_products"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True
    )
    code: Mapped[str] = mapped_column(
        String(80), unique=True, nullable=False
    )
    description: Mapped[str] = mapped_column(
        String(300), nullable=False
    )
    quantity: Mapped[float] = mapped_column(
        Float, default=0, nullable=False
    )
    min_quantity: Mapped[float] = mapped_column(
        Float, default=0, nullable=False
    )
    location: Mapped[str] = mapped_column(
        String(200), default="", nullable=False
    )
    supplier: Mapped[str] = mapped_column(
        String(200), default="", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )


class Order(InventoryBase):
    __tablename__ = "inventory_orders"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True
    )
    order_number: Mapped[str] = mapped_column(
        String(60), unique=True, nullable=False
    )
    order_date: Mapped[date] = mapped_column(
        Date, default=date.today, nullable=False
    )
    customer: Mapped[str] = mapped_column(
        String(250), default="", nullable=False
    )
    destination: Mapped[str] = mapped_column(
        String(300), default="", nullable=False
    )
    payment_method: Mapped[str] = mapped_column(
        String(100), default="Bonifico", nullable=False
    )
    notes: Mapped[str] = mapped_column(
        Text, default="", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )

    lines: Mapped[list["OrderLine"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan"
    )


class OrderLine(InventoryBase):
    __tablename__ = "inventory_order_lines"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True
    )
    order_id: Mapped[int] = mapped_column(
        ForeignKey("inventory_orders.id"), nullable=False
    )
    product_id: Mapped[int | None] = mapped_column(
        ForeignKey("inventory_products.id"), nullable=True
    )
    code: Mapped[str] = mapped_column(
        String(80), default="", nullable=False
    )
    description: Mapped[str] = mapped_column(
        String(300), nullable=False
    )
    quantity_ordered: Mapped[float] = mapped_column(
        Float, nullable=False
    )
    quantity_delivered: Mapped[float] = mapped_column(
        Float, default=0, nullable=False
    )
    unit_price: Mapped[float] = mapped_column(
        Float, default=0, nullable=False
    )
    discount_percent: Mapped[float] = mapped_column(
        Float, default=0, nullable=False
    )
    vat_percent: Mapped[float] = mapped_column(
        Float, default=22, nullable=False
    )

    order: Mapped["Order"] = relationship(
        back_populates="lines"
    )


# Creates ONLY these new inventory tables.
# Existing staff and attendance tables are not recreated or deleted.
InventoryBase.metadata.create_all(engine)


# --------------------------------------------------
# UTILITÀ
# --------------------------------------------------

def euro(value):
    return f"€ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def line_totals(line):
    imponibile = (
        line.quantity_ordered
        * line.unit_price
        * (1 - line.discount_percent / 100)
    )
    iva = imponibile * line.vat_percent / 100
    return imponibile, iva


def order_totals(order):
    imponibile = 0.0
    iva = 0.0

    for line in order.lines:
        line_imponibile, line_iva = line_totals(line)
        imponibile += line_imponibile
        iva += line_iva

    return imponibile, iva, imponibile + iva


def genera_pdf(order):
    output = BytesIO()

    doc = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm
    )

    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph(
        "<b>CONFERMA D'ORDINE</b>",
        styles["Title"]
    ))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph(
        f"<b>N.:</b> {order.order_number} "
        f"&nbsp;&nbsp;&nbsp; "
        f"<b>del:</b> {order.order_date.strftime('%d/%m/%Y')}",
        styles["Normal"]
    ))
    story.append(Spacer(1, 5 * mm))

    parties = [
        [
            Paragraph(
                f"<b>DESTINATARIO</b><br/>{order.customer or '-'}",
                styles["Normal"]
            ),
            Paragraph(
                f"<b>DESTINAZIONE</b><br/>{order.destination or '-'}",
                styles["Normal"]
            )
        ]
    ]

    party_table = Table(
        parties, colWidths=[88 * mm, 88 * mm],
        rowHeights=[25 * mm]
    )
    party_table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.7, colors.grey),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(party_table)
    story.append(Spacer(1, 5 * mm))

    rows = [[
        "Codice", "Descrizione", "Quantità",
        "Prezzo", "Sconto %", "Importo", "IVA %"
    ]]

    for line in order.lines:
        imponibile, _ = line_totals(line)
        rows.append([
            line.code or "-",
            Paragraph(line.description, styles["Normal"]),
            f"{line.quantity_ordered:g}",
            euro(line.unit_price),
            f"{line.discount_percent:g}",
            euro(imponibile),
            f"{line.vat_percent:g}"
        ])

    items_table = Table(
        rows,
        colWidths=[
            20 * mm, 48 * mm, 19 * mm, 21 * mm,
            18 * mm, 25 * mm, 15 * mm
        ],
        repeatRows=1
    )
    items_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 6 * mm))

    imponibile, iva, totale = order_totals(order)

    totals_table = Table([
        ["Modalità di pagamento", order.payment_method,
         "Tot. imponibile", euro(imponibile)],
        ["Note", order.notes or "-",
         "Tot. IVA", euro(iva)],
        ["", "", "Tot. documento", euro(totale)]
    ], colWidths=[35 * mm, 55 * mm, 38 * mm, 38 * mm])

    totals_table.setStyle(TableStyle([
        ("GRID", (2, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (2, 2), (-1, 2), colors.whitesmoke),
        ("FONTNAME", (2, 2), (-1, 2), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(totals_table)

    doc.build(story)
    output.seek(0)
    return output.getvalue()


# --------------------------------------------------
# SEZIONE MAGAZZINO & ORDINI
# --------------------------------------------------

def render_inventory():
    st.header("📦 Magazzino & Ordini")
    st.caption(
        "Gestione articoli, giacenze, ordini e quantità da consegnare."
    )

    tab_magazzino, tab_ordini, tab_consegne = st.tabs([
        "Magazzino",
        "Nuovo ordine",
        "Ordini e consegne"
    ])

    # ----------------------------------------------
    # MAGAZZINO
    # ----------------------------------------------
    with tab_magazzino:
        st.subheader("Articoli in magazzino")

        with st.form("nuovo_articolo", clear_on_submit=True):
            c1, c2 = st.columns(2)
            codice = c1.text_input("Codice articolo *")
            descrizione = c2.text_input("Descrizione *")

            c3, c4 = st.columns(2)
            quantita = c3.number_input(
                "Quantità attualmente disponibile",
                min_value=0.0, value=0.0, step=1.0
            )
            minimo = c4.number_input(
                "Scorta minima",
                min_value=0.0, value=0.0, step=1.0
            )

            c5, c6 = st.columns(2)
            ubicazione = c5.text_input("Ubicazione")
            fornitore = c6.text_input("Fornitore")

            salva_articolo = st.form_submit_button(
                "Salva articolo", type="primary"
            )

            if salva_articolo:
                if not codice.strip() or not descrizione.strip():
                    st.error("Inserisci il codice e la descrizione.")
                else:
                    with InventorySession() as session:
                        exists = session.query(Product).filter(
                            func.lower(Product.code) ==
                            codice.strip().lower()
                        ).first()

                        if exists:
                            st.error(
                                "Questo codice esiste già. "
                                "Usa un codice diverso."
                            )
                        else:
                            session.add(Product(
                                code=codice.strip(),
                                description=descrizione.strip(),
                                quantity=quantita,
                                min_quantity=minimo,
                                location=ubicazione.strip(),
                                supplier=fornitore.strip()
                            ))
                            session.commit()
                            st.success("Articolo salvato nel database.")
                            st.rerun()

        with InventorySession() as session:
            products = session.query(Product).order_by(
                Product.description
            ).all()

            product_rows = [{
                "Codice": p.code,
                "Descrizione": p.description,
                "Giacenza": p.quantity,
                "Scorta minima": p.min_quantity,
                "Ubicazione": p.location,
                "Fornitore": p.supplier
            } for p in products]

        if product_rows:
            st.dataframe(
                pd.DataFrame(product_rows),
                use_container_width=True,
                hide_index=True
            )

            low_stock = [
                p for p in product_rows
                if p["Giacenza"] <= p["Scorta minima"]
            ]
            if low_stock:
                st.warning(
                    f"Attenzione: {len(low_stock)} articoli "
                    "sono alla scorta minima o sotto la soglia."
                )
        else:
            st.info("Nessun articolo registrato.")

    # ----------------------------------------------
    # CREAZIONE ORDINE
    # ----------------------------------------------
    with tab_ordini:
        st.subheader("Crea conferma d'ordine")

        with InventorySession() as session:
            product_options = session.query(Product).order_by(
                Product.description
            ).all()

            product_choices = {
                f"{p.code} — {p.description}": p.id
                for p in product_options
            }

        with st.form("nuovo_ordine", clear_on_submit=True):
            c1, c2 = st.columns(2)
            numero = c1.text_input(
                "Numero ordine *",
                value=f"ORD-{date.today():%Y%m%d}"
            )
            data_ordine = c2.date_input(
                "Data ordine", value=date.today(),
                format="DD/MM/YYYY"
            )

            c3, c4 = st.columns(2)
            cliente = c3.text_input("Destinatario / Cliente *")
            destinazione = c4.text_input("Indirizzo di destinazione")

            pagamento = st.selectbox(
                "Modalità di pagamento",
                ["Bonifico", "Contanti", "Carta", "Altro"]
            )

            usa_catalogo = st.checkbox(
                "Seleziona un articolo già presente in magazzino"
            )

            prodotto_id = None
            codice_riga = ""
            descrizione_riga = ""

            if usa_catalogo:
                if product_choices:
                    scelta = st.selectbox(
                        "Articolo", list(product_choices.keys())
                    )
                    prodotto_id = product_choices[scelta]
                    prodotto = next(
                        p for p in product_options
                        if p.id == prodotto_id
                    )
                    codice_riga = prodotto.code
                    descrizione_riga = prodotto.description
                else:
                    st.warning(
                        "Prima registra un articolo nella scheda Magazzino."
                    )
            else:
                c5, c6 = st.columns(2)
                codice_riga = c5.text_input("Codice articolo")
                descrizione_riga = c6.text_input(
                    "Descrizione articolo *"
                )

            c7, c8, c9 = st.columns(3)
            q_ordinata = c7.number_input(
                "Quantità ordinata", min_value=0.01,
                value=1.0, step=1.0
            )
            prezzo = c8.number_input(
                "Prezzo unitario (€)", min_value=0.0,
                value=0.0, step=0.01
            )
            sconto = c9.number_input(
                "Sconto (%)", min_value=0.0,
                max_value=100.0, value=0.0, step=1.0
            )

            c10, c11 = st.columns(2)
            iva_percent = c10.selectbox(
                "Aliquota IVA (%)", [22.0, 10.0, 5.0, 4.0, 0.0]
            )
            consegnata = c11.number_input(
                "Quantità già consegnata",
                min_value=0.0, value=0.0, step=1.0
            )

            note = st.text_area("Note")
            crea_ordine = st.form_submit_button(
                "Salva ordine", type="primary"
            )

            if crea_ordine:
                if not numero.strip() or not cliente.strip():
                    st.error(
                        "Numero ordine e destinatario sono obbligatori."
                    )
                elif q_ordinata <= 0:
                    st.error("La quantità deve essere maggiore di zero.")
                elif consegnata > q_ordinata:
                    st.error(
                        "La quantità consegnata non può superare "
                        "quella ordinata."
                    )
                elif usa_catalogo and not product_choices:
                    st.error("Registra prima un articolo in magazzino.")
                elif not usa_catalogo and not descrizione_riga.strip():
                    st.error("Inserisci la descrizione dell'articolo.")
                else:
                    with InventorySession() as session:
                        duplicate = session.query(Order).filter_by(
                            order_number=numero.strip()
                        ).first()

                        if duplicate:
                            st.error("Questo numero ordine esiste già.")
                        else:
                            ordine = Order(
                                order_number=numero.strip(),
                                order_date=data_ordine,
                                customer=cliente.strip(),
                                destination=destinazione.strip(),
                                payment_method=pagamento,
                                notes=note.strip()
                            )
                            ordine.lines.append(OrderLine(
                                product_id=prodotto_id,
                                code=codice_riga.strip(),
                                description=descrizione_riga.strip(),
                                quantity_ordered=q_ordinata,
                                quantity_delivered=consegnata,
                                unit_price=prezzo,
                                discount_percent=sconto,
                                vat_percent=iva_percent
                            ))
                            session.add(ordine)
                            session.commit()

                            st.success(
                                "Ordine salvato nel database Neon."
                            )
                            st.rerun()

    # ----------------------------------------------
    # ORDINI E CONSEGNE
    # ----------------------------------------------
    with tab_consegne:
        st.subheader("Ordini registrati")

        with InventorySession() as session:
            orders = session.query(Order).order_by(
                Order.order_date.desc(), Order.id.desc()
            ).all()

            order_options = {
                f"{o.order_number} — {o.customer} "
                f"({o.order_date:%d/%m/%Y})": o.id
                for o in orders
            }

            order_rows = []
            for o in orders:
                imponibile, iva, totale = order_totals(o)
                for line in o.lines:
                    order_rows.append({
                        "Ordine": o.order_number,
                        "Data": o.order_date.strftime("%d/%m/%Y"),
                        "Destinatario": o.customer,
                        "Articolo": line.description,
                        "Quantità ordinata": line.quantity_ordered,
                        "Quantità consegnata": line.quantity_delivered,
                        "Da consegnare": max(
                            0, line.quantity_ordered -
                            line.quantity_delivered
                        ),
                        "Totale ordine": euro(totale)
                    })

        if order_rows:
            st.dataframe(
                pd.DataFrame(order_rows),
                use_container_width=True,
                hide_index=True
            )

            st.divider()
            st.subheader("Aggiorna consegna e scarica PDF")

            scelta_ordine = st.selectbox(
                "Seleziona ordine", list(order_options.keys())
            )
            ordine_id = order_options[scelta_ordine]

            with InventorySession() as session:
                ordine = session.get(Order, ordine_id)

                if ordine and ordine.lines:
                    linea = ordine.lines[0]
                    residua = max(
                        0,
                        linea.quantity_ordered -
                        linea.quantity_delivered
                    )

                    nuova_consegna = st.number_input(
                        "Quantità aggiuntiva consegnata",
                        min_value=0.0,
                        max_value=float(residua),
                        value=0.0,
                        step=1.0,
                        key=f"delivery_{ordine.id}_{linea.id}"
                    )

                    if st.button(
                        "Registra consegna", type="primary"
                    ):
                        # Aggiorna solo la quantità consegnata.
                        # La giacenza non viene modificata automaticamente.
                        linea.quantity_delivered += nuova_consegna
                        session.commit()
                        st.success("Consegna aggiornata.")
                        st.rerun()

                    pdf_bytes = genera_pdf(ordine)

                    st.download_button(
                        "📄 Scarica PDF — Conferma d'ordine",
                        data=pdf_bytes,
                        file_name=f"conferma_ordine_{ordine.order_number}.pdf",
                        mime="application/pdf"
                    )
        else:
            st.info("Non ci sono ancora ordini registrati.")
