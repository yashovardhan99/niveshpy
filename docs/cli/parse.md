# Parse

::: mkdocs-click
    :module: niveshpy.cli.parse
    :command: parse
    :prog_name: niveshpy parse
    :depth: 1
    :list_subcommands: true

## Parsers

NiveshPy comes bundled with a few useful parsers. However, you can use any custom parser with NiveshPy as well.

### Bundled Parsers

| Parser Name | Description                                                         | Command                  |
| ----------- | ------------------------------------------------------------------- | ------------------------ |
| CAS Parser  | Parser for CAMS and Kfintech Consolidated Account Statements (CAS). | `niveshpy parse cas ...` |

### Custom Parsers

To learn how to create your own custom parser, check [our guide](../advanced/parsers.md#custom-parsers)
