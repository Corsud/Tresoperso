from flask import Flask, request, jsonify
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import check_password_hash
import webbrowser
import threading
import os
import csv
import re
from datetime import datetime, timedelta
from sqlalchemy import func, or_

from .models import (
    init_db,
    SessionLocal,
    Transaction,
    BankAccount,
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


@app.route('/accounts')
@login_required
def accounts():
    """Return all bank accounts."""
    session = SessionLocal()
    data = [
        {
            'id': a.id,
            'account_type': a.account_type,
            'number': a.number,
            'export_date': a.export_date.isoformat() if a.export_date else None,
        }
        for a in session.query(BankAccount).all()
    ]
    session.close()
    return jsonify(data)


def parse_csv(content):
    """Parse CSV content and return valid transactions, account info and errors.

    The BNP CSV files described in the README do not have a header line and
    use a semicolon (``;``) as delimiter. The first line contains account
    information and must be ignored. Each transaction line is expected to
    contain the fields ``date`` , ``type`` , ``moyen de paiement`` , ``libellé``
    and ``montant`` in that order. The ``type`` and ``moyen de paiement``
    columns are now stored alongside ``date``, ``libellé`` and ``montant``.

    Duplicate rows based on (date, label, amount) are returned separately
    instead of being treated as errors. They can then be reviewed by the user
    before insertion.
    """

    reader = csv.reader(content.splitlines(), delimiter=';')
    rows = list(reader)
    if not rows:
        return [], [], ['Fichier vide'], {}

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

    transactions = []
    duplicates = []
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

            # Detect negative formats like "123,45-" or "(123,45)"
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
            errors.append(f'Ligne {line_no}: montant invalide')
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
    """Update transactions matching a rule and lacking categorisation.

    Only transactions whose labels contain the rule pattern (case-insensitive)
    and whose ``category_id`` or ``subcategory_id`` is null are updated.

    Returns the number of rows updated.
    """

    pattern = rule.pattern.lower()
    updated = (
        session.query(Transaction)
        .filter(func.lower(Transaction.label).contains(pattern))
        .filter(or_(Transaction.category_id == None, Transaction.subcategory_id == None))
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

    transactions, csv_duplicates, csv_errors, account_info = parse_csv(content)
    errors = list(csv_errors)

    session = SessionLocal()
    imported = 0
    duplicates = list(csv_duplicates)

    account = session.query(BankAccount).filter_by(
        account_type=account_info.get('account_type'),
        number=account_info.get('number'),
        export_date=account_info.get('export_date'),
    ).first()
    if not account:
        account = BankAccount(
            account_type=account_info.get('account_type'),
            number=account_info.get('number'),
            export_date=account_info.get('export_date'),
        )
        session.add(account)
        session.commit()

    # Load rules once for auto-categorisation
    rules = session.query(Rule).all()

    try:
        for t in transactions:
            exists = session.query(Transaction).filter_by(
                date=t['date'], label=t['label'], amount=t['amount'], bank_account_id=account.id
            ).first()
            if exists:
                duplicates.append({
                    'date': t['date'].isoformat(),
                    'type': t['type'],
                    'payment_method': t['payment_method'],
                    'label': t['label'],
                    'amount': t['amount'],
                    'account_id': account.id,
                })
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
                bank_account_id=account.id,
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

    response = {
        'imported': imported,
        'account': {
            'id': account.id,
            'account_type': account.account_type,
            'number': account.number,
            'export_date': account.export_date.isoformat() if account.export_date else None,
        }
    }
    if duplicates:
        response['duplicates'] = [
            {
                **d,
                'date': d['date'].isoformat() if hasattr(d['date'], 'isoformat') else d['date'],
            }
            for d in duplicates
        ]
    if errors:
        response['errors'] = errors
        return jsonify(response), 400
    return jsonify(response)


@app.route('/import/confirm', methods=['POST'])
@login_required
def confirm_import():
    """Insert transactions that were previously flagged as duplicates."""
    data = request.get_json() or {}
    rows = data.get('transactions', [])
    account_id = data.get('account_id')

    session = SessionLocal()
    imported = 0
    errors = []

    rules = session.query(Rule).all()

    try:
        for t in rows:
            try:
                date = datetime.strptime(t['date'], '%Y-%m-%d').date()
            except (KeyError, ValueError):
                errors.append('Date invalide')
                continue

            exists = session.query(Transaction).filter_by(
                date=date, label=t.get('label'), amount=t.get('amount'), bank_account_id=account_id
            ).first()
            if exists:
                continue

            category_id = None
            subcategory_id = None
            for r in rules:
                if r.pattern.lower() in t.get('label', '').lower():
                    category_id = r.category_id
                    subcategory_id = r.subcategory_id
                    break

            session.add(Transaction(
                date=date,
                tx_type=t.get('type', ''),
                payment_method=t.get('payment_method', ''),
                label=t.get('label', ''),
                amount=t.get('amount'),
                bank_account_id=account_id,
                category_id=category_id,
                subcategory_id=subcategory_id,
                reconciled=False,
                to_analyze=True,
            ))
            imported += 1
        session.commit()
    except Exception as e:
        session.rollback()
        session.close()
        return jsonify({'error': str(e)}), 400
    finally:
        session.close()

    response = {'imported': imported}
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

    account_id = request.args.get('account_id')
    if account_id:
        try:
            query = query.filter(Transaction.bank_account_id == int(account_id))
        except ValueError:
            pass

    category = request.args.get('category')
    if category:
        query = query.join(Category).filter(Category.name == category)

    tx_type = request.args.get('type')
    if tx_type:
        query = query.filter(Transaction.tx_type == tx_type)

    payment_method = request.args.get('payment_method')
    if payment_method:
        query = query.filter(Transaction.payment_method == payment_method)

    label = request.args.get('label')
    if label:
        query = query.filter(Transaction.label.contains(label))

    subcategory = request.args.get('subcategory')
    if subcategory:
        query = query.join(Subcategory).filter(Subcategory.name == subcategory)

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
            'account_id': t.bank_account_id,
            'favorite': t.favorite,
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
            'account_id': tx.bank_account_id,
            'favorite': tx.favorite,
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
    if 'favorite' in data:
        tx.favorite = bool(data['favorite'])
    if 'reconciled' in data:
        tx.reconciled = bool(data['reconciled'])
    if 'to_analyze' in data:
        tx.to_analyze = bool(data['to_analyze'])
    session.commit()
    result = {
        'id': tx.id,
        'favorite': tx.favorite,
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
    query = session.query(
        func.strftime('%Y-%m', Transaction.date).label('month'),
        func.sum(Transaction.amount).label('total')
    )

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

    data = query.group_by('month').order_by('month').all()
    session.close()
    return jsonify([{ 'month': m, 'total': t } for m, t in data])


@app.route('/stats/categories')
@login_required
def stats_categories():
    session = SessionLocal()
    query = session.query(
        Category.name,
        Category.color,
        func.sum(func.case([(Transaction.amount >= 0, Transaction.amount)], else_=0)).label('positive'),
        func.sum(func.case([(Transaction.amount < 0, Transaction.amount)], else_=0)).label('negative')
    ).join(Transaction, Transaction.category_id == Category.id)

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

    data = query.group_by(Category.id).all()
    session.close()
    result = []
    for name, color, pos, neg in data:
        result.append({
            'name': name,
            'color': color,
            'positive': pos or 0,
            'negative': neg or 0,
        })
    return jsonify(result)


@app.route('/stats/sankey')
@login_required
def stats_sankey():
    """Aggregate amounts from categories to subcategories for Sankey chart."""
    session = SessionLocal()
    query = session.query(
        Category.name.label('source'),
        Subcategory.name.label('target'),
        func.sum(Transaction.amount).label('total')
    ).join(Subcategory, Subcategory.category_id == Category.id)
    query = query.join(Transaction, Transaction.subcategory_id == Subcategory.id)

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

    data = query.group_by(Category.id, Subcategory.id).all()
    session.close()
    result = [
        {
            'source': src,
            'target': tgt,
            'value': abs(total) if total is not None else 0,
        }
        for src, tgt, total in data
    ]
    return jsonify(result)


@app.route('/dashboard')
@login_required
def dashboard():
    session = SessionLocal()
    fav_count = session.query(func.count(Transaction.id)).filter(Transaction.favorite == True).scalar() or 0
    cutoff = datetime.now().date() - timedelta(days=30)
    recent_total = session.query(func.sum(Transaction.amount)).filter(Transaction.date >= cutoff).scalar() or 0
    session.close()
    return jsonify({'favorite_count': fav_count, 'recent_total': recent_total})


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
                    'favorite': c.favorite,
                    'subcategories': [
                        {
                            'id': s.id,
                            'name': s.name,
                            'color': s.color,
                            'favorite': s.favorite,
                        }
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
            'favorite': category.favorite,
            'subcategories': [
                {
                    'id': s.id,
                    'name': s.name,
                    'color': s.color,
                    'favorite': s.favorite,
                }
                for s in category.subcategories
            ],
        }
        session.close()
        return jsonify(result)

    if request.method == 'POST':
        data = request.get_json() or {}
        name = data.get('name')
        color = data.get('color', '')
        favorite = bool(data.get('favorite', False))
        if not name:
            session.close()
            return jsonify({'error': 'Missing name'}), 400
        category = Category(name=name, color=color, favorite=favorite)
        session.add(category)
        session.commit()
        result = {'id': category.id, 'name': category.name, 'color': category.color, 'favorite': category.favorite}
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
        if 'favorite' in data:
            category.favorite = bool(data['favorite'])
        if name is not None:
            category.name = name
        if color is not None:
            category.color = color
        session.commit()
        result = {'id': category.id, 'name': category.name, 'color': category.color, 'favorite': category.favorite}
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
                    'favorite': s.favorite,
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
            'favorite': sub.favorite,
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
        favorite = bool(data.get('favorite', False))
        if not name or not category_id:
            session.close()
            return jsonify({'error': 'Missing fields'}), 400

        if not color:
            cat = session.query(Category).get(int(category_id))
            color = cat.color if cat else ''

        sub = Subcategory(name=name, category_id=int(category_id), color=color, favorite=favorite)

        session.add(sub)
        session.commit()
        result = {
            'id': sub.id,
            'name': sub.name,
            'color': sub.color,
            'favorite': sub.favorite,
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
        if 'favorite' in data:
            sub.favorite = bool(data['favorite'])

        if 'color' in data:
            new_color = data['color']
        else:
            new_color = None

        if new_color is None or new_color == '':
            cat = session.query(Category).get(sub.category_id)
            new_color = cat.color if cat else ''

        if new_color is not None:
            sub.color = new_color
        session.commit()
        result = {
            'id': sub.id,
            'name': sub.name,
            'color': sub.color,
            'favorite': sub.favorite,
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
        updated = apply_rule_to_transactions(session, rule)
        result = {
            'id': rule.id,
            'pattern': rule.pattern,
            'category_id': rule.category_id,
            'subcategory_id': rule.subcategory_id,
            'category': rule.category.name if rule.category else None,
            'subcategory': rule.subcategory.name if rule.subcategory else None,
            'updated': updated,
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
        updated = apply_rule_to_transactions(session, rule)
        result = {
            'id': rule.id,
            'pattern': rule.pattern,
            'category_id': rule.category_id,
            'subcategory_id': rule.subcategory_id,
            'category': rule.category.name if rule.category else None,
            'subcategory': rule.subcategory.name if rule.subcategory else None,
            'updated': updated,
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
