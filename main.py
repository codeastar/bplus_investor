from email.mime import message
import os
from dotenv import load_dotenv
from edgar import Company, set_identity
from utility import format_human_number

def display_holdings_changes(changes_df, message, cols_present):
   if not changes_df.empty:
     print(message)
     print(changes_df[cols_present].to_string(index=False))
     print()

load_dotenv()
set_identity(os.getenv("IDENTITY_EMAIL"))
the_company = Company(os.getenv("CIK"))
filings = the_company.get_filings(form="13F-HR")
current_13f = filings[0].obj()   # Most recent quarter
previous_13f = filings[1].obj()  # Prior quarter
df = current_13f.holdings.rename(columns={"SharesPrnAmount": "Shares"})
total_value = df["Value"].sum()
df["Weight (%)"] = (df["Value"] / total_value * 100).round(2)

print("Current holdings:")
current_holdings = df[["Ticker", "Issuer", "Value", "Shares", "Weight (%)"]].assign(
    Shares=lambda d: d["Shares"].map(format_human_number),
    Value=lambda d: d["Value"].map(format_human_number).apply(lambda x: f"${x}" if x else "")
)
print(current_holdings)
print("\n" + "="*50 + "\n")

print(f"Comparing [{previous_13f.report_period}] vs [{current_13f.report_period}]")
changes = current_13f.compare_holdings(previous_13f)
df = changes.data.assign( 
    PrevShares=lambda d: d["PrevShares"].map(format_human_number),
    ShareChange=lambda d: d["ShareChange"].map(format_human_number),
    ShareChangePct=lambda d: d["ShareChangePct"].map(format_human_number).apply(lambda x: f"{x}%" if x else ""),
    Value=lambda d: d["Value"].map(format_human_number).apply(lambda x: f"${x}" if x else ""),
    Shares=lambda d: d["Shares"].map(format_human_number),)
display_holdings_changes(df[df['Status'].str.upper() == 'NEW'].copy(), "--- NEW POSITIONS BOUGHT ---", ['Status', 'Ticker', 'Issuer', 'Shares', 'Value'])
display_holdings_changes(df[df['Status'].str.upper() == 'CLOSED'].copy(), "--- POSITIONS FULLY CLOSED ---", ['Status', 'Ticker', 'Issuer', 'PrevShares'])
display_holdings_changes(df[df['Status'].str.upper().isin(['INCREASED', 'DECREASED'])].copy()
, "--- MODIFIED POSITIONS (INCREASED / DECREASED) ---", ['Status', 'Ticker', 'Issuer', 'PrevShares', 'Shares', 'Value', 'ShareChange', 'ShareChangePct'])