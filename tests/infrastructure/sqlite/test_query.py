"""Tests for the SQLite Query Builder."""

import pytest

from niveshpy.infrastructure.sqlite.query import Col, Delete, Fn, Insert, Query, or_


class TestSelectClause:
    """Tests for the SELECT clause of the Query Builder."""

    def test_simple_select(self):
        """Test basic SELECT with multiple columns."""
        q = Query().select("id", "name")
        assert str(q) == "SELECT\n  id,\n  name\n"
        assert q.params == ()

    def test_select_with_alias(self):
        """Test SELECT with column alias."""
        q = Query().select(("name", "username"))
        assert "name AS username" in str(q)

    def test_select_distinct(self):
        """Test SELECT with DISTINCT keyword."""
        q = Query().select("id", distinct=True)
        assert "SELECT DISTINCT\n" in str(q)

    def test_select_all(self):
        """Test SELECT with ALL keyword."""
        q = Query().select("id", all_=True)
        assert "SELECT ALL\n" in str(q)

    def test_select_distinct_and_all_raises(self):
        """Test that using both DISTINCT and ALL raises a ValueError."""
        with pytest.raises(ValueError, match="Cannot use both DISTINCT and ALL"):
            Query().select("id", distinct=True, all_=True)


class TestFromClause:
    """Tests for the FROM clause of the Query Builder."""

    def test_simple_from(self):
        """Test basic FROM with a single table."""
        q = Query().select("*").from_("users")
        sql = str(q)
        assert 'FROM\n  "users"\n' in sql

    def test_from_with_alias(self):
        """Test FROM with table alias."""
        q = Query().select("*").from_(("users", "u"))
        assert '"users" AS u' in str(q)

    def test_multiple_from(self):
        """Test FROM with multiple tables."""
        q = Query().select("*").from_("users", "orders")
        sql = str(q)
        assert '"users",' in sql
        assert '"orders"' in sql

    def test_from_with_whitespace_raises(self):
        """Test that FROM rejects table names with whitespace."""
        with pytest.raises(ValueError, match="contains whitespace"):
            Query().select("*").from_("users u")

    def test_from_with_tab_raises(self):
        """Test that FROM rejects table names with tab whitespace."""
        with pytest.raises(ValueError, match="contains whitespace"):
            Query().select("*").from_("users\tu")

    def test_from_with_newline_raises(self):
        """Test that FROM rejects table names with newline whitespace."""
        with pytest.raises(ValueError, match="contains whitespace"):
            Query().select("*").from_("users\nu")


class TestWhereClause:
    """Tests for the WHERE clause of the Query Builder."""

    def test_where_no_params(self):
        """Test WHERE clause with no parameters."""
        q = Query().select("*").from_("users").where(Col("active").eq(1))
        assert 'WHERE\n  "active" = ?\n' in str(q)
        assert q.params == (1,)

    def test_where_single_param(self):
        """Test WHERE clause with a single parameter."""
        q = Query().select("*").from_("users").where(Col("age").gt(18))
        assert 'WHERE\n  "age" > ?\n' in str(q)
        assert q.params == (18,)

    def test_where_two_params(self):
        """Test WHERE clause with two parameters."""
        q = (
            Query()
            .select("*")
            .from_("users")
            .where(Col("created_at").between("2023-01-01", "2023-12-31"))
        )
        assert q.params == ("2023-01-01", "2023-12-31")

    def test_where_multiple_conditions(self):
        """Test WHERE clause with multiple conditions combined with AND."""
        q = (
            Query()
            .select("*")
            .from_("users")
            .where(Col("age").gt(18), Col("status").eq("active"))
        )
        sql = str(q)
        assert "AND" in sql
        assert q.params == (18, "active")

    def test_where_or_conditions(self):
        """Test WHERE clause with OR-combined conditions."""
        q = (
            Query()
            .select("*")
            .from_("users")
            .where(or_(Col("status").eq("active"), Col("status").eq("pending")))
        )
        sql = str(q)
        assert '("status" = ? OR "status" = ?)' in sql
        assert q.params == ("active", "pending")

    def test_where_or_mixed_with_and(self):
        """Test OR group combined with AND conditions."""
        q = (
            Query()
            .select("*")
            .from_("users")
            .where(
                Col("age").gt(18),
                or_(Col("status").eq("active"), Col("status").eq("pending")),
            )
        )
        sql = str(q)
        assert '"age" > ?' in sql
        assert 'AND ("status" = ? OR "status" = ?)' in sql
        assert q.params == (18, "active", "pending")

    def test_where_or_no_params(self):
        """Test OR with conditions that have no parameters."""
        q = (
            Query()
            .select("*")
            .from_("users")
            .where(or_(Col("deleted_at").is_null(), Col("active").eq(Col("active"))))
        )
        sql = str(q)
        assert '("deleted_at" IS NULL OR "active" = "active")' in sql
        assert q.params == ()


class TestJoinClause:
    """Tests for the JOIN clause of the Query Builder."""

    def test_inner_join(self):
        """Test INNER JOIN with a simple condition."""
        q = (
            Query()
            .select("u.id", "o.id")
            .from_("users", "u")
            .join(("orders", "o"), Col("u", "id").eq(Col("o", "user_id")))
        )
        sql = str(q)
        assert 'JOIN "orders" AS o\n' in sql
        assert 'ON\n  "u"."id" = "o"."user_id"\n' in sql

    def test_left_join(self):
        """Test LEFT JOIN with a simple condition."""
        q = (
            Query()
            .select("*")
            .from_("users", "u")
            .join(("orders", "o"), Col("u", "id").eq(Col("o", "user_id")), type="left")
        )
        assert 'LEFT JOIN "orders" AS o\n' in str(q)

    def test_cross_join_no_on(self):
        """Test CROSS JOIN without an ON condition."""
        q = (
            Query()
            .select("a.id", "b.id")
            .from_("table_a", "a")
            .join(("table_b", "b"), type="cross")
        )
        sql = str(q)
        assert 'CROSS JOIN "table_b" AS b\n' in sql
        assert "ON" not in sql
        assert q.params == ()

    def test_join_with_parameterized_condition(self):
        """Test JOIN with a parameterized condition in the ON clause."""
        q = (
            Query()
            .select("*")
            .from_("users", "u")
            .join(
                ("orders", "o"),
                Col("u", "id").eq(Col("o", "user_id")),
                Col("o", "amount").gt(100),
            )
        )
        sql = str(q)
        assert 'JOIN "orders" AS o\n' in sql
        assert 'AND "o"."amount" > ?\n' in sql
        assert q.params == (100,)

    def test_join_with_alias_tuple(self):
        """Test JOIN with table specified as a tuple alias."""
        q = (
            Query()
            .select("*")
            .from_("users", "u")
            .join(("orders", "o"), Col("u", "id").eq(Col("o", "user_id")))
        )
        assert 'JOIN "orders" AS o\n' in str(q)

    def test_multiple_joins(self):
        """Test chaining multiple JOINs in a single query."""
        q = (
            Query()
            .select("u.id", "o.id", "p.id")
            .from_("users", "u")
            .join(("orders", "o"), Col("u", "id").eq(Col("o", "user_id")))
            .join(("products", "p"), Col("o", "product_id").eq(Col("p", "id")))
        )
        sql = str(q)
        assert 'JOIN "orders" AS o\n' in sql
        assert 'JOIN "products" AS p\n' in sql

    def test_join_with_whitespace_raises(self):
        """Test that JOIN rejects table names with whitespace."""
        with pytest.raises(ValueError, match="contains whitespace"):
            Query().select("*").from_("users").join(
                "orders o", Col("users.id").eq(Col("orders.user_id"))
            )

    def test_join_with_tab_raises(self):
        """Test that JOIN rejects table names with tab whitespace."""
        with pytest.raises(ValueError, match="contains whitespace"):
            Query().select("*").from_("users").join(
                "orders\to", Col("users.id").eq(Col("orders.user_id"))
            )

    def test_join_with_newline_raises(self):
        """Test that JOIN rejects table names with newline whitespace."""
        with pytest.raises(ValueError, match="contains whitespace"):
            Query().select("*").from_("users").join(
                "orders\no", Col("users.id").eq(Col("orders.user_id"))
            )

    def test_join_appears_before_where_in_sql(self):
        """Test that JOIN clause appears before WHERE in generated SQL."""
        q = (
            Query()
            .select("*")
            .from_(("users", "u"))
            .join(("orders", "o"), Col("u", "id").eq(Col("o", "user_id")))
            .where(Col("u", "age").gt(18))
        )
        sql = str(q)
        join_pos = sql.index("JOIN")
        where_pos = sql.index("WHERE")
        assert join_pos < where_pos

    def test_join_params_before_where_params(self):
        """Test that JOIN params come before WHERE params in param tuple."""
        q = (
            Query()
            .select("*")
            .from_(("users", "u"))
            .join(
                ("orders", "o"),
                Col("u", "id").eq(Col("o", "user_id")),
                Col("o", "amount").gt(500),
            )
            .where(Col("u", "age").gt(18))
        )
        assert q.params == (500, 18)

    def test_join_params_between_cte_and_where(self):
        """Test param order is CTE → JOIN → WHERE."""
        cte = Query().select("id").from_("orders").where(Col("amount").gt(1000))
        q = (
            Query()
            .with_cte("big_orders", cte)
            .select("*")
            .from_(("users", "u"))
            .join(
                ("big_orders", "o"),
                Col("o", "user_id").eq(Col("u", "id")),
                Col("o", "amount").gt(2000),
            )
            .where(Col("u", "status").eq("active"))
        )
        assert q.params == (1000, 2000, "active")


class TestGroupByClause:
    """Tests for the GROUP BY clause of the Query Builder."""

    def test_group_by(self):
        """Test basic GROUP BY with a single column."""
        q = Query().select("country", "COUNT(*)").from_("users").group_by("country")
        assert "GROUP BY\n  country\n" in str(q)


class TestHavingClause:
    """Tests for the HAVING clause of the Query Builder."""

    def test_having_with_param(self):
        """Test HAVING clause with a parameterized condition."""
        q = (
            Query()
            .select("country", "COUNT(*)")
            .from_("users")
            .group_by("country")
            .having(Fn("COUNT", Col("*")).gt(5))
        )
        sql = str(q)
        assert "HAVING\n  COUNT(*) > ?\n" in sql
        assert q.params == (5,)


class TestOrderByClause:
    """Tests for the ORDER BY clause of the Query Builder."""

    def test_order_by(self):
        """Test ORDER BY with a single column."""
        q = Query().select("*").from_("users").order_by("name ASC")
        assert "ORDER BY\n  name ASC\n" in str(q)

    def test_multiple_order_by(self):
        """Test ORDER BY with multiple columns."""
        q = Query().select("*").from_("users").order_by("name ASC", "id DESC")
        sql = str(q)
        assert "name ASC,\n" in sql
        assert "id DESC\n" in sql


class TestLimitOffset:
    """Tests for the LIMIT and OFFSET clauses of the Query Builder."""

    def test_limit(self):
        """Test LIMIT clause adds parameter placeholder."""
        q = Query().select("*").from_("users").limit(10)
        assert "LIMIT ?\n" in str(q)
        assert q.params == (10,)

    def test_offset(self):
        """Test OFFSET clause adds parameter placeholder."""
        q = Query().select("*").from_("users").limit(10).offset(20)
        assert "OFFSET ?\n" in str(q)
        assert q.params == (10, 20)


class TestCTE:
    """Tests for Common Table Expressions (CTEs)."""

    def test_simple_cte(self):
        """Test a single CTE wrapping a subquery."""
        inner = Query().select("id").from_("users").where(Col("active").eq(1))
        q = Query().with_cte("active_users", inner).select("*").from_("active_users")
        sql = str(q)
        assert sql.startswith("WITH active_users AS (\n")
        assert q.params == (1,)

    def test_multiple_ctes(self):
        """Test multiple CTEs separated by commas."""
        cte1 = Query().select("id").from_("users").where(Col("active").eq(1))
        cte2 = Query().select("id").from_("orders").where(Col("amount").gt(100))
        q = (
            Query()
            .with_cte("active_users", cte1)
            .with_cte("big_orders", cte2)
            .select("*")
            .from_("active_users")
        )
        sql = str(q)
        assert "active_users AS (" in sql
        assert "big_orders AS (" in sql
        assert q.params == (1, 100)


class TestFluentChaining:
    """Tests for fluent API chaining behavior."""

    def test_chaining_returns_same_instance(self):
        """Test that all builder methods return the same Query instance."""
        q = Query()
        result = q.select("*").from_("users").order_by("id").limit(5)
        assert result is q


class TestParamOrdering:
    """Tests for parameter ordering in the query."""

    def test_full_query_param_order(self):
        """Params follow SQL clause order: CTE → JOIN → WHERE → HAVING → LIMIT → OFFSET."""
        cte = Query().select("id").from_("orders").where(Col("amount").gt(1000))
        q = (
            Query()
            .with_cte("big_orders", cte)
            .select("u.id", "COUNT(*)")
            .from_(("users", "u"))
            .join(
                ("big_orders", "o"),
                Col("o", "user_id").eq(Col("u", "id")),
                Col("o", "qty").gt(5),
            )
            .where(Col("u", "status").eq("active"))
            .group_by("u.id")
            .having(Fn("COUNT", Col("*")).gt(3))
            .order_by("u.id")
            .limit(10)
            .offset(20)
        )
        assert q.params == (1000, 5, "active", 3, 10, 20)


class TestSQLClauseOrdering:
    """Tests for SQL clause ordering in generated output."""

    def test_clause_order(self):
        """SQL clauses appear in standard order regardless of builder call order."""
        q = (
            Query()
            .select("u.id", "COUNT(*)")
            .from_(("users", "u"))
            .join(("orders", "o"), Col("u", "id").eq(Col("o", "user_id")))
            .where(Col("u", "age").gt(18))
            .group_by("u.id")
            .having(Fn("COUNT", Col("*")).gt(1))
            .order_by("u.id")
            .limit(10)
            .offset(0)
        )
        sql = str(q)
        positions = [
            sql.index("SELECT"),
            sql.index("FROM"),
            sql.index("JOIN"),
            sql.index("WHERE"),
            sql.index("GROUP BY"),
            sql.index("HAVING"),
            sql.index("ORDER BY"),
            sql.index("LIMIT"),
            sql.index("OFFSET"),
        ]
        assert positions == sorted(positions)


class TestInsert:
    """Tests for the INSERT statement builder."""

    def test_simple_insert(self):
        """Test basic INSERT INTO with columns and values."""
        stmt = (
            Insert()
            .into("accounts")
            .columns("name", "institution")
            .values_("Foo", "Bar")
        )
        sql = str(stmt)
        assert "INSERT" in sql
        assert 'INTO "accounts"' in sql
        assert '("name", "institution")' in sql
        assert "VALUES" in sql
        assert "(?, ?)" in sql
        assert stmt.params == ("Foo", "Bar")

    def test_insert_or_ignore(self):
        """Test INSERT OR IGNORE flag."""
        stmt = (
            Insert()
            .or_ignore()
            .into("accounts")
            .columns("name", "institution")
            .values_("Foo", "Bar")
        )
        sql = str(stmt)
        assert "INSERT OR IGNORE" in sql
        assert 'INTO "accounts"' in sql
        assert stmt.params == ("Foo", "Bar")

    def test_insert_or_replace(self):
        """Test INSERT OR REPLACE flag."""
        stmt = (
            Insert()
            .or_replace()
            .into("prices")
            .columns("security_key", "date", "close")
            .values_("AXIS123", "2024-01-01", 150.5)
        )
        sql = str(stmt)
        assert "INSERT OR REPLACE" in sql
        assert 'INTO "prices"' in sql
        assert "(?, ?, ?)" in sql
        assert stmt.params == ("AXIS123", "2024-01-01", 150.5)

    def test_insert_returning(self):
        """Test RETURNING clause on insert."""
        stmt = (
            Insert()
            .into("accounts")
            .columns("name")
            .values_("Foo")
            .returning(Col("id").alias(None))
        )
        sql = str(stmt)
        assert 'RETURNING "id"' in sql

    def test_insert_returning_with_alias(self):
        """Test RETURNING clause with aliased column."""
        stmt = (
            Insert()
            .into("accounts")
            .columns("name")
            .values_("Foo")
            .returning(Col("name").alias("account_name"))
        )
        sql = str(stmt)
        assert 'RETURNING "name" AS account_name' in sql

    def test_insert_bulk_values(self):
        """Test multiple .values_() calls produce multi-row VALUES."""
        stmt = (
            Insert()
            .into("accounts")
            .columns("name", "institution")
            .values_("A", "X")
            .values_("B", "Y")
        )
        sql = str(stmt)
        assert sql.count("(?, ?)") == 1

    def test_insert_params_single_row(self):
        """Test params for a single row insert."""
        stmt = Insert().into("t").columns("a", "b", "c").values_(1, 2, 3)
        assert stmt.params == (1, 2, 3)

    def test_insert_params_bulk(self):
        """Test params are flattened across multiple rows."""
        stmt = (
            Insert()
            .into("t")
            .columns("a", "b")
            .values_(1, 2)
            .values_(3, 4)
            .values_(5, 6)
        )
        assert stmt.params == (1, 2, 3, 4, 5, 6)

    def test_insert_no_table_raises(self):
        """Test ValueError when table is not specified."""
        stmt = Insert().columns("a").values_(1)
        with pytest.raises(ValueError, match="Table must be specified"):
            str(stmt)

    def test_insert_value_count_mismatch_raises(self):
        """Test ValueError when values count doesn't match columns."""
        stmt = Insert().into("t").columns("a", "b")
        with pytest.raises(ValueError, match="Expected 2 values, got 3"):
            stmt.values_(1, 2, 3)

    def test_insert_chaining(self):
        """Test fluent API returns same instance."""
        stmt = Insert()
        result = (
            stmt.or_ignore()
            .into("t")
            .columns("a")
            .values_(1)
            .returning(Col("id").alias(None))
        )
        assert result is stmt

    def test_on_conflict_do_update_generates_correct_sql(self):
        """Test single conflict column + multiple update columns generates correct ON CONFLICT DO UPDATE."""
        stmt = (
            Insert()
            .into("prices")
            .columns("security_key", "date", "open", "high", "low", "close")
            .values_("AXIS123", "2024-01-01", 100, 110, 90, 105)
            .on_conflict("security_key")
            .do_update("open", "high", "low", "close")
        )
        sql = str(stmt)
        assert 'ON CONFLICT ("security_key")' in sql
        assert "DO UPDATE SET" in sql
        assert '"open" = excluded."open"' in sql
        assert '"high" = excluded."high"' in sql
        assert '"low" = excluded."low"' in sql
        assert '"close" = excluded."close"' in sql
        assert stmt.params == ("AXIS123", "2024-01-01", 100, 110, 90, 105)

    def test_on_conflict_composite_key_conflict_target(self):
        """Test two conflict columns (composite key) appear in ON CONFLICT clause."""
        stmt = (
            Insert()
            .into("prices")
            .columns("security_key", "date", "close")
            .values_("AXIS123", "2024-01-01", 105)
            .on_conflict("security_key", "date")
            .do_update("close")
        )
        sql = str(stmt)
        assert 'ON CONFLICT ("security_key", "date")' in sql
        assert 'DO UPDATE SET "close" = excluded."close"' in sql

    def test_on_conflict_do_nothing_when_no_update_columns(self):
        """Test on_conflict without do_update generates DO NOTHING."""
        stmt = (
            Insert()
            .into("prices")
            .columns("security_key", "date", "close")
            .values_("AXIS123", "2024-01-01", 105)
            .on_conflict("security_key", "date")
        )
        sql = str(stmt)
        assert 'ON CONFLICT ("security_key", "date")' in sql
        assert "DO NOTHING" in sql
        assert "DO UPDATE" not in sql

    def test_on_conflict_params_unchanged(self):
        """Test ON CONFLICT clause doesn't add extra parameters."""
        stmt = (
            Insert()
            .into("prices")
            .columns(
                "security_key", "date", "open", "high", "low", "close", "properties"
            )
            .values_("AXIS123", "2024-01-01", 100, 110, 90, 105, "{}")
            .on_conflict("security_key", "date")
            .do_update("open", "high", "low", "close", "properties")
        )
        # Params should only be the insert values, not anything from the ON CONFLICT clause
        assert stmt.params == ("AXIS123", "2024-01-01", 100, 110, 90, 105, "{}")

    def test_on_conflict_cannot_combine_with_or_replace(self):
        """Test that calling or_replace() after on_conflict() raises ValueError."""
        stmt = (
            Insert()
            .into("prices")
            .columns("security_key", "date", "close")
            .values_("AXIS123", "2024-01-01", 105)
            .on_conflict("security_key", "date")
        )
        with pytest.raises(ValueError, match="Cannot combine OR REPLACE"):
            stmt.or_replace()

    def test_on_conflict_cannot_combine_with_or_ignore(self):
        """Test that calling or_ignore() after on_conflict() raises ValueError."""
        stmt = (
            Insert()
            .into("prices")
            .columns("security_key", "date", "close")
            .values_("AXIS123", "2024-01-01", 105)
            .on_conflict("security_key", "date")
        )
        with pytest.raises(ValueError, match="Cannot combine OR REPLACE"):
            stmt.or_ignore()

    def test_or_replace_before_on_conflict_raises(self):
        """Test that calling on_conflict() after or_replace() raises ValueError."""
        stmt = (
            Insert()
            .into("prices")
            .or_replace()
            .columns("security_key", "date", "close")
            .values_("AXIS123", "2024-01-01", 105)
        )
        with pytest.raises(ValueError, match="Cannot combine ON CONFLICT"):
            stmt.on_conflict("security_key", "date")

    def test_do_update_without_on_conflict_raises(self):
        """Test that calling do_update() without on_conflict() raises ValueError."""
        stmt = (
            Insert()
            .into("prices")
            .columns("security_key", "date", "close")
            .values_("AXIS123", "2024-01-01", 105)
        )
        with pytest.raises(ValueError, match="on_conflict\\(\\) must be called before"):
            stmt.do_update("close")

    def test_on_conflict_do_update_comes_before_returning_in_sql(self):
        """Test that ON CONFLICT appears before RETURNING in generated SQL."""
        stmt = (
            Insert()
            .into("prices")
            .columns("security_key", "date", "close")
            .values_("AXIS123", "2024-01-01", 105)
            .on_conflict("security_key", "date")
            .do_update("close")
            .returning(Col("security_key").alias(None))
        )
        sql = str(stmt)
        conflict_pos = sql.find("ON CONFLICT")
        returning_pos = sql.find("RETURNING")
        assert conflict_pos != -1, "ON CONFLICT not found in SQL"
        assert returning_pos != -1, "RETURNING not found in SQL"
        assert conflict_pos < returning_pos, (
            "ON CONFLICT should appear before RETURNING"
        )


class TestDelete:
    """Tests for the DELETE statement builder."""

    def test_simple_delete(self):
        """Test basic DELETE FROM with WHERE."""
        stmt = Delete().from_("accounts").where(Col("id").eq(5))
        sql = str(stmt)
        assert 'DELETE FROM "accounts"' in sql
        assert "WHERE" in sql
        assert '"id" = ?' in sql
        assert stmt.params == (5,)

    def test_delete_multiple_conditions(self):
        """Test DELETE with multiple AND conditions."""
        stmt = (
            Delete()
            .from_("transactions")
            .where(
                Col("account_id").eq(1),
                Col("transaction_date").ge("2024-01-01"),
            )
        )
        sql = str(stmt)
        assert '"account_id" = ?' in sql
        assert "AND" in sql
        assert '"transaction_date" >= ?' in sql
        assert stmt.params == (1, "2024-01-01")

    def test_delete_with_or(self):
        """Test DELETE with OR-combined conditions."""
        stmt = (
            Delete()
            .from_("accounts")
            .where(or_(Col("name").eq("A"), Col("name").eq("B")))
        )
        sql = str(stmt)
        assert '("name" = ? OR "name" = ?)' in sql
        assert stmt.params == ("A", "B")

    def test_delete_returning(self):
        """Test RETURNING clause on delete."""
        stmt = (
            Delete()
            .from_("accounts")
            .where(Col("id").eq(1))
            .returning(Col("id").alias(None), Col("name").alias(None))
        )
        sql = str(stmt)
        assert 'RETURNING "id", "name"' in sql

    def test_delete_no_table_raises(self):
        """Test ValueError when table is not specified."""
        stmt = Delete().where(Col("id").eq(1))
        with pytest.raises(ValueError, match="Table must be specified"):
            str(stmt)

    def test_delete_no_where(self):
        """Test unconditional DELETE (no WHERE clause)."""
        stmt = Delete().from_("temp_table")
        sql = str(stmt)
        assert 'DELETE FROM "temp_table"' in sql
        assert "WHERE" not in sql
        assert stmt.params == ()

    def test_delete_params(self):
        """Test params collected from all conditions."""
        stmt = (
            Delete()
            .from_("prices")
            .where(
                Col("security_key").eq("AXIS123"),
                Col("date").between("2024-01-01", "2024-12-31"),
            )
        )
        assert stmt.params == ("AXIS123", "2024-01-01", "2024-12-31")

    def test_delete_chaining(self):
        """Test fluent API returns same instance."""
        stmt = Delete()
        result = stmt.from_("t").where(Col("id").eq(1)).returning(Col("id").alias(None))
        assert result is stmt
