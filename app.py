from flask import Flask, request, session, redirect, url_for, render_template_string
import psycopg2
from psycopg2 import sql

app = Flask(__name__)
app.secret_key = "dev-only-change-me"

PAGE = """
<!doctype html>
<title>LocalDB viewer</title>
<style>
  :root{--b:#e2e6ea;--bg:#fafbfc;--hd:#f1f3f5;--hov:#fff7d6;--mut:#888;--accent:#0366d6}
  *{box-sizing:border-box}
  body{font-family:system-ui;margin:1rem;color:#222}
  input,textarea,button,select{font:inherit;padding:.4rem;border:1px solid var(--b);border-radius:4px}
  button{background:var(--accent);color:#fff;border-color:var(--accent);cursor:pointer}
  textarea{width:100%;min-height:110px;font-family:ui-monospace,Consolas,monospace;font-size:.9rem}
  .row{display:flex;gap:1rem;flex-wrap:wrap;align-items:flex-end}
  .row label{display:flex;flex-direction:column;font-size:.8rem;color:var(--mut)}
  .err{color:#b00;white-space:pre-wrap;background:#fff5f5;padding:.5rem;border-radius:4px}
  .bar{display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem;padding-bottom:.5rem;border-bottom:1px solid var(--b)}
  .layout{display:flex;gap:1rem;align-items:flex-start}
  aside{flex:0 0 220px;max-height:calc(100vh - 80px);overflow:auto;border:1px solid var(--b);border-radius:4px;padding:.5rem;background:var(--bg)}
  aside strong{display:block;margin-bottom:.4rem;font-size:.8rem;text-transform:uppercase;color:var(--mut)}
  aside a{display:block;padding:.25rem .4rem;font-size:.85rem;text-decoration:none;color:#222;border-radius:3px;font-family:ui-monospace,monospace}
  aside a:hover{background:#fff}
  main{flex:1;min-width:0}
  .meta{display:flex;justify-content:space-between;align-items:center;margin:.75rem 0 .25rem;font-size:.85rem;color:var(--mut)}
  .tbl-wrap{border:1px solid var(--b);border-radius:4px;overflow:auto;max-height:70vh;background:#fff}
  table{border-collapse:separate;border-spacing:0;width:100%;font-size:.85rem}
  th,td{padding:.35rem .6rem;border-bottom:1px solid var(--b);border-right:1px solid var(--b);white-space:nowrap;max-width:340px;overflow:hidden;text-overflow:ellipsis;text-align:left;vertical-align:top}
  th:last-child,td:last-child{border-right:0}
  thead th{position:sticky;top:0;background:var(--hd);font-weight:600;cursor:pointer;user-select:none;z-index:1}
  thead th:hover{background:#e6e9ec}
  thead th::after{content:" \\21C5";color:#bbb;font-size:.75em}
  thead th.asc::after{content:" \\2191";color:#222}
  thead th.desc::after{content:" \\2193";color:#222}
  tbody tr:nth-child(even){background:#fafbfc}
  tbody tr:hover{background:var(--hov)}
  td.num{text-align:right;font-variant-numeric:tabular-nums;font-family:ui-monospace,monospace}
  td.null{color:#bbb;font-style:italic}
  td.bool-t{color:#178a4a;font-weight:600}
  td.bool-f{color:#b00;font-weight:600}
  td .rownum{color:var(--mut);font-family:ui-monospace,monospace}
</style>
<script>
function sortCol(th){
  const tbl=th.closest('table'),idx=Array.from(th.parentNode.children).indexOf(th);
  const asc=!th.classList.contains('asc');
  th.parentNode.querySelectorAll('th').forEach(x=>x.classList.remove('asc','desc'));
  th.classList.add(asc?'asc':'desc');
  const rows=Array.from(tbl.tBodies[0].rows);
  const num=rows.every(r=>{const t=r.cells[idx].textContent.trim();return t===''||t==='NULL'||!isNaN(parseFloat(t))});
  rows.sort((a,b)=>{
    let x=a.cells[idx].textContent.trim(),y=b.cells[idx].textContent.trim();
    if(num){x=parseFloat(x)||0;y=parseFloat(y)||0;return asc?x-y:y-x}
    return asc?x.localeCompare(y):y.localeCompare(x);
  });
  rows.forEach(r=>tbl.tBodies[0].appendChild(r));
}
</script>

{% if not connected %}
  <h2>Connect to PostgreSQL</h2>
  <form method=post action="{{ url_for('connect') }}" class=row>
    <label>Host<input name=host value="localhost"></label>
    <label>Port<input name=port value="5432" size=6></label>
    <label>Database<input name=dbname required></label>
    <label>User<input name=user required></label>
    <label>Password<input name=password type=password></label>
    <button>Connect</button>
  </form>
  {% if error %}<p class=err>{{ error }}</p>{% endif %}
{% else %}
  <div class=bar>
    <strong>{{ conn.user }}@{{ conn.host }}/{{ conn.dbname }}</strong>
    <a href="{{ url_for('disconnect') }}">disconnect</a>
  </div>

  <div class=layout>
  <aside>
    <strong>Tables ({{ tables|length }})</strong>
    {% for t in tables %}
      <a href="{{ url_for('view_table', name=t) }}" title="{{ t }}">{{ t }}</a>
    {% endfor %}
  </aside>

  <main>
    <form method=post action="{{ url_for('query') }}">
      <textarea name=sql placeholder="SELECT ...">{{ last_sql or '' }}</textarea>
      <button>Run SQL</button>
    </form>

    {% if error %}<p class=err>{{ error }}</p>{% endif %}

    {% if rows is not none %}
      <div class=meta>
        <span>{{ rows|length }} row(s){% if truncated %} &middot; truncated to 500{% endif %} &middot; {{ cols|length }} column(s)</span>
        <span>click header to sort</span>
      </div>
      <div class=tbl-wrap>
      <table>
        <thead><tr><th title="row">#</th>{% for c in cols %}<th onclick="sortCol(this)" title="{{ c }}">{{ c }}</th>{% endfor %}</tr></thead>
        <tbody>
        {% for r in rows %}
          <tr><td class=rownum>{{ loop.index }}</td>
          {% for v in r %}
            {% if v is none %}<td class=null>NULL</td>
            {% elif v is sameas true %}<td class=bool-t>true</td>
            {% elif v is sameas false %}<td class=bool-f>false</td>
            {% elif v is number %}<td class=num>{{ v }}</td>
            {% else %}<td title="{{ v }}">{{ v }}</td>{% endif %}
          {% endfor %}</tr>
        {% endfor %}
        </tbody>
      </table>
      </div>
    {% endif %}
  </main>
  </div>
{% endif %}
"""


def get_conn():
    c = session.get("conn")
    if not c:
        return None
    return psycopg2.connect(**c)


def list_tables(cur):
    cur.execute("""
        SELECT table_schema || '.' || table_name
        FROM information_schema.tables
        WHERE table_schema NOT IN ('pg_catalog','information_schema')
        ORDER BY 1
    """)
    return [r[0] for r in cur.fetchall()]


def render(**kw):
    kw.setdefault("connected", "conn" in session)
    kw.setdefault("conn", session.get("conn"))
    kw.setdefault("tables", [])
    kw.setdefault("rows", None)
    kw.setdefault("cols", [])
    kw.setdefault("error", None)
    kw.setdefault("last_sql", session.get("last_sql", ""))
    kw.setdefault("truncated", False)
    if kw["connected"] and not kw["tables"]:
        try:
            with get_conn() as c, c.cursor() as cur:
                kw["tables"] = list_tables(cur)
        except Exception as e:
            kw["error"] = str(e)
    return render_template_string(PAGE, **kw)


@app.route("/")
def index():
    return render()


@app.route("/connect", methods=["POST"])
def connect():
    cfg = {k: request.form[k] for k in ("host", "port", "dbname", "user", "password")}
    try:
        psycopg2.connect(**cfg).close()
    except Exception as e:
        return render(error=str(e))
    session["conn"] = cfg
    session.pop("last_sql", None)
    return redirect(url_for("index"))


@app.route("/disconnect")
def disconnect():
    session.clear()
    return redirect(url_for("index"))


@app.route("/table/<name>")
def view_table(name):
    if not get_conn():
        return redirect(url_for("index"))
    schema, _, tbl = name.partition(".")
    q = sql.SQL("SELECT * FROM {}.{} LIMIT 500").format(sql.Identifier(schema), sql.Identifier(tbl))
    session["last_sql"] = q.as_string(get_conn())
    return _run(session["last_sql"])


@app.route("/query", methods=["POST"])
def query():
    if not get_conn():
        return redirect(url_for("index"))
    session["last_sql"] = request.form.get("sql", "")
    return _run(session["last_sql"])


def _run(sql_text):
    try:
        with get_conn() as c, c.cursor() as cur:
            cur.execute(sql_text)
            if cur.description:
                cols = [d.name for d in cur.description]
                rows = cur.fetchmany(500)
                truncated = len(rows) == 500
                return render(cols=cols, rows=rows, truncated=truncated)
            return render(cols=["status"], rows=[[f"OK, {cur.rowcount} row(s) affected"]])
    except Exception as e:
        return render(error=str(e))


# ponytail: assert-based self-check; full pytest suite if this grows
def _selftest():
    with app.test_client() as c:
        r = c.get("/")
        assert b"Connect to PostgreSQL" in r.data
        r = c.post("/connect", data={"host": "x", "port": "1", "dbname": "x", "user": "x", "password": ""})
        assert b"Connect to PostgreSQL" in r.data and b"err" in r.data
    print("ok")


if __name__ == "__main__":
    import sys
    if "--test" in sys.argv:
        _selftest()
    else:
        app.run(debug=True, port=5000)
