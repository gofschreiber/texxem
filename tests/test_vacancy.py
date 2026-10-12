from datetime import date

import pytest

from app.services.vacancy import vacancy_periods

TODAY = date(2025, 6, 1)


def test_no_tenancy_means_vacant_since_availability():
    assert vacancy_periods(date(2020, 1, 1), [], TODAY) == [(date(2020, 1, 1), None)]


def test_not_yet_available_unit_has_no_vacancy():
    assert vacancy_periods(date(2026, 1, 1), [], TODAY) == []


def test_open_ended_tenancy_from_availability_has_no_vacancy():
    assert vacancy_periods(date(2020, 1, 1), [(date(2020, 1, 1), None)], TODAY) == []


def test_gap_before_first_and_between_tenancies():
    tenancies = [(date(2021, 3, 1), date(2021, 12, 31)), (date(2022, 2, 1), None)]
    assert vacancy_periods(date(2020, 1, 1), tenancies, TODAY) == [
        (date(2020, 1, 1), date(2021, 2, 28)),
        (date(2022, 1, 1), date(2022, 1, 31)),
    ]


def test_back_to_back_tenancies_leave_no_gap():
    tenancies = [(date(2020, 1, 1), date(2020, 12, 31)), (date(2021, 1, 1), date(2021, 6, 30))]
    assert vacancy_periods(date(2020, 1, 1), tenancies, TODAY) == [(date(2021, 7, 1), None)]


def test_order_of_input_does_not_matter():
    a = (date(2020, 1, 1), date(2020, 12, 31))
    b = (date(2022, 1, 1), None)
    assert vacancy_periods(date(2020, 1, 1), [b, a], TODAY) == vacancy_periods(date(2020, 1, 1), [a, b], TODAY)


def test_tenancy_starting_before_availability_is_handled():
    assert vacancy_periods(date(2020, 6, 1), [(date(2020, 1, 1), date(2020, 12, 31))], TODAY) == [
        (date(2021, 1, 1), None)
    ]


@pytest.mark.parametrize(
    "move_out,expected",
    [
        (date(2025, 6, 1), []),  # moves out today: vacancy would start tomorrow
        (date(2025, 5, 31), [(date(2025, 6, 1), None)]),  # vacancy starts the day after move-out
    ],
)
def test_vacancy_starts_the_day_after_move_out(move_out, expected):
    assert vacancy_periods(date(2020, 1, 1), [(date(2020, 1, 1), move_out)], TODAY) == expected
