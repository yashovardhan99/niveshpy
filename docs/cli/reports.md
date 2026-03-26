# Reports

Reports provide insights into your portfolio — holdings, asset allocation, performance metrics, and a comprehensive summary dashboard.

???+ warning
    The source for this page is AI-generated and may contain errors.

    If you spot an error, please [Open an issue](https://github.com/yashovardhan99/niveshpy/issues/new)
    on our [GitHub repo](https://github.com/yashovardhan99/niveshpy/).

::: mkdocs-click
    :module: niveshpy.cli.report
    :command: cli
    :prog_name: niveshpy reports
    :depth: 1
    :list_subcommands: true

## Usage notes and examples

### Holdings

Show current holdings across all accounts, including invested amount and current value.

!!! example

    ```sh
    niveshpy reports holdings # (1)
    niveshpy reports holdings UTI DSP # (2)
    niveshpy reports holdings 'date:2025-01' --no-total # (3)
    niveshpy reports holdings --format json # (4)
    niveshpy reports holdings --limit 5 # (5)
    ```

    1. Show all current holdings with a total row.
    2. Filter holdings for securities matching "UTI" or "DSP".
    3. Show holdings for January 2025 without the total row.
    4. Output holdings as JSON.
    5. Show only the top 5 holdings.

!!! warning "Date filtering and invested amounts"

    When using date filters, the **current value** reflects the filtered date range,
    but the **invested amount** is calculated from the full transaction history.
    This may lead to unexpected results when filtering by date.

### Allocation

Show asset allocation grouped by security type, category, or both.

!!! example

    ```sh
    niveshpy reports allocation # (1)
    niveshpy reports allocation --type # (2)
    niveshpy reports allocation --category # (3)
    niveshpy reports allocation --format json # (4)
    ```

    1. Show allocation grouped by both type and category (default).
    2. Group allocation by security type only (e.g., Mutual Fund, Stock).
    3. Group allocation by security category only (e.g., Equity, Debt, Hybrid).
    4. Output allocation as JSON.

### Performance

Show per-holding performance metrics — current value, invested amount, absolute gains, gains percentage, and XIRR.

!!! example

    ```sh
    niveshpy reports performance # (1)
    niveshpy reports performance HDFC # (2)
    niveshpy reports performance --no-total # (3)
    niveshpy reports performance --format csv # (4)
    niveshpy reports performance --limit 10 --offset 5 # (5)
    ```

    1. Show performance for all holdings with a total row.
    2. Filter performance for securities matching "HDFC".
    3. Hide the aggregated total row.
    4. Export performance data as CSV.
    5. Show 10 holdings starting from the 6th.

!!! tip "Understanding XIRR"

    XIRR (Extended Internal Rate of Return) is an annualized return metric that accounts
    for the timing of each transaction. It provides a more accurate picture of investment
    performance than simple gain/loss calculations.

### Summary

Display a comprehensive portfolio dashboard combining key metrics, top holdings, and asset allocation in a single view.

!!! example

    ```sh
    niveshpy reports summary # (1)
    niveshpy reports summary --format json # (2)
    niveshpy reports summary UTI DSP # (3)
    ```

    1. Show a full portfolio summary dashboard.
    2. Output the summary as JSON (CSV is not supported for summary).
    3. Show summary for securities matching "UTI" or "DSP".

!!! note

    The summary command only supports **TABLE** and **JSON** output formats.
    CSV output is not available for this command due to its multi-section layout.

The summary dashboard includes:

- **Portfolio metrics** — total current value, total invested, absolute gains with percentage, and XIRR.
- **Top holdings** — your largest holdings by current value with their individual XIRR.
- **Asset allocation** — category-wise allocation with a visual bar chart.

## Model Reference

::: niveshpy.models.report
