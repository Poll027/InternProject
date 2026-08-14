import os
import subprocess
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from flask import Flask, jsonify, redirect, render_template, request, session, url_for

from database.db import get_connection

app = Flask(__name__)
app.secret_key = "regwatch-demo-key"

TEAMS = {
    "AI_DATA": {"label": "AI & Data", "icon": "ti-brain"},
    "TAX": {"label": "Tax", "icon": "ti-receipt-tax"},
    "AUDIT": {"label": "Audit", "icon": "ti-clipboard-check"},
    "CYBERSECURITY": {"label": "Cybersecurity", "icon": "ti-shield-lock"},
}


@app.route("/")
def index():
    return redirect(url_for("login"))


@app.route("/login", methods=["GET"])
def login():
    return render_template("login.html", teams=TEAMS)


@app.route("/login", methods=["POST"])
def login_submit():
    team = request.form.get("team")
    if team in TEAMS:
        session["team"] = team
        return redirect(url_for("dashboard"))
    return render_template("login.html", teams=TEAMS)


@app.route("/dashboard")
def dashboard():
    team = session.get("team")
    if not team:
        return redirect(url_for("login"))

    conn = get_connection()

    stats = conn.execute(
        """
        SELECT
            COUNT(*) AS total,
            COALESCE(SUM(CASE WHEN urgency IN ('CRITICAL', 'HIGH') THEN 1 ELSE 0 END), 0) AS critical_high,
            COALESCE(SUM(CASE WHEN created_at >= datetime('now', '-7 days') THEN 1 ELSE 0 END), 0) AS this_week
        FROM findings
        WHERE service_line = ?
        """,
        (team,),
    ).fetchone()

    urgent = conn.execute(
        """
        SELECT findings.id, findings.headline, findings.urgency, findings.confidence_score,
               findings.created_at, source_items.published_date, sources.name AS source_name
        FROM findings
        JOIN source_items ON source_items.id = findings.source_item_id
        JOIN sources ON sources.id = source_items.source_id
        WHERE findings.service_line = ?
          AND findings.urgency IN ('CRITICAL', 'HIGH')
          AND findings.created_at >= datetime('now', '-7 days')
        ORDER BY CASE findings.urgency
            WHEN 'CRITICAL' THEN 1
            WHEN 'HIGH' THEN 2
            WHEN 'MEDIUM' THEN 3
            ELSE 4 END,
        findings.confidence_score DESC
        """,
        (team,),
    ).fetchall()

    monthly = conn.execute(
        """
        SELECT findings.id, findings.headline, findings.urgency, findings.confidence_score,
               findings.created_at, source_items.published_date, sources.name AS source_name
        FROM findings
        JOIN source_items ON source_items.id = findings.source_item_id
        JOIN sources ON sources.id = source_items.source_id
        WHERE findings.service_line = ?
          AND findings.created_at >= datetime('now', '-30 days')
        ORDER BY CASE findings.urgency
            WHEN 'CRITICAL' THEN 1
            WHEN 'HIGH' THEN 2
            WHEN 'MEDIUM' THEN 3
            ELSE 4 END,
        findings.confidence_score DESC
        """,
        (team,),
    ).fetchall()

    sources = conn.execute(
        """
        SELECT sources.name,
               sources.pipeline,
               MAX(COALESCE(source_items.last_seen_at, source_items.first_seen_at)) AS last_active,
               COALESCE(SUM(CASE WHEN source_items.processing_status = 'FETCH_FAILED' THEN 1 ELSE 0 END), 0) AS failure_count,
               COUNT(source_items.id) AS total_items
        FROM sources
        LEFT JOIN source_items ON source_items.source_id = sources.id
        WHERE sources.service_lines LIKE ?
        GROUP BY sources.id
        ORDER BY sources.name
        """,
        (f"%{team}%",),
    ).fetchall()

    errors = conn.execute(
        """
        SELECT source_items.id, source_items.title, source_items.url, source_items.first_seen_at,
               sources.name AS source_name
        FROM source_items
        JOIN sources ON sources.id = source_items.source_id
        WHERE source_items.processing_status = 'FETCH_FAILED'
          AND source_items.first_seen_at >= datetime('now', '-7 days')
          AND sources.service_lines LIKE ?
        ORDER BY source_items.first_seen_at DESC
        LIMIT 5
        """,
        (f"%{team}%",),
    ).fetchall()

    conn.close()

    return render_template(
        "dashboard.html",
        stats=stats,
        urgent=urgent,
        monthly=monthly,
        sources=sources,
        errors=errors,
        team=team,
        team_label=TEAMS[team]["label"],
        teams=TEAMS,
    )


@app.route("/finding/<int:finding_id>")
def finding(finding_id):
    team = session.get("team")
    if not team:
        return redirect(url_for("login"))

    conn = get_connection()

    finding_row = conn.execute(
        """
        SELECT findings.id, findings.service_line, findings.urgency, findings.headline, findings.summary,
               findings.confidence_score, findings.source_url, findings.evidence_excerpt, findings.created_at,
               source_items.title, source_items.published_date,
               sources.name AS source_name
        FROM findings
        JOIN source_items ON source_items.id = findings.source_item_id
        JOIN sources ON sources.id = source_items.source_id
        WHERE findings.id = ?
        """,
        (finding_id,),
    ).fetchone()

    if not finding_row:
        conn.close()
        return redirect(url_for("dashboard"))

    framing = conn.execute(
        """
        SELECT framing_text
        FROM opportunity_framings
        WHERE finding_id = ? AND service_line = ?
        """,
        (finding_id, finding_row["service_line"]),
    ).fetchone()

    conn.close()

    return render_template(
        "finding.html",
        finding=finding_row,
        framing=framing,
        team=team,
        team_label=TEAMS[team]["label"],
        finding_team_label=TEAMS[finding_row["service_line"]]["label"],
    )


@app.route("/switch-team", methods=["POST"])
def switch_team():
    team = request.form.get("team")
    if team in TEAMS:
        session["team"] = team
    return redirect(url_for("dashboard"))


@app.route("/api/run", methods=["POST"])
def api_run():
    try:
        subprocess.Popen(
            [sys.executable, "main.py", "--stages", "rss,fetch,classify,frame"],
            cwd=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
        )
        return jsonify({"status": "started"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)
