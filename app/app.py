import os
import pymysql
from flask import Flask
from markupsafe import escape

app = Flask(__name__)

def get_db():
    return pymysql.connect(
        host=os.environ["DB_HOST"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.environ["DB_NAME"],
        cursorclass=pymysql.cursors.DictCursor,
    )

@app.route("/")
def index():
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, title FROM posts ORDER BY id")
            posts = cur.fetchall()
    finally:
        conn.close()
    items = "".join(f"<li>{p['id']}. {escape(p['title'])}</li>" for p in posts)
    html = (f"<!DOCTYPE html><html lang='zh'><head><meta charset='utf-8'>"
            f"<title>我的博客</title>"
            f"<link rel='stylesheet' href='/static/style.css'>"
            f"<link rel='icon' type='image/svg+xml' href='/static/favicon.svg'>"
            f"</head><body><h1>我的博客</h1><ul>{items}</ul>"
            f"<footer>Powered by Flask + Nginx + MySQL · 部署于阿里云</footer>"
            f"</body></html>")
    return html
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
