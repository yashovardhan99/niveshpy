# Price Providers

A price provider is used to provide historical or current [prices](../cli/prices.md) for [securities](../cli/securities.md).

## Bundled Providers

NiveshPy comes bundled with a few useful providers.

| Provider Name | Description                           | Command                                |
| ------------- | ------------------------------------- | -------------------------------------- |
| AMFI          | Provide mutual fund prices from AMFI. | `niveshpy prices sync --provider amfi` |

## Custom Providers

You can create your own custom price provider for NiveshPy with Python.

In your `pyproject.toml` file, include an [entry point](https://packaging.python.org/en/latest/specifications/entry-points/) with the group `niveshpy.providers.price`.

```toml
[project.entry-points."niveshpy.providers.price"] # (1)
my_provider = "my_plugin:MyPluginFactory" # (2)
```

1. This needs to be added as-is to ensure NiveshPy can find your provider.
2. Replace `my_provider` with a unique key, and replace the string with a reference to your `PluginFactory` class.

Create a class `my_plugin.MyPluginFactory` that follows the protocol [`ProviderFactory`][niveshpy.models.provider.ProviderFactory].
This factory will be responsible for actually creating the provider object with the input file and password.

The [`create_provider`][niveshpy.models.provider.ProviderFactory.create_provider] method must return an instance of a class that follows the protocol [`Provider`][niveshpy.models.provider.Provider].

The [`get_provider_info`][niveshpy.models.provider.ProviderFactory.get_provider_info] method must return an object of type [`ProviderInfo`][niveshpy.models.provider.ProviderInfo]

### Usage

To use a custom price provider, install it in the same virtual environment as NiveshPy and run the command:

```sh
niveshpy prices sync --provider my_provider
```

NiveshPy will use the name defined in your `pyproject.toml` as a unique key (in this example, `my_provider`).

???+ warning
    If another installed price provider has the same key, your provider may be overwritten.
    If this happens, a warning will be logged.
    If you find yourself in this situation, you can change your provider key or advise the user to uninstall the other provider.

### Shell Completion

[NiveshPy CLI](../cli/index.md) supports shell completion. If the user types the partial command `niveshpy prices sync --provider ...` and presses ++tab++, the CLI will look for providers with keys starting with the partial key entered by the user (or all providers if no key is provided).
Depending on the terminal, the CLI will show a list of all such keys along with the name defined in your [`ProviderInfo.name`][niveshpy.models.provider.ProviderInfo.name]

???+ tip
    For this reason, it is recommended that your provider factory return a `ProviderInfo` object quickly. Do not write any initialization code in your provider factory. Any initialization code can be placed in the `create_provider` method as that will only be called after the user has run the relevant command.

## API Reference

::: niveshpy.models.provider.ProviderInfo
    options:
        show_root_heading: true
        show_root_full_path: false
        heading_level: 3

::: niveshpy.models.provider.Provider
    options:
        show_root_heading: true
        show_root_full_path: false
        heading_level: 3

::: niveshpy.models.provider.ProviderFactory
    options:
        show_root_heading: true
        show_root_full_path: false
        heading_level: 3
