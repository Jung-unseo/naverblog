import os
import sqlite3
from datetime import datetime
import requests
from flask import Flask, render_template, request, redirect, url_for
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

DB_PATH = "app.db"

# 네이버 API (있으면 블로그 검색이 실제로 됨)
NAVER_CLIENT_ID = os.getenv("1jI7baJJcb01hfmHySDj", "")
NAVER_CLIENT_SECRET = os.getenv("JXcqYphg4n", "")

# -----------------------------
# DB
# -----------------------------
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_conn() as con:
        cur = con.cursor()

        # 블로그 검색어 저장
        cur.execute("""
        CREATE TABLE IF NOT EXISTS blog_keywords (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """)

        # 아티스트 검색어 저장
        cur.execute("""
        CREATE TABLE IF NOT EXISTS artist_keywords (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """)

        # (선택) 아티스트 데이터(검색 대상)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS artists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            genre TEXT,
            agency TEXT
        )
        """)

        # artists 테이블이 비어있으면 샘플 데이터 넣기
        cur.execute("SELECT COUNT(*) AS cnt FROM artists")
        if cur.fetchone()["cnt"] == 0:
            sample = [
                ("IU", "K-POP", "EDAM"),
                ("BTS", "K-POP", "HYBE"),
                ("NewJeans", "K-POP", "ADOR"),
                ("AKMU", "K-POP", "YG"),
                ("DAY6", "K-POP", "JYP"),
            ]
            cur.executemany("INSERT INTO artists(name, genre, agency) VALUES(?,?,?)", sample)

        con.commit()

def save_keyword(table: str, keyword: str):
    keyword = (keyword or "").strip()
    if not keyword:
        return
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_conn() as con:
        con.execute(f"INSERT INTO {table}(keyword, created_at) VALUES(?, ?)", (keyword, now))
        con.commit()

def get_ranking(table: str, limit=20):
    with get_conn() as con:
        rows = con.execute(f"""
            SELECT keyword, COUNT(*) AS cnt
            FROM {table}
            GROUP BY keyword
            ORDER BY cnt DESC, keyword ASC
            LIMIT ?
        """, (limit,)).fetchall()
    return rows

# -----------------------------
# NAVER BLOG SEARCH
# -----------------------------
def naver_blog_search(query: str, start: int = 1, display: int = 10):
    """
    네이버 블로그 검색 API
    start: 1 ~ 1000 범위(네이버 제한 있음)
    display: 1 ~ 100
    """
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        # 키가 없으면 더미 결과 반환 (템플릿은 동작)
        return {
            "total": 2,
            "items": [
                {
                    "title": f"[샘플] {query} 맛집 후기",
                    "link": "https://example.com",
                    "description": "네이버 API 키를 .env에 넣으면 실제 검색 결과가 나옵니다.",
                    "bloggername": "Sample Blogger",
                    "bloggerlink": "https://example.com",
                    "postdate": "20250101"
                },
                {
                    "title": f"[샘플] {query} 여행 코스 정리",
                    "link": "https://example.com",
                    "description": "지금은 샘플 데이터로 보여주는 상태예요.",
                    "bloggername": "Sample Blogger2",
                    "bloggerlink": "https://example.com",
                    "postdate": "20250102"
                },
            ]
        }

    url = "https://openapi.naver.com/v1/search/blog.json"
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    }
    params = {"query": query, "start": start, "display": display, "sort": "sim"}
    r = requests.get(url, headers=headers, params=params, timeout=10)
    r.raise_for_status()
    return r.json()

# -----------------------------
# ROUTES (템플릿 파일명 그대로)
# -----------------------------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/search/blog")
def search_blog():
    q = (request.args.get("q") or "").strip()
    page = int(request.args.get("page") or 1)
    display = 10
    start = (page - 1) * display + 1

    results = []
    total = 0
    max_page = 1

    if q:
        save_keyword("blog_keywords", q)
        data = naver_blog_search(q, start=start, display=display)
        results = data.get("items", [])
        total = int(data.get("total", 0))

        # 네이버 start 제한 때문에 페이지 너무 커지지 않게 컷(보통 1000까지)
        max_page = min(((total - 1) // display + 1) if total else 1, 100)

    return render_template(
        "search_blog.html",
        q=q,
        results=results,
        total=total,
        page=page,
        max_page=max_page
    )

@app.route("/ranking")
def ranking():
    top = get_ranking("blog_keywords", limit=30)
    return render_template("ranking.html", top=top)

@app.route("/search/artist")
def artist_search():
    q = (request.args.get("q") or "").strip()
    rows = []

    if q:
        save_keyword("artist_keywords", q)
        like = f"%{q}%"
        with get_conn() as con:
            rows = con.execute("""
                SELECT id, name, genre, agency
                FROM artists
                WHERE name LIKE ?
                ORDER BY name ASC
                LIMIT 50
            """, (like,)).fetchall()

    return render_template("artist_search.html", q=q, rows=rows)

@app.route("/artist/ranking")
def artist_ranking():
    top = get_ranking("artist_keywords", limit=30)
    return render_template("artist_ranking.html", top=top)

@app.route("/melon/chart")
def melon_chart():
    # ✅ 일단 샘플 차트 데이터 (나중에 크롤링/API 붙이기 쉬운 구조)
    chart = [
        {"rank": 1, "title": "샘플곡 A", "artist": "샘플아티스트 1"},
        {"rank": 2, "title": "샘플곡 B", "artist": "샘플아티스트 2"},
        {"rank": 3, "title": "샘플곡 C", "artist": "샘플아티스트 3"},
        {"rank": 4, "title": "샘플곡 D", "artist": "샘플아티스트 4"},
        {"rank": 5, "title": "샘플곡 E", "artist": "샘플아티스트 5"},
    ]
    return render_template("melon_chart.html", chart=chart)

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
