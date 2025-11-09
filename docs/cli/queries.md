# Queries

This is meant to document what kind of queries will be supported by the CLI and how it's parsing will work.

default: `gold`

This should by-default match a security (with some exceptions based on the command being used).

Spaces can be used to divide into multiple queries:
`gold nifty` which would match any text containing either "nifty" OR "gold".

If you have a space as part of your query, use quotes: `'ABC mutual fund'`

All text queries are case-insensitive and support regex, so you can do things like:  
`'^ABC Mutual Fund'`  
`'Gold ETF$'`  
`'uti (gold|nifty)'`  

If you want to search on specific fields, you can use the following prefixes:

## `acct:<account>`

Matches account name (or institution) containing the regex `<account>`

## `amt:<amount>`

Matches transaction amount.

Amount expressions also support inequality comparisons and range expressions with the following syntax:

- `amt:100` matches an amount of 100 exactly.
- `amt:'>200'` matches all amounts greater than 200.
- `amt:'>=200'` matches all amounts greater than or equal to 200.
- `amt:'<200'` matches all amounts less than 200.
- `amt:'<=200'` matches all amounts less than or equal to 200.
- `amt:100..200` matches all amounts between 100 and 200 (both inclusive).

Do note that amounts can be negative, so you might need to prefix it with a `-` sign to match sale transactions.

## `date:<date>`

`date:<date>` will match either the full date or part of a date.
This expects dates in the format `YYYY-MM-DD`. However, it can also be used with only a part of the format. For example:

- `date:2025` matches all dates between `2025-01-01` and `2025-12-31`
- `date:2025-01` matches all dates in January 2025.

A period can also be provided with the syntax `date:<from>..<to>`. Examples:

- `date:2025-01-01..2025-01-15` matches all records from 1st January 2025 to 15th January 2025.
- `date:2025..2025-02` matches all records from 1st January 2025 to 28th February 2025.

It's important to note that partial date expressions can be used in both `date:<date>` and `date:<from>..<to>` expressions,
but they can have different meanings in both cases. In the case of `<from>`, the date takes the starting of the partial date expression, while in the case of `<to>`, the date takes the end of that expression. Also note, that both `<from>` and `<to>` are optional field, in which case, they will match all records starting with `<from>` or ending at `<to>`. Some examples:

- `date:2025..2026` matches all records from 2025-01-01 to 2026-12-31
- `date:2025-04..2026-03` matches all records from 2025-04-01 to 2026-03-31.
- `date:2025..2025` matches all records from 2025-01-01 to 2025-12-31, though you can just use `date:2025` to get the same result.
- `date:2025..` matches all records starting 2025-01-01.
- `date:..2025` matches all records ending 2025-12-31. Note the different parsing rules for `<from>` and `<to>` dates.

Date cannot be used when querying `securities` or `accounts`.

## `desc:<description>`

Searches the transaction description field.

## `sec:<security>`

Matches across any of the security fields (key, name, type or category) containing the regex `<security>`.

## `type:<type>`

`type:` will match transaction type by default. (It will match security type when running the `securities` command).

## `sec:<security>` or `<security>`

Matches any security matching the regular expression `<security>`.

## Negative queries

`not:query` can be used to negate a query. For example:

- `not:etf` matches all transactions EXCEPT those where the security contains "ETF".

## Space

Space is used to separate individual expressions from each other. If your query has a space, use quotes to avoid separation.

When multiple space separated queries are given, the following order of precedence applies:

- Any negative queries (combined with AND); AND
- An available date filter; AND
- Any amount filters; AND
- Any type expressions; AND
- Any of the description terms; AND
- Any of the account terms; AND
- Any of the security terms;

Multiple expressions of the same type are combined with an OR. So, for example:
`amt:>=100` and `amt:<=200` won't work as intended. Instead, consider using a range filter for such scenarios: `amt:100..200`.

Expressions of different kinds are combined with an `AND`.

## Future scope

- Add support for boolean expressions such as `and` and `or`.
- Consider adding an AI query where users can just add a free text query and it will be parsed via an LLM?
