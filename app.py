from flask import Flask, request, session, redirect, url_for, render_template_string
import psycopg2
from psycopg2 import sql
import sqlite3, os

app = Flask(__name__)
app.secret_key = os.environ.get("LDV_SECRET", "dev-only-change-me")

# ponytail: passwords stored plaintext in local sqlite. Local dev tool only.
# Upgrade path: keyring/OS credential store, or encrypt-at-rest with a passphrase.
DB_PATH = os.environ.get("LDV_DB", "ldv.db")


def store():
    c = sqlite3.connect(DB_PATH)
    c.execute("""CREATE TABLE IF NOT EXISTS conns(
        name TEXT PRIMARY KEY, host TEXT, port TEXT, dbname TEXT,
        user TEXT, password TEXT, last_used TEXT DEFAULT (datetime('now')))""")
    return c


def saved_conns():
    with store() as c:
        return [dict(zip(["name", "host", "port", "dbname", "user"], r))
                for r in c.execute("SELECT name,host,port,dbname,user FROM conns ORDER BY last_used DESC")]


def save_conn(cfg):
    name = f"{cfg['user']}@{cfg['host']}:{cfg['port']}/{cfg['dbname']}"
    with store() as c:
        c.execute("INSERT OR REPLACE INTO conns(name,host,port,dbname,user,password,last_used) VALUES(?,?,?,?,?,?,datetime('now'))",
                  (name, cfg["host"], cfg["port"], cfg["dbname"], cfg["user"], cfg["password"]))
    return name


def load_conn(name):
    with store() as c:
        r = c.execute("SELECT host,port,dbname,user,password FROM conns WHERE name=?", (name,)).fetchone()
    return dict(zip(["host", "port", "dbname", "user", "password"], r)) if r else None


def delete_conn(name):
    with store() as c:
        c.execute("DELETE FROM conns WHERE name=?", (name,))

PAGE = """
<!doctype html>
<title>LocalDB viewer</title>
<style>
  :root{
    --b:#e7ebf0; --b2:#eef1f4; --bg:#f7f8fa; --card:#fff;
    --ink:#1f2328; --mut:#6b7280; --soft:#9aa3ad;
    --accent:#3b82f6; --accent-soft:#eaf2ff;
    --ok:#16a34a; --bad:#dc2626; --hov:#f3f7ff;
    --mono:ui-monospace,SFMono-Regular,Consolas,monospace;
  }
  *{box-sizing:border-box}
  html,body{background:var(--bg)}
  body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,system-ui,sans-serif;
       color:var(--ink);margin:0;padding:1.25rem;line-height:1.45;font-size:14px}
  h1,h2,h3{margin:0 0 .75rem;font-weight:600;letter-spacing:-.01em}
  h2{font-size:1.2rem}
  a{color:var(--accent);text-decoration:none}
  a:hover{text-decoration:underline}

  input,textarea,select{font:inherit;padding:.5rem .65rem;border:1px solid var(--b);
       border-radius:6px;background:var(--card);color:var(--ink);outline:none;transition:border-color .15s,box-shadow .15s}
  input:focus,textarea:focus,select:focus{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-soft)}
  button{font:inherit;font-weight:500;padding:.5rem .9rem;border:1px solid var(--accent);
       border-radius:6px;background:var(--accent);color:#fff;cursor:pointer;transition:filter .15s}
  button:hover{filter:brightness(.95)}
  textarea{width:100%;min-height:110px;font-family:var(--mono);font-size:.85rem;resize:vertical}

  .card{background:var(--card);border:1px solid var(--b);border-radius:10px;padding:1.1rem}
  .login{max-width:480px;margin:3rem auto}
  .login h2{margin-bottom:.25rem}
  .login .sub{color:var(--mut);margin-bottom:1.25rem;font-size:.9rem}
  .form-grid{display:grid;grid-template-columns:1fr 1fr;gap:.75rem}
  .form-grid label{display:flex;flex-direction:column;font-size:.78rem;color:var(--mut);gap:.25rem}
  .form-grid .full{grid-column:1/-1}
  .actions{display:flex;justify-content:space-between;align-items:center;margin-top:1rem;gap:.5rem}
  .check{display:flex;align-items:center;gap:.4rem;color:var(--mut);font-size:.85rem}

  .saved{display:flex;flex-direction:column;gap:.4rem;margin-bottom:1.25rem}
  .saved-item{display:flex;align-items:center;gap:.5rem;padding:.55rem .75rem;
       background:var(--card);border:1px solid var(--b);border-radius:8px;transition:border-color .15s}
  .saved-item:hover{border-color:var(--accent)}
  .saved-item a.use{flex:1;font-family:var(--mono);font-size:.85rem;color:var(--ink)}
  .saved-item a.use:hover{text-decoration:none;color:var(--accent)}
  .saved-item .x{color:var(--soft);font-size:.78rem;padding:.15rem .45rem;border-radius:4px}
  .saved-item .x:hover{color:var(--bad);background:#fef2f2;text-decoration:none}

  .err{color:var(--bad);background:#fef2f2;border:1px solid #fecaca;border-radius:6px;
       padding:.6rem .75rem;white-space:pre-wrap;font-size:.85rem;margin:.75rem 0}

  .bar{display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem;
       padding:.6rem .85rem;background:var(--card);border:1px solid var(--b);border-radius:8px}
  .bar .conn{display:flex;align-items:center;gap:.5rem;font-family:var(--mono);font-size:.85rem}
  .bar .dot{width:8px;height:8px;border-radius:50%;background:var(--ok);box-shadow:0 0 0 3px #dcfce7}

  .layout{display:flex;gap:1rem;align-items:flex-start}
  aside{flex:0 0 240px;max-height:calc(100vh - 110px);overflow:auto;
       background:var(--card);border:1px solid var(--b);border-radius:10px;padding:.6rem}
  aside .head{display:flex;justify-content:space-between;align-items:center;
       padding:.3rem .5rem .5rem;font-size:.72rem;text-transform:uppercase;letter-spacing:.05em;color:var(--mut)}
  aside a.t{display:block;padding:.35rem .5rem;font-size:.83rem;color:var(--ink);
       border-radius:5px;font-family:var(--mono);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  aside a.t:hover{background:var(--hov);color:var(--accent);text-decoration:none}
  main{flex:1;min-width:0}

  .panel{background:var(--card);border:1px solid var(--b);border-radius:10px;padding:.85rem;margin-bottom:.85rem}
  .panel .panel-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:.5rem;
       font-size:.72rem;text-transform:uppercase;letter-spacing:.05em;color:var(--mut)}

  .meta{display:flex;justify-content:space-between;align-items:center;margin:.5rem 0;
       font-size:.8rem;color:var(--mut)}
  .pill{display:inline-block;background:var(--accent-soft);color:var(--accent);
       padding:.1rem .5rem;border-radius:999px;font-size:.72rem;font-weight:500}

  .tbl-wrap{border:1px solid var(--b);border-radius:10px;overflow:auto;
       max-height:70vh;background:var(--card)}
  table{border-collapse:separate;border-spacing:0;width:100%;font-size:.84rem}
  th,td{padding:.45rem .7rem;border-bottom:1px solid var(--b2);
       white-space:nowrap;max-width:340px;overflow:hidden;text-overflow:ellipsis;
       text-align:left;vertical-align:top}
  tbody tr:last-child td{border-bottom:0}
  thead th{position:sticky;top:0;background:#fafbfc;font-weight:600;color:var(--ink);
       cursor:pointer;user-select:none;z-index:1;border-bottom:1px solid var(--b);
       font-size:.75rem;text-transform:uppercase;letter-spacing:.03em}
  thead th:hover{background:#f1f4f8}
  thead th::after{content:" \\21C5";color:#cdd3da;font-size:.75em;margin-left:.15rem}
  thead th.asc::after{content:" \\2191";color:var(--accent)}
  thead th.desc::after{content:" \\2193";color:var(--accent)}
  tbody tr:nth-child(even){background:#fbfcfd}
  tbody tr:hover{background:var(--hov)}
  td.num{text-align:right;font-variant-numeric:tabular-nums;font-family:var(--mono)}
  td.null{color:var(--soft);font-style:italic;font-size:.78rem}
  td.bool-t{color:var(--ok);font-weight:600}
  td.bool-f{color:var(--bad);font-weight:600}
  td.rownum{color:var(--soft);font-family:var(--mono);font-size:.78rem;text-align:right;
       background:#fafbfc;border-right:1px solid var(--b2)}

  .empty{padding:2rem;text-align:center;color:var(--mut);font-size:.9rem;
       border:1px dashed var(--b);border-radius:10px;background:var(--card)}
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
  <div class=login>
    <div class=card>
      <h2>LocalDB viewer</h2>
      <div class=sub>Connect to a PostgreSQL database.</div>

      {% if saved %}
        <div class=saved>
        {% for s in saved %}
          <div class=saved-item>
            <a class=use href="{{ url_for('use_saved', name=s.name) }}">{{ s.name }}</a>
            <a class=x href="{{ url_for('forget', name=s.name) }}" onclick="return confirm('Forget {{ s.name }}?')">forget</a>
          </div>
        {% endfor %}
        </div>
      {% endif %}

      <form method=post action="{{ url_for('connect') }}">
        <div class=form-grid>
          <label class=full>Host<input name=host value="localhost"></label>
          <label>Port<input name=port value="5432"></label>
          <label>Database<input name=dbname required></label>
          <label>User<input name=user required></label>
          <label>Password<input name=password type=password></label>
        </div>
        <div class=actions>
          <label class=check><input type=checkbox name=save value=1 checked> Remember this connection</label>
          <button>Connect</button>
        </div>
      </form>
      {% if error %}<p class=err>{{ error }}</p>{% endif %}
    </div>
  </div>
{% else %}
  <div class=bar>
    <div class=conn><span class=dot></span>{{ conn.user }}@{{ conn.host }}:{{ conn.port }}/{{ conn.dbname }}</div>
    <a href="{{ url_for('disconnect') }}">disconnect</a>
  </div>

  <div class=layout>
  <aside>
    <div class=head><span>Tables</span><span class=pill>{{ tables|length }}</span></div>
    {% for t in tables %}
      <a class=t href="{{ url_for('view_table', name=t) }}" title="{{ t }}">{{ t }}</a>
    {% endfor %}
  </aside>

  <main>
    <div class=panel>
      <div class=panel-head><span>SQL</span><span>Ctrl/Cmd + Enter to submit</span></div>
      <form method=post action="{{ url_for('query') }}" onkeydown="if((event.ctrlKey||event.metaKey)&&event.key==='Enter')this.submit()">
        <textarea name=sql placeholder="SELECT * FROM ...">{{ last_sql or '' }}</textarea>
        <div class=actions><span></span><button>Run SQL</button></div>
      </form>
    </div>

    {% if error %}<p class=err>{{ error }}</p>{% endif %}

    {% if rows is not none %}
      <div class=meta>
        <span><span class=pill>{{ rows|length }} rows</span> &nbsp; {{ cols|length }} columns{% if truncated %} &middot; truncated to 500{% endif %}</span>
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
    {% elif not error %}
      <div class=empty>Pick a table on the left or run a query above.</div>
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
    kw.setdefault("saved", [] if kw["connected"] else saved_conns())
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
    if request.form.get("save"):
        save_conn(cfg)
    session["conn"] = cfg
    session.pop("last_sql", None)
    return redirect(url_for("index"))


@app.route("/use/<name>")
def use_saved(name):
    cfg = load_conn(name)
    if not cfg:
        return redirect(url_for("index"))
    try:
        psycopg2.connect(**cfg).close()
    except Exception as e:
        return render(error=f"{name}: {e}")
    save_conn(cfg)  # bump last_used
    session["conn"] = cfg
    session.pop("last_sql", None)
    return redirect(url_for("index"))


@app.route("/forget/<name>")
def forget(name):
    delete_conn(name)
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
        assert b"LocalDB viewer" in r.data
        r = c.post("/connect", data={"host": "x", "port": "1", "dbname": "x", "user": "x", "password": ""})
        assert b"LocalDB viewer" in r.data and b"err" in r.data
    print("ok")


if __name__ == "__main__":
    import sys
    if "--test" in sys.argv:
        _selftest()
    else:
        app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)
