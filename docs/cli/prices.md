# Prices

::: mkdocs-click
    :module: niveshpy.cli.price
    :command: cli
    :prog_name: niveshpy prices
    :depth: 1
    :list_subcommands: true

## Usage notes and examples

### List prices

!!! example

    ```sh
    niveshpy prices list # (1)
    niveshpy prices list UTI DSP # (2)
    niveshpy prices list 'date:2023-01-01..2023-01-31' # (3)
    niveshpy prices list UTI 'date:2023-01-01' # (4)
    ```

    1. Show the latest prices for all available securities
    2. Show the latest prices for all securities matching the regex "UTI" or "DSP"
    3. Show all prices from 2023-01-01 to 2023-01-31.
    4. Show price of all securities matching "UTI" for date 2023-01-01

### Update prices

!!! note

    1. If 1 value is provided for `<ohlc>`, it is treated as the closing price. Other prices are set to the same value.
    2. If 2 values are provided, they are treated as opening and closing prices. High and Low are automatically set.
    3. If 4 values are provided, they are treated as opening, high, low, and closing prices respectively.
    4. Any other number of values will raise an error.

!!! example

    ```sh
    niveshpy prices update # (1)
    niveshpy prices update AAPL 2023-01-15 150.25 # (2)
    ```

    1. Update prices interactively.
    2. Set closing price of security with key "AAPL" on 2023-01-15 to 150.25.

### Sync prices

!!! example

    ```sh
    niveshpy prices sync # (1)
    niveshpy prices sync UTI DSP # (2)
    niveshpy prices sync 'date:2023-01' # (3)
    niveshpy prices sync 'UTI Nifty' 'date:2025' --force --provider amfi # (4)
    ```

    1. Sync prices for all securities with default providers
    2. Sync prices for securites matching regex "UTI" and "DSP".
    3. Sync prices for all securities from 2023-01-01 to 2023-01-31.
    4. Sync prices for securities matching regex "UTI Nifty" from 2025-01-01 to 2025-12-31 using the provider "amfi". Due to `--force`, it will forcefully re-fetch all prices even if the prices were already available in the database.

## Price Providers

NiveshPy comes bundled with a few useful providers. However, you can use your own custom provider as well.

### Bundled Providers

| Provider Name | Description                           | Command                                |
| ------------- | ------------------------------------- | -------------------------------------- |
| AMFI          | Provide mutual fund prices from AMFI. | `niveshpy prices sync --provider amfi` |

### Custom Providers

To learn how to create your own custom provider, check [our guide](../advanced/providers.md#custom-providers)

## Model Reference

::: niveshpy.models.price
