"""BBVA México · cuenta de débito (p. ej. Tarjeta Nómina Básica). Ver docs/bancos/bbva-cuenta.md."""

from __future__ import annotations

import re

from ..loader import Line, LoadedDocument
from ..models.raw import RawStatement, RawTransaction
from ..normalize.dates import parse_full_date, parse_short_date
from ..text import norm
from .base import BankParser, Columns, amounts, ints, label_text, numbers, search
from .merchants import match_merchant

TX_DATE = re.compile(r"^\d{2}/[A-Z]{3}$")
FOOTER_MARGIN = 45  # pt desde el borde inferior: pie legal y GAT

# (patrón sobre la primera línea normalizada, type, descripción canónica)
RULES: list[tuple[re.Pattern, str, str]] = [
    (re.compile(r"^SPEI RECIBIDO\s*(?P<bank>.*)$"), "spei_in", "SPEI RECIBIDO"),
    (re.compile(r"^SPEI ENVIADO\s*(?P<bank>.*)$"), "spei_out", "SPEI ENVIADO"),
    (re.compile(r"^SPEI DEVUELTO\s*(?P<bank>.*)$"), "spei_refund", "SPEI DEVUELTO"),
    (re.compile(r"^PAGO CUENTA DE TERCERO"), "transfer_out", "PAGO CUENTA DE TERCERO"),
    (re.compile(r"^PAGO TARJETA DE CREDITO"), "card_payment", "PAGO TARJETA DE CREDITO"),
    (re.compile(r"^PAGO DE PRESTAMO"), "loan_payment", "PAGO DE PRESTAMO"),
    (re.compile(r"^RETIRO CAJERO AUTOMATICO"), "cash_withdrawal", "RETIRO CAJERO AUTOMATICO"),
    (re.compile(r"^RETIRO SIN TARJETA"), "cash_withdrawal", "RETIRO SIN TARJETA"),
    # retiro en cajero de otro banco: el monto YA incluye la comisión + IVA (no es solo comisión)
    (re.compile(r"^RET CAJ OTRO BCO COM IVA"), "cash_withdrawal", "RETIRO EN CAJERO DE OTRO BANCO (INCLUYE COMISION E IVA)"),
    (re.compile(r"^SU PAGO EN EFECTIVO"), "cash_deposit", "SU PAGO EN EFECTIVO"),
    (re.compile(r"^RECARGAS Y PAQUETES"), "mobile_topup", "RECARGAS Y PAQUETES BMOV"),
    (re.compile(r"^SAT\b"), "tax_payment", "SAT"),
    # 10 dígitos pegados: probablemente un teléfono (retiro por celular)
    (re.compile(r"^(?P<num>\d+)\s*DISPOS\.?\s*EFECTIVO"), "cash_withdrawal", "DISPOSICION DE EFECTIVO"),
]

TRACKING_RE = re.compile(r"^(?:[A-Z]{4}\d{16,}|\d{18,})$")
REF_CONCEPT_RE = re.compile(r"^(\d{5,})\s*(.*)$")
THIRD_PARTY_RE = re.compile(r"^([A-Z]{3,5})\s+(\d{10,18})\s*(.*)$")
DIGITS4 = re.compile(r"\d[\d-]{3,}")


class BBVADebitParser(BankParser):
    bank = "bbva"
    bank_name = "BBVA México"
    product = "debit"
    layout_version = "2024.1"

    def fingerprint(self, doc: LoadedDocument) -> float:
        t = doc.ntext
        score = 0.0
        if "BBVA MEXICO, S.A., INSTITUCION DE BANCA MULTIPLE" in t:
            score += 0.5
        if "DETALLE DE MOVIMIENTOS REALIZADOS" in t:
            score += 0.2
        if "INFORMACION FINANCIERA" in t:
            score += 0.1
        if "DESCRIPCION REFERENCIA CARGOS ABONOS OPERACION LIQUIDACION" in t:
            score += 0.2
        return round(score, 2)

    # ------------------------------------------------------------------
    def parse(self, doc: LoadedDocument, confidence: float) -> RawStatement:
        raw = RawStatement(
            bank=self.bank, bank_name=self.bank_name, product=self.product, product_name=None,
            layout_version=self.layout_version, confidence=confidence, pages=len(doc.pages),
            balance_mode="per_day",
        )
        p1 = doc.pages[0]
        self._header(doc, raw)
        self._summary(p1.lines, raw)
        self._transactions(doc, raw)
        return raw

    def _header(self, doc: LoadedDocument, raw: RawStatement) -> None:
        p1 = doc.pages[0]
        lines = p1.lines
        h = raw.header

        title = next((ln for ln in lines if ln.top < 40 and "TARJETA" in ln.ntext), None)
        if title:
            raw.product_name = re.sub(r"\s*BBVA$", "", norm(title.text_within(400))).strip() or None
        if m := search(lines, r"PERIODO DEL (\d{2}/\d{2}/\d{4}) AL (\d{2}/\d{2}/\d{4})"):
            raw.period_start, raw.period_end = parse_full_date(m.group(1)), parse_full_date(m.group(2))
        if m := search(lines, r"FECHA DE CORTE (\d{2}/\d{2}/\d{4})"):
            raw.statement_date = parse_full_date(m.group(1))
        if m := search(lines, r"NO\. DE CUENTA (\d{8,12})"):
            h.account_number = m.group(1)
            h.add("account_number", m.group(1))
        if m := search(lines, r"NO\. DE CLIENTE (\d{5,12})"):
            h.add("client_number", m.group(1))
        if m := search(lines, r"R\.?F\.?C\.?:? ([A-Z&]{3,4}\d{6}[A-Z0-9]{3})"):
            h.add("rfc", m.group(1))
            raw.holder_type = "business" if len(m.group(1)) == 12 else "individual"
        if m := search(lines, r"CLABE ((?:\d ?){18})"):
            h.add("clabe", m.group(1).replace(" ", ""))

        # bloque izquierdo: nombre y domicilio; bloque derecho: sucursal
        client = p1.find("No. de Cliente")
        info = p1.find("Informacion Financiera")
        start = client.top + 1 if client else 90
        end = info.top if info else 220
        left = [ln.text_within(0, 300) for ln in lines if start < ln.top < end]
        left = [t for t in left if t]
        if left:
            h.add("holder_name", left[0])
            h.add("address", " ".join(left[1:]))
        branch = p1.find("SUCURSAL")
        if branch:
            h.add("branch", " ".join(ln.text_within(370) for ln in lines if branch.top <= ln.top < end))

        # CFDI: nombre y código postal del receptor
        for page in doc.pages[1:]:
            receptor = page.find("Nombre del Receptor")
            if receptor:
                h.add("holder_name", receptor.text.split(":", 1)[-1])
                if m := search(page.lines, r"DOMICILIO FISCAL ?: ?(\d{5})"):
                    h.add("postal_code", m.group(1))

    def _summary(self, lines: list[Line], raw: RawStatement) -> None:
        info = next((ln for ln in lines if "INFORMACION FINANCIERA" in ln.ntext), None)
        detail = next((ln for ln in lines if "DETALLE DE MOVIMIENTOS" in ln.ntext), None)
        if not info:
            raw.warnings.append("No se encontró la sección Información Financiera.")
            return
        s = raw.summary
        for line in lines:
            if not (info.top < line.top < (detail.top if detail else 480)):
                continue
            left, right = line.within(0, 300), line.within(300)
            ll, rl = label_text(left), label_text(right)
            la, ra = [v for _, v in amounts(left)], [v for _, v in amounts(right)]
            if "PROMEDIO GRAVABLE" in ll:
                pass
            elif "SALDO PROMEDIO" in ll and la:
                s["average_balance"] = la[-1]
            elif "DIAS DEL PERIODO" in ll and ints(left):
                raw.days = ints(left)[-1]
            elif "TASA" in ll and "ANUAL" in ll and numbers(left):
                raw.rates["gross_annual_rate_percent"] = numbers(left)[-1]
            elif "INTERESES A FAVOR" in ll and la:
                s["interest_earned"] = la[-1]
            elif "ISR" in ll and la:
                s["tax_withheld"] = la[-1]
            elif "TOTAL COMISIONES" in ll and la:
                s["fees_total"] = la[-1]

            if not ra:
                continue
            ri = ints(right)
            if "SALDO ANTERIOR" in rl:
                s["opening_balance"] = ra[-1]
            elif "ABONOS" in rl:
                s["total_credits"] = ra[-1]
                if ri:
                    s["credits_count"] = ri[0]
            elif "CARGOS" in rl:
                s["total_debits"] = ra[-1]
                if ri:
                    s["debits_count"] = ri[0]
            elif "MINIMO" in rl:
                s["minimum_average_balance"] = ra[-1]
            elif rl.startswith("SALDO"):
                s["closing_balance"] = ra[-1]

    # ------------------------------------------------------------------
    def _transactions(self, doc: LoadedDocument, raw: RawStatement) -> None:
        p1 = doc.pages[0]
        header = next((ln for ln in p1.lines if "DESCRIPCION" in ln.ntext and "REFERENCIA" in ln.ntext), None)
        if not header:
            raw.warnings.append("No se encontró la tabla de movimientos.")
            return
        pos = {norm(w.text): w.x0 for w in header.words}
        columns = Columns({
            "debit": pos.get("CARGOS", 381),
            "credit": pos.get("ABONOS", 427),
            "balance_operation": pos.get("OPERACION", 469),
            "balance": pos.get("LIQUIDACION", 536),
        })
        desc_x = pos.get("DESCRIPCION", 105) - 5
        ref_x = pos.get("REFERENCIA", 321) - 5

        rows: list[Line] = []
        done = False
        for page in doc.pages:
            if done:
                break
            if page.number == 1:
                start = header.top
            else:
                client = page.find("No. de Cliente")
                start = client.top if client else 0
            plines = page.lines
            for i, line in enumerate(plines):
                if line.top <= start or line.top > page.height - FOOTER_MARGIN:
                    continue
                n = line.ntext
                if "INSTITUCION DE BANCA MULTIPLE" in n or n.startswith("LA GAT REAL"):
                    continue
                if n.startswith("TOTAL DE MOVIMIENTOS"):
                    self._bank_totals(plines[i + 1:], raw)
                    done = True
                    break
                rows.append(line)

        groups: list[dict] = []
        for line in rows:
            w = line.words
            if len(w) >= 2 and w[0].x0 < 40 and TX_DATE.match(norm(w[0].text)) and TX_DATE.match(norm(w[1].text)):
                groups.append({"line": line, "dates": (w[0].text, w[1].text), "rows": [line], "first": None})
            elif groups:
                groups[-1]["rows"].append(line)

        for g in groups:
            tx = self._transaction(g, columns, desc_x, ref_x, raw)
            if tx:
                raw.transactions.append(tx)

    def _bank_totals(self, lines: list[Line], raw: RawStatement) -> None:
        for line in lines[:4]:
            n = line.ntext
            left = [v for _, v in amounts(line.within(0, 300))]
            count = ints(line.within(500))
            if "TOTAL IMPORTE CARGOS" in n:
                raw.bank_totals["total_debits"] = left[-1] if left else None
                raw.bank_totals["debits_count"] = count[-1] if count else None
            elif "TOTAL IMPORTE ABONOS" in n:
                raw.bank_totals["total_credits"] = left[-1] if left else None
                raw.bank_totals["credits_count"] = count[-1] if count else None

    def _transaction(self, g: dict, columns: Columns, desc_x: float, ref_x: float, raw: RawStatement) -> RawTransaction | None:
        rows: list[Line] = g["rows"]
        # renglón solo con fechas: la descripción (y los montos) vienen en el siguiente
        first_idx = 0
        if not rows[0].text_within(desc_x, ref_x) and len(rows) > 1:
            first_idx = 1
        first_line = rows[first_idx].text_within(desc_x, ref_x)
        found = amounts(rows[0].within(340)) + (amounts(rows[1].within(340)) if first_idx == 1 else [])
        if not found and len(rows) > first_idx + 1:
            found = amounts(rows[first_idx + 1].within(340))
        values: dict[str, object] = {}
        for word, value in found:
            col = columns.assign(word)
            if col and col not in values:
                values[col] = value
        details = rows[first_idx + 1:]

        d0 = parse_short_date(g["dates"][0], raw.period_start, raw.period_end)
        d1 = parse_short_date(g["dates"][1], raw.period_start, raw.period_end)
        if not d0:
            raw.warnings.append("Movimiento con fecha ilegible omitido.")
            return None

        tx = RawTransaction(
            date=d0, posting_date=d1, page=rows[0].page, first_line=first_line,
            description=norm(first_line), type="other",
            debit=values.get("debit"), credit=values.get("credit"),
            balance=values.get("balance"), balance_operation=values.get("balance_operation"),
        )
        self._classify(tx)
        self._details(tx, details, desc_x, ref_x)
        if tx.debit is None and tx.credit is None:
            raw.warnings.append("Movimiento sin monto de cargo/abono.")
        return tx

    def _classify(self, tx: RawTransaction) -> None:
        n = norm(tx.first_line)
        for rx, typ, canonical in RULES:
            m = rx.match(n)
            if m:
                tx.type, tx.description = typ, canonical
                groups = m.groupdict()
                if groups.get("bank"):
                    tx.counterparty_bank = groups["bank"].strip()
                if groups.get("num"):
                    tx.pii.append(groups["num"])
                return
        merchant = match_merchant(n)
        is_cash = n.endswith(" CASH")
        if merchant:
            tx.merchant = merchant
            tx.description = f"{merchant} CASH" if is_cash else merchant
        if is_cash:
            tx.type = "cash_deposit" if tx.credit and not tx.debit else "cash_withdrawal"
        elif merchant:
            tx.type = "card_purchase" if tx.debit else "refund"

    def _details(self, tx: RawTransaction, details: list[Line], desc_x: float, ref_x: float) -> None:
        texts = []
        for line in details:
            words = line.words
            for i, w in enumerate(words):
                if norm(w.text) == "REFERENCIA" and i + 1 < len(words):
                    tx.pii.append(words[i + 1].text)
            t = norm(line.text_within(desc_x, ref_x))
            if t:
                texts.append(t)
                tx.pii += DIGITS4.findall(t)

        if tx.type in ("spei_in", "spei_out", "spei_refund"):
            for t in texts:
                compact = t.replace(" ", "")
                if TRACKING_RE.match(compact):
                    tx.tracking_key = tx.tracking_key or compact
                elif m := REF_CONCEPT_RE.match(t):
                    tx.concept = m.group(2) or tx.concept
                elif not re.search(r"\d", t) and len(t) >= 3:
                    tx.counterparty_name = t  # renglón solo con letras: nombre de la contraparte
        elif tx.type == "transfer_out":
            for t in texts:
                if m := THIRD_PARTY_RE.match(t):
                    tx.counterparty_account = m.group(2)
                    tx.concept = m.group(3) or None
