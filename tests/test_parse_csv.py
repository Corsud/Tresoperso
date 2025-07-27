import datetime
import pytest

from backend.csv_utils import parse_csv


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


def test_parse_csv_with_header_and_account_info():
    csv_data = (
        "Compte courant;Mon compte;12345678;2021-01-01;;1000,00\n"
        "\n"
        "Date operation;Libelle court;Type operation;Libelle operation;Montant operation en euro\n"
        "2021-01-02;CB;Debit;Achat;-12,34\n"
        "2021-01-03;VIR;Credit;Salaire;1000,00\n"
    )
    transactions, duplicates, errors, info = parse_csv(csv_data)

    assert not errors
    assert duplicates == []
    assert len(transactions) == 2
    assert info["account_type"] == "Compte courant"
    assert info["number"] == "12345678"
    assert info["export_date"] == datetime.date(2021, 1, 1)


def test_parse_csv_trailing_blank_line():
    csv_data = """Compte courant 12345678 2021-01-01
2021-01-02;Debit;CB;Achat;-12,34

"""
    transactions, duplicates, errors, info = parse_csv(csv_data)

    assert not errors
    assert duplicates == []
    assert len(transactions) == 1


@pytest.mark.parametrize("label", ["=1+2", "+test", "-cmd", "@SUM"])
def test_parse_csv_sanitizes_label(label):
    csv_data = f"""Compte courant 12345678 2021-01-01
2021-01-02;Debit;CB;{label};1,00
"""
    transactions, duplicates, errors, info = parse_csv(csv_data)

    assert not errors
    assert transactions[0]["label"] == "'" + label


@pytest.mark.parametrize(
    "csv_data,mapping",
    [
        (
            """Compte courant 12345678 2021-01-01\nAchat;Debit;2021-01-02;-12,34;CB\n""",
            {
                'label': 0,
                'type': 1,
                'date': 2,
                'amount': 3,
                'payment_method': 4,
            },
        ),
        (
            """Compte courant 12345678 2021-01-01\n-12,34;CB;Achat;Debit;2021-01-02\n""",
            {
                'amount': 0,
                'payment_method': 1,
                'label': 2,
                'type': 3,
                'date': 4,
            },
        ),
    ],
)
def test_parse_csv_with_custom_mapping(csv_data, mapping):
    transactions, duplicates, errors, info = parse_csv(csv_data, mapping=mapping)

    assert not errors
    assert duplicates == []
    assert len(transactions) == 1
    t = transactions[0]
    assert t['label'] == 'Achat'
    assert t['type'] == 'Debit'
    assert t['payment_method'] == 'CB'
    assert t['date'] == datetime.date(2021, 1, 2)
    assert t['amount'] == -12.34
