from bond_agent.data_loader import BOND_NAME, MATURITY_YEARS, YIELD, describe_data_source, load_bond_data, parse_maturity_to_years


def test_load_bond_data_reads_project_excel():
    df = load_bond_data()

    assert len(df) > 3000
    assert BOND_NAME in df.columns
    assert YIELD in df.columns
    assert MATURITY_YEARS in df.columns
    assert df[YIELD].notna().sum() > 0


def test_parse_maturity_to_years_handles_years_and_days():
    assert parse_maturity_to_years("9.68Y") == 9.68
    assert round(parse_maturity_to_years("364D"), 4) == round(364 / 365, 4)
    assert parse_maturity_to_years("bad-data") is None


def test_describe_data_source_marks_static_excel_and_legacy_crawler():
    profile = describe_data_source()

    assert profile["source_id"] == "local_static_excel"
    assert profile["source_name"] == "data/testdata.xlsx"
    assert profile["runtime_mode"] == "static_sample"
    assert profile["row_count"] > 3000
    assert profile["active_crawler"] is False
    assert profile["legacy_crawler"]["status"] == "historical_only"
