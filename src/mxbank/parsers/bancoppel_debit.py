"""BanCoppel · cuenta de débito digital. Ver docs/bancos/bancoppel-cuenta.md."""

from __future__ import annotations

import re

from ..loader import Line, LoadedDocument
from ..models.raw import RawStatement, RawTransaction
from ..normalize.amounts import parse_number
from ..normalize.dates import parse_full_date, parse_short_date
from ..text import norm
from .base import BankParser, Columns, all_lines, amounts, ints, label_text, numbers, search

TX_DATE = re.compile(r"^\d{2}/\d{2}$")  # MM/DD (mes primero)
LABEL_RE = re.compile(r"^([A-Z][A-Z ]{1,30}):\s*(.*)$")
DIGITS4 = re.compile(r"\d[\d-]{3,}")
FOOTER_MARGIN = 50

RULES: list[tuple[re.Pattern, str, str]] = [
    (re.compile(r"^ABONO SPEI\s*(?P<track>\S*)"), "spei_in", "ABONO SPEI"),
    (re.compile(r"^CARGO SPEI\s*(?P<track>\S*)"), "spei_out", "CARGO SPEI"),
    (re.compile(r"^PAGO DE INTERESES"), "interest", "PAGO DE INTERESES"),
    # el concepto escrito por el usuario empieza en la misma primera línea
    (re.compile(r"^TRASPASO EN CUENTA\s*(?P<acct>\d+)?\s*(?P<concept>.*)$"), "transfer_out", "TRASPASO EN CUENTA"),
    (re.compile(r"^TRAS\.? ENTRE CTAS\.?\s*(?P<acct>\d+)?\s*(?P<concept>.*)$"), "transfer_internal", "TRASPASO ENTRE CUENTAS"),
    (re.compile(r"^RECARGA DE TIEMPO AIRE"), "mobile_topup", "RECARGA DE TIEMPO AIRE A TRAVES DE APP"),
]


class BanCoppelDebitParser(BankParser):
    bank = "bancoppel"
    bank_name = "BanCoppel"
    product = "debit"
    layout_version = "2025.1"

    def fingerprint(self, doc: LoadedDocument) -> float:
        t = doc.ntext
        score = 0.0
        if "BANCOPPEL, S" in t:
            score += 0.5
        if "RESUMEN DE LA CUENTA" in t:
            score += 0.2
        if re.search(r"\bHOJA 1 DE \d+", t):
            score += 0.2
        if "DETALLE DE MOVIMIENTOS" in t and "PERIODO:" in t:
            score += 0.1
        return round(score, 2)

    def parse(self, doc: LoadedDocument, confidence: float) -> RawStatement:
        raw = RawStatement(
            bank=self.bank, bank_name=self.bank_name, product=self.product, product_name=None,
            layout_version=self.layout_version, confidence=confidence, pages=len(doc.pages),
            balance_mode="per_row",
            totals_exclude=frozenset({"interest"}),  # "Más Depósitos" no incluye los intereses
        )
        self._header(doc, raw)
        self._summary(doc, raw)
        self._transactions(doc, raw)
        return raw

    # ------------------------------------------------------------------
    def _header(self, doc: LoadedDocument, raw: RawStatement) -> None:
        p1 = doc.pages[0]
        lines = p1.lines
        h = raw.header

        product = next((ln for ln in lines if "DIGITAL" in ln.ntext and ln.text_within(380)), None)
        if product:
            raw.product_name = norm(product.text_within(380)) or None
        if m := search(all_lines(doc), r"PERIODO: (\d{2}/[A-Z]{3}\.?/\d{4}) AL (\d{2}/[A-Z]{3}\.?/\d{4})"):
            raw.period_start, raw.period_end = parse_full_date(m.group(1)), parse_full_date(m.group(2))
        if m := search(lines, r"NUMERO DE CUENTA: ?(\d{8,12})"):
            h.account_number = m.group(1)
            h.add("account_number", m.group(1))
        if m := search(lines, r"NO\. DE CLIENTE: ?(\d{5,12})"):
            h.add("client_number", m.group(1))
        if m := search(lines, r"CLABE: ?(\d{18})"):
            h.add("clabe", m.group(1))
        if m := search(lines, r"GAT NOMINAL (-?\d+\.\d+)"):
            raw.rates["gat_nominal_percent"] = parse_number(m.group(1))
        if m := search(lines, r"GAT REAL (-?\d+\.\d+)"):
            raw.rates["gat_real_percent"] = parse_number(m.group(1))

        detail = p1.find("Detalle de Movimientos")
        branch = p1.find("Sucursal:")
        client = p1.find("No. de cliente")
        end = detail.top if detail else 340
        block_end = branch.top if branch else 175
        left = [ln.text_within(0, 300) for ln in lines if 85 < ln.top < block_end]
        left = [t for t in left if t]
        if left:
            h.add("holder_name", left[0])
            h.add("address", " ".join(left[1:]))
        if branch:
            h.add("branch", branch.text.split(":", 1)[-1])
        if branch and client:
            # renglones entre sucursal y número de cliente: personal de la sucursal (dato de tercero)
            for ln in lines:
                if branch.top < ln.top < client.top and ":" in ln.text:
                    h.add("branch_staff", ln.text.split(":", 1)[-1])
        for ln in lines:
            if ln.top < end:
                for w in ln.within(0, 300):
                    if re.fullmatch(r"\d{5,}", w.text):
                        h.add("header_number", w.text)

        # CFDI: columna del receptor
        for page in doc.pages[1:]:
            receptor = next((ln for ln in page.lines if "RECEPTOR" in ln.ntext and ln.text_within(265)), None)
            if not receptor:
                continue
            stop = page.find("Numero de Certificado")
            for ln in page.lines:
                if receptor.top < ln.top < (stop.top if stop else receptor.top + 100):
                    text = ln.text_within(265)
                    h.add("cfdi_receptor", text)
                    if m := re.search(r"RFC: ?([A-Z&]{3,4}\d{6}[A-Z0-9]{3})", norm(text)):
                        raw.holder_type = "business" if len(m.group(1)) == 12 else "individual"

    def _summary(self, doc: LoadedDocument, raw: RawStatement) -> None:
        page = next((p for p in doc.pages if p.find("Resumen de la Cuenta")), None)
        if not page:
            raw.warnings.append("No se encontró el Resumen de la Cuenta.")
            return
        s = raw.summary
        resumen = page.find("Resumen de la Cuenta")
        in_resumen = True
        for line in page.lines:
            if line.top <= resumen.top:
                continue
            n = label_text(line.words)
            a = [v for _, v in amounts(line.words)]
            if in_resumen:
                if not a:
                    continue
                if "ANTERIOR" in n:
                    s["opening_balance"] = a[-1]
                elif "SALDO ACTUAL" in n:
                    s["closing_balance"] = a[-1]
                    in_resumen = False
                elif "MAS" in n and "INTERESES" in n:
                    s["interest_earned"] = a[-1]
                elif "MAS" in n:
                    s["total_credits"] = a[-1]
                elif "MENOS" in n and "IVA" in n:
                    s["fees_vat"] = a[-1]
                elif "MENOS" in n and "COMISIONES" in n:
                    s["fees_total"] = a[-1]
                elif "MENOS" in n:
                    s["total_debits"] = a[-1]
            else:
                if "MENSUAL" in n and a:
                    s["average_balance"] = a[-1]
                elif "DIAS DEL PERIODO" in n and ints(line.words):
                    raw.days = ints(line.words)[-1]
                elif "TASA" in n and numbers(line.words):
                    raw.rates["gross_annual_rate_percent"] = numbers(line.words)[-1]
                elif "MENOS" in n and a:
                    s["tax_withheld"] = a[-1]

    # ------------------------------------------------------------------
    def _transactions(self, doc: LoadedDocument, raw: RawStatement) -> None:
        rows: list[Line] = []
        columns: Columns | None = None
        done = False
        for page in doc.pages:
            if done:
                break
            header = next(
                (ln for ln in page.lines
                 if ln.words and norm(ln.words[0].text) == "FECHA" and ln.words[0].x0 < 60 and "SALDO" in ln.ntext),
                None,
            )
            if not header:
                continue
            cols = [w for w in header.words if w.x0 > 340]
            if len(cols) == 3:
                columns = Columns(dict(zip(("debit", "credit", "balance"), (w.x0 for w in cols), strict=False)))
            for line in page.lines:
                if line.top <= header.top or line.top > page.height - FOOTER_MARGIN:
                    continue
                if line.ntext.startswith("MOVIMIENTOS EN PROCESO DE ACLARACION"):
                    done = True
                    break
                rows.append(line)
        if columns is None:
            columns = Columns({"debit": 356, "credit": 431, "balance": 524})

        groups: list[list[Line]] = []
        for line in rows:
            w = line.words
            if w and w[0].x0 < 60 and TX_DATE.match(w[0].text):
                groups.append([line])
            elif groups:
                groups[-1].append(line)
        for g in groups:
            tx = self._transaction(g, columns, raw)
            if tx:
                raw.transactions.append(tx)
        # BanCoppel lista del más reciente al más antiguo: se emite en orden cronológico
        txs = raw.transactions
        if len(txs) > 1 and txs[0].date > txs[-1].date:
            txs.reverse()

    def _transaction(self, rows: list[Line], columns: Columns, raw: RawStatement) -> RawTransaction | None:
        start = rows[0]
        d = parse_short_date(start.words[0].text, raw.period_start, raw.period_end, month_first=True)
        if not d:
            raw.warnings.append("Movimiento con fecha ilegible omitido.")
            return None
        values: dict[str, object] = {}
        for word, value in amounts(start.within(350)):
            col = columns.assign(word)
            if col and col not in values:
                values[col] = value
        first_line = start.text_within(75, 350)
        tx = RawTransaction(
            date=d, page=start.page, first_line=first_line, description=norm(first_line), type="other",
            debit=values.get("debit"), credit=values.get("credit"), balance=values.get("balance"),
        )
        n = norm(first_line)
        for rx, typ, canonical in RULES:
            m = rx.match(n)
            if not m:
                continue
            tx.type, tx.description = typ, canonical
            g = m.groupdict()
            if g.get("track"):
                tx.tracking_key = g["track"]
            if g.get("acct"):
                tx.counterparty_account = g["acct"]
            if g.get("concept"):
                tx.concept = g["concept"]
            break
        if tx.type == "transfer_out" and tx.credit and not tx.debit:
            tx.type = "transfer_in"
        self._details(tx, rows[1:])
        if tx.debit is None and tx.credit is None:
            raw.warnings.append("Movimiento sin monto de retiro/depósito.")
        return tx

    def _details(self, tx: RawTransaction, rows: list[Line]) -> None:
        last = None
        for line in rows:
            t = norm(line.text_within(75, 350))
            if not t:
                continue
            tx.pii += DIGITS4.findall(t)
            m = LABEL_RE.match(t)
            if m:
                label, value = m.group(1), m.group(2).strip()
                if "BANCO" in label:
                    tx.counterparty_bank, last = value or None, "bank"
                elif "FECHA" in label:
                    tx.value_date, last = parse_full_date(value), "date"
                elif "CLABE" in label or "CUENTA" in label:
                    tx.counterparty_account, last = re.sub(r"\D", "", value) or None, "account"
                elif "CONCEPTO" in label:
                    tx.concept, last = value or None, "concept"
                elif label in ("REF", "REFERENCIA"):
                    tx.pii.append(value)
                    last = "ref"
                else:  # ORDENANTE / BENEFICIARIO
                    tx.counterparty_name, last = value or None, "name"
            elif t.startswith("("):
                continue  # "(Dato no verificado por esta Institución)"
            elif last in (None, "concept"):
                if re.fullmatch(r"[A-Z0-9]{12,}", t.replace(" ", "")) and re.search(r"\d{6}", t):
                    tx.tracking_key = tx.tracking_key or t.replace(" ", "")
                else:
                    tx.concept = f"{tx.concept} {t}" if tx.concept else t
            elif last == "name" and tx.counterparty_name:
                tx.counterparty_name += f" {t}"

