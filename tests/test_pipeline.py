import pytest

from meter_medallion.pipeline import check, run
from meter_medallion.sample import DAYS, LEAKING, RESETTING, generate


@pytest.fixture(scope="module")
def result(tmp_path_factory):
    data = tmp_path_factory.mktemp("data")
    generate(data)
    return run(data)


def one(result, sql):
    return result.connection.execute(sql).fetchone()[0]


def test_every_model_builds_and_every_assertion_holds(result):
    assert len(result.built) == 12
    assert result.assertions_checked >= 15


def test_resent_readings_are_deduplicated(result):
    hours = DAYS * 24
    assert result.row_counts["bronze_readings"] > result.row_counts["silver_readings"]
    assert result.row_counts["silver_readings"] == 12 * hours


def test_bad_rows_are_quarantined_with_a_reason(result):
    reasons = {r[0] for r in result.connection.execute("SELECT reject_reason FROM silver_rejected_readings")}
    assert reasons == {"unparseable timestamp", "missing reading", "unknown apartment"}


def test_a_meter_reset_never_produces_negative_use(result):
    assert one(result, "SELECT MIN(litres) FROM silver_consumption") >= 0
    resets = result.connection.execute("SELECT meter_id FROM silver_consumption WHERE meter_reset = 1").fetchall()
    assert resets == [("M-" + RESETTING[2:],)]


def test_only_the_leaking_apartment_raises_an_alert(result):
    alerts = result.connection.execute("SELECT apartment_id, nights_with_continuous_flow FROM gold_leak_alerts").fetchall()
    assert [a[0] for a in alerts] == [LEAKING]
    assert alerts[0][1] >= 3


def test_daily_totals_add_up_to_the_interval_data(result):
    assert one(result, "SELECT SUM(litres) FROM gold_daily_consumption") == one(result, "SELECT SUM(litres) FROM silver_consumption")
    assert one(result, "SELECT SUM(litres) FROM gold_building_daily") == one(result, "SELECT SUM(litres) FROM gold_daily_consumption")


def test_report_has_one_row_per_building_with_the_alert_attached(result):
    rows = dict(result.connection.execute("SELECT building_id, open_leak_alerts FROM report_building_kpis").fetchall())
    assert rows == {"B-01": 1, "B-02": 0, "B-03": 0}


def test_ai_dataset_carries_no_personal_data(result):
    assert check(result.connection, "ai_building_consumption", "no_personal_data") == []
    columns = [d[0] for d in result.connection.execute("SELECT * FROM ai_building_consumption LIMIT 0").description]
    assert "city" in columns and not {"contact_name", "contact_email", "resident_name", "address"} & set(columns)


def test_the_personal_data_check_would_catch_a_leak(result):
    failures = check(result.connection, "silver_buildings", "no_personal_data")
    assert any("contact_email" in f for f in failures)
    assert any("email addresses" in f for f in failures)
