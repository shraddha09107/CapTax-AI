# 07. Backend Business Logic & Pipeline Workflow

> **Module Focus:** Complete End-to-End Business Logic & Algorithmic Execution Sequences  
> **Author & Mentor:** Senior Backend Developer & Technical Mentor  
> **Key Domains:** Multi-Broker Ingestion, Stock Dilution, FIFO Matching & Tax Synthesis

---

## 1. End-to-End Pipeline Workflow Diagram

The diagram below details the exact chronological sequence of data transformations occurring across the backend and AI/ML layers when `/pipeline/run` is called:

```mermaid
flowchart TD
    START([User clicks 'Run Pipeline' or POST /pipeline/run]) --> S1[1. generate_datasets.py]
    
    subgraph Step1 ["Stage 1: Mock Market Generation"]
        S1 --> S1_OUT1[zerodha_trades.csv]
        S1 --> S1_OUT2[groww_trades.csv]
        S1 --> S1_OUT3[icici_direct_trades.csv]
        S1 --> S1_OUT4[interactive_brokers_trades.csv]
        S1 --> S1_OUT5[corporate_actions.csv]
        S1 --> S1_OUT6[foreign_dividends.csv]
    end

    S1_OUT1 & S1_OUT2 & S1_OUT3 & S1_OUT4 --> S2[2. ingest.py]

    subgraph Step2 ["Stage 2: Multi-Broker Ingestion & Canonicalization"]
        S2 --> S2_DATE[Parse 5 Date Formats to YYYY-MM-DD]
        S2_DATE --> S2_SIDE[Normalize buy/sell to BUY/SELL]
        S2_SIDE --> S2_FX[Convert USD to INR via FXRateToINR]
        S2_FX --> S2_OUT[normalized_trades.csv]
    end

    S2_OUT & S1_OUT5 --> S3[3. corporate_actions_adjuster.py]

    subgraph Step3 ["Stage 3: Corporate Actions Lot Dilution"]
        S3 --> S3_PARSE[Regex parse split/bonus ratios]
        S3_PARSE --> S3_MASK[Filter BUY lots dated before Ex-Date]
        S3_MASK --> S3_MATH[Divide price by multiplier & multiply quantity]
        S3_MATH --> S3_OUT[adjusted_trades.csv]
    end

    S3_OUT --> S4[4. fifo_matcher.py]

    subgraph Step4 ["Stage 4: FIFO Cost-Basis Matching Engine"]
        S4 --> S4_SORT[Sort by symbol and trade_date ASC]
        S4_SORT --> S4_QUEUE[Enqueue BUY lots in collections.deque]
        S4_QUEUE --> S4_DEQUE[Consume oldest lots for each SELL order]
        S4_DEQUE --> S4_CALC[Calculate holding_period_days and realized_gain_inr]
        S4_CALC --> S4_OUT[realized_gains.csv]
    end

    S4_OUT --> S5[5. tax_classifier.py]

    subgraph Step5 ["Stage 5: Capital Gains Tax Classification (AIML)"]
        S5 --> S5_CLASS[Holding > 365 days? LTCG else STCG]
        S5_CLASS --> S5_FY[Assign Indian Financial Year Apr 1 - Mar 31]
        S5_FY --> S5_EXEMPT[Apply Rs. 1,25,000 LTCG annual exemption]
        S5_EXEMPT --> S5_TAX[Apply 12.5% LTCG & 20% STCG flat rates]
        S5_TAX --> S5_OUT[tax_summary.csv & classified_gains.csv]
    end

    S1_OUT6 --> S6[6. dtaa_relief.py]

    subgraph Step6 ["Stage 6: DTAA Foreign Tax Credit (AIML)"]
        S6 --> S6_WHT[Convert US Gross & 25% WHT to INR]
        S6_WHT --> S6_IND[Compute 30% Indian Slab Liability]
        S6_IND --> S6_MIN[Relief = min of Foreign Tax and Indian Tax]
        S6_MIN --> S6_OUT[dtaa_relief.csv]
    end

    S5_OUT & S6_OUT & S1_OUT4 --> S7[7. disclosure_generator.py]

    subgraph Step7 ["Stage 7: Final ITR Disclosure Assembly (AIML)"]
        S7 --> S7_SCH_CG[Assemble Schedule CG summary]
        S7 --> S7_SCH_FSI[Assemble Schedule FSI summary]
        S7 --> S7_SCH_FA[Calculate net positive US holdings for Schedule FA]
        S7 --> S7_OUT[disclosure_summary.txt]
    end

    S7_OUT --> END([Pipeline Finished: HTTP 200 OK Response Returned to Client])
```

---

## 2. In-Depth Breakdown of Each Business Logic Stage

### Stage 1: Synthetic Dataset Generation (`generate_datasets.py`)
- **Owner:** Anishka Jain (Backend Lead)
- **Execution Trigger:** Step 1 of `POST /pipeline/run` or standalone `python generate_datasets.py`.
- **Input:** Hardcoded master ticker lists (`INDIAN_STOCKS`, `US_STOCKS`) and random seeds.
- **Output:** 6 CSV files created in `./data/`:
  1. `zerodha_trades.csv` (180 rows)
  2. `groww_trades.csv` (150 rows)
  3. `icici_direct_trades.csv` (120 rows)
  4. `interactive_brokers_trades.csv` (90 rows)
  5. `corporate_actions.csv` (25 rows)
  6. `foreign_dividends.csv` (40 rows)
- **Business Purpose:** Mimics the fragmentation of the real financial world, embedding varied date representations, mixed casing, and currency exchange rates.

---

### Stage 2: Ingestion & Canonical Normalization (`ingest.py`)
- **Owner:** Anishka Jain (Backend Lead)
- **Main Functions:** `normalize_all()`, `_std_side()`, `validate()`, and 4 loader functions.
- **Input:** The 4 broker trade CSV files from `./data/`.
- **Transformation Sequence:**
  1. Iterates through loaders (`load_zerodha`, `load_groww`, `load_icici_direct`, `load_interactive_brokers`).
  2. Parses dates into ISO standard:
     - Zerodha: `%Y-%m-%d` $\rightarrow$ `2023-04-15`
     - Groww: `%d/%m/%Y` $\rightarrow$ `15/04/2023` $\rightarrow$ `2023-04-15`
     - ICICI: `%d-%b-%Y` $\rightarrow$ `15-Apr-2023` $\rightarrow$ `2023-04-15`
     - IBKR: `%Y%m%d` $\rightarrow$ `20230415` $\rightarrow$ `2023-04-15`
  3. Directional standardization: `_std_side()` translates all variations (`"B"`, `"buy"`, `"BUY"`) into `"BUY"`.
  4. Currency conversion: Foreign amounts (IBKR in USD) are multiplied by `FXRateToINR`. Brokerage fees in USD are also converted to INR.
  5. Computes `gross_amount_inr = round(price_inr * quantity, 2)`.
  6. Enforces validation assertions (all prices $> 0$, all quantities $> 0$).
- **Output:** `./data/normalized_trades.csv` (540 consolidated rows).

---

### Stage 3: Corporate Action Adjustment (`corporate_actions_adjuster.py`)
- **Owner:** Anishka Jain (Backend Lead)
- **Main Functions:** `apply_adjustments()`, `parse_ratio()`, `load_actions()`.
- **Input:** `./data/normalized_trades.csv` and `./data/corporate_actions.csv`.
- **Business Logic & Mathematical Dilution:**
  - When a stock split or bonus issue occurs, the physical number of shares changes on the **Ex-Date**, but the economic value remains identical.
  - Regex extracts ratios:
    - `"Stock split 1:2"` $\rightarrow \text{multiplier} = \frac{2}{1} = 2.0$.
    - `"Bonus issue 1:1"` $\rightarrow \text{multiplier} = \frac{1+1}{1} = 2.0$.
  - The module selects BUY lots where `symbol == action_symbol` and `trade_date < ex_date`.
  - Dilution formula:
    $$\text{adj\_quantity} = \text{round}(\text{quantity} \times \text{multiplier})$$
    $$\text{adj\_price} = \frac{\text{price\_inr}}{\text{multiplier}}$$
- **Output:** `./data/adjusted_trades.csv`.

---

### Stage 4: FIFO Cost-Basis Matching (`fifo_matcher.py`)
- **Owner:** Anishka Jain (Backend Lead)
- **Main Functions:** `fifo_match()`.
- **Input:** `./data/adjusted_trades.csv`.
- **Core Algorithm:**
  1. Groups all trades by `symbol` and sorts chronologically.
  2. Maintains a queue of BUY lots (`collections.deque`) per symbol.
  3. When a `SELL` is processed:
     - Extracts the oldest buy lot from `lots[0]`.
     - Matched quantity: $\min(\text{sell\_qty}, \text{lot\_qty})$.
     - Calculates holding period:
       $$\text{holding\_period\_days} = (\text{sell\_date} - \text{buy\_date}).\text{days}$$
     - Calculates financial gain:
       $$\text{cost\_basis} = \text{matched\_qty} \times \text{buy\_price}$$
       $$\text{sale\_value} = \text{matched\_qty} \times \text{sell\_price}$$
       $$\text{realized\_gain} = \text{sale\_value} - \text{cost\_basis}$$
     - If the lot is exhausted, calls `lots.popleft()`.
     - If `sell_qty` exceeds all available buy lots, creates an audit record flagged with `"UNMATCHED_SELL_QUANTITY"`.
- **Output:** `./data/realized_gains.csv`.

---

### Stage 5: Capital Gains Tax Classification (`tax_classifier.py`)
- **Owner:** Shraddha Singh (Lead & AI/Interpretation Lead)
- **Input:** `./data/realized_gains.csv`.
- **Rules Applied (Indian Income Tax Act - Budget 2024 Regime):**
  - **Holding Period Threshold:**
    $$\text{gain\_type} = \begin{cases} \text{LTCG} & \text{if holding\_period\_days} > 365 \\ \text{STCG} & \text{otherwise} \end{cases}$$
  - **Financial Year Grouping:** April 1 to March 31.
  - **Annual LTCG Exemption:** ₹1,25,000 deducted from aggregate annual LTCG gains.
  - **Tax Rates:**
    - Taxable LTCG taxed at flat **12.5%**.
    - STCG taxed at flat **20.0%**.
- **Output:** `./data/classified_gains.csv` and `./data/tax_summary.csv`.

---

### Stage 6: Foreign Tax Credit / DTAA Relief (`dtaa_relief.py`)
- **Owner:** Shraddha Singh (Lead & AI/Interpretation Lead)
- **Input:** `./data/foreign_dividends.csv`.
- **Rules Applied (Section 90 & Article 25 India-US Treaty):**
  - Indian tax resident pays tax on global dividend income at their marginal slab rate (modeled as 30%).
  - The US has already deducted 25% withholding tax at source (Form 1042-S).
  - Relief formula:
    $$\text{dtaa\_relief\_inr} = \min(\text{foreign\_tax\_withheld\_inr}, \text{indian\_tax\_on\_income\_inr})$$
    $$\text{net\_indian\_tax\_payable\_inr} = \text{indian\_tax\_on\_income\_inr} - \text{dtaa\_relief\_inr}$$
- **Output:** `./data/dtaa_relief.csv`.

---

### Stage 7: Final Disclosure Synthesis (`disclosure_generator.py`)
- **Owner:** Shraddha Singh (Lead & AI/Interpretation Lead)
- **Input:** `tax_summary.csv`, `dtaa_relief.csv`, `interactive_brokers_trades.csv`.
- **Behavior:**
  - Calculates net open positions in US stocks to approximate Schedule FA (Foreign Assets) reporting.
  - Aggregates capital gains by FY for Schedule CG.
  - Formats dividend tax relief for Schedule FSI.
  - Assembles a clean, human-readable ASCII text summary.
- **Output:** `./data/disclosure_summary.txt`.
