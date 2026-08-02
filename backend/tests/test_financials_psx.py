"""Parser tests for the DPS financials scraper (no network — static fixtures).

Guards the sector-aware behavior: banks report 'Mark-up Earned' where
industrials report 'Sales', both report 'Profit after Taxation' + 'EPS', and the
quarterly header uses 'Q1 2026' style periods.
"""
from bs4 import BeautifulSoup

from app.scrapers.financials_psx import _parse_annual, _parse_quarterly

# Bank-style page: annual + quarterly income + a ratios table sharing the year header.
BANK_HTML = """
<table><tr><th></th><th>2025</th><th>2024</th></tr>
  <tr><td>Mark-up Earned</td><td>634,895,672</td><td>768,558,718</td></tr>
  <tr><td>Profit after Taxation</td><td>62,492,417</td><td>56,765,819</td></tr>
  <tr><td>EPS</td><td>42.60</td><td>38.70</td></tr>
</table>
<table><tr><th></th><th>Q1 2026</th><th>Q3 2025</th></tr>
  <tr><td>Mark-up Earned</td><td>172,134,268</td><td>167,695,843</td></tr>
  <tr><td>Profit after Taxation</td><td>15,415,506</td><td>15,968,959</td></tr>
  <tr><td>EPS</td><td>10.51</td><td>10.89</td></tr>
</table>
<table><tr><th></th><th>2025</th><th>2024</th></tr>
  <tr><td>Net Profit Margin (%)</td><td>9.84</td><td>7.39</td></tr>
  <tr><td>EPS Growth (%)</td><td>10.08</td><td>(0.15)</td></tr>
</table>
"""

INDUSTRIAL_HTML = """
<table><tr><th></th><th>2025</th><th>2024</th></tr>
  <tr><td>Sales</td><td>124,511,744</td><td>115,324,942</td></tr>
  <tr><td>Profit after Taxation</td><td>33,092,162</td><td>28,106,539</td></tr>
  <tr><td>EPS</td><td>22.59</td><td>18.91</td></tr>
</table>
"""


def _soup(html):
    return BeautifulSoup(html, "lxml")


def test_parse_annual_bank_uses_markup_as_topline_and_joins_ratios():
    rows = _parse_annual(_soup(BANK_HTML), "HBL")
    assert [r["year"] for r in rows] == [2025, 2024]
    r0 = rows[0]
    assert r0["sales"] == 634895672.0        # bank top-line = Mark-up Earned
    assert r0["net_income"] == 62492417.0
    assert r0["eps"] == 42.60
    assert r0["npm"] == 9.84                  # joined from the ratios table


def test_parse_annual_industrial_uses_sales():
    rows = _parse_annual(_soup(INDUSTRIAL_HTML), "LUCK")
    assert rows[0]["sales"] == 124511744.0
    assert rows[0]["eps"] == 22.59
    assert rows[0]["net_income"] == 33092162.0


def test_parse_quarterly_reads_q_periods_in_header_order():
    rows = _parse_quarterly(_soup(BANK_HTML), "HBL")
    # Each column maps to its own header period (not chronological order).
    assert [r["period"] for r in rows] == ["2026Q1", "2025Q3"]
    assert rows[0]["eps"] == 10.51
    assert rows[0]["net_income"] == 15415506.0


def test_duplicate_period_columns_are_deduped():
    # A repeated 'Q1 2026' column must not yield two rows with the same PK
    # (would break the ON CONFLICT upsert).
    dup = """
    <table><tr><th></th><th>Q1 2026</th><th>Q1 2026</th><th>Q3 2025</th></tr>
      <tr><td>Sales</td><td>100</td><td>100</td><td>90</td></tr>
      <tr><td>EPS</td><td>1.10</td><td>1.10</td><td>0.90</td></tr>
    </table>
    """
    rows = _parse_quarterly(_soup(dup), "X")
    periods = [r["period"] for r in rows]
    assert periods == ["2026Q1", "2025Q3"]  # no duplicate 2026Q1
    assert len(periods) == len(set(periods))


def test_ratios_table_is_never_mistaken_for_income():
    # A page with ONLY a ratios table must yield no annual income rows.
    ratios_only = """
    <table><tr><th></th><th>2025</th></tr>
      <tr><td>Net Profit Margin (%)</td><td>9.84</td></tr>
      <tr><td>EPS Growth (%)</td><td>10.08</td></tr>
    </table>
    """
    assert _parse_annual(_soup(ratios_only), "X") == []
