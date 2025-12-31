# Parsers

A parser is used to [parse](../cli/parse.md) financial documents such as account statements and transaction histories.

## Bundled Parsers

NiveshPy comes bundled with a few useful parsers.

| Parser Name | Description                                                         | Command                  |
| ----------- | ------------------------------------------------------------------- | ------------------------ |
| CAS Parser  | Parser for CAMS and Kfintech Consolidated Account Statements (CAS). | `niveshpy parse cas ...` |

## Custom Parsers

You can create your own custom parser for NiveshPy with Python.

In your `pyproject.toml` file, include an [entry point](https://packaging.python.org/en/latest/specifications/entry-points/) with the group `niveshpy.parsers`.

```toml
[project.entry-points."niveshpy.parsers"] # (1)
my_parser = "my_plugin:MyPluginFactory" # (2)
```

1. This needs to be added as-is to ensure NiveshPy can find your parser.
2. Replace `my_parser` with a unique key, and replace the string with a reference to your `PluginFactory` class.

Create a class `my_plugin.MyPluginFactory` that follows the protocol [`ParserFactory`][niveshpy.models.parser.ParserFactory].
This factory will be responsible for actually creating the parser object with the input file and password.

The [`create_parser`][niveshpy.models.parser.ParserFactory.create_parser] method must return an instance of a class that follows the protocol [`Parser`][niveshpy.models.parser.Parser].

The [`get_parser_info`][niveshpy.models.parser.ParserFactory.get_parser_info] method must return an object of type [`ParserInfo`][niveshpy.models.parser.ParserInfo]

### Usage

To use a custom parser, install it in the same virtual environment as NiveshPy and run the command:

```sh
niveshpy parse my_parser
```

NiveshPy will use the name defined in your `pyproject.toml` as a unique key (in this example, `my_parser`).

???+ warning
    If another installed parser has the same key, your parser may be overwritten.
    If this happens, a warning will be logged.
    If you find yourself in this situation, you can change your parser key or advise the user to uninstall the other parser.

### Shell Completion

[NiveshPy CLI](../cli/index.md) supports shell completion. If the user types the partial command `niveshpy parse ...` and presses ++tab++, the CLI will look for parsers with keys starting with the partial key entered by the user (or all parsers if no key is provided).
Depending on the terminal, the CLI will show a list of all such keys along with the name defined in your [`ParserInfo.name`][niveshpy.models.parser.ParserInfo.name]

???+ tip
    For this reason, it is recommended that your parser factory return a `ParserInfo` object quickly. Do not write any initialization code in your parser factory. Any initialization code can be placed in the `create_parser` method as that will only be called after the user has run the parse command.

### Example

<!-- markdownlint-disable MD046 MD009 -->
??? example "Example custom parser"

    ```py
    class SampleParser:
        def __init__(self, file_path: str):
            with open(file_path) as f:
                self.data = json.loads(f.read())
        def get_date_range(self) -> tuple[datetime.date, datetime.date]:
            return self.data.start_date, self.data.end_date  # (1)
        def get_accounts(self) -> list[AccountCreate]:
            return [
                AccountCreate(name=acc.name, institution=acc.org, properties={"source": "sample"})  # (2)
                for acc in self.data.accounts
            ]
        def get_securities(self) -> Iterable[SecurityCreate]:
            for acc in self.data.accounts:
                for sec in acc.securities:
                    yield SecurityCreate(
                        key=sec.key,
                        name=sec.name,
                        type=SecurityType.OTHER,
                        category=SecurityCategory.OTHER,
                        properties={"source": "sample", "isin": sec.isin},  # (3)
                    )
        def get_transactions(
            self, accounts: Iterable[AccountPublic]
        ) -> Iterable[TransactionCreate]:
            accounts_map = {(acc.name, acc.institution): acc.id for acc in accounts}
            for acc in self.data.accounts:
                account_id = accounts_map.get((acc.name, acc.org))
                for sec in acc.securities:
                    for transaction in sec.transactions:
                        txn_type = TransactionType(transaction.type.lower())
                        txn = TransactionCreate(
                            transaction_date=transaction.date,
                            type=txn_type,
                            description=transaction.description,
                            amount=transaction.amount,
                            units=transaction.units,
                            security_key=sec.key,
                            account_id=account_id,
                            properties={"source": "sample"},
                        )
                        yield txn
    class SampleParserFactory:
        @classmethod
        def get_parser_info(cls) -> ParserInfo:
            return ParserInfo(
                name="Sample Parser",
                description="Sample parser.",
                file_extensions=[".json"],
                password_required=False,  # (4)
            )
        @classmethod
        def create_parser(
            cls, file_path: Path, password: str | None = None
        ) -> SampleParser:
            file_path = file_path.as_posix()
            return SampleParser(file_path)
    ```
    
    1. Transactions for all provided security-account combinations in the given date-range will be overwritten. This is to ensure transactions remain accurate and current. Keep this in mind when returning these dates.
    2. It's a good practice to include a `source` key in the metadata dictionary for any object you are returning.
    3. You can also include other key-value pairs in the metadata dictionary that may be relevant.
    4. If password_required is True, the user will be prompted for a password.

    The above example is for illustrative purposes only. The code above may need to be modified to work.
<!-- markdownlint-enable MD046 MD009 -->

## API Reference

::: niveshpy.models.parser.ParserInfo
    options:
        show_root_heading: true
        show_root_full_path: false
        heading_level: 3

::: niveshpy.models.parser.Parser
    options:
        show_root_heading: true
        show_root_full_path: false
        heading_level: 3

::: niveshpy.models.parser.ParserFactory
    options:
        show_root_heading: true
        show_root_full_path: false
        heading_level: 3
