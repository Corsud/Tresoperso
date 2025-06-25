from flask import Flask, send_from_directory, request, jsonify
import webbrowser
import threading
import os
import csv
from datetime import datetime

from .models import init_db, SessionLocal, Transaction, Category

app = Flask(__name__, static_folder='../frontend', static_url_path='')

@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')


@app.route('/import', methods=['POST'])
def import_csv():
    """Import transactions from a CSV file."""
    if 'file' not in request.files:
        return jsonify({'error': 'Aucun fichier fourni'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Aucun fichier fourni'}), 400

    session = SessionLocal()
    imported = 0
    errors = []

    try:
        stream = file.stream.read().decode('utf-8')
        reader = csv.DictReader(stream.splitlines())
        for i, row in enumerate(reader, start=1):
            date_str = row.get('date') or row.get('Date')
            label = row.get('libellé') or row.get('libelle') or row.get('label') or row.get('Libellé')
            amount_str = row.get('montant') or row.get('amount') or row.get('Montant')

            if not (date_str and label and amount_str):
                errors.append(f'Ligne {i}: colonnes manquantes')
                continue

            try:
                try:
                    date = datetime.strptime(date_str.strip(), '%Y-%m-%d').date()
                except ValueError:
                    date = datetime.strptime(date_str.strip(), '%d/%m/%Y').date()
            except ValueError:
                errors.append(f'Ligne {i}: date invalide')
                continue

            try:
                amount = float(amount_str.replace(',', '.'))
            except ValueError:
                errors.append(f'Ligne {i}: montant invalide')
                continue

            existing = session.query(Transaction).filter_by(date=date, label=label, amount=amount).first()
            if existing:
                continue

            session.add(Transaction(date=date, label=label, amount=amount))
            imported += 1
        session.commit()
    except Exception as e:
        session.rollback()
        errors.append(str(e))
    finally:
        session.close()

    if errors:
        return jsonify({'imported': imported, 'errors': errors}), 400
    return jsonify({'message': f'{imported} transactions importées'})


@app.route('/transactions')
def list_transactions():
    """Return transactions with optional filtering and sorting."""
    session = SessionLocal()
    query = session.query(Transaction)

    category = request.args.get('category')
    if category:
        query = query.join(Category).filter(Category.name == category)

    start_date = request.args.get('start_date')
    if start_date:
        try:
            date = datetime.strptime(start_date, '%Y-%m-%d').date()
            query = query.filter(Transaction.date >= date)
        except ValueError:
            pass

    end_date = request.args.get('end_date')
    if end_date:
        try:
            date = datetime.strptime(end_date, '%Y-%m-%d').date()
            query = query.filter(Transaction.date <= date)
        except ValueError:
            pass

    min_amount = request.args.get('min_amount')
    if min_amount:
        try:
            query = query.filter(Transaction.amount >= float(min_amount))
        except ValueError:
            pass

    max_amount = request.args.get('max_amount')
    if max_amount:
        try:
            query = query.filter(Transaction.amount <= float(max_amount))
        except ValueError:
            pass

    sort_by = request.args.get('sort_by', 'date')
    sort_column = getattr(Transaction, sort_by, Transaction.date)
    order = request.args.get('order', 'desc')
    sort_column = sort_column.desc() if order == 'desc' else sort_column.asc()
    query = query.order_by(sort_column)

    results = []
    for t in query.all():
        results.append({
            'id': t.id,
            'date': t.date.isoformat(),
            'label': t.label,
            'amount': t.amount,
            'category': t.category.name if t.category else None
        })
    session.close()
    return jsonify(results)


def open_browser():
    webbrowser.open_new('http://localhost:5000')


def run():
    init_db()
    threading.Timer(1, open_browser).start()
    app.run()


if __name__ == '__main__':
    run()
