# Prices

::: mkdocs-click
    :module: niveshpy.cli.price
    :command: prices
    :prog_name: niveshpy prices
    :depth: 1
    :list_subcommands: true

## Price Providers

NiveshPy comes bundled with a few useful providers. However, you can use your own custom provider as well.

### Bundled Providers

| Provider Name | Description                           | Command                                |
| ------------- | ------------------------------------- | -------------------------------------- |
| AMFI          | Provide mutual fund prices from AMFI. | `niveshpy prices sync --provider amfi` |

### Custom Providers

To learn how to create your own custom provider, check [our guide](../advanced/providers.md#custom-providers)
