import datetime

from backend.csv_utils import detect_csv_structure


def test_detect_header_after_blank():
    csv_data = (
        "Compte courant;Mon compte;12345678;2021-01-01;;1000,00\n"
        "\n"
        "Date operation;Libelle court;Type operation;Libelle operation;Montant operation en euro\n"
        "2021-01-02;CB;Debit;Achat;-12,34\n"
        "2021-01-03;VIR;Credit;Salaire;1000,00\n"
    )
    delim, header_idx, cols = detect_csv_structure(csv_data)
    assert delim == ';'
    assert header_idx == 2
    assert cols[0].lower().startswith('date')
    assert cols[-1].lower().startswith('montant')


def test_detect_no_header():
    csv_data = """Compte courant 12345678 2021-01-01\n2021-01-02;Debit;CB;Achat;-12,34\n"""
    delim, header_idx, cols = detect_csv_structure(csv_data)
    assert delim == ';'
    assert header_idx is None
    assert cols == []


def test_detect_comma_delimiter():
    csv_data = """Date,Libelle,Montant\n2021-01-02,Achat,-12.34\n"""
    delim, header_idx, cols = detect_csv_structure(csv_data)
    assert delim == ','
    assert header_idx == 0
    assert cols == ['Date', 'Libelle', 'Montant']
