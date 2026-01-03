# Transactions

::: mkdocs-click
    :module: niveshpy.cli.transaction
    :command: cli
    :prog_name: niveshpy transactions
    :depth: 1
    :list_subcommands: true

## Usage notes and examples

### List transactions

!!! example

    ```sh
    niveshpy transactions
    niveshpy transactions list gold # (1)
    niveshpy transactions list acct:Z123 # (2)
    niveshpy transactions list type:purchase # (3)
    ```

    1. Filter by a security with 'gold' in its name or key.
    2. Filter by account 'Z123'.
    3. Filter by transaction type 'purchase'

## Model Reference

::: niveshpy.models.transaction
