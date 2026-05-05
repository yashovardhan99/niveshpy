"""Tests for the SQLite Query Builder."""

import pytest

from niveshpy.infrastructure.sqlite.query import Query, or_


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
        q = Query().select("id", all=True)
        assert "SELECT ALL\n" in str(q)

    def test_select_distinct_and_all_raises(self):
        """Test that using both DISTINCT and ALL raises a ValueError."""
        with pytest.raises(ValueError, match="Cannot use both DISTINCT and ALL"):
            Query().select("id", distinct=True, all=True)


class TestFromClause:
    """Tests for the FROM clause of the Query Builder."""

    def test_simple_from(self):
        """Test basic FROM with a single table."""
        q = Query().select("*").from_("users")
        sql = str(q)
        assert "FROM\n  users\n" in sql

    def test_from_with_alias(self):
        """Test FROM with table alias."""
        q = Query().select("*").from_(("users", "u"))
        assert "users AS u" in str(q)

    def test_multiple_from(self):
        """Test FROM with multiple tables."""
        q = Query().select("*").from_("users", "orders")
        sql = str(q)
        assert "users,\n" in sql
        assert "orders\n" in sql


class TestWhereClause:
    """Tests for the WHERE clause of the Query Builder."""

    def test_where_no_params(self):
        """Test WHERE clause with no parameters."""
        q = Query().select("*").from_("users").where("active = 1")
        assert "WHERE\n  active = 1\n" in str(q)
        assert q.params == ()

    def test_where_single_param(self):
        """Test WHERE clause with a single parameter."""
        q = Query().select("*").from_("users").where(("age > ?", 18))
        assert "WHERE\n  age > ?\n" in str(q)
        assert q.params == (18,)

    def test_where_two_params(self):
        """Test WHERE clause with two parameters."""
        q = (
            Query()
            .select("*")
            .from_("users")
            .where(("created_at BETWEEN ? AND ?", "2023-01-01", "2023-12-31"))
        )
        assert q.params == ("2023-01-01", "2023-12-31")

    def test_where_multiple_conditions(self):
        """Test WHERE clause with multiple conditions combined with AND."""
        q = (
            Query()
            .select("*")
            .from_("users")
            .where(("age > ?", 18), ("status = ?", "active"))
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
            .where(or_(("status = ?", "active"), ("status = ?", "pending")))
        )
        sql = str(q)
        assert "(status = ? OR status = ?)" in sql
        assert q.params == ("active", "pending")

    def test_where_or_mixed_with_and(self):
        """Test OR group combined with AND conditions."""
        q = (
            Query()
            .select("*")
            .from_("users")
            .where(
                ("age > ?", 18),
                or_(("status = ?", "active"), ("status = ?", "pending")),
            )
        )
        sql = str(q)
        assert "age > ?" in sql
        assert "AND (status = ? OR status = ?)" in sql
        assert q.params == (18, "active", "pending")

    def test_where_or_no_params(self):
        """Test OR with conditions that have no parameters."""
        q = (
            Query()
            .select("*")
            .from_("users")
            .where(or_("deleted_at IS NULL", "active = 1"))
        )
        sql = str(q)
        assert "(deleted_at IS NULL OR active = 1)" in sql
        assert q.params == ()


class TestJoinClause:
    """Tests for the JOIN clause of the Query Builder."""

    def test_inner_join(self):
        """Test INNER JOIN with a simple condition."""
        q = (
            Query()
            .select("u.id", "o.id")
            .from_("users u")
            .join("orders o", "u.id = o.user_id")
        )
        sql = str(q)
        assert "JOIN orders o\n" in sql
        assert "ON\n  u.id = o.user_id\n" in sql

    def test_left_join(self):
        """Test LEFT JOIN with a simple condition."""
        q = (
            Query()
            .select("*")
            .from_("users u")
            .join("orders o", "u.id = o.user_id", type="left")
        )
        assert "LEFT JOIN orders o\n" in str(q)

    def test_cross_join_no_on(self):
        """Test CROSS JOIN without an ON condition."""
        q = (
            Query()
            .select("a.id", "b.id")
            .from_("table_a a")
            .join("table_b b", type="cross")
        )
        sql = str(q)
        assert "CROSS JOIN table_b b\n" in sql
        assert "ON" not in sql
        assert q.params == ()

    def test_join_with_parameterized_condition(self):
        """Test JOIN with a parameterized condition in the ON clause."""
        q = (
            Query()
            .select("*")
            .from_("users u")
            .join("orders o", "u.id = o.user_id", ("o.amount > ?", 100))
        )
        sql = str(q)
        assert "JOIN orders o\n" in sql
        assert "AND o.amount > ?\n" in sql
        assert q.params == (100,)

    def test_join_with_alias_tuple(self):
        """Test JOIN with table specified as a tuple alias."""
        q = (
            Query()
            .select("*")
            .from_("users u")
            .join(("orders", "o"), "u.id = o.user_id")
        )
        assert "JOIN orders AS o\n" in str(q)

    def test_multiple_joins(self):
        """Test chaining multiple JOINs in a single query."""
        q = (
            Query()
            .select("u.id", "o.id", "p.id")
            .from_("users u")
            .join("orders o", "u.id = o.user_id")
            .join("products p", "o.product_id = p.id")
        )
        sql = str(q)
        assert "JOIN orders o\n" in sql
        assert "JOIN products p\n" in sql

    def test_join_appears_before_where_in_sql(self):
        """Test that JOIN clause appears before WHERE in generated SQL."""
        q = (
            Query()
            .select("*")
            .from_("users u")
            .join("orders o", "u.id = o.user_id")
            .where(("u.age > ?", 18))
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
            .from_("users u")
            .join("orders o", "u.id = o.user_id", ("o.amount > ?", 500))
            .where(("u.age > ?", 18))
        )
        assert q.params == (500, 18)

    def test_join_params_between_cte_and_where(self):
        """Test param order is CTE → JOIN → WHERE."""
        cte = Query().select("id").from_("orders").where(("amount > ?", 1000))
        q = (
            Query()
            .with_cte("big_orders", cte)
            .select("*")
            .from_("users u")
            .join("big_orders o", ("o.user_id = u.id AND o.amount > ?", 2000))
            .where(("u.status = ?", "active"))
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
            .having(("COUNT(*) > ?", 5))
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
        inner = Query().select("id").from_("users").where(("active = ?", 1))
        q = Query().with_cte("active_users", inner).select("*").from_("active_users")
        sql = str(q)
        assert sql.startswith("WITH active_users AS (\n")
        assert q.params == (1,)

    def test_multiple_ctes(self):
        """Test multiple CTEs separated by commas."""
        cte1 = Query().select("id").from_("users").where(("active = ?", 1))
        cte2 = Query().select("id").from_("orders").where(("amount > ?", 100))
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
        result = q.select("*").from_("users").where("1=1").order_by("id").limit(5)
        assert result is q


class TestParamOrdering:
    """Tests for parameter ordering in the query."""

    def test_full_query_param_order(self):
        """Params follow SQL clause order: CTE → JOIN → WHERE → HAVING → LIMIT → OFFSET."""
        cte = Query().select("id").from_("orders").where(("amount > ?", 1000))
        q = (
            Query()
            .with_cte("big_orders", cte)
            .select("u.id", "COUNT(*)")
            .from_("users u")
            .join("big_orders o", ("o.user_id = u.id AND o.qty > ?", 5))
            .where(("u.status = ?", "active"))
            .group_by("u.id")
            .having(("COUNT(*) > ?", 3))
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
            .from_("users u")
            .join("orders o", "u.id = o.user_id")
            .where(("u.age > ?", 18))
            .group_by("u.id")
            .having(("COUNT(*) > ?", 1))
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
