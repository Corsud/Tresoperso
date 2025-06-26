import datetime

from backend.app import parse_csv


def test_parse_csv_valid():
    csv_data = """Compte courant 12345678 2021-01-01
2021-01-02;Debit;CB;Achat;-12,34
2021-01-03;Credit;VIR;Salaire;1000,00
"""
    transactions, duplicates, errors, info = parse_csv(csv_data)

    assert not errors
    assert duplicates == []
    assert len(transactions) == 2
    assert info["account_type"] == "Compte courant"
    assert info["number"] == "12345678"
    assert info["export_date"] == datetime.date(2021, 1, 1)


def test_parse_csv_duplicates():
    csv_data = """Compte courant 12345678 2021-01-01
2021-01-02;Debit;CB;Achat;-12,34
2021-01-02;Debit;CB;Achat;-12,34
"""
    transactions, duplicates, errors, info = parse_csv(csv_data)

    assert not errors
    assert len(transactions) == 1
    assert len(duplicates) == 1
    d = duplicates[0]
    assert d["line_no"] == 3
    assert d["label"] == "Achat"
    assert d["amount"] == -12.34


def test_parse_csv_missing_fields():
    csv_data = """Compte courant 12345678 2021-01-01
2021-01-02;Debit;CB;Achat
"""
    transactions, duplicates, errors, info = parse_csv(csv_data)

    assert transactions == []
    assert duplicates == []
    assert errors
    assert "colonnes manquantes" in errors[0]


def test_parse_csv_trailing_minus():
    csv_data = """Compte courant 12345678 2021-01-01
2021-01-02;Debit;CB;Achat;123,45-
"""

    transactions, duplicates, errors, info = parse_csv(csv_data)

    assert not errors
    assert duplicates == []
    assert len(transactions) == 1
    assert transactions[0]["amount"] == -123.45
