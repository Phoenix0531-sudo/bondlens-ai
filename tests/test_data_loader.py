from bond_agent.data_loader import BOND_NAME, MATURITY_YEARS, YIELD, load_bond_data, parse_maturity_to_years


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
