from flask import Flask, request, jsonify
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import check_password_hash
import webbrowser
import threading
import os
import csv
from datetime import datetime
from sqlalchemy import func

from .models import (
    init_db,
    SessionLocal,
    Transaction,
    Category,
    Subcategory,
    Rule,
    User,
)

# Compute the absolute path to the frontend directory so Flask can
# reliably serve the static files no matter where the application is
# started from.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, '..', 'frontend')

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path='')
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret')

login_manager = LoginManager(app)
login_manager.login_view = 'login'


@login_manager.user_loader
def load_user(user_id):
    session = SessionLocal()
    user = session.query(User).get(int(user_id))
    session.close()
    return user

@app.route('/')
def index():
    return app.send_static_file('index.html')


@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid payload'}), 400

    username = data.get('username', '')
    password = data.get('password', '')

    session = SessionLocal()
    user = session.query(User).filter_by(username=username).first()
    session.close()

    if user and check_password_hash(user.password, password):
        login_user(user)
        return jsonify({'message': 'Logged in'})
    return jsonify({'error': 'Invalid credentials'}), 401


@app.route('/logout')
def logout():
    logout_user()
    return jsonify({'message': 'Logged out'})


@app.route('/me')
def me():
    if current_user.is_authenticated:
        return jsonify({'username': current_user.username})
    return jsonify({'error': 'Unauthorized'}), 401


def parse_csv(content):
    """Parse CSV content and return valid transactions and errors.

    The BNP CSV files described in the README do not have a header line and
    use a semicolon (``;``) as delimiter. The first line contains account
    information and must be ignored. Each transaction line is expected to
    contain the fields ``date`` , ``type`` , ``moyen de paiement`` , ``libellé``
    and ``montant`` in that order. The ``type`` and ``moyen de paiement``
    columns are now stored alongside ``date``, ``libellé`` and ``montant``.

    Duplicate rows based on (date, label, amount) are ignored and reported as
    errors.
    """

    reader = csv.reader(content.splitlines(), delimiter=';')
    rows = list(reader)
    if not rows:
        return [], ['Fichier vide']

    transactions = []
    errors = []
    seen = set()

    # Skip the first line which contains account information
    for line_no, row in enumerate(rows[1:], start=2):
        if len(row) < 5:
            errors.append(f'Ligne {line_no}: colonnes manquantes')
            continue

        date_str = row[0]
        tx_type = row[1]
        payment_method = row[2]
        label = row[3]
        amount_str = row[4]

        if not (date_str and label and amount_str):
            errors.append(f'Ligne {line_no}: colonnes manquantes')
            continue

        try:
            try:
                date = datetime.strptime(date_str.strip(), '%Y-%m-%d').date()
            except ValueError:
                date = datetime.strptime(date_str.strip(), '%d/%m/%Y').date()
        except ValueError:
            errors.append(f'Ligne {line_no}: date invalide')
            continue

        try:
            cleaned = amount_str.replace('\xa0', '').replace(' ', '')
            cleaned = cleaned.replace(',', '.')
            amount = float(cleaned)
        except ValueError:
            errors.append(f'Ligne {line_no}: montant invalide')
            continue

        key = (date, label.strip(), amount)
        if key in seen:
            errors.append(f'Ligne {line_no}: doublon d\'entrée')
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

    return transactions, errors


@app.route('/import', methods=['POST'])
@login_required
def import_csv():
    """Import transactions from a CSV file."""
    if 'file' not in request.files:
        return jsonify({'error': 'Aucun fichier fourni'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Aucun fichier fourni'}), 400

    errors = []
    try:
        content = file.stream.read().decode('utf-8')
    except Exception as e:
        return jsonify({'error': str(e)}), 400

    transactions, errors = parse_csv(content)

    session = SessionLocal()
    imported = 0
    skipped = 0

    # Load rules once for auto-categorisation
    rules = session.query(Rule).all()

    try:
        for t in transactions:
            exists = session.query(Transaction).filter_by(
                date=t['date'], label=t['label'], amount=t['amount']
            ).first()
            if exists:
                skipped += 1
                continue

            category_id = None
            subcategory_id = None
            for r in rules:
                if r.pattern.lower() in t['label'].lower():
                    category_id = r.category_id
                    subcategory_id = r.subcategory_id
                    break

            session.add(Transaction(
                date=t['date'],
                tx_type=t['type'],
                payment_method=t['payment_method'],
                label=t['label'],
                amount=t['amount'],
                category_id=category_id,
                subcategory_id=subcategory_id,
                reconciled=t['reconciled'],
                to_analyze=t['to_analyze']
            ))
            imported += 1
        session.commit()
    except Exception as e:
        session.rollback()
        errors.append(str(e))
    finally:
        session.close()

    response = {'imported': imported, 'skipped': skipped}
    if errors:
        response['errors'] = errors
        return jsonify(response), 400
    return jsonify(response)


@app.route('/transactions')
@login_required
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
            'type': t.tx_type,
            'payment_method': t.payment_method,
            'label': t.label,
            'amount': t.amount,
            'category_id': t.category_id,
            'category': t.category.name if t.category else None,
            'category_color': t.category.color if t.category else None,
            'subcategory_id': t.subcategory_id,
            'subcategory': t.subcategory.name if t.subcategory else None,
            'subcategory_color': t.subcategory.color if t.subcategory else None,
            'reconciled': t.reconciled,
            'to_analyze': t.to_analyze,
        })
    session.close()
    return jsonify(results)

@app.route('/transactions/<int:tx_id>', methods=['PUT', 'GET'])
@login_required
def update_transaction(tx_id):
    """Retrieve or update a single transaction."""
    session = SessionLocal()
    tx = session.query(Transaction).get(tx_id)
    if not tx:
        session.close()
        return jsonify({'error': 'Not found'}), 404

    if request.method == 'GET':
        result = {
            'id': tx.id,
            'date': tx.date.isoformat(),
            'type': tx.tx_type,
            'payment_method': tx.payment_method,
            'label': tx.label,
            'amount': tx.amount,
            'category_id': tx.category_id,
            'subcategory_id': tx.subcategory_id,
            'reconciled': tx.reconciled,
            'to_analyze': tx.to_analyze,
        }
        session.close()
        return jsonify(result)

    data = request.get_json() or {}
    if 'category_id' in data:
        tx.category_id = data['category_id'] or None
    if 'subcategory_id' in data:
        tx.subcategory_id = data['subcategory_id'] or None
    if 'reconciled' in data:
        tx.reconciled = bool(data['reconciled'])
    if 'to_analyze' in data:
        tx.to_analyze = bool(data['to_analyze'])
    session.commit()
    result = {
        'id': tx.id,
        'category_id': tx.category_id,
        'subcategory_id': tx.subcategory_id,
        'reconciled': tx.reconciled,
        'to_analyze': tx.to_analyze,
        'category': tx.category.name if tx.category else None,
        'category_color': tx.category.color if tx.category else None,
        'subcategory': tx.subcategory.name if tx.subcategory else None,
        'subcategory_color': tx.subcategory.color if tx.subcategory else None,
    }
    session.close()
    return jsonify(result)

@app.route('/stats')
@login_required
def stats():
    session = SessionLocal()
    data = session.query(
        func.strftime('%Y-%m', Transaction.date).label('month'),
        func.sum(Transaction.amount).label('total')
    ).group_by('month').order_by('month').all()
    session.close()
    return jsonify([{ 'month': m, 'total': t } for m, t in data])


@app.route('/projection')
@login_required
def projection():
    months = int(request.args.get('months', 6))
    session = SessionLocal()
    data = session.query(
        func.strftime('%Y-%m', Transaction.date).label('month'),
        func.sum(Transaction.amount).label('total')
    ).group_by('month').order_by('month').all()
    session.close()
    if not data:
        return jsonify([])

    avg = sum(d[1] for d in data) / len(data)
    last_month = data[-1][0]
    year, month = map(int, last_month.split('-'))
    result = []
    for i in range(1, months + 1):
        m = month + i
        y = year + (m - 1) // 12
        m = (m - 1) % 12 + 1
        result.append({'month': f'{y:04d}-{m:02d}', 'amount': avg})
    return jsonify(result)


@app.route('/categories', methods=['GET', 'POST'])
@app.route('/categories/<int:category_id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
def categories(category_id=None):
    session = SessionLocal()
    if request.method == 'GET':
        if category_id is None:
            data = [
                {
                    'id': c.id,
                    'name': c.name,
                    'color': c.color,
                    'subcategories': [
                        {'id': s.id, 'name': s.name, 'color': s.color}
                        for s in c.subcategories
                    ],
                }
                for c in session.query(Category).all()
            ]
            session.close()
            return jsonify(data)
        category = session.query(Category).get(category_id)
        if not category:
            session.close()
            return jsonify({'error': 'Not found'}), 404
        result = {
            'id': category.id,
            'name': category.name,
            'color': category.color,
            'subcategories': [
                {'id': s.id, 'name': s.name, 'color': s.color}
                for s in category.subcategories
            ],
        }
        session.close()
        return jsonify(result)

    if request.method == 'POST':
        data = request.get_json() or {}
        name = data.get('name')
        color = data.get('color', '')
        if not name:
            session.close()
            return jsonify({'error': 'Missing name'}), 400
        category = Category(name=name, color=color)
        session.add(category)
        session.commit()
        result = {'id': category.id, 'name': category.name, 'color': category.color}
        session.close()
        return jsonify(result), 201

    # PUT or DELETE
    category = session.query(Category).get(category_id)
    if not category:
        session.close()
        return jsonify({'error': 'Not found'}), 404

    if request.method == 'PUT':
        data = request.get_json() or {}
        name = data.get('name')
        color = data.get('color')
        if name is not None:
            category.name = name
        if color is not None:
            category.color = color
        session.commit()
        result = {'id': category.id, 'name': category.name, 'color': category.color}
        session.close()
        return jsonify(result)

    session.delete(category)
    session.commit()
    session.close()
    return jsonify({'message': 'deleted'})


@app.route('/subcategories', methods=['GET', 'POST'])
@app.route('/subcategories/<int:sub_id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
def subcategories(sub_id=None):
    session = SessionLocal()
    if request.method == 'GET':
        if sub_id is None:
            data = [
                {
                    'id': s.id,
                    'name': s.name,
                    'color': s.color,
                    'category_id': s.category_id,
                    'category': s.category.name if s.category else None,
                }
                for s in session.query(Subcategory).all()
            ]
            session.close()
            return jsonify(data)
        sub = session.query(Subcategory).get(sub_id)
        if not sub:
            session.close()
            return jsonify({'error': 'Not found'}), 404
        result = {
            'id': sub.id,
            'name': sub.name,
            'color': sub.color,
            'category_id': sub.category_id,
            'category': sub.category.name if sub.category else None,
        }
        session.close()
        return jsonify(result)

    if request.method == 'POST':
        data = request.get_json() or {}
        name = data.get('name')
        category_id = data.get('category_id')
        color = data.get('color', '')
        if not name or not category_id:
            session.close()
            return jsonify({'error': 'Missing fields'}), 400
        sub = Subcategory(name=name, category_id=int(category_id), color=color)

        session.add(sub)
        session.commit()
        result = {
            'id': sub.id,
            'name': sub.name,
            'color': sub.color,
            'category_id': sub.category_id,
        }
        session.close()
        return jsonify(result), 201

    sub = session.query(Subcategory).get(sub_id)
    if not sub:
        session.close()
        return jsonify({'error': 'Not found'}), 404

    if request.method == 'PUT':
        data = request.get_json() or {}
        if 'name' in data:
            sub.name = data['name']
        if 'category_id' in data:
            cid = data['category_id']
            sub.category_id = int(cid) if cid else None

        if 'color' in data:
            sub.color = data['color']
        session.commit()
        result = {
            'id': sub.id,
            'name': sub.name,
            'color': sub.color,
            'category_id': sub.category_id,
        }
        session.close()
        return jsonify(result)

    session.delete(sub)
    session.commit()
    session.close()
    return jsonify({'message': 'deleted'})


@app.route('/rules', methods=['GET', 'POST'])
@app.route('/rules/<int:rule_id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
def rules(rule_id=None):
    session = SessionLocal()
    if request.method == 'GET':
        if rule_id is None:
            data = [
                {
                    'id': r.id,
                    'pattern': r.pattern,
                    'category_id': r.category_id,
                    'subcategory_id': r.subcategory_id,
                    'category': r.category.name if r.category else None,
                    'subcategory': r.subcategory.name if r.subcategory else None,
                }
                for r in session.query(Rule).all()
            ]
            session.close()
            return jsonify(data)
        rule = session.query(Rule).get(rule_id)
        if not rule:
            session.close()
            return jsonify({'error': 'Not found'}), 404
        result = {
            'id': rule.id,
            'pattern': rule.pattern,
            'category_id': rule.category_id,
            'subcategory_id': rule.subcategory_id,
            'category': rule.category.name if rule.category else None,
            'subcategory': rule.subcategory.name if rule.subcategory else None,
        }
        session.close()
        return jsonify(result)

    if request.method == 'POST':
        data = request.get_json() or {}
        pattern = data.get('pattern')
        category_id = data.get('category_id')
        subcategory_id = data.get('subcategory_id')
        if not pattern or not category_id:
            session.close()
            return jsonify({'error': 'Missing fields'}), 400
        rule = Rule(
            pattern=pattern,
            category_id=int(category_id),
            subcategory_id=int(subcategory_id) if subcategory_id else None,
        )

        session.add(rule)
        session.commit()
        result = {
            'id': rule.id,
            'pattern': rule.pattern,
            'category_id': rule.category_id,
            'subcategory_id': rule.subcategory_id,
            'category': rule.category.name if rule.category else None,
            'subcategory': rule.subcategory.name if rule.subcategory else None,
        }
        session.close()
        return jsonify(result), 201

    rule = session.query(Rule).get(rule_id)
    if not rule:
        session.close()
        return jsonify({'error': 'Not found'}), 404

    if request.method == 'PUT':
        data = request.get_json() or {}
        if 'pattern' in data:
            rule.pattern = data['pattern']
        if 'category_id' in data:
            cid = data['category_id']
            rule.category_id = int(cid) if cid else None
        if 'subcategory_id' in data:
            sid = data['subcategory_id']
            rule.subcategory_id = int(sid) if sid else None

        session.commit()
        result = {
            'id': rule.id,
            'pattern': rule.pattern,
            'category_id': rule.category_id,
            'subcategory_id': rule.subcategory_id,
            'category': rule.category.name if rule.category else None,
            'subcategory': rule.subcategory.name if rule.subcategory else None,
        }
        session.close()
        return jsonify(result)

    session.delete(rule)
    session.commit()
    session.close()
    return jsonify({'message': 'deleted'})


@app.route('/reset', methods=['POST'])
@login_required
def reset():
    """Delete all transactions from the database."""
    session = SessionLocal()
    session.query(Transaction).delete()
    session.commit()
    session.close()
    return jsonify({'message': 'reset'})


def open_browser():
    webbrowser.open_new('http://localhost:5000')


def run():
    init_db()
    threading.Timer(1, open_browser).start()
    app.run(host='0.0.0.0')


if __name__ == '__main__':
    run()
