# CLI

NiveshPy provides an easy-to-use CLI to manage your investments right from your terminal.

**Usage:**

```bash
niveshpy [<options>] <command> ...
```

The following sub-commands are available:

{% for nav1 in navigation %}
    {% if nav1.title == 'CLI' %}
        {% for child in nav1.children %}
            {% if child.title != 'CLI' and child.title != 'Queries' %}
- [{{ child.title }}]( {{ child.canonical_url }} )
            {% endif %}
        {% endfor %}
    {% endif %}
{% endfor %}

## Global Options

```txt
  -v, --version           Show the version and exit.
  -d, --debug, --verbose  Enable verbose logging.
  --no-color              Disable colored output.
  -h, --help              Show this message and exit.
```

## Quick Start

To get started quickly, import your mutual fund CAS using:

```sh
niveshpy parse cas <path-to-file>
```

This will automatically import all your folios, funds and transactions into NiveshPy.
