import datetime
from calendar import monthrange
import pytest


def get_period_dates(option: str, today: datetime.date):
    day = today.weekday()  # Monday=0
    if option == 'current-week':
        start = today - datetime.timedelta(days=day)
        end = start + datetime.timedelta(days=6)
    elif option == 'previous-week':
        end = today - datetime.timedelta(days=day + 1)
        start = end - datetime.timedelta(days=6)
    elif option == 'current-month':
        start = today.replace(day=1)
        end = datetime.date(today.year, today.month, monthrange(today.year, today.month)[1])
    elif option == 'previous-month':
        year = today.year
        month = today.month - 1
        if month == 0:
            month = 12
            year -= 1
        start = datetime.date(year, month, 1)
        end = datetime.date(year, month, monthrange(year, month)[1])
    elif option == 'ytd':
        start = datetime.date(today.year, 1, 1)
        end = datetime.date(today.year, 12, 31)
    elif option == 'last-6-months':
        month = today.month - 5
        year = today.year
        while month <= 0:
            month += 12
            year -= 1
        start = datetime.date(year, month, 1)
        end = datetime.date(today.year, today.month, monthrange(today.year, today.month)[1])
    elif option == 'previous-year':
        year = today.year - 1
        start = datetime.date(year, 1, 1)
        end = datetime.date(year, 12, 31)
    else:
        start = None
        end = None
    return start, end


@pytest.mark.parametrize(
    "today, option, expected",
    [
        (datetime.date(2024, 5, 15), 'current-week', (datetime.date(2024, 5, 13), datetime.date(2024, 5, 19))),
        (datetime.date(2024, 5, 15), 'previous-week', (datetime.date(2024, 5, 6), datetime.date(2024, 5, 12))),
        (datetime.date(2024, 5, 15), 'current-month', (datetime.date(2024, 5, 1), datetime.date(2024, 5, 31))),
        (datetime.date(2024, 5, 15), 'previous-month', (datetime.date(2024, 4, 1), datetime.date(2024, 4, 30))),
        (datetime.date(2024, 5, 15), 'ytd', (datetime.date(2024, 1, 1), datetime.date(2024, 12, 31))),
        (datetime.date(2024, 5, 15), 'last-6-months', (datetime.date(2023, 12, 1), datetime.date(2024, 5, 31))),
        (datetime.date(2024, 5, 15), 'previous-year', (datetime.date(2023, 1, 1), datetime.date(2023, 12, 31))),
        (datetime.date(2024, 1, 2), 'previous-week', (datetime.date(2023, 12, 25), datetime.date(2023, 12, 31))),
        (datetime.date(2024, 1, 15), 'previous-month', (datetime.date(2023, 12, 1), datetime.date(2023, 12, 31))),
        (datetime.date(2024, 2, 20), 'current-month', (datetime.date(2024, 2, 1), datetime.date(2024, 2, 29))),
    ]
)
def test_get_period_dates(today, option, expected):
    assert get_period_dates(option, today) == expected
