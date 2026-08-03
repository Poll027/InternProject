def in_clause(column, values):
    if not values:
        return "", ()
    placeholders = ",".join("?" for _ in values)
    return f" AND {column} IN ({placeholders})", tuple(values)

if __name__ == "__main__":
    clause, params = in_clause("sources.name", ["CBN", "SEC"])
    assert clause == " AND sources.name IN (?,?)"
    assert params == ("CBN", "SEC")
    clause, params = in_clause("sources.name", None)
    assert clause == "" and params == ()
    print("in_clause: OK")
