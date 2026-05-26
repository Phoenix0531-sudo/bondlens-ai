import pandas as pd

from bond_agent.data_loader import (
    BOND_NAME,
    LIVE_CHANGE_BP,
    MATURITY_YEARS,
    PRICE,
    VOLUME,
    WEIGHTED_YIELD,
    YIELD,
    describe_data_source,
    load_bond_data,
    load_live_bond_data,
    parse_maturity_to_years,
    resolve_bond_data,
)


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
    assert profile["active_live_feed"] is False
    assert profile["legacy_crawler"]["status"] == "preserved_in_legacy_branch"


def test_load_live_bond_data_normalizes_akshare_columns():
    def fake_fetcher():
        return pd.DataFrame(
            {
                "债券简称": ["25国开20", "26超长特别国债02"],
                "成交净价": [101.23, 98.76],
                "最新收益率": [2.12, 2.65],
                "涨跌": [-0.3, 1.2],
                "加权收益率": [2.11, 2.66],
                "交易量": [4.5, 8.0],
            }
        )

    df = load_live_bond_data(fetcher=fake_fetcher)

    assert list(df[BOND_NAME]) == ["25国开20", "26超长特别国债02"]
    assert df[PRICE].tolist() == [101.23, 98.76]
    assert df[YIELD].tolist() == [2.12, 2.65]
    assert df[WEIGHTED_YIELD].tolist() == [2.11, 2.66]
    assert df[VOLUME].tolist() == [4.5, 8.0]
    assert df[LIVE_CHANGE_BP].tolist() == [-0.3, 1.2]
    assert MATURITY_YEARS in df.columns


def test_resolve_bond_data_uses_live_profile_when_available():
    def fake_fetcher():
        return pd.DataFrame(
            {
                "债券简称": ["25国开20"],
                "成交净价": [101.23],
                "最新收益率": [2.12],
                "涨跌": [-0.3],
                "加权收益率": [2.11],
                "交易量": [4.5],
            }
        )

    df, profile = resolve_bond_data(mode="live", live_fetcher=fake_fetcher)

    assert df.iloc[0][BOND_NAME] == "25国开20"
    assert profile["source_id"] == "akshare_bond_spot_deal"
    assert profile["runtime_mode"] == "live"
    assert profile["requested_mode"] == "live"
    assert profile["active_live_feed"] is True
    assert profile["fetched_at"]


def test_resolve_bond_data_falls_back_to_static_sample_when_live_fails():
    def failing_fetcher():
        raise RuntimeError("network down")

    df, profile = resolve_bond_data(mode="auto", live_fetcher=failing_fetcher)

    assert len(df) > 3000
    assert profile["source_id"] == "local_static_excel"
    assert profile["runtime_mode"] == "static_fallback"
    assert profile["requested_mode"] == "auto"
    assert profile["active_live_feed"] is False
    assert "network down" in profile["fallback_reason"]
