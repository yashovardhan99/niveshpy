---
hide:
    - navigation
---

# Getting Started

## Installation

### With pip

To get started, install NiveshPy from [PyPi](https://pypi.org/project/NiveshPy/):

```sh
pip install niveshpy
```

### With git

You can also download the app from GitHub and build it on your own.

First, clone the repository:

```sh
git clone https://github.com/yashovardhan99/niveshpy.git
```

Next, install the package and all it's dependencies with:

```sh
pip install -e niveshpy
```

## Quick Start

After installing, you can simply start using NiveshPy:

```sh
niveshpy <command>
```

### Mutual Funds

Indian mutual fund investors can easily import their CAS statements into NiveshPy.

To import your mutual funds, follow the steps:

1. Go to [CAMS Online](https://www.camsonline.com/Investors/Statements/Consolidated-Account-Statement)
2. Download CAS - CAMS + KFinTech with the following settings:
      1. Statement Type - Detailed (Includes transaction listing)
      2. Period - Specific Period
      3. Select an appropriate From date based on when you started investing in mutual funds.
      4. Leave To date as today's date.
      5. Folio Lising - Transacted folios and folios with balance
      6. Enter your email ID, PAN and a suitable password.
      7. Take a note of this password - you will need this later.
      8. Submit the form
3. You will soon receive an email with your CAS attached.
4. Download the PDF and save it on your PC. Take note of where you saved it.
5. Run the following command:

```sh
niveshpy parse cas <path_to_cas>
```

For instance, if you saved the file at `~/CAS.pdf`, then run

```sh
niveshpy parse cas ~/CAS.pdf
```

You will be prompted for your password, enter the password and follow the prompts to complete importing your mutual fund investments.

## What's next?

NiveshPy comes with a bundle of useful CLI commands to help you analyze your investments. Go to [CLI commands](cli/index.md)
