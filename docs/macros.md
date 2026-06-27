<!-- File containing useful macros -->

{% macro list_pages_l1(page_title, navigation) -%}
    {% for nav1 in navigation %}
        {% if nav1.title == page_title %}
            {% for child in nav1.children %}
                {% if child.title != page_title %}
- [{{ child.title }}]( {{ child.canonical_url }} )
                {% endif %}
            {% endfor %}
        {% endif %}
    {% endfor %}
{%- endmacro %}

{% macro list_pages_l2(top_title, page_title, navigation) -%}
    {% for nav1 in navigation %}
        {% if nav1.title == top_title %}
            {% for nav2 in nav1.children %}
                {% if nav2.title == page_title %}
                    {% for child in nav2.children %}
                        {% if child.title != page_title %}

- [{{ child.title }}]( {{ child.canonical_url }} )

                        {% endif %}
                    {% endfor %}
                {% endif %}
            {% endfor %}
        {% endif %}
    {% endfor %}
{%- endmacro %}
