# Migration scripts for NiveshPy

NiveshPy uses a sqlite database with sql-alchemy. This folder will house the necessary .sql files to run database migrations.

## Foreign Key Constraints

When using rename and shift method to migrate tables, ensure all old tables are dropped only at the end and taking in account the order of their dependencies. For example, ensure transaction table is dropped before account/security tables to avoid Foreign Key Constraint Failures.
