from flask import Flask, send_from_directory, request, jsonify
import webbrowser
import threading
import os
import csv
from datetime import datetime

from .models import init_db, SessionLocal, Transaction

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


def open_browser():
    webbrowser.open_new('http://localhost:5000')


def run():
    init_db()
    threading.Timer(1, open_browser).start()
    app.run()


if __name__ == '__main__':
    run()
