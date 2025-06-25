from flask import Flask, request, jsonify
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import check_password_hash
import webbrowser
import threading
import os
import csv
from datetime import datetime
from sqlalchemy import func

from .models import init_db, SessionLocal, Transaction, Category, Rule, User

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
    and ``montant`` in that order. Only the ``date``, ``libellé`` and
    ``montant`` columns are used.

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
            amount = float(amount_str.replace(',', '.'))
        except ValueError:
            errors.append(f'Ligne {line_no}: montant invalide')
            continue

        key = (date, label.strip(), amount)
        if key in seen:
            errors.append(f'Ligne {line_no}: doublon d\'entrée')
            continue
        seen.add(key)

        transactions.append({'date': date, 'label': label.strip(), 'amount': amount})

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
            for r in rules:
                if r.pattern.lower() in t['label'].lower():
                    category_id = r.category_id
                    break

            session.add(Transaction(
                date=t['date'], label=t['label'], amount=t['amount'],
                category_id=category_id
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
            'label': t.label,
            'amount': t.amount,
            'category': t.category.name if t.category else None
        })
    session.close()
    return jsonify(results)


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
            data = [{'id': c.id, 'name': c.name} for c in session.query(Category).all()]
            session.close()
            return jsonify(data)
        category = session.query(Category).get(category_id)
        if not category:
            session.close()
            return jsonify({'error': 'Not found'}), 404
        result = {'id': category.id, 'name': category.name}
        session.close()
        return jsonify(result)

    if request.method == 'POST':
        data = request.get_json() or {}
        name = data.get('name')
        if not name:
            session.close()
            return jsonify({'error': 'Missing name'}), 400
        category = Category(name=name)
        session.add(category)
        session.commit()
        result = {'id': category.id, 'name': category.name}
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
        if name:
            category.name = name
            session.commit()
        result = {'id': category.id, 'name': category.name}
        session.close()
        return jsonify(result)

    session.delete(category)
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
                    'category': r.category.name if r.category else None,
                } for r in session.query(Rule).all()
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
            'category': rule.category.name if rule.category else None,
        }
        session.close()
        return jsonify(result)

    if request.method == 'POST':
        data = request.get_json() or {}
        pattern = data.get('pattern')
        category_id = data.get('category_id')
        if not pattern or not category_id:
            session.close()
            return jsonify({'error': 'Missing fields'}), 400
        rule = Rule(pattern=pattern, category_id=category_id)
        session.add(rule)
        session.commit()
        result = {
            'id': rule.id,
            'pattern': rule.pattern,
            'category_id': rule.category_id,
            'category': rule.category.name if rule.category else None,
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
            rule.category_id = data['category_id']
        session.commit()
        result = {
            'id': rule.id,
            'pattern': rule.pattern,
            'category_id': rule.category_id,
            'category': rule.category.name if rule.category else None,
        }
        session.close()
        return jsonify(result)

    session.delete(rule)
    session.commit()
    session.close()
    return jsonify({'message': 'deleted'})


def open_browser():
    webbrowser.open_new('http://localhost:5000')


def run():
    init_db()
    threading.Timer(1, open_browser).start()
    app.run(host='0.0.0.0')


if __name__ == '__main__':
    run()
