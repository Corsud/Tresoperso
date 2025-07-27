import csv
import re
from datetime import datetime  # use standard datetime
from typing import List, Optional, Tuple

from sqlalchemy import func

from .models import Transaction


def detect_csv_structure(content: str) -> Tuple[str, Optional[int], List[str]]:
    """Guess delimiter and header line in CSV text.

    The function uses :class:`csv.Sniffer` when possible and falls back to a
    simple heuristic. It skips empty lines at the beginning of the file and
    returns the delimiter, the index of the header line in ``content.splitlines``
    and the list of detected column names. ``None`` is returned as the header
    index when no obvious header could be detected.
    """

    lines = content.splitlines()
    if not lines:
        return ',', None, []

    # Remove leading blank lines but keep their count to compute the index
    start_index = 0
    for i, line in enumerate(lines):
        if line.strip():
            start_index = i
            break
    else:
        return ',', None, []

    sample_lines = [l for l in lines[start_index:start_index + 10] if l.strip()]
    sample = '\n'.join(sample_lines)
    sniffer = csv.Sniffer()
    delimiter = ','
    try:
        dialect = sniffer.sniff(sample, delimiters=[',', ';', '\t', '|'])
        delimiter = dialect.delimiter
    except csv.Error:
        counts = {d: sample.count(d) for d in [',', ';', '\t', '|']}
        delimiter = max(counts, key=counts.get)

    header_index: Optional[int] = None
    columns: List[str] = []

    for idx in range(start_index, len(lines)):
        row = lines[idx]
        if not row.strip():
            continue
        parts = [c.strip().lower() for c in row.split(delimiter)]
        if any('date' in p for p in parts) and any('montant' in p or 'amount' in p for p in parts):
            header_index = idx
            columns = [c.strip() for c in row.split(delimiter)]
            break
    if header_index is None and sample_lines:
        # Use Sniffer.has_header on the first data lines
        try:
            if sniffer.has_header(sample):
                header_index = start_index
                columns = [c.strip() for c in lines[start_index].split(delimiter)]
        except csv.Error:
            pass

    return delimiter, header_index, columns


def parse_csv(content):
    """Parse CSV content and return transactions, duplicates, errors and account info."""
    reader = csv.reader(content.splitlines(), delimiter=';')
    rows = list(reader)
    if not rows:
        return [], [], ['Fichier totalement vide'], {}

    # Detect a BNP export with a header line after an empty row
    header_mode = False
    if len(rows) >= 3 and not any(c.strip() for c in rows[1]):
        hdr = [c.lower() for c in rows[2]]
        if hdr and 'date' in hdr[0] and 'montant' in hdr[-1]:
            header_mode = True

    if header_mode and len(rows[0]) >= 4:
        raw = rows[0]
        account_type = raw[0].strip()
        name = raw[1].strip() if len(raw) > 1 else ''
        number = raw[2].strip() if len(raw) > 2 else ''
        export_date = None
        if len(raw) > 3 and raw[3].strip():
            for fmt in ('%Y-%m-%d', '%d/%m/%Y'):
                try:
                    export_date = datetime.strptime(raw[3].strip(), fmt).date()
                    break
                except ValueError:
                    continue
        balance = None
        if len(raw) > 5 and raw[5].strip():
            cleaned = raw[5].replace('\xa0', '').replace(' ', '').replace(',', '.')
            try:
                balance = float(cleaned)
            except ValueError:
                balance = None
        account_info = {
            'account_type': account_type,
            'name': name,
            'number': number,
            'export_date': export_date,
        }
        if balance is not None:
            account_info['initial_balance'] = balance
            account_info['balance_date'] = export_date
        start_idx = 3
    else:
        account_row = rows[0]
        info_str = ' '.join(account_row)
        number = ''
        export_date = None
        account_type = info_str
        m = re.search(r'(\d{2}/\d{2}/\d{4}|\d{4}-\d{2}-\d{2})', info_str)
        if m:
            date_str = m.group(1)
            try:
                export_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                try:
                    export_date = datetime.strptime(date_str, '%d/%m/%Y').date()
                except ValueError:
                    export_date = None
            account_type = info_str[:m.start()].strip()
        n = re.search(r'(\d{4,})', info_str)
        if n:
            number = n.group(1)
            if n.start() < len(account_type):
                account_type = account_type[:n.start()].strip()

        account_info = {
            'account_type': account_type.strip(),
            'number': number,
            'export_date': export_date,
        }
        start_idx = 1

    transactions = []
    duplicates = []
    errors = []
    seen = set()

    for line_no, row in enumerate(rows[start_idx:], start=start_idx + 1):
        if not any(cell.strip() for cell in row):
            continue
        if len(row) < 5:
            errors.append(
                f"Ligne {line_no}: colonnes manquantes (ligne comportant moins "
                "de cinq colonnes ou des colonnes essentielles manquantes)"
            )
            continue

        date_str = row[0]
        tx_type = row[1]
        payment_method = row[2]
        label = row[3].strip()
        if label.startswith(('=', '+', '-', '@')):
            label = "'" + label

        amount_str = row[4]

        if not (date_str and label and amount_str):
            errors.append(
                f"Ligne {line_no}: colonnes manquantes (ligne comportant moins "
                "de cinq colonnes ou des colonnes essentielles manquantes)"
            )
            continue

        try:
            try:
                date = datetime.strptime(date_str.strip(), '%Y-%m-%d').date()
            except ValueError:
                date = datetime.strptime(date_str.strip(), '%d/%m/%Y').date()
        except ValueError:
            errors.append(
                f"Ligne {line_no}: date impossible à convertir (formats acceptés : YYYY-MM-DD ou DD/MM/YYYY)"
            )
            continue

        try:
            cleaned = amount_str.replace('\xa0', '').replace(' ', '')
            negative = False
            if cleaned.endswith('-'):
                negative = True
                cleaned = cleaned[:-1]
            elif cleaned.startswith('(') and cleaned.endswith(')'):
                negative = True
                cleaned = cleaned[1:-1]

            cleaned = cleaned.replace(',', '.')
            amount = float(cleaned)
            if negative:
                amount = -amount
        except ValueError:
            errors.append(
                f"Ligne {line_no}: montant non numérique (gestion du signe - en fin ou de parenthèses)"
            )
            continue

        key = (date, label.strip(), amount)
        if key in seen:
            duplicates.append({
                'line_no': line_no,
                'date': date,
                'type': tx_type.strip(),
                'payment_method': payment_method.strip(),
                'label': label.strip(),
                'amount': amount,
            })
            continue
        seen.add(key)

        transactions.append({
            'date': date,
            'type': tx_type.strip(),
            'payment_method': payment_method.strip(),
            'label': label.strip(),
            'amount': amount,
            'reconciled': False,
            'to_analyze': True
        })

    return transactions, duplicates, errors, account_info


def apply_rule_to_transactions(session, rule):
    """Update transactions matching a rule and return the number updated."""
    words = [w for w in rule.pattern.split() if w]
    if not words:
        return 0

    like_pattern = '%' + '%'.join(words) + '%'
    updated = (
        session.query(Transaction)
        .filter(func.lower(Transaction.label).like(like_pattern.lower()))
        .update(
            {
                Transaction.category_id: rule.category_id,
                Transaction.subcategory_id: rule.subcategory_id,
            },
            synchronize_session=False,
        )
    )
    session.commit()
    return updated
