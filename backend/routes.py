from flask import request, jsonify
import logging
from flask_login import login_required
from sqlalchemy import func, or_, and_, case
from datetime import datetime, timedelta  # use standard datetime
import numpy as np
import re
from difflib import SequenceMatcher

from .app import app, load_categories_json, save_categories_json
from . import models
from .csv_utils import parse_csv, apply_rule_to_transactions

logger = logging.getLogger(__name__)

# Default thresholds for recurring transaction detection
SIMILARITY_THRESHOLD = 0.8  # Minimum fuzzy label similarity
AMOUNT_TOLERANCE = 0.3      # Allowed deviation (\u00b130%) around the average


def _parse_account_ids():
    """Return a list of account IDs from the ``account_ids`` query parameter."""
    ids_param = request.args.get('account_ids')
    if not ids_param:
        return []
    ids = []
    for part in ids_param.split(','):
        try:
            ids.append(int(part))
        except ValueError:
            continue
    return ids


@app.route('/')
def index():
    return app.send_static_file('index.html')


@app.route('/accounts', methods=['GET', 'POST'])
@login_required
def accounts():
    """Return all bank accounts or create a new one."""
    session = models.SessionLocal()
    if request.method == 'POST':
        data = request.get_json() or {}
        acc = models.BankAccount(
            name=data.get('name', ''),
            account_type=data.get('account_type'),
            number=data.get('number'),
        )
        session.add(acc)
        session.commit()
        logger.info("Created account %s (id=%s)", acc.name, acc.id)
        result = {
            'id': acc.id,
            'name': acc.name,
            'account_type': acc.account_type,
            'number': acc.number,
            'export_date': acc.export_date.isoformat() if acc.export_date else None,
            'initial_balance': acc.initial_balance,
            'balance_date': acc.balance_date.isoformat() if acc.balance_date else None,
        }
        session.close()
        return jsonify(result), 201

    data = [
        {
            'id': a.id,
            'name': a.name,
            'account_type': a.account_type,
            'number': a.number,
            'export_date': a.export_date.isoformat() if a.export_date else None,
            'initial_balance': a.initial_balance,
            'balance_date': a.balance_date.isoformat() if a.balance_date else None,
        }
        for a in session.query(models.BankAccount).all()
    ]
    session.close()
    return jsonify(data)


@app.route('/accounts/<int:account_id>/balance', methods=['GET', 'PUT'])
@login_required
def account_balance(account_id):
    """Retrieve or update an account's initial balance information."""
    session = models.SessionLocal()
    acc = session.query(models.BankAccount).get(account_id)
    if not acc:
        session.close()
        return jsonify({'error': 'Not found'}), 404

    if request.method == 'GET':
        result = {
            'id': acc.id,
            'initial_balance': acc.initial_balance,
            'balance_date': acc.balance_date.isoformat() if acc.balance_date else None,
        }
        session.close()
        return jsonify(result)

    data = request.get_json() or {}
    if 'initial_balance' in data:
        try:
            acc.initial_balance = float(data['initial_balance'])
        except (TypeError, ValueError):
            session.close()
            return jsonify({'error': 'invalid balance'}), 400
    if 'balance_date' in data:
        val = data['balance_date']
        if val:
            try:
                acc.balance_date = datetime.strptime(val, '%Y-%m-%d').date()
            except ValueError:
                session.close()
                return jsonify({'error': 'invalid balance'}), 400
        else:
            acc.balance_date = None
    session.commit()
    logger.info(
        "Updated balance for account %s: initial_balance=%s balance_date=%s",
        acc.id,
        acc.initial_balance,
        acc.balance_date,
    )
    result = {
        'id': acc.id,
        'initial_balance': acc.initial_balance,
        'balance_date': acc.balance_date.isoformat() if acc.balance_date else None,
    }
    session.close()
    return jsonify(result)


@app.route('/accounts/<int:account_id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
def account_detail(account_id):
    """Retrieve, update or delete a bank account."""
    session = models.SessionLocal()
    acc = session.query(models.BankAccount).get(account_id)
    if not acc:
        session.close()
        return jsonify({'error': 'Not found'}), 404

    if request.method == 'GET':
        result = {
            'id': acc.id,
            'name': acc.name,
            'account_type': acc.account_type,
            'number': acc.number,
            'export_date': acc.export_date.isoformat() if acc.export_date else None,
            'initial_balance': acc.initial_balance,
            'balance_date': acc.balance_date.isoformat() if acc.balance_date else None,
        }
        session.close()
        return jsonify(result)

    if request.method == 'DELETE':
        session.delete(acc)
        session.commit()
        logger.info("Deleted account %s (id=%s)", acc.name, acc.id)
        session.close()
        return '', 204

    data = request.get_json() or {}
    if 'name' in data:
        acc.name = data['name'] or ''
    if 'account_type' in data:
        acc.account_type = data['account_type']
    if 'number' in data:
        acc.number = data['number']
    if 'export_date' in data:
        val = data['export_date']
        if val:
            try:
                acc.export_date = datetime.strptime(val, '%Y-%m-%d').date()
            except ValueError:
                pass
        else:
            acc.export_date = None
    session.commit()
    logger.info("Updated account %s (id=%s)", acc.name, acc.id)
    result = {
        'id': acc.id,
        'name': acc.name,
        'account_type': acc.account_type,
        'number': acc.number,
        'export_date': acc.export_date.isoformat() if acc.export_date else None,
        'initial_balance': acc.initial_balance,
        'balance_date': acc.balance_date.isoformat() if acc.balance_date else None,
    }
    session.close()
    return jsonify(result)


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

    session = models.SessionLocal()
    imported = 0
    duplicates = list(csv_duplicates)

    account = session.query(models.BankAccount).filter_by(
        account_type=account_info.get('account_type'),
        number=account_info.get('number'),
    ).first()
    if not account:
        account = models.BankAccount(
            account_type=account_info.get('account_type'),
            number=account_info.get('number'),
            export_date=account_info.get('export_date'),
            name=account_info.get('name', ''),
        )
        if account_info.get('initial_balance') is not None:
            account.initial_balance = account_info['initial_balance']
            account.balance_date = account_info.get('balance_date')
        session.add(account)
        session.commit()
    else:
        account.export_date = account_info.get('export_date')
        if account_info.get('name'):
            account.name = account_info['name']
        session.commit()

    rules = session.query(models.Rule).all()

    try:
        for t in transactions:
            exists = session.query(models.Transaction).filter_by(
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

            session.add(models.Transaction(
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
            'name': account.name,
            'account_type': account.account_type,
            'number': account.number,
            'export_date': account.export_date.isoformat() if account.export_date else None,
            'initial_balance': account.initial_balance,
            'balance_date': account.balance_date.isoformat() if account.balance_date else None,
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
        logger.info(
            "CSV import for account %s had errors: %s", account.id, errors
        )
        return jsonify(response), 400
    logger.info(
        "CSV import for account %s: imported=%s duplicates=%s", account.id, imported, len(duplicates)
    )
    return jsonify(response)


@app.route('/import/confirm', methods=['POST'])
@login_required
def confirm_import():
    """Insert transactions that were previously flagged as duplicates."""
    data = request.get_json() or {}
    rows = data.get('transactions', [])
    account_id = data.get('account_id')

    session = models.SessionLocal()
    imported = 0
    errors = []

    rules = session.query(models.Rule).all()

    try:
        for t in rows:
            try:
                date = datetime.strptime(t['date'], '%Y-%m-%d').date()
            except (KeyError, ValueError):
                errors.append('Date invalide')
                continue

            exists = session.query(models.Transaction).filter_by(
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

            session.add(models.Transaction(
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
        logger.info(
            "CSV confirm import for account %s had errors: %s", account_id, errors
        )
        return jsonify(response), 400
    logger.info(
        "CSV confirm import for account %s: imported=%s", account_id, imported
    )
    return jsonify(response)


@app.route('/transactions')
@login_required
def list_transactions():
    """Return transactions with optional filtering and sorting."""
    session = models.SessionLocal()
    query = session.query(models.Transaction)

    if request.args.get('account_none') in ('true', '1', 'yes'):
        query = query.filter(models.Transaction.bank_account_id.is_(None))
    else:
        account_id = request.args.get('account_id')
        if account_id:
            try:
                query = query.filter(models.Transaction.bank_account_id == int(account_id))
            except ValueError:
                pass

    category_id = request.args.get('category_id')
    if category_id:
        try:
            query = query.filter(models.Transaction.category_id == int(category_id))
        except ValueError:
            pass

    if request.args.get('category_none') in ('true', '1', 'yes'):
        query = query.filter(models.Transaction.category_id.is_(None))

    tx_type = request.args.get('type')
    if tx_type:
        query = query.filter(models.Transaction.tx_type == tx_type)

    payment_method = request.args.get('payment_method')
    if payment_method:
        query = query.filter(models.Transaction.payment_method == payment_method)

    label = request.args.get('label')
    if label:
        query = query.filter(models.Transaction.label.contains(label))

    subcategory = request.args.get('subcategory')
    if subcategory:
        query = query.join(models.Subcategory).filter(models.Subcategory.name == subcategory)

    start_date = request.args.get('start_date')
    if start_date:
        try:
            date = datetime.strptime(start_date, '%Y-%m-%d').date()
            query = query.filter(models.Transaction.date >= date)
        except ValueError:
            pass

    end_date = request.args.get('end_date')
    if end_date:
        try:
            date = datetime.strptime(end_date, '%Y-%m-%d').date()
            query = query.filter(models.Transaction.date <= date)
        except ValueError:
            pass

    min_amount = request.args.get('min_amount')
    if min_amount:
        try:
            query = query.filter(models.Transaction.amount >= float(min_amount))
        except ValueError:
            pass

    max_amount = request.args.get('max_amount')
    if max_amount:
        try:
            query = query.filter(models.Transaction.amount <= float(max_amount))
        except ValueError:
            pass

    favorite = request.args.get('favorite')
    if favorite in ('true', 'false'):
        query = query.filter(models.Transaction.favorite == (favorite == 'true'))

    reconciled = request.args.get('reconciled')
    if reconciled in ('true', 'false'):
        query = query.filter(models.Transaction.reconciled == (reconciled == 'true'))

    to_analyze = request.args.get('to_analyze')
    if to_analyze in ('true', 'false'):
        query = query.filter(models.Transaction.to_analyze == (to_analyze == 'true'))

    sort_by = request.args.get('sort_by', 'date')
    sort_column = getattr(models.Transaction, sort_by, models.Transaction.date)
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
    session = models.SessionLocal()
    tx = session.query(models.Transaction).get(tx_id)
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
        cat_id = data['category_id'] or None
        if cat_id is not None:
            exists = session.query(models.Category).get(cat_id)
            if not exists:
                session.close()
                return jsonify({'error': 'invalid category'}), 400
        tx.category_id = cat_id
    if 'subcategory_id' in data:
        sub_id = data['subcategory_id'] or None
        if sub_id is not None:
            exists = session.query(models.Subcategory).get(sub_id)
            if not exists:
                session.close()
                return jsonify({'error': 'invalid category'}), 400
        tx.subcategory_id = sub_id
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


@app.route('/transactions/unassigned', methods=['DELETE'])
@login_required
def delete_unassigned_transactions():
    """Delete all transactions without an associated bank account."""
    session = models.SessionLocal()
    count = session.query(models.Transaction).filter(
        models.Transaction.bank_account_id.is_(None)
    ).delete(synchronize_session=False)
    session.commit()
    session.close()
    logger.info("Deleted %s unassigned transactions", count)
    return jsonify({'deleted': count})


@app.route('/transactions/unassigned/count')
@login_required
def count_unassigned_transactions():
    """Return the number of transactions without an associated bank account."""
    session = models.SessionLocal()
    count = session.query(func.count(models.Transaction.id)).filter(
        models.Transaction.bank_account_id.is_(None)
    ).scalar() or 0
    session.close()
    return jsonify({'count': count})


@app.route('/stats')
@login_required
def stats():
    session = models.SessionLocal()
    query = session.query(
        func.strftime('%Y-%m', models.Transaction.date).label('month'),
        func.sum(models.Transaction.amount).label('total')
    )

    start_date = request.args.get('start_date')
    if start_date:
        try:
            date = datetime.strptime(start_date, '%Y-%m-%d').date()
            query = query.filter(models.Transaction.date >= date)
        except ValueError:
            pass

    end_date = request.args.get('end_date')
    if end_date:
        try:
            date = datetime.strptime(end_date, '%Y-%m-%d').date()
            query = query.filter(models.Transaction.date <= date)
        except ValueError:
            pass

    data = query.group_by('month').all()
    session.close()
    result = [
        {
            'month': month,
            'total': total or 0,
        }
        for month, total in data
    ]
    return jsonify(result)


@app.route('/stats/categories')
@login_required
def stats_by_category():
    session = models.SessionLocal()
    query = session.query(
        models.Category.name,
        models.Category.color,
        func.sum(
            case((models.Transaction.amount > 0, models.Transaction.amount), else_=0)
        ).label('positive'),
        func.sum(
            case((models.Transaction.amount < 0, func.abs(models.Transaction.amount)), else_=0)
        ).label('negative')
    ).join(models.Transaction, models.Transaction.category_id == models.Category.id)

    start_date = request.args.get('start_date')
    if start_date:
        try:
            date = datetime.strptime(start_date, '%Y-%m-%d').date()
            query = query.filter(models.Transaction.date >= date)
        except ValueError:
            pass

    end_date = request.args.get('end_date')
    if end_date:
        try:
            date = datetime.strptime(end_date, '%Y-%m-%d').date()
            query = query.filter(models.Transaction.date <= date)
        except ValueError:
            pass

    data = query.group_by(models.Category.id).all()
    session.close()
    result = [
        {
            'name': name,
            'color': color,
            'positive': pos or 0,
            'negative': neg or 0,
        }
        for name, color, pos, neg in data
    ]
    return jsonify(result)


@app.route('/stats/sankey')
@login_required
def stats_sankey():
    """Aggregate positive and negative amounts separately for Sankey chart."""
    session = models.SessionLocal()
    query = session.query(
        models.Category.name.label('category'),
        models.Subcategory.name.label('subcategory'),
        func.sum(
            case((models.Transaction.amount > 0, models.Transaction.amount), else_=0)
        ).label('positive'),
        func.sum(
            case((models.Transaction.amount < 0, func.abs(models.Transaction.amount)), else_=0)
        ).label('negative'),
    ).join(models.Subcategory, models.Subcategory.category_id == models.Category.id)
    query = query.join(models.Transaction, models.Transaction.subcategory_id == models.Subcategory.id)

    start_date = request.args.get('start_date')
    if start_date:
        try:
            date = datetime.strptime(start_date, '%Y-%m-%d').date()
            query = query.filter(models.Transaction.date >= date)
        except ValueError:
            pass

    end_date = request.args.get('end_date')
    if end_date:
        try:
            date = datetime.strptime(end_date, '%Y-%m-%d').date()
            query = query.filter(models.Transaction.date <= date)
        except ValueError:
            pass

    data = query.group_by(models.Category.id, models.Subcategory.id).all()
    session.close()
    result = []
    for cat, sub, pos, neg in data:
        if pos:
            result.append({
                'source': cat,
                'target': sub,
                'value': pos,
                'sign': 1,
            })
        if neg:
            result.append({
                'source': cat,
                'target': sub,
                'value': neg,
                'sign': -1,
            })
    return jsonify(result)


@app.route('/stats/recurrents')
@login_required
def stats_recurrents():
    """Return recurring transactions for the last six months."""
    month = request.args.get('month')
    if month:
        try:
            current_first = datetime.strptime(month + '-01', '%Y-%m-%d').date()
        except ValueError:
            current_first = datetime.now().date().replace(day=1)
    else:
        current_first = datetime.now().date().replace(day=1)

    start = _shift_month(current_first, -5)
    end = _shift_month(current_first, 1) - timedelta(days=1)

    session = models.SessionLocal()
    recs = compute_recurrents(session, start, end)
    if not recs:
        session.close()
        return jsonify({'message': 'Aucune transaction récurrente trouvée selon les critères de similarité ou de montant.'})

    result = []
    for rec in recs:
        txs = rec['transactions']
        cat = rec['category']
        avg_amount = rec['average_amount']
        last_date = rec['last_date']
        
        if len(txs) > 1:
            diffs = [
                (txs[i].date - txs[i - 1].date).days for i in range(1, len(txs))
            ]
            avg_diff = sum(diffs) / len(diffs)
        else:
            avg_diff = 0

        def _freq(days):
            if days < 10:
                return 'weekly'
            if days < 20:
                return 'biweekly'
            if days < 40:
                return 'monthly'
            if days < 70:
                return 'bimonthly'
            if days < 100:
                return 'quarterly'
            if days < 200:
                return 'semiannual'
            if days < 400:
                return 'annual'
            return 'unknown'

        item = {
            'day': rec['day'],
            'category': {
                'id': cat.id if cat else None,
                'name': cat.name if cat else None,
                'color': cat.color if cat else ''
            },
            'average_amount': avg_amount,
            'last_date': last_date.isoformat(),
            'frequency': _freq(avg_diff) if avg_diff else None,
            'transactions': [
                {
                    'date': t.date.isoformat(),
                    'label': t.label,
                    'amount': t.amount,
                }
                for t in txs
            ]
        }
        result.append(item)

    result.sort(key=lambda r: r['day'])
    session.close()
    return jsonify(result)


@app.route('/stats/recurrents/categories')
@login_required
def stats_recurrents_categories():
    """Return negative recurrent totals aggregated by category."""
    month = request.args.get('month')
    if month:
        try:
            current_first = datetime.strptime(month + '-01', '%Y-%m-%d').date()
        except ValueError:
            current_first = datetime.now().date().replace(day=1)
    else:
        current_first = datetime.now().date().replace(day=1)

    start = _shift_month(current_first, -5)
    end = _shift_month(current_first, 1) - timedelta(days=1)

    session = models.SessionLocal()
    recs = compute_recurrents(session, start, end)
    totals = aggregate_recurrents_by_category(recs)
    session.close()
    result = [
        {'category': name, 'total': total}
        for name, total in sorted(totals.items())
    ]
    return jsonify(result)


@app.route('/stats/recurrents/summary')
@login_required
def stats_recurrents_summary():
    """Return monthly totals and recurrent expense summary."""
    month = request.args.get('month')
    if month:
        try:
            current_first = datetime.strptime(month + '-01', '%Y-%m-%d').date()
        except ValueError:
            current_first = datetime.now().date().replace(day=1)
    else:
        current_first = datetime.now().date().replace(day=1)

    start = current_first
    end = _shift_month(current_first, 1) - timedelta(days=1)

    session = models.SessionLocal()

    positive = (
        session.query(func.sum(models.Transaction.amount))
        .filter(models.Transaction.amount > 0)
        .filter(models.Transaction.date >= start)
        .filter(models.Transaction.date <= end)
        .scalar()
        or 0
    )
    negative = (
        session.query(func.sum(func.abs(models.Transaction.amount)))
        .filter(models.Transaction.amount < 0)
        .filter(models.Transaction.date >= start)
        .filter(models.Transaction.date <= end)
        .scalar()
        or 0
    )

    balance = sum(a.initial_balance or 0 for a in session.query(models.BankAccount).all())
    balance += (
        session.query(func.sum(models.Transaction.amount))
        .filter(models.Transaction.date <= end)
        .scalar()
        or 0
    )

    rec_ref = datetime.now().date().replace(day=1)
    rec_start = _shift_month(rec_ref, -5)
    rec_end = _shift_month(rec_ref, 1) - timedelta(days=1)
    recs = compute_recurrents(session, rec_start, rec_end)
    recurrent_total = sum(
        abs(r['average_amount']) for r in recs if r['average_amount'] < 0
    )

    session.close()
    return jsonify({
        'positive': positive,
        'negative': negative,
        'balance': balance,
        'recurrent': recurrent_total,
    })


def _normalize_label(label):
    """Return a simplified label for recurrence grouping.

    The preprocessing removes any digit characters, lowercases the text and
    strips all spaces and punctuation so that labels differing only by numbers
    or formatting still match.
    """

    s = re.sub(r"\d+", "", label.lower())
    # Remove spaces and non alphanumeric characters
    s = re.sub(r"[^a-zA-Z]+", "", s)
    return s


def _shift_month(date, offset):
    """Return the first day of the month shifted by ``offset`` months."""
    y = date.year + (date.month - 1 + offset) // 12
    m = (date.month - 1 + offset) % 12 + 1
    return date.replace(year=y, month=m, day=1)


def compute_recurrents(
    session,
    start,
    end,
    *,
    similarity_threshold=SIMILARITY_THRESHOLD,
    amount_tolerance=AMOUNT_TOLERANCE,
):
    """Return recurring transactions grouped between ``start`` and ``end``.

    ``similarity_threshold`` and ``amount_tolerance`` are exposed as keyword
    arguments so that the detection parameters can easily be tuned. Labels are
    normalized via :func:`_normalize_label` and grouped using fuzzy matching
    when the similarity ratio reaches ``similarity_threshold``. Groups with
    amounts that deviate by more than ``amount_tolerance`` of the group's
    average are discarded.  The former rule restricting the day-of-month spread
    was removed to allow for more flexible detection.
    """
    rows = (
        session.query(models.Transaction)
        .filter(models.Transaction.date >= start)
        .filter(models.Transaction.date <= end)
        .all()
    )

    groups = {}
    for tx in rows:
        label = _normalize_label(tx.label)
        found = None
        for key in groups:
            if SequenceMatcher(None, label, key).ratio() >= similarity_threshold:
                found = key
                break
        if not found:
            found = label
            groups[found] = []
        groups[found].append(tx)

    result = []
    for label, txs in groups.items():
        reasons = []
        if len(txs) < 2:
            reasons.append("moins de 2 transactions")
        avg = sum(abs(t.amount) for t in txs) / len(txs)
        if not all(
            (1 - amount_tolerance) * avg <= abs(t.amount) <= (1 + amount_tolerance) * avg
            for t in txs
        ):
            reasons.append(
                f"montants hors ±{int(amount_tolerance * 100)}%"
            )
        if reasons:
            logger.debug("Group '%s' rejected: %s", label, ", ".join(reasons))
            continue
        # Previous versions limited the difference in ``date.day`` values
        # between months.  This constraint has been removed for a more
        # permissive detection of recurring transactions.

        txs.sort(key=lambda t: t.date)
        result.append(
            {
                'day': txs[0].date.day,
                'category': txs[0].category,
                'average_amount': sum(t.amount for t in txs) / len(txs),
                'last_date': txs[-1].date,
                'transactions': txs,
            }
        )

    result.sort(key=lambda r: r['day'])

    if not result:
        logger.info(
            "No recurring transactions found between %s and %s", start, end
        )

    return result


def aggregate_recurrents_by_category(recs):
    """Return negative recurrent totals aggregated by category name."""
    totals = {}
    for rec in recs:
        avg = rec['average_amount']
        if avg < 0:
            name = rec['category'].name if rec['category'] else 'Inconnu'
            totals[name] = totals.get(name, 0) + abs(avg)
    return totals


def compute_dashboard_averages(session, months=3, favorites_only=False):
    """Return per-category averages and income average.

    When ``favorites_only`` is ``True``, only transactions marked as favorite
    contribute to the computations. The income average is computed over the
    specified number of months. Per-category averages consider every
    transaction regardless of date unless ``favorites_only`` is enabled.
    
    """
    query = session.query(
        models.Transaction.category_id,
        func.avg(func.abs(models.Transaction.amount)),
    ).filter(models.Transaction.category_id.isnot(None))
    if favorites_only:
        query = query.filter(models.Transaction.favorite.is_(True))
    cat_avgs = dict(query.group_by(models.Transaction.category_id).all())

    today = datetime.now().date()
    curr_first = today.replace(day=1)
    months_list = []
    for i in range(1, months + 1):
        start = _shift_month(curr_first, -i)
        end = _shift_month(curr_first, -(i - 1)) - timedelta(days=1)
        income_query = (
            session.query(func.sum(models.Transaction.amount))
            .filter(models.Transaction.amount > 0)
            .filter(models.Transaction.date >= start)
            .filter(models.Transaction.date <= end)
        )
        if favorites_only:
            income_query = income_query.filter(models.Transaction.favorite.is_(True))
        total = income_query.scalar() or 0
        months_list.append(total)
    income_avg = sum(months_list) / len(months_list) if months_list else 0
    return cat_avgs, income_avg


def compute_category_monthly_averages(session, months=12, account_ids=None):
    """Return a mapping of category name to average monthly amount.

    The computation spans the ``months`` prior to the current month and
    includes months without transactions as zero.
    """
    today = datetime.now().date()
    current_start = today.replace(day=1)
    start = _shift_month(current_start, -months)

    join_cond = and_(
        models.Transaction.category_id == models.Category.id,
        models.Transaction.date >= start,
        models.Transaction.date < current_start,
        models.Transaction.to_analyze.is_(True),
    )
    if account_ids:
        join_cond = and_(join_cond, models.Transaction.bank_account_id.in_(account_ids))

    data = (
        session.query(
            models.Category.name,
            func.sum(models.Transaction.amount),
        )
        .select_from(models.Category)
        .outerjoin(models.Transaction, join_cond)
        .group_by(models.Category.name)
        .all()
    )

    result = {
        (name or "Inconnu"): (total or 0) / months
        for name, total in data
    }

    return result


def compute_category_forecast(session, months=12, forecast=12, account_ids=None):
    """Return per-category forecast for the next ``forecast`` months.

    A simple linear regression is fitted on the totals of the past ``months``
    months for each category. Months without transactions are considered to
    have a total of zero.
    """
    today = datetime.now().date()
    current_start = today.replace(day=1)
    start = _shift_month(current_start, -months)

    query = session.query(
        func.strftime('%Y-%m', models.Transaction.date).label('month'),
        models.Category.name,
        func.sum(models.Transaction.amount),
    ).outerjoin(models.Category, models.Transaction.category_id == models.Category.id)
    if account_ids:
        query = query.filter(models.Transaction.bank_account_id.in_(account_ids))
    rows = (
        query.filter(models.Transaction.date >= start)
        .filter(models.Transaction.date < current_start)
        .filter(models.Transaction.to_analyze.is_(True))
        .group_by('month', models.Category.name)
        .all()
    )

    hist_months = [_shift_month(start, i).strftime('%Y-%m') for i in range(months)]
    data = {}
    for month, cat, total in rows:
        cat = cat or 'Inconnu'
        data.setdefault(cat, {})[month] = total or 0

    future_months = [
        _shift_month(current_start, i).strftime('%Y-%m') for i in range(forecast)
    ]

    x = np.arange(months)
    result_rows = []
    for cat in sorted(data.keys()):
        y = [data[cat].get(m, 0) for m in hist_months]
        if y and max(y) == min(y):
            preds = [float(y[0])] * forecast
        elif y:
            slope, intercept = np.polyfit(x, y, 1)
            preds = [float(intercept + slope * (months + i)) for i in range(forecast)]
        else:
            preds = [0.0] * forecast
        result_rows.append({'category': cat, 'values': preds})

    return {
        'period': f"{future_months[0]} to {future_months[-1]}",
        'months': future_months,
        'rows': result_rows,
    }


def compute_account_balance(session, account, date=None):
    """Return the balance of ``account`` up to ``date``.

    The account's ``initial_balance`` is considered to be the balance on
    ``account.balance_date`` when set. Transactions prior to that date are
    ignored when computing the running balance. If a ``date`` before
    ``balance_date`` is provided, the function subtracts transactions between
    the given date and ``balance_date``.
    """

    base = account.initial_balance or 0
    if account.balance_date:
        if date is None or date >= account.balance_date:
            q = session.query(func.sum(models.Transaction.amount)).filter(
                models.Transaction.bank_account_id == account.id,
                models.Transaction.date > account.balance_date,
            )
            if date:
                q = q.filter(models.Transaction.date <= date)
            return base + (q.scalar() or 0)
        else:
            q = session.query(func.sum(models.Transaction.amount)).filter(
                models.Transaction.bank_account_id == account.id,
                models.Transaction.date > date,
                models.Transaction.date <= account.balance_date,
            )
            return base - (q.scalar() or 0)
    else:
        q = session.query(func.sum(models.Transaction.amount)).filter(
            models.Transaction.bank_account_id == account.id
        )
        if date:
            q = q.filter(models.Transaction.date <= date)
        return base + (q.scalar() or 0)


@app.route('/dashboard')
@login_required
def dashboard():
    session = models.SessionLocal()
    try:
        threshold = float(request.args.get('threshold', 1.5))
    except ValueError:
        threshold = 1.5
    fav_param = request.args.get('favorites_only')
    favorites_only = str(fav_param).lower() in ('true', '1', 'yes')
    filters = session.query(models.FavoriteFilter).all()
    conditions = [models.Transaction.favorite]
    for f in filters:
        subconds = []
        if f.pattern:
            subconds.append(func.lower(models.Transaction.label).contains(f.pattern.lower()))
        if f.category_id:
            subconds.append(models.Transaction.category_id == f.category_id)
        if f.subcategory_id:
            subconds.append(models.Transaction.subcategory_id == f.subcategory_id)
        if subconds:
            conditions.append(and_(*subconds))
    fav_count = session.query(func.count(models.Transaction.id)).filter(or_(*conditions)).scalar() or 0
    cutoff = datetime.now().date() - timedelta(days=30)
    recent_total = (
        session.query(func.sum(models.Transaction.amount))
        .filter(models.Transaction.date >= cutoff)
        .scalar()
        or 0
    )
    total = 0
    for acc in session.query(models.BankAccount).all():
        total += compute_account_balance(session, acc)

    months_param = request.args.get('months')
    try:
        months = int(months_param) if months_param else 3
    except ValueError:
        months = 3
    cat_avgs, income_avg = compute_dashboard_averages(
        session, months=months, favorites_only=favorites_only
    )

    alerts = []
    recent_query = (
        session.query(models.Transaction)
        .outerjoin(models.Category)
        .filter(models.Transaction.date >= cutoff)
    )
    if favorites_only:
        recent_query = recent_query.filter(models.Transaction.favorite.is_(True))
    recent_txs = recent_query.all()
    for tx in recent_txs:
        name = tx.category.name if tx.category else "Inconnu"
        cat_avg = cat_avgs.get(tx.category_id)
        if cat_avg and abs(tx.amount) > cat_avg * threshold:
            reason = "category_threshold"
        elif abs(tx.amount) > income_avg:
            reason = "income_threshold"
        else:
            continue
        alerts.append(
            {
                "date": tx.date.isoformat(),
                "label": tx.label,
                "amount": tx.amount,
                "category": name,
                "reason": reason,
            }
        )

    current_start = datetime.now().date().replace(day=1)
    groups = {}

    def add_item(cat_name, item):
        group = groups.setdefault(cat_name, {"category": cat_name, "items": []})
        group["items"].append(item)

    for f in filters:
        subconds = []
        if f.pattern:
            subconds.append(func.lower(models.Transaction.label).contains(f.pattern.lower()))
        if f.category_id:
            subconds.append(models.Transaction.category_id == f.category_id)
        if f.subcategory_id:
            subconds.append(models.Transaction.subcategory_id == f.subcategory_id)
        cond = and_(*subconds) if subconds else True
        current = (
            session.query(func.sum(models.Transaction.amount))
            .filter(cond)
            .filter(models.Transaction.date >= current_start)
            .scalar()
            or 0
        )
        prev = []
        for i in range(1, 7):
            start = _shift_month(current_start, -i)
            end = _shift_month(current_start, -(i - 1)) - timedelta(days=1)
            val = (
                session.query(func.sum(models.Transaction.amount))
                .filter(cond)
                .filter(models.Transaction.date >= start)
                .filter(models.Transaction.date <= end)
                .scalar()
                or 0
            )
            prev.append(val)
        avg6 = sum(prev) / 6 if prev else 0
        item = {
            'type': 'filter',
            'name': f.pattern or 'Filtre',
            'current_total': current,
            'six_month_avg': avg6,
        }
        if f.subcategory:
            cat_name = f.subcategory.category.name
        elif f.category:
            cat_name = f.category.name
        else:
            cat_name = 'Autre'
        add_item(cat_name, item)

    for c in session.query(models.Category).filter_by(favorite=True).all():
        cond = models.Transaction.category_id == c.id
        current = (
            session.query(func.sum(models.Transaction.amount))
            .filter(cond)
            .filter(models.Transaction.date >= current_start)
            .scalar()
            or 0
        )
        prev = []
        for i in range(1, 7):
            start = _shift_month(current_start, -i)
            end = _shift_month(current_start, -(i - 1)) - timedelta(days=1)
            val = (
                session.query(func.sum(models.Transaction.amount))
                .filter(cond)
                .filter(models.Transaction.date >= start)
                .filter(models.Transaction.date <= end)
                .scalar()
                or 0
            )
            prev.append(val)
        avg6 = sum(prev) / 6 if prev else 0
        item = {
            'type': 'category',
            'name': c.name,
            'current_total': current,
            'six_month_avg': avg6,
        }
        add_item(c.name, item)

    for s in session.query(models.Subcategory).filter_by(favorite=True).all():
        cond = models.Transaction.subcategory_id == s.id
        current = (
            session.query(func.sum(models.Transaction.amount))
            .filter(cond)
            .filter(models.Transaction.date >= current_start)
            .scalar()
            or 0
        )
        prev = []
        for i in range(1, 7):
            start = _shift_month(current_start, -i)
            end = _shift_month(current_start, -(i - 1)) - timedelta(days=1)
            val = (
                session.query(func.sum(models.Transaction.amount))
                .filter(cond)
                .filter(models.Transaction.date >= start)
                .filter(models.Transaction.date <= end)
                .scalar()
                or 0
            )
            prev.append(val)
        avg6 = sum(prev) / 6 if prev else 0
        item = {
            'type': 'subcategory',
            'name': s.name,
            'current_total': current,
            'six_month_avg': avg6,
        }
        add_item(s.category.name, item)

    session.close()
    summaries = list(groups.values())
    result = {
        'alerts': alerts,
        'favorite_count': fav_count,
        'recent_total': recent_total,
        'balance_total': total,
        'favorites_only': favorites_only,
        'favorite_summaries': summaries,
    }
    return jsonify(result)


@app.route('/projection')
@login_required
def projection():
    session = models.SessionLocal()
    six_months_ago = datetime.now().date() - timedelta(days=180)
    account_ids = _parse_account_ids()
    query = session.query(
        func.strftime('%Y-%m', models.Transaction.date).label('month'),
        func.sum(models.Transaction.amount)
    ).filter(models.Transaction.date >= six_months_ago)
    if account_ids:
        query = query.filter(models.Transaction.bank_account_id.in_(account_ids))
    data = (
        query.filter(models.Transaction.to_analyze.is_(True))
        .group_by('month')
        .order_by('month')
        .all()
    )
    session.close()
    result = [
        {
            'month': month,
            'total': total or 0,
        }
        for month, total in data
    ]
    return jsonify(result)


@app.route('/projection/categories')
@login_required
def projection_categories():
    session = models.SessionLocal()
    account_ids = _parse_account_ids()
    today = datetime.now().date()
    current_start = today.replace(day=1)
    start = _shift_month(current_start, -12)
    end = current_start
    query = session.query(
        func.strftime('%Y-%m', models.Transaction.date).label('month'),
        models.Category.name,
        func.sum(models.Transaction.amount),
    ).outerjoin(models.Category, models.Transaction.category_id == models.Category.id)
    if account_ids:
        query = query.filter(models.Transaction.bank_account_id.in_(account_ids))
    rows = (
        query.filter(models.Transaction.date >= start)
        .filter(models.Transaction.date < end)
        .filter(models.Transaction.to_analyze.is_(True))
        .group_by('month', models.Category.name)
        .all()
    )
    session.close()

    months = [
        _shift_month(start, i).strftime('%Y-%m')
        for i in range(12)
    ]

    data = {}
    for month, cat, total in rows:
        cat = cat or 'Inconnu'
        data.setdefault(cat, {})[month] = total or 0

    result_rows = [
        {
            'category': cat,
            'values': [data[cat].get(m, 0) for m in months],
        }
        for cat in sorted(data.keys())
    ]

    result = {
        'period': f"{months[0]} to {months[-1]}",
        'months': months,
        'rows': result_rows,
    }
    return jsonify(result)


@app.route('/projection/categories/average')
@login_required
def projection_categories_average():
    """Return per-category average monthly amount for the last 12 months."""
    session = models.SessionLocal()
    account_ids = _parse_account_ids()
    averages = compute_category_monthly_averages(session, months=12, account_ids=account_ids)
    session.close()
    result = [
        {'category': name, 'average': avg}
        for name, avg in sorted(averages.items())
    ]
    return jsonify(result)


@app.route('/projection/categories/forecast')
@login_required
def projection_categories_forecast():
    """Return per-category forecast for the next 12 months."""
    session = models.SessionLocal()
    account_ids = _parse_account_ids()
    result = compute_category_forecast(session, months=12, forecast=12, account_ids=account_ids)
    session.close()
    return jsonify(result)


@app.route('/balance')
@login_required
def balance():
    """Return account balance up to a specific date."""
    date_str = request.args.get('date')
    if date_str:
        try:
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'error': 'invalid date'}), 400
    else:
        date = None
    account_ids = _parse_account_ids()
    session = models.SessionLocal()
    query = session.query(models.BankAccount)
    if account_ids:
        query = query.filter(models.BankAccount.id.in_(account_ids))
    accounts = query.all()
    total = 0
    for acc in accounts:
        total += compute_account_balance(session, acc, date)
    session.close()
    return jsonify({'balance': float(total)})


@app.route('/category-options')
@login_required
def category_options():
    session = models.SessionLocal()
    categories = session.query(models.Category).all()

    result = []
    for cat in categories:
        sub_list = [
            {
                'id': sub.id,
                'name': sub.name,
                'color': sub.color,
                'favorite': sub.favorite,
            }
            for sub in cat.subcategories
        ]

        result.append(
            {
                'id': cat.id,
                'name': cat.name,
                'color': cat.color,
                'favorite': cat.favorite,
                'subcategories': sub_list,
            }
        )

    session.close()
    return jsonify(result)


@app.route('/categories', methods=['GET', 'POST'])
@app.route('/categories/<int:category_id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
def categories(category_id=None):
    session = models.SessionLocal()
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
                for c in session.query(models.Category).all()
            ]
            session.close()
            return jsonify(data)
        category = session.query(models.Category).get(category_id)
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
        category = models.Category(name=name, color=color, favorite=favorite)
        session.add(category)
        session.commit()
        logger.info("Created category %s (id=%s)", name, category.id)
        data_json = load_categories_json()
        if name not in data_json:
            data_json[name] = []
            save_categories_json(data_json)
        result = {'id': category.id, 'name': category.name, 'color': category.color, 'favorite': category.favorite}
        session.close()
        return jsonify(result), 201

    # PUT or DELETE
    category = session.query(models.Category).get(category_id)
    if not category:
        session.close()
        return jsonify({'error': 'Not found'}), 404

    if request.method == 'PUT':
        data = request.get_json() or {}
        old_name = category.name
        name = data.get('name')
        color = data.get('color')
        if 'favorite' in data:
            category.favorite = bool(data['favorite'])
        if name is not None:
            category.name = name
        if color is not None:
            category.color = color
            for sub in category.subcategories:
                sub.color = color
        session.commit()
        logger.info("Updated category %s (id=%s)", category.name, category.id)

        if name is not None and name != old_name:
            data_json = load_categories_json()
            lst = data_json.pop(old_name, [])
            data_json.setdefault(name, lst)
            save_categories_json(data_json)

        result = {'id': category.id, 'name': category.name, 'color': category.color, 'favorite': category.favorite}
        session.close()
        return jsonify(result)

    if category.subcategories or category.transactions:
        transactions = [
            {
                'id': t.id,
                'date': t.date.isoformat(),
                'label': t.label,
                'amount': t.amount,
            }
            for t in category.transactions
        ]
        subs = [
            {
                'id': s.id,
                'name': s.name,
            }
            for s in category.subcategories
        ]
        session.close()
        return (
            jsonify(
                {
                    'error': (
                        'Remove or reassign subcategories and transactions before '
                        'deleting this category'
                    ),
                    'transactions': transactions,
                    'subcategories': subs,
                }
            ),
            400,
        )

    cat_name = category.name
    session.delete(category)
    session.commit()
    logger.info("Deleted category %s (id=%s)", cat_name, category.id)

    data_json = load_categories_json()
    if cat_name in data_json:
        data_json.pop(cat_name, None)
        save_categories_json(data_json)

    session.close()
    return jsonify({'message': 'deleted'})


@app.route('/subcategories', methods=['GET', 'POST'])
@app.route('/subcategories/<int:sub_id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
def subcategories(sub_id=None):
    session = models.SessionLocal()
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
                for s in session.query(models.Subcategory).all()
            ]
            session.close()
            return jsonify(data)
        sub = session.query(models.Subcategory).get(sub_id)
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
            cat = session.query(models.Category).get(int(category_id))
            color = cat.color if cat else ''

        sub = models.Subcategory(name=name, category_id=int(category_id), color=color, favorite=favorite)

        session.add(sub)
        session.commit()
        logger.info(
            "Created subcategory %s (id=%s) under category %s",
            name,
            sub.id,
            category_id,
        )
        cat = session.query(models.Category).get(int(category_id)) if not locals().get('cat') else cat
        data_json = load_categories_json()
        if cat and cat.name:
            lst = data_json.setdefault(cat.name, [])
            if name not in lst:
                lst.append(name)
                save_categories_json(data_json)
        result = {
            'id': sub.id,
            'name': sub.name,
            'color': sub.color,
            'favorite': sub.favorite,
            'category_id': sub.category_id,
        }
        session.close()
        return jsonify(result), 201

    sub = session.query(models.Subcategory).get(sub_id)
    if not sub:
        session.close()
        return jsonify({'error': 'Not found'}), 404

    if request.method == 'PUT':
        data = request.get_json() or {}

        old_name = sub.name
        old_cat_name = sub.category.name if sub.category else None

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
            cat = session.query(models.Category).get(sub.category_id)
            new_color = cat.color if cat else ''

        if new_color is not None:
            sub.color = new_color
        session.commit()
        logger.info("Updated subcategory %s (id=%s)", sub.name, sub.id)

        new_name = sub.name
        new_cat = session.query(models.Category).get(sub.category_id)
        new_cat_name = new_cat.name if new_cat else None

        data_json = load_categories_json()
        modified = False
        if old_cat_name and old_name in data_json.get(old_cat_name, []):
            if old_cat_name != new_cat_name or old_name != new_name:
                try:
                    data_json[old_cat_name].remove(old_name)
                    modified = True
                except ValueError:
                    pass
        if new_cat_name:
            lst = data_json.setdefault(new_cat_name, [])
            if new_name not in lst:
                lst.append(new_name)
                modified = True
        if modified:
            save_categories_json(data_json)

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
    logger.info("Deleted subcategory %s (id=%s)", sub.name, sub.id)
    session.close()
    return jsonify({'message': 'deleted'})


@app.route('/rules', methods=['GET', 'POST'])
@app.route('/rules/<int:rule_id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
def rules(rule_id=None):
    session = models.SessionLocal()
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
                for r in session.query(models.Rule).all()
            ]
            session.close()
            return jsonify(data)
        rule = session.query(models.Rule).get(rule_id)
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
        pattern = (data.get('pattern') or '').strip()
        category_id = data.get('category_id')
        subcategory_id = data.get('subcategory_id')
        if not pattern:
            session.close()
            return jsonify({'error': 'Missing fields'}), 400
        rule = models.Rule(
            pattern=pattern,
            category_id=int(category_id) if category_id else None,
            subcategory_id=int(subcategory_id) if subcategory_id else None,
        )
        session.add(rule)
        session.commit()
        logger.info(
            "Created rule %s (id=%s) for category %s subcategory %s",
            pattern,
            rule.id,
            category_id,
            subcategory_id,
        )
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

    rule = session.query(models.Rule).get(rule_id)
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
        logger.info("Updated rule %s (id=%s)", rule.pattern, rule.id)
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
    logger.info("Deleted rule %s (id=%s)", rule.pattern, rule.id)
    session.close()
    return jsonify({'message': 'deleted'})


@app.route('/favorite_filters', methods=['GET', 'POST'])
@app.route('/favorite_filters/<int:filter_id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
def favorite_filters(filter_id=None):
    session = models.SessionLocal()
    if request.method == 'GET':
        if filter_id is None:
            data = [
                {
                    'id': f.id,
                    'pattern': f.pattern,
                    'category_id': f.category_id,
                    'subcategory_id': f.subcategory_id,
                    'category': f.category.name if f.category else None,
                    'subcategory': f.subcategory.name if f.subcategory else None,
                }
                for f in session.query(models.FavoriteFilter).all()
            ]
            session.close()
            return jsonify(data)
        fil = session.query(models.FavoriteFilter).get(filter_id)
        if not fil:
            session.close()
            return jsonify({'error': 'Not found'}), 404
        result = {
            'id': fil.id,
            'pattern': fil.pattern,
            'category_id': fil.category_id,
            'subcategory_id': fil.subcategory_id,
            'category': fil.category.name if fil.category else None,
            'subcategory': fil.subcategory.name if fil.subcategory else None,
        }
        session.close()
        return jsonify(result)

    if request.method == 'POST':
        data = request.get_json() or {}
        pattern = (data.get('pattern') or '').strip()
        category_id = data.get('category_id')
        subcategory_id = data.get('subcategory_id')
        if not pattern and not category_id and not subcategory_id:
            session.close()
            return jsonify({'error': 'Missing fields'}), 400
        fil = models.FavoriteFilter(
            pattern=pattern,
            category_id=int(category_id) if category_id else None,
            subcategory_id=int(subcategory_id) if subcategory_id else None,
        )
        session.add(fil)
        session.commit()
        logger.info(
            "Created favorite filter %s (id=%s)",
            pattern,
            fil.id,
        )
        result = {
            'id': fil.id,
            'pattern': fil.pattern,
            'category_id': fil.category_id,
            'subcategory_id': fil.subcategory_id,
            'category': fil.category.name if fil.category else None,
            'subcategory': fil.subcategory.name if fil.subcategory else None,
        }
        session.close()
        return jsonify(result), 201

    fil = session.query(models.FavoriteFilter).get(filter_id)
    if not fil:
        session.close()
        return jsonify({'error': 'Not found'}), 404

    if request.method == 'PUT':
        data = request.get_json() or {}
        if 'pattern' in data:
            fil.pattern = data['pattern']
        if 'category_id' in data:
            cid = data['category_id']
            fil.category_id = int(cid) if cid else None
        if 'subcategory_id' in data:
            sid = data['subcategory_id']
            fil.subcategory_id = int(sid) if sid else None
        session.commit()
        logger.info("Updated favorite filter %s (id=%s)", fil.pattern, fil.id)
        result = {
            'id': fil.id,
            'pattern': fil.pattern,
            'category_id': fil.category_id,
            'subcategory_id': fil.subcategory_id,
            'category': fil.category.name if fil.category else None,
            'subcategory': fil.subcategory.name if fil.subcategory else None,
        }
        session.close()
        return jsonify(result)

    session.delete(fil)
    session.commit()
    logger.info("Deleted favorite filter %s (id=%s)", fil.pattern, fil.id)
    session.close()
    return jsonify({'message': 'deleted'})


@app.route('/reset', methods=['POST'])
@login_required
def reset():
    """Delete all transactions from the database."""
    session = models.SessionLocal()
    session.query(models.Transaction).delete()
    session.commit()
    session.close()
    return jsonify({'message': 'reset'})
