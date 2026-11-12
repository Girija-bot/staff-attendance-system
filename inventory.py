import os
import uuid
from io import BytesIO
from datetime import date, datetime
from xml.sax.saxutils import escape

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

# DATABASE

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///attendance.db")

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
    DATABASE_URL, connect_args=connect_args, pool_pre_ping=True
)

InventorySession = sessionmaker(bind=engine, expire_on_commit=False)


class InventoryBase(DeclarativeBase):
    pass


class Product(InventoryBase):
    __tablename__ = "inventory_products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String(300), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    min_quantity: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    location: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    supplier: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    unit_cost: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )


class Order(InventoryBase):
    __tablename__ = "inventory_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
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
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )

    lines: Mapped[list["OrderLine"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )


class OrderLine(InventoryBase):
    __tablename__ = "inventory_order_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("inventory_orders.id"), nullable=False
    )
    product_id: Mapped[int | None] = mapped_column(
        ForeignKey("inventory_products.id"), nullable=True
    )
    code: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    description: Mapped[str] = mapped_column(String(300), nullable=False)
    quantity_ordered: Mapped[float] = mapped_column(Float, nullable=False)
    quantity_delivered: Mapped[float] = mapped_column(
        Float, default=0, nullable=False
    )
    unit_price: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    discount_percent: Mapped[float] = mapped_column(
        Float, default=0, nullable=False
    )
    vat_percent: Mapped[float] = mapped_column(Float, default=22, nullable=False)

    order: Mapped["Order"] = relationship(back_populates="lines")


class Purchase(InventoryBase):
    __tablename__ = "inventory_purchases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int | None] = mapped_column(
        ForeignKey("inventory_products.id", ondelete="SET NULL"), nullable=True
    )
    product_code: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    description: Mapped[str] = mapped_column(String(300), nullable=False)
    supplier: Mapped[str] = mapped_column(String(200), nullable=False)
    purchase_date: Mapped[date] = mapped_column(Date, default=date.today, nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    unit_cost: Mapped[float] = mapped_column(Float, nullable=False)
    total_cost: Mapped[float] = mapped_column(Float, nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)


class Expense(InventoryBase):
    __tablename__ = "inventory_expenses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    expense_date: Mapped[date] = mapped_column(Date, default=date.today, nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(String(300), nullable=False)
    supplier: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    payment_method: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    purchase_id: Mapped[int | None] = mapped_column(
        ForeignKey("inventory_purchases.id", ondelete="SET NULL"), nullable=True
    )


class StockMovement(InventoryBase):
    __tablename__ = "inventory_stock_movements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int | None] = mapped_column(
        ForeignKey("inventory_products.id", ondelete="SET NULL"), nullable=True
    )
    product_code: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    description: Mapped[str] = mapped_column(String(300), nullable=False)
    movement_date: Mapped[date] = mapped_column(Date, default=date.today, nullable=False)
    movement_type: Mapped[str] = mapped_column(String(30), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    destination: Mapped[str] = mapped_column(String(250), default="", nullable=False)
    reference: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    unit_cost: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)


InventoryBase.metadata.create_all(engine)

# Safe additive migration for existing inventory databases.
from sqlalchemy import inspect, text as sql_text
if "unit_cost" not in {c["name"] for c in inspect(engine).get_columns("inventory_products")}:
    with engine.begin() as connection:
        connection.execute(sql_text(
            "ALTER TABLE inventory_products ADD COLUMN unit_cost FLOAT NOT NULL DEFAULT 0"
        ))


# UTILITY FUNCTIONS

def euro(value):
    return f"€ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def to_xlsx(df):
    """Serialize a DataFrame to an .xlsx file for download."""
    output = BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Dati")

    output.seek(0)

    return output.getvalue()


def line_totals(line):
    taxable = (
        line.quantity_ordered * line.unit_price
        * (1 - line.discount_percent / 100)
    )
    vat = taxable * line.vat_percent / 100
    return taxable, vat


def order_totals(order):
    taxable = vat = 0.0

    for line in order.lines:
        line_taxable, line_vat = line_totals(line)
        taxable += line_taxable
        vat += line_vat

    return taxable, vat, taxable + vat


def load_products(session):
    return session.query(Product).order_by(Product.description).all()


def order_label(order):
    return (
        f"{order.order_date:%d/%m/%Y} — "
        f"{order.customer or 'Senza destinatario'} — "
        f"{order.order_number}"
    )


# PDF GENERATION

def genera_pdf(order):
    output = BytesIO()

    doc = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=12 * mm,
        leftMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm
    )

    styles = getSampleStyleSheet()

    story = [
        Paragraph("<b>CONFERMA D'ORDINE</b>", styles["Title"]),
        Spacer(1, 4 * mm),
        Paragraph(
            f"<b>N.:</b> {escape(order.order_number)}"
            f"&nbsp;&nbsp;&nbsp; <b>del:</b> {order.order_date:%d/%m/%Y}",
            styles["Normal"]
        ),
        Spacer(1, 4 * mm)
    ]

    parties = [[
        Paragraph(
            f"<b>DESTINATARIO</b><br/>{escape(order.customer or '-')}",
            styles["Normal"]
        ),
        Paragraph(
            f"<b>DESTINAZIONE</b><br/>{escape(order.destination or '-')}",
            styles["Normal"]
        )
    ]]

    party_table = Table(
        parties,
        colWidths=[88 * mm, 88 * mm],
        rowHeights=[22 * mm]
    )

    party_table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.7, colors.grey),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
    ]))

    story.extend([party_table, Spacer(1, 5 * mm)])

    rows = [[
        "N.", "Codice", "Descrizione", "Quantità",
        "Prezzo unit.", "Sconto %", "Importo", "IVA %"
    ]]

    for number, line in enumerate(order.lines, start=1):
        taxable, _ = line_totals(line)

        rows.append([
            str(number),
            escape(line.code or "-"),
            Paragraph(escape(line.description), styles["Normal"]),
            f"{line.quantity_ordered:g}",
            euro(line.unit_price),
            f"{line.discount_percent:g}",
            euro(taxable),
            f"{line.vat_percent:g}"
        ])

    items_table = Table(
        rows,
        colWidths=[
            9 * mm, 18 * mm, 48 * mm, 17 * mm,
            22 * mm, 16 * mm, 23 * mm, 16 * mm
        ],
        repeatRows=1
    )

    items_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (0, 1), (0, -1), "CENTER"),
        ("ALIGN", (3, 1), (-1, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))

    story.extend([items_table, Spacer(1, 5 * mm)])

    taxable, vat, total = order_totals(order)

    totals_table = Table([
        ["Modalità di pagamento", escape(order.payment_method or "-"),
         "Tot. imponibile", euro(taxable)],
        ["Note", Paragraph(escape(order.notes or "-"), styles["Normal"]),
         "Tot. IVA", euro(vat)],
        ["", "", "Tot. documento", euro(total)]
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


# MAIN INVENTORY PAGE

def render_inventory():
    st.header("📦 Magazzino & Ordini")
    st.caption(
        "Gestione articoli, ordini con più righe, consegne e PDF."
    )

    tab_magazzino, tab_consegne = st.tabs([
        "Magazzino",
        "Ordini e consegne"
    ])

    # MAGAZZINO
    with tab_magazzino:
        st.subheader("Articoli in magazzino")

        with st.form("nuovo_articolo", clear_on_submit=True):
            c1, c2 = st.columns(2)

            codice = c1.text_input("Codice articolo *")
            descrizione = c2.text_input("Descrizione *")

            c3, c4 = st.columns(2)

            quantita = c3.number_input(
                "Quantità attualmente disponibile",
                min_value=0.0,
                value=0.0,
                step=1.0
            )

            minimo = c4.number_input(
                "Scorta minima",
                min_value=0.0,
                value=0.0,
                step=1.0
            )

            c5, c6 = st.columns(2)

            ubicazione = c5.text_input("Ubicazione")
            fornitore = c6.text_input("Fornitore")
            costo_unitario = st.number_input(
                "Costo unitario (€)", min_value=0.0, value=0.0,
                step=0.01, format="%.2f"
            )

            salva_articolo = st.form_submit_button(
                "Salva articolo",
                type="primary"
            )

        if salva_articolo:
            if not codice.strip() or not descrizione.strip():
                st.error("Inserisci il codice e la descrizione.")
            else:
                with InventorySession() as session:
                    exists = session.query(Product).filter(
                        func.lower(Product.code) == codice.strip().lower()
                    ).first()

                    if exists:
                        st.error(
                            "Questo codice esiste già. Usa un codice diverso."
                        )
                    else:
                        session.add(Product(
                            code=codice.strip(),
                            description=descrizione.strip(),
                            quantity=quantita,
                            min_quantity=minimo,
                            location=ubicazione.strip(),
                            supplier=fornitore.strip(),
                            unit_cost=costo_unitario
                        ))

                        session.commit()
                        st.success("Articolo salvato.")
                        st.rerun()

        st.divider()
        st.subheader("Elenco articoli")

        with InventorySession() as session:
            products = load_products(session)

            product_data = [{
                "ID": p.id,
                "Codice": p.code,
                "Descrizione": p.description,
                "Giacenza": p.quantity,
                "Scorta minima": p.min_quantity,
                "Ubicazione": p.location,
                "Fornitore": p.supplier,
                "Ultimo costo unitario (€)": round(float(p.unit_cost or 0), 2)
            } for p in products]

            product_choices = {
                f"{p.code} — {p.description} (ID {p.id})": p.id
                for p in products
            }

        if product_data:
            st.dataframe(
                pd.DataFrame(product_data).drop(columns=["ID"]),
                use_container_width=True,
                hide_index=True
            )

            low_stock = [
                p for p in product_data
                if p["Giacenza"] <= p["Scorta minima"]
            ]

            if low_stock:
                st.warning(
                    f"Attenzione: {len(low_stock)} articoli sono alla "
                    "scorta minima o sotto la soglia."
                )

            selected_product_label = st.selectbox(
                "Seleziona un articolo da modificare o eliminare",
                list(product_choices.keys()),
                key="manage_product_choice"
            )

            selected_product_id = product_choices[selected_product_label]

            with InventorySession() as session:
                selected_product = session.get(Product, selected_product_id)

                with st.form(f"edit_product_{selected_product_id}"):
                    st.markdown("**Modifica articolo selezionato**")

                    ec1, ec2 = st.columns(2)

                    edit_code = ec1.text_input(
                        "Codice",
                        value=selected_product.code
                    )

                    edit_description = ec2.text_input(
                        "Descrizione",
                        value=selected_product.description
                    )

                    ec3, ec4 = st.columns(2)

                    edit_quantity = ec3.number_input(
                        "Giacenza",
                        min_value=0.0,
                        value=float(selected_product.quantity),
                        step=1.0
                    )

                    edit_minimum = ec4.number_input(
                        "Scorta minima",
                        min_value=0.0,
                        value=float(selected_product.min_quantity),
                        step=1.0
                    )

                    ec5, ec6 = st.columns(2)

                    edit_location = ec5.text_input(
                        "Ubicazione",
                        value=selected_product.location or ""
                    )

                    edit_supplier = ec6.text_input(
                        "Fornitore",
                        value=selected_product.supplier or ""
                    )
                    edit_unit_cost = st.number_input(
                        "Ultimo costo unitario (€)", min_value=0.0,
                        value=float(selected_product.unit_cost or 0),
                        step=0.01, format="%.2f",
                        key=f"edit_unit_cost_{selected_product_id}"
                    )

                    save_product_changes = st.form_submit_button(
                        "Salva modifiche articolo",
                        type="primary"
                    )

                if save_product_changes:
                    if not edit_code.strip() or not edit_description.strip():
                        st.error("Codice e descrizione sono obbligatori.")
                    else:
                        duplicate = session.query(Product).filter(
                            func.lower(Product.code) == edit_code.strip().lower(),
                            Product.id != selected_product_id
                        ).first()

                        if duplicate:
                            st.error(
                                "Un altro articolo usa già questo codice."
                            )
                        else:
                            selected_product.code = edit_code.strip()
                            selected_product.description = edit_description.strip()
                            selected_product.quantity = edit_quantity
                            selected_product.min_quantity = edit_minimum
                            selected_product.location = edit_location.strip()
                            selected_product.supplier = edit_supplier.strip()
                            selected_product.unit_cost = edit_unit_cost

                            session.commit()
                            st.success("Articolo modificato.")
                            st.rerun()

            with st.expander("Elimina articolo selezionato"):
                st.warning(
                    "L'eliminazione rimuove l'articolo dal magazzino. "
                    "Le righe degli ordini già registrati restano salvate."
                )

                confirm_product_delete = st.checkbox(
                    "Confermo di voler eliminare questo articolo",
                    key=f"confirm_product_delete_{selected_product_id}"
                )

                if st.button(
                    "Elimina articolo",
                    key=f"delete_product_{selected_product_id}",
                    disabled=not confirm_product_delete
                ):
                    with InventorySession() as session:
                        product = session.get(Product, selected_product_id)

                        if product:
                            session.query(OrderLine).filter(
                                OrderLine.product_id == selected_product_id
                            ).update(
                                {OrderLine.product_id: None},
                                synchronize_session=False
                            )

                            session.delete(product)
                            session.commit()

                    st.success("Articolo eliminato dal magazzino.")
                    st.rerun()

            # --------------------------------------------------
            # STOCK IN (RESTOCK): increase quantity, update cost, log CARICO
            # --------------------------------------------------
            with st.expander("📥 Registra carico (rientro merce)"):
                st.caption(
                    "Quando la merce torna in magazzino: la giacenza e "
                    "l'ultimo costo unitario vengono aggiornati automaticamente."
                )

                product_cost_lookup = {
                    p.id: float(p.unit_cost or 0) for p in products
                }

                with st.form("manual_stock_in_form", clear_on_submit=True):
                    in_label = st.selectbox(
                        "Articolo",
                        list(product_choices.keys()),
                        key="stock_in_product"
                    )

                    in_default_cost = product_cost_lookup[
                        product_choices[in_label]
                    ]

                    ic1, ic2 = st.columns(2)

                    in_quantity = ic1.number_input(
                        "Quantità caricata",
                        min_value=0.01, value=1.0, step=1.0
                    )

                    in_date = ic2.date_input(
                        "Data carico", value=date.today(), format="DD/MM/YYYY"
                    )

                    in_unit_cost = st.number_input(
                        "Costo unitario (€)",
                        min_value=0.0,
                        value=in_default_cost,
                        step=0.01,
                        format="%.2f",
                        key="stock_in_unit_cost"
                    )

                    in_total = float(in_quantity) * float(in_unit_cost)

                    st.info(
                        f"Valore totale carico: {euro(in_total)} "
                        f"({float(in_quantity):g} × {euro(float(in_unit_cost))})"
                    )

                    in_supplier = st.text_input("Fornitore")
                    in_notes = st.text_area("Note (fattura, riferimento)")

                    save_in = st.form_submit_button(
                        "Registra carico", type="primary"
                    )

                if save_in:
                    in_product_id = product_choices[in_label]

                    with InventorySession() as session:
                        product = session.get(Product, in_product_id)

                        if not product:
                            st.error("Articolo non trovato.")
                        else:
                            product.quantity = (
                                float(product.quantity or 0)
                                + float(in_quantity)
                            )

                            if float(in_unit_cost) > 0:
                                product.unit_cost = float(in_unit_cost)

                            if in_supplier.strip():
                                product.supplier = in_supplier.strip()

                            session.add(StockMovement(
                                product_id=product.id,
                                product_code=product.code,
                                description=product.description,
                                movement_date=in_date,
                                movement_type="CARICO",
                                quantity=float(in_quantity),
                                destination="Magazzino",
                                reference=in_supplier.strip(),
                                unit_cost=float(in_unit_cost),
                                notes=in_notes.strip()
                            ))

                            session.commit()

                            st.success(
                                f"Carico registrato. "
                                f"Nuova giacenza: {product.quantity:g}."
                            )
                            st.rerun()

            with st.expander("📜 Storico carichi"):
                with InventorySession() as session:
                    in_movements = session.query(StockMovement).filter(
                        StockMovement.movement_type == "CARICO"
                    ).order_by(
                        StockMovement.movement_date.desc(),
                        StockMovement.id.desc()
                    ).all()

                    in_rows = [{
                        "Data": m.movement_date.strftime("%d/%m/%Y"),
                        "Codice": m.product_code,
                        "Articolo": m.description,
                        "Quantità caricata": m.quantity,
                        "Fornitore": m.reference,
                        "Costo unitario (€)": round(m.unit_cost, 2),
                        "Valore carico (€)": round(m.quantity * m.unit_cost, 2),
                        "Note": m.notes
                    } for m in in_movements]

                if in_rows:
                    in_df = pd.DataFrame(in_rows)

                    st.metric(
                        "Valore totale carichi",
                        euro(float(in_df["Valore carico (€)"].sum()))
                    )

                    st.dataframe(
                        in_df, use_container_width=True, hide_index=True
                    )
                else:
                    st.info("Nessun carico registrato.")

        else:
            st.info("Nessun articolo registrato.")
                # --------------------------------------------------
    # REGISTERED ORDERS: VIEW / EDIT / DELETE / DELIVERY / PDF
    # --------------------------------------------------
    with tab_consegne:
        st.subheader("Ordini registrati")

        with InventorySession() as session:
            orders = session.query(Order).order_by(
                Order.order_date.desc(), Order.id.desc()
            ).all()
            order_choices = {order_label(o): o.id for o in orders}
            order_rows = []
            for o in orders:
                _, _, total = order_totals(o)
                for index, line in enumerate(o.lines, start=1):
                    linked_product = session.get(Product, line.product_id) if line.product_id else None
                    available_stock = float(linked_product.quantity or 0) if linked_product else None
                    remaining_delivery = max(0, line.quantity_ordered - line.quantity_delivered)
                    quantity_to_buy = (
                        max(0, remaining_delivery - available_stock)
                        if available_stock is not None else None
                    )
                    order_rows.append({
                        "Ordine": o.order_number,
                        "Data": o.order_date.strftime("%d/%m/%Y"),
                        "Destinatario": o.customer,
                        "N. articolo": index,
                        "Codice": line.code,
                        "Articolo": line.description,
                        "Quantità ordinata": line.quantity_ordered,
                        "Quantità consegnata": line.quantity_delivered,
                        "Da consegnare": remaining_delivery,
                        "Giacenza disponibile": available_stock,
                        "Da acquistare": quantity_to_buy,
                        "Totale ordine": euro(total)
                    })

        if order_rows:
            st.dataframe(
                pd.DataFrame(order_rows),
                use_container_width=True, hide_index=True
            )

            st.divider()
            st.subheader("Modifica o elimina un ordine")
            selected_order_label = st.selectbox(
                "Seleziona ordine (data — destinatario — numero ordine)",
                list(order_choices.keys()), key="manage_order_choice"
            )
            selected_order_id = order_choices[selected_order_label]

            with InventorySession() as session:
                order_to_edit = session.get(Order, selected_order_id)
                old_lines = list(order_to_edit.lines)
                edit_count = st.number_input(
                    "Numero di articoli da mantenere nell'ordine",
                    min_value=1, max_value=40,
                    value=max(1, len(old_lines)), step=1,
                    key=f"edit_count_{selected_order_id}"
                )

                with st.form(f"edit_order_form_{selected_order_id}"):
                    st.markdown("**Modifica dati dell'ordine**")
                    h1, h2 = st.columns(2)
                    edit_number = h1.text_input(
                        "Numero ordine", value=order_to_edit.order_number
                    )
                    edit_date = h2.date_input(
                        "Data ordine", value=order_to_edit.order_date,
                        format="DD/MM/YYYY"
                    )
                    h3, h4 = st.columns(2)
                    edit_customer = h3.text_input(
                        "Destinatario / Cliente", value=order_to_edit.customer
                    )
                    edit_destination = h4.text_input(
                        "Destinazione", value=order_to_edit.destination
                    )
                    payment_options = ["Bonifico", "Contanti", "Carta", "Altro"]
                    current_payment = (
                        order_to_edit.payment_method
                        if order_to_edit.payment_method in payment_options
                        else "Altro"
                    )
                    edit_payment = st.selectbox(
                        "Modalità di pagamento", payment_options,
                        index=payment_options.index(current_payment)
                    )
                    edit_notes = st.text_area(
                        "Note", value=order_to_edit.notes or ""
                    )

                    st.markdown("### Articoli dell'ordine")
                    edited_items = []
                    for i in range(int(edit_count)):
                        st.markdown(f"**Articolo {i + 1}**")
                        existing = old_lines[i] if i < len(old_lines) else None
                        d1, d2 = st.columns(2)
                        line_code = d1.text_input(
                            f"Codice {i + 1}",
                            value=existing.code if existing else "",
                            key=f"edit_code_{selected_order_id}_{i}"
                        )
                        line_description = d2.text_input(
                            f"Descrizione {i + 1} *",
                            value=existing.description if existing else "",
                            key=f"edit_desc_{selected_order_id}_{i}"
                        )
                        d3, d4, d5 = st.columns(3)
                        line_qty = d3.number_input(
                            f"Quantità ordinata {i + 1}", min_value=0.01,
                            value=float(existing.quantity_ordered) if existing else 1.0,
                            step=1.0, key=f"edit_qty_{selected_order_id}_{i}"
                        )
                        line_delivered = d4.number_input(
                            f"Quantità consegnata {i + 1}", min_value=0.0,
                            value=float(existing.quantity_delivered) if existing else 0.0,
                            step=1.0, key=f"edit_delivered_{selected_order_id}_{i}"
                        )
                        line_price = d5.number_input(
                            f"Prezzo unitario € {i + 1}", min_value=0.0,
                            value=float(existing.unit_price) if existing else 0.0,
                            step=0.01, key=f"edit_price_{selected_order_id}_{i}"
                        )
                        d6, d7 = st.columns(2)
                        line_discount = d6.number_input(
                            f"Sconto % {i + 1}", min_value=0.0, max_value=100.0,
                            value=float(existing.discount_percent) if existing else 0.0,
                            step=1.0, key=f"edit_discount_{selected_order_id}_{i}"
                        )
                        vat_values = [22.0, 10.0, 5.0, 4.0, 0.0]
                        current_vat = (
                            float(existing.vat_percent)
                            if existing and float(existing.vat_percent) in vat_values
                            else 22.0
                        )
                        line_vat = d7.selectbox(
                            f"IVA % {i + 1}", vat_values,
                            index=vat_values.index(current_vat),
                            key=f"edit_vat_{selected_order_id}_{i}"
                        )
                        edited_items.append({
                            "existing_id": existing.id if existing else None,
                            "code": line_code, "description": line_description,
                            "quantity": line_qty, "delivered": line_delivered,
                            "price": line_price, "discount": line_discount,
                            "vat": line_vat,
                            "product_id": existing.product_id if existing else None
                        })
                        if i < int(edit_count) - 1:
                            st.divider()
                        save_order_changes = st.form_submit_button(
                        "Salva modifiche ordine", type="primary"
                    )

                # Save edited order and all its articles
                if save_order_changes:
                    duplicate = session.query(Order).filter(
                        func.lower(Order.order_number)
                        == edit_number.strip().lower(),
                        Order.id != selected_order_id
                    ).first() if edit_number.strip() else None

                    if not edit_number.strip() or not edit_customer.strip():
                        st.error("Numero ordine e destinatario sono obbligatori.")
                    elif duplicate:
                        st.error("Esiste già un altro ordine con questo numero.")
                    elif any(
                        not item["description"].strip()
                        for item in edited_items
                    ):
                        st.error("La descrizione di ogni articolo è obbligatoria.")
                    elif any(
                        item["delivered"] > item["quantity"]
                        for item in edited_items
                    ):
                        st.error(
                            "La quantità consegnata non può superare "
                            "quella ordinata."
                        )
                    else:
                        order_to_edit.order_number = edit_number.strip()
                        order_to_edit.order_date = edit_date
                        order_to_edit.customer = edit_customer.strip()
                        order_to_edit.destination = edit_destination.strip()
                        order_to_edit.payment_method = edit_payment
                        order_to_edit.notes = edit_notes.strip()

                        # Reconcile stock for changes to already-delivered quantities.
                        stock_error = None
                        for i, item in enumerate(edited_items):
                            if i < len(old_lines):
                                previous_line = old_lines[i]
                                delta = float(item["delivered"]) - float(previous_line.quantity_delivered or 0)
                                product = session.get(Product, previous_line.product_id) if previous_line.product_id else None
                                if product and abs(delta) > 0:
                                    if delta > 0 and float(product.quantity or 0) < delta:
                                        stock_error = (
                                            f"Giacenza insufficiente per {product.description}: "
                                            f"disponibili {float(product.quantity or 0):g}, richiesti {delta:g}."
                                        )
                                        break
                                    product.quantity = float(product.quantity or 0) - delta
                                    session.add(StockMovement(
                                        product_id=product.id,
                                        product_code=product.code,
                                        description=product.description,
                                        movement_date=date.today(),
                                        movement_type="SCARICO" if delta > 0 else "CARICO",
                                        quantity=abs(delta),
                                        destination=order_to_edit.destination or order_to_edit.customer,
                                        reference=f"Rettifica ordine {order_to_edit.order_number}",
                                        unit_cost=float(product.unit_cost or 0),
                                        notes="Rettifica giacenza dopo modifica quantità consegnata"
                                    ))
                        if stock_error:
                            session.rollback()
                            st.error(stock_error)
                        else:
                            # Update existing lines, add new ones, remove extras.
                            for i, item in enumerate(edited_items):
                                if i < len(old_lines):
                                    line = old_lines[i]
                                else:
                                    line = OrderLine()
                                    order_to_edit.lines.append(line)

                                line.product_id = item["product_id"]
                                line.code = item["code"].strip()
                                line.description = item["description"].strip()
                                line.quantity_ordered = item["quantity"]
                                line.quantity_delivered = item["delivered"]
                                line.unit_price = item["price"]
                                line.discount_percent = item["discount"]
                                line.vat_percent = item["vat"]

                            for line in old_lines[len(edited_items):]:
                                # If an already-delivered line is removed from the
                                # order, restore that quantity to warehouse stock.
                                if line.product_id and float(line.quantity_delivered or 0) > 0:
                                    product = session.get(Product, line.product_id)
                                    if product:
                                        restored = float(line.quantity_delivered)
                                        product.quantity = float(product.quantity or 0) + restored
                                        session.add(StockMovement(
                                            product_id=product.id,
                                            product_code=product.code,
                                            description=product.description,
                                            movement_date=date.today(),
                                            movement_type="CARICO",
                                            quantity=restored,
                                            destination="Magazzino",
                                            reference=f"Rettifica ordine {order_to_edit.order_number}",
                                            unit_cost=float(product.unit_cost or 0),
                                            notes="Ripristino giacenza per rimozione riga ordine già consegnata"
                                        ))
                                order_to_edit.lines.remove(line)

                            session.commit()
                            st.success("Ordine modificato correttamente.")
                            st.rerun()

            # Delete the complete order
            with st.expander("Elimina ordine selezionato"):
                st.warning(
                    "Verranno eliminati l'ordine e tutte le sue righe articolo. "
                    "Questa operazione non può essere annullata."
                )
                confirm_order_delete = st.checkbox(
                    "Confermo di voler eliminare questo ordine",
                    key=f"confirm_order_delete_{selected_order_id}"
                )

                if st.button(
                    "Elimina ordine",
                    key=f"delete_order_{selected_order_id}",
                    disabled=not confirm_order_delete
                ):
                    with InventorySession() as session:
                        order = session.get(Order, selected_order_id)
                        if order:
                            session.delete(order)
                            session.commit()

                    st.success("Ordine eliminato.")
                    st.rerun()

            # Delivery and complete order PDF
            st.divider()
            st.subheader("Aggiorna consegna e scarica PDF")
            st.caption(
                "Seleziona l'ordine completo tramite data, destinatario e numero. "
                "Tutti gli articoli dell'ordine sono inclusi nello stesso PDF."
            )

            with InventorySession() as session:
                selected_order = session.get(Order, selected_order_id)

                if selected_order and selected_order.lines:
                    with st.form(f"delivery_form_{selected_order_id}"):
                        st.markdown(
                            "**Quantità aggiuntiva consegnata per articolo**"
                        )
                        delivery_values = []

                        for index, line in enumerate(
                            selected_order.lines, start=1
                        ):
                            remaining = max(
                                0.0,
                                line.quantity_ordered - line.quantity_delivered
                            )

                            st.write(
                                f"{index}. **{line.description}** — "
                                f"Ordinata: {line.quantity_ordered:g} | "
                                f"Già consegnata: {line.quantity_delivered:g} | "
                                f"Residua: {remaining:g}"
                            )

                            additional = st.number_input(
                                f"Nuova quantità consegnata — articolo {index}",
                                min_value=0.0,
                                max_value=float(remaining),
                                value=0.0,
                                step=1.0,
                                key=f"delivery_qty_{selected_order_id}_{line.id}"
                            )

                            delivery_values.append((line.id, additional))

                        save_delivery = st.form_submit_button(
                            "Registra tutte le consegne",
                            type="primary"
                        )

                    if save_delivery:
                        for line_id, additional in delivery_values:
                            line = session.get(OrderLine, line_id)
                            if line and additional > 0:
                                line.quantity_delivered += additional
                                product = session.get(Product, line.product_id) if line.product_id else None
                                if product:
                                    available = float(product.quantity or 0)
                                    if additional > available:
                                        st.error(
                                            f"Giacenza insufficiente per {product.description}: "
                                            f"disponibili {available:g}, richiesti {additional:g}."
                                        )
                                        session.rollback()
                                        st.stop()
                                    product.quantity = available - float(additional)
                                    session.add(StockMovement(
                                        product_id=product.id,
                                        product_code=product.code,
                                        description=product.description,
                                        movement_date=date.today(),
                                        movement_type="SCARICO",
                                        quantity=float(additional),
                                        destination=selected_order.destination or selected_order.customer,
                                        reference=f"Ordine {selected_order.order_number}",
                                        unit_cost=float(product.unit_cost or 0),
                                        notes="Scarico automatico per consegna ordine"
                                    ))

                        session.commit()
                        st.success("Consegne aggiornate e giacenza aggiornata per gli articoli collegati al magazzino.")
                        st.rerun()

                    pdf_bytes = genera_pdf(selected_order)

                    st.download_button(
                        "📄 Scarica PDF — Ordine completo",
                        data=pdf_bytes,
                        file_name=f"ordine_{selected_order.order_number}.pdf",
                        mime="application/pdf",
                        key=f"download_pdf_{selected_order_id}"
                    )
                else:
                    st.info("Questo ordine non contiene articoli.")

        else:
            st.info("Non ci sono ancora ordini registrati.")

# ==================================================
# EXPENSE REGISTER (used by the main app navigation)
# ==================================================

def render_expenses():
    st.header("💶 Elenco delle spese")
    st.caption("Acquisti registrati dai fornitori e altre spese aziendali.")

    with st.expander("Registra una nuova spesa", expanded=True):
        with st.form("manual_expense_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            expense_date = c1.date_input("Data", value=date.today(), format="DD/MM/YYYY")
            expense_category = c2.selectbox(
                "Categoria", ["Generale", "Trasporto", "Ufficio", "Manutenzione", "Servizi", "Altro"]
            )
            expense_description = st.text_input("Descrizione *")
            c3, c4 = st.columns(2)
            expense_supplier = c3.text_input("Fornitore")
            expense_amount = c4.number_input("Importo (€)", min_value=0.0, value=0.0, step=0.01, format="%.2f")
            expense_payment = st.selectbox("Metodo di pagamento", ["", "Bonifico", "Contanti", "Carta", "Altro"])
            expense_notes = st.text_area("Note")
            save_expense = st.form_submit_button("Salva spesa", type="primary")
        if save_expense:
            if not expense_description.strip() or expense_amount <= 0:
                st.error("Inserisci una descrizione e un importo maggiore di zero.")
            else:
                with InventorySession() as session:
                    session.add(Expense(
                        expense_date=expense_date,
                        category=expense_category,
                        description=expense_description.strip(),
                        supplier=expense_supplier.strip(),
                        amount=float(expense_amount),
                        payment_method=expense_payment,
                        notes=expense_notes.strip()
                    ))
                    session.commit()
                st.success("Spesa registrata.")
                st.rerun()

    with InventorySession() as session:
        rows = session.query(Expense).order_by(Expense.expense_date.desc(), Expense.id.desc()).all()
        data = [{
            "Data": x.expense_date.strftime("%d/%m/%Y"),
            "Categoria": x.category,
            "Descrizione": x.description,
            "Fornitore": x.supplier,
            "Importo (€)": round(x.amount, 2),
            "Pagamento": x.payment_method,
            "Note": x.notes
        } for x in rows]
    if data:
        df = pd.DataFrame(data)
        st.metric("Totale spese registrate", euro(float(df["Importo (€)"].sum())))
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button(
            "Scarica elenco spese Excel",
            data=to_xlsx(df),
            file_name="elenco_spese.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.info("Nessuna spesa registrata.")


# ==================================================
# STOCK DISCHARGE REGISTER (used by the main app navigation)
# ==================================================

def render_stock_outflow():
    st.header("📤 Elenco scarico magazzino")
    st.caption("Registra le uscite manuali e consulta gli scarichi automatici per consegna ordine.")

    with InventorySession() as session:
        products = load_products(session)
        options = {f"{p.code} — {p.description} (disponibili: {p.quantity:g})": p.id for p in products}

    with st.expander("Registra uno scarico manuale", expanded=True):
        if not options:
            st.info("Nessun articolo in magazzino.")
        else:
            product_lookup = {p.id: p for p in products}

            with st.form("manual_stock_out_form", clear_on_submit=True):
                selected_label = st.selectbox("Articolo", list(options))
                default_unit_cost = float(
                    product_lookup[options[selected_label]].unit_cost or 0
                )
                c1, c2 = st.columns(2)
                out_quantity = c1.number_input("Quantità da scaricare", min_value=0.01, value=1.0, step=1.0)
                out_date = c2.date_input("Data scarico", value=date.today(), format="DD/MM/YYYY")
                out_unit_cost = st.number_input(
                    "Costo unitario (€)",
                    min_value=0.0,
                    value=default_unit_cost,
                    step=0.01,
                    format="%.2f",
                    help="Il totale viene calcolato automaticamente: quantità × costo unitario."
                )
                computed_total = float(out_quantity) * float(out_unit_cost)
                st.info(
                    f"Totale scarico: {euro(computed_total)} "
                    f"({float(out_quantity):g} × {euro(float(out_unit_cost))})"
                )
                out_destination = st.text_input("Destinazione / Reparto / Persona")
                out_reference = st.text_input("Riferimento (ordine, richiesta, documento)")
                out_notes = st.text_area("Note")
                save_out = st.form_submit_button("Registra scarico", type="primary")
            if save_out:
                product_id = options[selected_label]
                with InventorySession() as session:
                    product = session.get(Product, product_id)
                    if not product or float(product.quantity or 0) < float(out_quantity):
                        st.error("Giacenza insufficiente: scarico non registrato.")
                    else:
                        product.quantity = float(product.quantity or 0) - float(out_quantity)
                        product.unit_cost = float(out_unit_cost)
                        session.add(StockMovement(
                            product_id=product.id,
                            product_code=product.code,
                            description=product.description,
                            movement_date=out_date,
                            movement_type="SCARICO",
                            quantity=float(out_quantity),
                            destination=out_destination.strip(),
                            reference=out_reference.strip(),
                            unit_cost=float(out_unit_cost),
                            notes=out_notes.strip()
                        ))
                        session.commit()
                        st.success(f"Scarico registrato. Giacenza residua: {product.quantity:g}.")
                        st.rerun()

    with InventorySession() as session:
        movements = session.query(StockMovement).filter(
            StockMovement.movement_type == "SCARICO"
        ).order_by(StockMovement.movement_date.desc(), StockMovement.id.desc()).all()
        rows = [{
            "Data": m.movement_date.strftime("%d/%m/%Y"),
            "Codice": m.product_code,
            "Articolo": m.description,
            "Quantità scaricata": m.quantity,
            "Destinazione": m.destination,
            "Riferimento": m.reference,
            "Costo unitario (€)": round(m.unit_cost, 2),
            "Valore scarico (€)": round(m.quantity * m.unit_cost, 2),
            "Note": m.notes
        } for m in movements]
    if rows:
        df = pd.DataFrame(rows)
        st.metric(
            "Valore totale scarichi",
            euro(float(df["Valore scarico (€)"].sum()))
        )
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button(
            "Scarica scarichi Excel",
            data=to_xlsx(df),
            file_name="elenco_scarico_magazzino.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.info("Nessuno scarico registrato.")