import argparse
from dataclasses import dataclass, field
from typing import Optional

import yfinance as yf
import pandas as pd
import numpy as np
from utility import format_human_number, format_percentage

@dataclass
class BRuleScore:
    name: str
    score: float
    max_score: float
    detail: dict = field(default_factory=dict)

# Gets back series containing only periods that exist in the list
def _align(*series: Optional[pd.Series]) -> list[pd.Series]:
    good = [s.sort_index() for s in series if s is not None and len(s)]
    if not good:
        return []
    idx = good[0].index
    for s in good[1:]:
        idx = idx.intersection(s.index)
    if len(idx) == 0:
        return []
    return [s.loc[idx].astype(float) for s in good]

# rate the attribute to 0, 0.5, 1, 1.5, 2.0 
def _rate(x: Optional[float], excellent: float, strong: float, good: float, minimum: float, higher_is_better: bool = True,) -> int:
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return 1
    if higher_is_better:
        if x >= excellent:
            return 5
        if x >= strong:
            return 4
        if x >= good:
            return 3
        if x >= minimum:
            return 2
        return 1
    if x <= excellent:
        return 5
    if x <= strong:
        return 4
    if x <= good:
        return 3
    if x <= minimum:
        return 2
    return 1

# Change input 0, 0.5, 1, 1.5, 2.0 to stars 1, 2, 3, 4, 5
def _score_to_stars(score: float) -> int:
    if score is None or not np.isfinite(score):
        num_of_stars = 1
    else:
        num_of_stars = int(np.clip(round(float(score)), 1, 5))
    return "★" * num_of_stars + "☆" * (5 - num_of_stars)

def score_economic_moat(financial_statement, balance_sheet, cashflow, info) -> BRuleScore:
    # Gross Margin is used to measure the profitability of a company. A higher gross margin indicates that a company is able to retain more profit from its sales.
    gross_margins_latest = float(info.get("grossMargins")) if info.get("grossMargins") is not None else None
    gross_margin_score = _rate(gross_margins_latest, 0.50, 0.42, 0.35, 0.20)

    revenue = financial_statement.loc["Total Revenue"]
    gross_profit = financial_statement.loc["Gross Profit"]
    if revenue is not None and gross_profit is not None:
        aligned = _align(revenue, gross_profit)
        if len(aligned) == 2:
            aligned_revenue, aligned_gross_profit = aligned
            # turn division by zero into NaN and drop them
            gross_margin_series = (aligned_gross_profit / aligned_revenue).replace([np.inf, -np.inf], np.nan).dropna() 
    gross_margin_std = float(gross_margin_series.std()) if gross_margin_series is not None and len(gross_margin_series) >= 3 else None
    gross_margin_stability_score = _rate(gross_margin_std, 0.03, 0.05, 0.08, 0.15, higher_is_better=False)
 
    # Return on Invested Capital (ROIC)  Check
    net_income = financial_statement.loc["Net Income"]
    equity = balance_sheet.loc["Stockholders Equity"]
    debt = balance_sheet.loc["Total Debt"]
    cash = balance_sheet.loc["Cash Cash Equivalents And Short Term Investments"]

    roic_series = []
    if net_income is not None and equity is not None:
        invested_capital = equity.copy()
        if debt is not None:
            invested_capital = invested_capital.add(debt.reindex(invested_capital.index), fill_value=0)
        if cash is not None:
            invested_capital = invested_capital.sub(cash.reindex(invested_capital.index), fill_value=0)
        aligned = _align(net_income, invested_capital)
        if len(aligned) == 2:
            aligned_net_income, aligned_invested_capital = aligned
            roic_series = (aligned_net_income / aligned_invested_capital.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan).dropna()
    roic_avg = float(roic_series.mean()) if len(roic_series) else None
    roic_score = _rate(roic_avg, 0.20, 0.16, 0.12, 0.08)
 
    # Check negative revenue growth years in the last 3 years
    negative_growth_years = None
    if revenue is not None and len(revenue) >= 3:
        revenue_growth = revenue.sort_index().pct_change().dropna()
        negative_growth_years = (revenue_growth < 0).sum()
    revenue_growth_score = _rate(negative_growth_years, 0, 1, 2, 3, higher_is_better=False) if negative_growth_years is not None else 0.0
 
    # Check how paper profit is converted into cash, as a company can report profit but not have cash in hand, which is a sign of poor quality of earnings
    # cash_conversion = reported profit turned into cash
    cash_conversion_ratio = None
    operating_cash_flow = cashflow.loc["Operating Cash Flow"]
    if operating_cash_flow is not None and net_income is not None:
        aligned = _align(operating_cash_flow, net_income)
        if len(aligned) == 2:
            aligned_operating_cash_flow, aligned_net_income = aligned
            has_net_income_from_series = aligned_net_income > 0
            if has_net_income_from_series.any():
                cash_conversion_ratio = float((aligned_operating_cash_flow[has_net_income_from_series] / aligned_net_income[has_net_income_from_series]).mean())
    cash_conversion_score = _rate(cash_conversion_ratio, 1.20, 1.05, 0.90, 0.60)

    free_cash_flow = cashflow.loc["Free Cash Flow"] if "Free Cash Flow" in cashflow.index else None
    free_cash_flow_margin = None
    if free_cash_flow is not None and revenue is not None:
        aligned = _align(free_cash_flow, revenue)
        if len(aligned) == 2:
            aligned_free_cash_flow, aligned_revenue = aligned
            free_cash_flow_margin = float((aligned_free_cash_flow / aligned_revenue.replace(0, np.nan)).mean())
    free_cash_flow_score = _rate(free_cash_flow_margin, 0.20, 0.15, 0.10, 0.05)

    rated_moat_score = float(np.mean([gross_margin_score, gross_margin_stability_score, roic_score, revenue_growth_score, cash_conversion_score, free_cash_flow_score]))
    
    return BRuleScore(
        "Economic Moat",
        rated_moat_score,
        5.0,
        {
            "gross_margin": gross_margins_latest,
            "gross_margin_std": gross_margin_std,
            "roic_avg": roic_avg,
            "revenue_down_years": negative_growth_years,
            "cash_conversion_ratio": cash_conversion_ratio,
            "free_cash_flow_margin": free_cash_flow_margin,
        },
    ) #score_economic_moat

def score_financial_discipline(financial_statement, cashflow, balance_sheet, info) -> BRuleScore:
    net_income = financial_statement.loc["Net Income"]
    interest = financial_statement.loc["Interest Expense"]
    ebit = financial_statement.loc["EBIT"]
    
    total_debt = float(info.get("totalDebt")) if info.get("totalDebt") is not None else None
    net_income_avg = float(net_income.mean()) if net_income is not None and len(net_income) else None
    debt_over_net_income = (total_debt / net_income_avg) if (total_debt is not None and net_income_avg) else None
    debt_over_net_income_score = (_rate(debt_over_net_income, 2.0, 3.0, 4.0, 7.0, higher_is_better=False) if debt_over_net_income is not None and debt_over_net_income >= 0 else (5 if total_debt == 0 else 1))

    # operating profit cover interest expense, as interest may vary from year to year, we take the average of the ratio of EBIT to interest expense over the years
    profit_cover_interest = None
    if ebit is not None and interest is not None:
        aligned = _align(ebit, interest)
        if len(aligned) == 2:
            aligned_ebit, aligned_interest = aligned
            aligned_interest = aligned_interest.abs()
            with_aligned_interest = aligned_interest > 0
            if with_aligned_interest.any():
                profit_cover_interest = float((aligned_ebit[with_aligned_interest] / aligned_interest[with_aligned_interest]).mean())
            elif float(aligned_ebit.mean()) > 0:
                profit_cover_interest = 99.0  #no interest expense, but profitable = very strong
    profit_cover_interest_score = _rate(profit_cover_interest, 8.0, 6.5, 5.0, 3.0) 

    # debt to equity ratio, to find out the general financial leverage of the company
    debt_to_equity = info.get("debtToEquity")
    debt_to_equity_ratio = None
    if debt_to_equity is not None:
        # > 5 means the value is in percentage (500% is extremely rare), so we convert it to ratio
        debt_to_equity_ratio = float(debt_to_equity) / 100.0 if float(debt_to_equity) > 5 else float(debt_to_equity)
 
    # Consider buyback of shares as a form of debt, as it is a commitment to return cash to shareholders, which is similar to paying interest on debt. So we add the buyback amount to the total debt when calculating the debt to equity ratio.
    buybacks_sum = None
    buybacks = cashflow.loc["Repurchase Of Capital Stock"] if "Repurchase Of Capital Stock" in cashflow.index else None
    debt_series = balance_sheet.loc["Total Debt"] if "Total Debt" in balance_sheet.index else None
    equity_series = balance_sheet.loc["Stockholders Equity"] if "Stockholders Equity" in balance_sheet.index else None
    if buybacks is not None and len(buybacks):
        buybacks_sum = float(buybacks.abs().sum())
    # Use the last full fiscal year's debt and equity to adjust the debt to equity raito with buybacks 
    if (debt_to_equity_ratio is not None and buybacks_sum is not None and buybacks_sum > 0 
        and debt_series is not None and equity_series is not None):
        aligned = _align(debt_series, equity_series)
        if len(aligned) == 2:
            aligned_debt, aligned_equity = aligned
            latest_debt = float(aligned_debt.iloc[0])
            latest_equity = float(aligned_equity.iloc[0])
            if latest_debt and latest_equity:
                adjusted_equity = latest_equity + buybacks_sum
                debt_to_equity_ratio = latest_debt / adjusted_equity
    debt_to_equity_score = _rate(debt_to_equity_ratio, 0.30, 0.40, 0.50, 1.00, higher_is_better=False) if debt_to_equity_ratio is not None else 0.0

    rated_financial_discipline_score = float(np.mean([debt_over_net_income_score, profit_cover_interest_score, debt_to_equity_score]))

    return BRuleScore(
        "Financial Discipline",
        rated_financial_discipline_score,
        5.0,
        {
            "total_debt": total_debt,
            "avg_net_income": net_income_avg,
            "debt_over_net_income": debt_over_net_income,
            "interest_coverage": profit_cover_interest,
            "debt_to_equity": debt_to_equity_ratio,
        },
    ) #score_financial_discipline

def score_fair_price(financial_statement, cashflow, info) -> BRuleScore:
    current_price = info.get("currentPrice")
    shares_on_the_market = info.get("sharesOutstanding")
    net_income = financial_statement.loc["Net Income"]
    capital_expenditure = cashflow.loc["Capital Expenditure"]
    # company tangible and non-tangible assets, values stay flat or drop over time
    depreciation_amortization = cashflow.loc["Depreciation And Amortization"]
    if depreciation_amortization is None:
        depreciation_amortization = financial_statement.loc["Reconciled Depreciation"]  

    # Owner Earnings ~= Net Income + Depreciation and Amortization - Capital Expenditure
    owner_earnings = None
    if net_income is not None:
        owner_earnings = net_income.copy()
        if depreciation_amortization is not None:
            aligned = _align(owner_earnings, depreciation_amortization)
            if len(aligned) == 2:
                aligned_owner_earnings, aligned_depreciation_amortization = aligned
                owner_earnings = aligned_owner_earnings + aligned_depreciation_amortization
        if capital_expenditure is not None:
            aligned = _align(owner_earnings, capital_expenditure)
            if len(aligned) == 2:
                aligned_owner_earnings, aligned_capital_expenditure = aligned
                # abs() because capital expenditure is usually negative in cashflow statement
                owner_earnings = aligned_owner_earnings - aligned_capital_expenditure.abs()

    owner_earnings_avg = float(owner_earnings.mean()) if owner_earnings is not None and len(owner_earnings) else None
    revenue = financial_statement.loc["Total Revenue"]
    growth_rate = 0.03  # 3% is selected as modern growth rate is around 2-4% for developed companies
    if revenue is not None and len(revenue) >= 2:
        revenue_sorted = revenue.sort_index()
        first, last = float(revenue_sorted.iloc[0]), float(revenue_sorted.iloc[-1])
        years = max(len(revenue_sorted) - 1, 1)
        if first > 0 and last > 0:
            growth_rate = (last / first) ** (1 / years) - 1
    growth_rate = float(np.clip(growth_rate, 0.0, 0.06)) # avg growth rate >= 6% is considered too high for a mature company, so we cap it at 6%

    returned_rate = 0.10  # 10% is selected as the required rate of return for a mature company
    intrinsic_value = None # "Price is what you pay, value is what you get" 
    intrinsic_value_per_share = None
    margin_of_safety = None
    if owner_earnings_avg and owner_earnings_avg > 0 and shares_on_the_market:
        # use Gordon Growth Model to calculate intrinsic value, which is a simplified version by using the average values
        intrinsic_value = owner_earnings_avg * (1 + growth_rate) / (returned_rate - growth_rate)
        intrinsic_value_per_share = intrinsic_value / float(shares_on_the_market)
        if current_price:
            margin_of_safety = 1.0 - float(current_price) / intrinsic_value_per_share
    # 30% margin of safety means 30% off the intrinsic value, which is considered a good deal for a mature company
    margin_of_safety_score = _rate(margin_of_safety, 0.30, 0.20, 0.15, 0.00) if margin_of_safety is not None else 0.0

    trailing_pe = info.get("trailingPE", None) # current price divided by the last twelve months of earnings per share
    earning_yield = (1.0 / float(trailing_pe)) if trailing_pe and float(trailing_pe) > 0 else None
    # earing yield is preferred to trailing P/E, because it earier to read and understand, and it is more intuitive to compare with the required rate of return
    earning_yield_score = _rate(earning_yield, 0.08, 0.07, 0.06, 0.04) if earning_yield is not None else 0.0
    
    rated_fair_price_score = float(np.mean([margin_of_safety_score, earning_yield_score]))
    
    return BRuleScore(
        "Fair Price",
        rated_fair_price_score,
        5.0,
        {
            "earning_yield": earning_yield,
            "margin_of_safety": margin_of_safety,
            "intrinsic_value_per_share": intrinsic_value_per_share,
        },
    ) #score_fair_price

def score_predictable_earnings(financial_statement) -> BRuleScore:
    net_income = financial_statement.loc["Net Income"]
    if net_income is None or len(net_income) < 3:
        return BRuleScore("Predictable Earnings", 1.0, 5.0, {"note": "need >=3 years of net income"})

    net_income = net_income.sort_index().astype(float)
    year_of_neg_net_income = int((net_income <= 0).sum())
    year_of_neg_net_income_score = 5 if year_of_neg_net_income == 0 else 1

    yoy_net_income_growth = net_income.pct_change().dropna()
    year_of_neg_growth = int((yoy_net_income_growth < 0).sum())
    year_of_neg_growth_score = _rate(year_of_neg_growth, 0, 1, 2, 3, higher_is_better=False) if year_of_neg_growth is not None else 0.0
 
    net_income_mean = float(net_income.mean())
    net_income_std = float(net_income.std())
    net_income_coefficient_of_variation = (net_income_std / abs(net_income_mean)) if net_income_mean else None
    net_income_coefficient_of_variation_score = _rate(net_income_coefficient_of_variation, 0.20, 0.27, 0.35, 0.55, higher_is_better=False) if net_income_coefficient_of_variation is not None else 0.0
 
    y = net_income.values
    x = np.arange(len(y), dtype=float)
    # need at least 3 years of data to form a line
    if len(y) >= 3 and np.std(y) > 0:
        # 1 for plotting a straight line, y = ax + b, where a is the slope and b is the intercept
        coeff = np.polyfit(x, y, 1)
        # slope = a = coeff[0], a = 0 = flat, close to x-axis, a > 0 = upward trend (close to y-axis), a < 0 = downward trend
        slope = float(coeff[0])
        estimated_y = np.polyval(coeff, x)
        # residual sum of squares of y, the smaller the better, 0 is perfect fit
        rss_y = float(np.sum((y - estimated_y) ** 2))
        # total sum of squares of y, baseline of data, larger means more variation in data, smaller means more stable data, 0 means all data points are the same
        tss_y = float(np.sum((y - y.mean()) ** 2))
        # R-squared, the proportion of variance in y that is predictable from x, 1 is perfect fit, 0 means no fit, negative means worse than just using the mean of y
        r_squared = 1.0 - rss_y / tss_y if tss_y else None

    r_squared_score = _rate(r_squared, 0.80, 0.70, 0.60, 0.40) if r_squared is not None else 0.0

    # year_of_neg_net_income_score and year_of_neg_growth_score are included for providing the direction of the earning / losing money trend
    rated_predictable_earnings_score = float(np.mean([year_of_neg_net_income_score, year_of_neg_growth_score, net_income_coefficient_of_variation_score, r_squared_score]))

    return BRuleScore(
        "Predictable Earnings",
        rated_predictable_earnings_score,
        5.0,
        {
            "year_of_neg_net_income": year_of_neg_net_income,
            "year_of_neg_growth": year_of_neg_growth,
            "net_income_coefficient_of_variation": net_income_coefficient_of_variation,
            "net_income_r_squared": r_squared,
            "net_income_trend_slope": slope,
        },
    ) # score_predictable_earnings 

def get_stock_info(info) -> dict:
    company_name = info.get("longName") or info.get("shortName")
    stock_price = info.get("currentPrice") or info.get("regularMarketPrice")
    officers = info.get("companyOfficers", [])
    top_officer = officers[0] if officers else None
    officer_summary = (
        f" Its top officer is {top_officer.get('name', 'Unknown')} ({top_officer.get('age', 'Age Unknown')}), "
        f"serving as {top_officer.get('title', 'Unknown')}."
        if top_officer
        else " No top officer information is available."
    )
    short_summary = (
        f"{company_name} is a {info.get('sector')} company working in "
        f"{info.get('industry')} with {info.get('fullTimeEmployees'):,} employees."
        f"{officer_summary}"
    )

    return {
        "name": company_name,
        "current_price": stock_price,
        "summary": short_summary,
        "website": info.get("website", "None"),
    } 

def screen_buffett_stock(ticker_symbol: str) -> None:

    stock = yf.Ticker(ticker_symbol)
    # info contains last 12 months data
    info = stock.info
    # Financial statement contains 4 years of data
    financial_statement = stock.financials
    balance_sheet = stock.balance_sheet
    cashflow = stock.cashflow
    print(f"B+ Investor Stock Screener for [{ticker_symbol}]:")
    print("")

    # 1 Know the business and its management
    company_info = get_stock_info(info)
    print(f"Company Name: {company_info['name']}")
    print(f"Current Price: {company_info['current_price']:.2f}")
    print(f"Company Website: {company_info['website']}")
    print(f"Company Description: {company_info['summary']}")
    print("")

    # 2 Economic Moat Check
    results = score_economic_moat(financial_statement, balance_sheet, cashflow, info)
    print(f"Score for {results.name}: {_score_to_stars(results.score)}")
    print(f"Gross Margin: {format_percentage(results.detail.get("gross_margin"))}, Gross Margin Standard Deviation: {format_percentage(results.detail.get('gross_margin_std'))}, ROIC Avg: {format_percentage(results.detail.get('roic_avg'))}, Year(s) of Revenue Decline: {results.detail.get('revenue_down_years')}, Cash Conversion Ratio: {format_percentage(results.detail.get('cash_conversion_ratio'))}, Free Cash Flow Margin: {format_percentage(results.detail.get('free_cash_flow_margin'))}")
    print("")

    # 3 Financial Discipline Check
    results = score_financial_discipline(financial_statement, cashflow, balance_sheet, info)
    print(f"Score for {results.name}: {_score_to_stars(results.score)}")
    print(f"Total Debt: {format_human_number(results.detail.get('total_debt'))}, Avg Net Income: {format_human_number(results.detail.get('avg_net_income'))}, Debt Burden to Earning Power: {format_percentage(results.detail.get('debt_over_net_income'))}, Interest Coverage: {format_percentage(results.detail.get('interest_coverage'))}, Debt to Equity: {format_percentage(results.detail.get('debt_to_equity'))}")
    print("")
    
    # 4 Predictable Earnings Check
    results = score_predictable_earnings(financial_statement)
    print(f"Score for {results.name}: {_score_to_stars(results.score)}")
    print(f"Year(s) of Net Loss: {results.detail.get('year_of_neg_net_income')}, Year(s) of Net Income Decline: {results.detail.get('year_of_neg_growth')}, Trend Predictability: {format_percentage(results.detail.get('net_income_r_squared'))}, Relative Volatility: {format_percentage(results.detail.get('net_income_coefficient_of_variation'))}")
    print("")

    # 5 Fair Price Check
    results = score_fair_price(financial_statement, cashflow, info)
    print(f"Score for {results.name}: {_score_to_stars(results.score)}")
    print(f"Intrinsic Value: {results.detail.get('intrinsic_value_per_share'):.2f}, Discount to Intrinsic Value: {format_percentage(results.detail.get('margin_of_safety'))}, Earnings Yield: {format_percentage(results.detail.get('earning_yield'))}")
    print("")

def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        description="Run the Buffett-style stock screen for one ticker.",
        usage="%(prog)s <ticker>",
    )
    parser.add_argument("ticker", nargs="?", help="Yahoo Finance ticker, e.g. AAPL")
    args = parser.parse_args(argv)

    if args.ticker is None:
        parser.print_usage()
        print("Example: python bbuy.py AAPL")
        return

    screen_buffett_stock(args.ticker)

if __name__ == "__main__":
    main()