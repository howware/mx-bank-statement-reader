"""BBVA México · tarjeta de crédito. Ver docs/bancos/bbva-credito.md."""

from __future__ import annotations

import re
from decimal import Decimal

from ..loader import Line, LoadedDocument, Page
from ..models.raw import RawStatement, RawTransaction
from ..normalize.amounts import parse_amount, parse_number
from ..normalize.dates import parse_full_date
from ..text import norm
from .base import BankParser, amounts, label_text, search
from .merchants import match_merchant

DATE = r"\d{2}-[A-Z]{3}-\d{4}"
TX_DATE = re.compile(rf"^{DATE}$")
INSTALLMENT_RE = re.compile(r"^(\d{1,2}) DE (\d{1,2}) (.+)$")
FX_RE = re.compile(r"^(\w{3}) \$?([\d,]+\.\d{2}) TIPO DE CAMBIO \$?([\d,]+\.\d+)")
# BBVA a veces imprime el código numérico ISO 4217; MXP es el código antiguo del peso
CURRENCY = {"840": "USD", "978": "EUR", "826": "GBP", "124": "CAD", "484": "MXN", "MXP": "MXN"}
N_OF_M_RE = re.compile(r"(\d{1,2}) DE (\d{1,2})")
# cargo informativo que va al saldo a meses, no al de cargos regulares (su contraparte es "ABONO FINANC.")
TO_INSTALLMENTS_RE = re.compile(r"^ALTA PARA MESES")

# (patrón sobre la descripción normalizada, type)
RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^(BMOVIL\.?\s*PAGO|PAGO TDC|SU PAGO|PAGO RECIBIDO)"), "card_payment"),
    (re.compile(r"^USO DE PUNTOS"), "rewards_redemption"),
    # su monto coincide con "Monto de comisiones" del resumen
    (re.compile(r"^CONTRATACION BENEFICIOS"), "fee"),
    (re.compile(r"^(ABONO FINANC|ALTA PARA MESES|ABONO POR TRASP)"), "installment_conversion"),
    (re.compile(r"^INTERES"), "interest"),
    (re.compile(r"^(COMISION|COM\b)"), "fee"),
    (re.compile(r"^IVA\b"), "tax"),
]


class BBVACreditParser(BankParser):
    bank = "bbva"
    bank_name = "BBVA México"
    product = "credit"
    layout_version = "2025.1"

    def fingerprint(self, doc: LoadedDocument) -> float:
        t = doc.ntext
        score = 0.0
        if "BBVA MEXICO, S.A., INSTITUCION DE BANCA MULTIPLE" in t:
            score += 0.4
        if "TU PAGO REQUERIDO" in t:
            score += 0.3
        if "PAGO PARA NO GENERAR INTERESES" in t:
            score += 0.2
        if "TARJETA TITULAR" in t:
            score += 0.1
        return round(score, 2)

    def parse(self, doc: LoadedDocument, confidence: float) -> RawStatement:
        raw = RawStatement(
            bank=self.bank, bank_name=self.bank_name, product=self.product, product_name=None,
            layout_version=self.layout_version, confidence=confidence, pages=len(doc.pages),
        )
        page = next((p for p in doc.pages if p.find("TU PAGO REQUERIDO")), None)
        if not page:
            raw.warnings.append("No se encontró la sección de pago requerido.")
            return raw
        self._header(doc, page, raw)
        self._summary(page, raw)
        self._movements(doc, page.number, raw)
        self._reconcile(raw)
        return raw

    # ------------------------------------------------------------------
    def _header(self, doc: LoadedDocument, page: Page, raw: RawStatement) -> None:
        lines, h, c = page.lines, raw.header, raw.credit
        if m := search(lines, rf"PERIODO: ({DATE}) AL ({DATE})"):
            raw.period_start, raw.period_end = parse_full_date(m.group(1)), parse_full_date(m.group(2))
        if m := search(lines, rf"FECHA DE CORTE: ({DATE})"):
            raw.statement_date = c["cut_off_date"] = parse_full_date(m.group(1))
        if m := search(lines, r"NUMERO DE DIAS EN EL PERIODO (\d+)"):
            raw.days = int(m.group(1))
        due = page.find("Fecha limite de pago")
        if due:
            for ln in lines:
                if abs(ln.top - due.top) <= 8 and (m := re.search(DATE, ln.ntext)):
                    c["payment_due_date"] = parse_full_date(m.group(0))
                    break
        if m := search(lines, r"NUMERO DE TARJETA: ?(\d{15,16})"):
            h.add("card_number", m.group(1))
        if m := search(lines, r"NUMERO DE CLIENTE: ?(\d{5,12})"):
            h.add("client_number", m.group(1))
        if m := search(lines, r"R\.?F\.?C\.?: ?([A-Z&]{3,4}\d{6}[A-Z0-9]{3})"):
            h.add("rfc", m.group(1))
            raw.holder_type = "business" if len(m.group(1)) == 12 else "individual"
        if m := search(lines, r"CLABE: ?(\d{18})"):
            h.add("clabe", m.group(1))
        branch = page.find("Sucursal:")
        if branch:
            h.add("branch", branch.text_within(0, 300).split(":", 1)[-1])

        # nombre y domicilio: bloque izquierdo arriba del nombre del producto
        product = next((ln for ln in lines if norm(ln.text_within(0, 300)).startswith("TARJETA ")), None)
        if product:
            raw.product_name = norm(product.text_within(0, 300))
            left = [ln.text_within(0, 300) for ln in lines if 50 < ln.top < product.top]
            left = [t for t in left if t]
            if left:
                h.add("holder_name", left[0])
                h.add("address", " ".join(left[1:]))

        # CFDI: número de crédito (cuenta estable entre meses), cliente y receptor
        for p in doc.pages:
            receptor = p.find("Nombre del Receptor")
            if not receptor:
                continue
            h.add("holder_name", receptor.text.split(":", 1)[-1])
            if m := search(p.lines, r"CREDITO (\d{8,12})"):
                h.account_number = m.group(1)
                h.add("account_number", m.group(1))
            if m := search(p.lines, r"DOMICILIO FISCAL: ?(\d{5})"):
                h.add("postal_code", m.group(1))
        if not h.account_number:
            card = next((v for k, v in h.fields if k == "card_number"), None)
            h.account_number = card

    def _summary(self, page: Page, raw: RawStatement) -> None:
        c = raw.credit
        resumen = page.find("RESUMEN DE CARGOS Y ABONOS")
        limit = resumen.top if resumen else 360
        for line in page.lines:
            right = line.within(300)
            rl, ra = label_text(right), [v for _, v in amounts(right)]
            if line.top < limit and ra:
                if "PAGO PARA NO GENERAR INTERESES" in rl:
                    c["no_interest_payment"] = ra[-1]
                elif "PAGO MINIMO" in rl and "MESES" in rl:
                    c["minimum_payment_with_installments"] = ra[-1]
                elif "PAGO MINIMO" in rl:
                    c["minimum_payment"] = ra[-1]
        if not resumen:
            raw.warnings.append("No se encontró el resumen de cargos y abonos.")
            return

        block = [ln for ln in page.lines if resumen.top < ln.top < resumen.top + 320]
        for i, line in enumerate(block):
            left, right = line.within(0, 300), line.within(300)
            ll, rl = label_text(left), label_text(right)
            la, ra = [v for _, v in amounts(left)], [v for _, v in amounts(right)]
            if la:
                if "PERIODO ANTERIOR" in ll:
                    c["previous_balance"] = la[-1]
                elif "CARGOS REGULARES" in ll:
                    c["regular_charges"] = la[-1]
                elif "CARGOS COMPRAS A MESES" in ll:
                    c["installment_charges"] = la[-1]
                elif "MONTO DE INTERESES" in ll:
                    c["interest_charged"] = la[-1]
                elif "MONTO DE COMISIONES" in ll:
                    c["fees_charged"] = la[-1]
                elif "IVA DE INTERESES" in ll:
                    c["vat_on_interest_and_fees"] = la[-1]
                elif "PAGOS Y ABONOS" in ll:
                    c["payments_and_credits"] = abs(la[-1])
            if ra:
                if "SALDO CARGOS REGULARES" in rl:
                    c["regular_balance"] = ra[-1]
                elif "SALDO CARGO A MESES" in rl:
                    c["installment_balance"] = ra[-1]
                elif "SALDO DEUDOR TOTAL" in rl:
                    c["total_balance"] = ra[-1]
                elif "LIMITE DE CREDITO" in rl:
                    c["credit_limit"] = ra[-1]
                elif "CREDITO DISPONIBLE" in rl:
                    c["available_credit"] = ra[-1]
            if "CAT:" in rl:
                # los porcentajes vienen en el renglón siguiente: CAT y tasa anual
                for nxt in block[i + 1:i + 3]:
                    pct = [parse_number(w.text) for w in nxt.within(300) if w.text.endswith("%")]
                    pct = [p for p in pct if p is not None]
                    if pct:
                        c["cat_percent"] = pct[0]
                        if len(pct) > 1:
                            c["annual_interest_rate_percent"] = pct[-1]
                        break
        s = raw.summary
        s["interest_earned"] = None
        s["fees_total"] = c.get("fees_charged")

    # ------------------------------------------------------------------
    def _movements(self, doc: LoadedDocument, first_page: int, raw: RawStatement) -> None:
        section: str | None = None
        for page in doc.pages[first_page - 1:]:
            for line in page.lines:
                n = line.ntext
                if "TARJETA TITULAR" in n or "TARJETA ADICIONAL" in n:
                    section = "msi" if "DIFERIDOS" in n else "regular" if "ABONOS" in n else None
                    continue
                if n.startswith("NOTAS") or section is None:
                    continue
                if n.startswith("TOTAL CARGOS") or n.startswith("TOTAL ABONOS"):
                    found = amounts(line.words)
                    key = "total_debits" if "CARGOS" in n else "total_credits"
                    if found:
                        raw.bank_totals[key] = abs(found[-1][1])
                    if key == "total_credits":
                        section = None
                    continue
                if section == "msi":
                    self._plan(line, raw)
                else:
                    self._regular(line, raw)
        # "TOTAL CARGOS" de BBVA no incluye las comisiones (verificado en 4 estados)
        if raw.bank_totals.get("total_debits") is not None:
            raw.bank_totals["total_debits"] += raw.credit.get("fees_charged") or Decimal(0)
        raw.summary["total_credits"] = raw.bank_totals.get("total_credits")

    def _plan(self, line: Line, raw: RawStatement) -> None:
        w = line.words
        if not w or w[0].x0 > 40 or not TX_DATE.match(norm(w[0].text)):
            return
        money = [v for _, v in amounts(line.within(300, 490))]
        plan: dict[str, object] = {
            "description": line.text_within(110, 310).partition(" ; ")[0],
            "start_date": parse_full_date(norm(w[0].text)),
        }
        for key, value in zip(("original_amount", "pending_balance", "required_payment"), money, strict=False):
            plan[key] = value
        if m := N_OF_M_RE.search(norm(line.text_within(490, 545))):
            plan["installment_number"], plan["installments_total"] = int(m.group(1)), int(m.group(2))
        rate = [parse_number(x.text) for x in line.within(545) if x.text.endswith("%")]
        if rate and rate[0] is not None:
            plan["interest_rate_percent"] = rate[0]
        raw.installment_plans.append(plan)

    def _regular(self, line: Line, raw: RawStatement) -> None:
        w = line.words
        if len(w) >= 3 and TX_DATE.match(norm(w[0].text)) and TX_DATE.match(norm(w[1].text)):
            raw.transactions.append(self._transaction(line, raw))
            return
        if not raw.transactions:
            return
        tx = raw.transactions[-1]
        n = line.ntext
        if m := FX_RE.match(n):
            code = m.group(1)
            tx.original_currency = CURRENCY.get(code, code if code.isalpha() else None)
            tx.original_amount = parse_amount(m.group(2))
            tx.exchange_rate = parse_number(m.group(3).replace(",", ""))

    def _transaction(self, line: Line, raw: RawStatement) -> RawTransaction:
        w = line.words
        money = amounts(line.within(500))
        value = abs(money[-1][1]) if money else None
        is_credit = any(x.text == "-" or x.text.startswith("-$") for x in line.within(500))
        text = line.text_within(195, 505)
        base, _, suffix = text.partition(" ; ")
        tx = RawTransaction(
            date=parse_full_date(norm(w[0].text)), posting_date=parse_full_date(norm(w[1].text)),
            page=line.page, first_line=text, description=norm(base), type="other",
            credit=value if is_credit else None, debit=None if is_credit else value,
        )
        if "TARJETA DIGITAL" in norm(suffix):
            tx.card_type = "digital"
        if suffix:
            tx.pii.append(suffix)  # "Tarjeta Digital ***1234": liga el movimiento a la tarjeta
        if m := INSTALLMENT_RE.match(tx.description):
            tx.installment_number, tx.installments_total = int(m.group(1)), int(m.group(2))
            tx.description = m.group(3)
            tx.type = "installment"
            return tx
        for rx, typ in RULES:
            if rx.match(tx.description):
                tx.type = typ
                return tx
        tx.type = "card_purchase" if tx.debit else "refund"
        tx.merchant = match_merchant(tx.description)
        return tx

    def _reconcile(self, raw: RawStatement) -> None:
        """Adeudo anterior + cargos − abonos + intereses + IVA = saldo de cargos regulares.

        Verificado con 4 estados reales; los cargos "ALTA PARA MESES" van al saldo a meses.
        """
        c = raw.credit
        prev, reported = c.get("previous_balance"), c.get("regular_balance")
        if prev is None or reported is None:
            return
        zero = Decimal(0)
        debits = sum((t.debit or zero for t in raw.transactions if not TO_INSTALLMENTS_RE.match(t.description)), zero)
        credits = sum((t.credit or zero for t in raw.transactions), zero)
        extra = (c.get("interest_charged") or zero) + (c.get("vat_on_interest_and_fees") or zero)
        raw.reconciliation = (prev + debits - credits + extra, reported)
