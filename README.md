# 📈 Becoming a B+ Investor

**Track any fund's 13F-HR stock holdings straight from SEC EDGAR — see what they own now, and exactly what changed since last quarter.**

Why spend 40 hours a week sifting through thousands of stocks when you can piggyback on world-class due diligence? Inspired by Model Distillation in Machine Learning, this project distills your search space down to  pre-screened portfolio. 

📖 Read the full philosophy and tutorial: [How to Build a Warren Buffett Stock Filter in Python Through Distillation](https://www.codeastar.com/become-a-bplus-investor/)


Point it at a fund's CIK (Berkshire Hathaway by default), and it pulls the latest [13F-HR](https://www.sec.gov/) filing, compares it to the prior quarter, and prints a clean breakdown of new positions, closed positions, and everything that got bigger or smaller in between.

---

## Features

- **Current holdings snapshot** — ticker, issuer, value, shares, and portfolio weight
- **New positions** the fund just opened
- **Closed positions** it fully exited
- **Increased / decreased** positions with share and percentage change
- Human-readable numbers (`$2.50M`, `1.23B`) instead of raw floats
- Works with **any** SEC filer's CIK, not just Berkshire

## Requirements

- Python **3.12+**
- [uv](https://docs.astral.sh/uv/)

## Installation

Clone the repo and install dependencies with [uv](https://docs.astral.sh/uv/):

```bash
git clone <your-repo-url>
cd bplus_investor
uv sync
```

<details>
<summary>Prefer pip?</summary>

```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
pip install edgartools python-dotenv
```

</details>

## Configuration

Copy the example environment file and fill it in:

```bash
cp .env.example .env
```

```dotenv
CIK=0001067983          # The fund's SEC CIK number (default: Berkshire Hathaway)
IDENTITY_EMAIL=you@example.com   # SEC EDGAR requires a real contact email
```

> 🪪 **Why the email?** The SEC requires all automated EDGAR requests to self-identify with a contact address. Use your own — it's not shared anywhere else.

Not sure of a CIK? Look it up on the [SEC EDGAR full-text search](https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany) or company filing page.

## ▶Usage

```bash
uv run main.py
```

That's it — the script fetches the two most recent 13F-HR filings for the configured CIK and prints the comparison straight to your terminal.

### Example output

```
Current holdings:
  Ticker              Issuer      Value    Shares  Weight (%)
    AAPL           Apple Inc    $71.20B   300.00M       28.40
    BAC   Bank of America Corp  $29.50B   700.00M       11.76
     KO         Coca-Cola Co    $24.10B   400.00M        9.61

==================================================

Comparing [2025-03-31] vs [2025-06-30]
--- NEW POSITIONS BOUGHT ---
 Status Ticker          Issuer   Shares    Value
    NEW   CVX     Chevron Corp   15.00M   $1.80B

--- POSITIONS FULLY CLOSED ---
 Status Ticker         Issuer PrevShares
 CLOSED    TSM  Taiwan Semi.       8.00M

--- MODIFIED POSITIONS (INCREASED / DECREASED) ---
    Status Ticker    Issuer PrevShares   Shares    Value ShareChange ShareChangePct
 INCREASED   AAPL Apple Inc    280.00M  300.00M  $71.20B      20.00M          7.14%
```

*(sample data for illustration — real output reflects the fund's actual filings)*


## How it works

1. Loads `CIK` and `IDENTITY_EMAIL` from `.env`
2. Uses [`edgartools`](https://github.com/dgunning/edgartools) to fetch the fund's filing history and pull its two most recent `13F-HR` reports
3. Computes portfolio weight for each current holding
4. Diffs the current filing against the prior one to classify each position as new, closed, increased, or decreased
5. Formats everything into readable tables printed to the console

## Project structure

```
bplus_investor/
├── main.py           # Entry point — fetch, compare, and print holdings
├── .env.example       # Template for required environment variables
└── pyproject.toml     # Project metadata & dependencies
```