# ============================================================
#  광고 차단 필터링 검색기 - 웹 버전 (app.py)
#
#  브라우저 검색창에서 아무거나 검색하면
#  네이버 블로그 결과를 가져와 광고 글을 걸러내고
#  깨끗한 후기만 화면에 보여주는 웹페이지입니다.
#
#  ────────────────────────────────────────────────
#  [실행 방법]
#    1) 필요한 라이브러리 설치
#         pip install flask requests
#    2) 프로그램 실행
#         python app.py
#    3) 브라우저를 열고 아래 주소로 접속
#         http://localhost:5000
#
#  [구조]
#    브라우저(검색창) -> Flask 서버 -> 네이버 API
#    -> 필터링 -> 브라우저에 결과 표시
#
#  [API 키 발급 방법]
#    https://developers.naver.com 접속 -> 애플리케이션 등록
#    -> "검색" API 선택 -> Client ID / Secret 복사
#  ============================================================

from flask import Flask, request, jsonify, render_template_string
import requests
import re
import html
import os

app = Flask(__name__)


# ──────────────────────────────────────────────
#  API 키 설정 (발급받은 키를 입력하세요)
# ──────────────────────────────────────────────
CLIENT_ID     = "vOF3Agl4npP3SMEHHNAD"
CLIENT_SECRET = "6kBuexZlqV"


# ──────────────────────────────────────────────
#  광고 의심 키워드 목록 (자유롭게 추가/수정 가능)
# ──────────────────────────────────────────────
AD_KEYWORDS = [
    "소정의 수수료",
    "협찬",
    "광고",
    "유료광고",
    "이 포스팅은",
    "제품을 제공받아",
    "원고료",
    "체험단",
    "서포터즈",
    "PPL",
    "간접광고",
    "파트너십",
    "제휴",
    "#AD",
    "#광고",
    "무상으로 제공",
    "대가를 받고",
    "서비스를 제공받아",
]


# ──────────────────────────────────────────────
#  HTML 태그 및 특수문자 제거 함수
# ──────────────────────────────────────────────
def clean_text(text):
    """네이버 API 결과의 HTML 태그(<b> 등)와
    엔티티(&amp; 등)를 제거해 깨끗한 문자열로 만듭니다."""
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    return text.strip()


# ──────────────────────────────────────────────
#  광고 의심 여부 판단 함수
# ──────────────────────────────────────────────
def find_ad_keyword(title, description):
    """제목 + 본문에서 광고 키워드를 찾습니다.
    대소문자 구분 없이 비교하고,
    발견되면 해당 키워드를, 없으면 None을 반환합니다."""
    combined = (title + " " + description).lower()
    for keyword in AD_KEYWORDS:
        if keyword.lower() in combined:
            return keyword
    return None


# ──────────────────────────────────────────────
#  네이버 블로그 검색 API 호출 함수
# ──────────────────────────────────────────────
def search_naver_blog(query, display=20):
    """검색어로 네이버 블로그 API에 요청을 보내고
    결과(dict)를 반환합니다. 오류 시 (None, 오류메시지)."""
    url = "https://openapi.naver.com/v1/search/blog.json"
    headers = {
        "X-Naver-Client-Id": CLIENT_ID,
        "X-Naver-Client-Secret": CLIENT_SECRET,
    }
    params = {"query": query, "display": display, "sort": "sim"}

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=5)
    except requests.exceptions.ConnectionError:
        return None, "인터넷 연결을 확인해주세요."
    except requests.exceptions.Timeout:
        return None, "요청 시간이 초과됐습니다. 다시 시도해주세요."

    if resp.status_code == 401:
        return None, "API 키가 올바르지 않습니다. CLIENT_ID / SECRET을 확인하세요."
    elif resp.status_code != 200:
        return None, f"API 오류 (상태코드: {resp.status_code})"

    return resp.json(), None


# ──────────────────────────────────────────────
#  검색 API 엔드포인트 (브라우저 JS가 호출하는 주소)
# ──────────────────────────────────────────────
@app.route("/api/search")
def api_search():
    """브라우저에서 검색어를 받아 네이버에 요청하고,
    필터링한 결과를 JSON으로 돌려줍니다."""
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "검색어를 입력해주세요."})

    data, error = search_naver_blog(query, display=20)
    if error:
        return jsonify({"error": error})

    items = data.get("items", [])
    normal_results = []   # 정상 글
    ad_results = []       # 광고 의심 글

    for item in items:
        title = clean_text(item.get("title", ""))
        description = clean_text(item.get("description", ""))
        result = {
            "title": title,
            "description": description,
            "blogger": item.get("bloggername", "알 수 없음"),
            "link": item.get("link", ""),
        }
        keyword = find_ad_keyword(title, description)
        if keyword:
            result["keyword"] = keyword
            ad_results.append(result)
        else:
            normal_results.append(result)

    return jsonify({
        "query": query,
        "total": len(items),
        "ad_count": len(ad_results),
        "normal_count": len(normal_results),
        "normal": normal_results,
        "ads": ad_results,
    })


# ──────────────────────────────────────────────
#  메인 페이지 (검색창이 있는 웹페이지 HTML)
# ──────────────────────────────────────────────
PAGE_HTML = """
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Bori - 광고 없는 검색기</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif;
    background: #FFF6F9; color: #2C2C2A; line-height: 1.6;
    padding: 0 16px;
  }
  .wrap { max-width: 1100px; margin: 0 auto; padding: 40px 0 80px; }

  .header { text-align: center; margin-bottom: 28px; }
  .header img { max-width: 320px; width: 70%; height: auto; }
  .header p { font-size: 14px; color: #C44; margin-top: 4px; }

  .search-box { display: flex; justify-content: center; margin-bottom: 28px; }
  .search-box input {
    width: 100%; max-width: 640px; height: 54px; padding: 0 22px; font-size: 16px;
    border: 2px solid #FFB6CC; border-radius: 27px; outline: none;
    background: #FFD1DC; color: #2C2C2A; transition: border-color .15s;
  }
  .search-box input::placeholder { color: #B5708A; }
  .search-box input:focus { border-color: #FF7FA8; }

  .stats {
    background: #fff; border: 1px solid #FAD4E0; border-radius: 12px;
    padding: 14px 18px; margin-bottom: 20px; font-size: 14px;
    display: none; text-align: center;
  }
  .stats .num { font-weight: 700; color: #E84D8A; }
  .stats .ad-num { font-weight: 700; color: #BA7517; }

  .toggle-row {
    display: flex; align-items: center; gap: 8px; justify-content: center;
    margin-bottom: 24px; font-size: 14px; color: #5F5E5A;
  }
  .toggle-row input { width: 16px; height: 16px; cursor: pointer; }
  .toggle-row label { cursor: pointer; user-select: none; }

  .grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
  }
  .card {
    background: #fff; border: 1px solid #FAD4E0; border-radius: 12px;
    padding: 16px; aspect-ratio: 3 / 4; display: flex; flex-direction: column;
    overflow: hidden;
  }
  .card.ad { border-color: #FAC775; background: #FFFBF3; }

  .card .badge {
    display: inline-block; align-self: flex-start; font-size: 11px; font-weight: 700;
    padding: 2px 9px; border-radius: 6px; margin-bottom: 10px;
  }
  .badge.normal { background: #FCE4EE; color: #C2185B; }
  .badge.ad { background: #FFF3DF; color: #854F0B; }

  .card .title {
    font-size: 15px; font-weight: 600; color: #1A1A1A; margin-bottom: 6px;
    line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 2;
    -webkit-box-orient: vertical; overflow: hidden;
  }
  .card .title a { color: inherit; text-decoration: none; }
  .card .title a:hover { text-decoration: underline; }
  .card .blogger { font-size: 12px; color: #B5708A; margin-bottom: 8px; }
  .card .desc {
    font-size: 13px; color: #5F5E5A; flex: 1;
    display: -webkit-box; -webkit-line-clamp: 6;
    -webkit-box-orient: vertical; overflow: hidden;
  }

  .loading, .empty { text-align: center; padding: 40px; color: #B5708A; font-size: 15px; display: none; }
  .footer-note { margin-top: 28px; font-size: 12px; color: #D0A0B5; text-align: center; }

  @media (max-width: 900px) { .grid { grid-template-columns: repeat(2, 1fr); } }
  @media (max-width: 520px) { .grid { grid-template-columns: 1fr; } }
</style>
</head>
<body>
<div class="wrap">

  <div class="header">
    <img src="/static/logo.png" alt="Bori - Ad-Free Web Experience">
  </div>

  <div class="search-box">
    <input type="text" id="query" placeholder="검색어를 입력하세요" autofocus>
  </div>

  <div class="toggle-row">
    <input type="checkbox" id="showAds">
    <label for="showAds">광고 의심 글도 함께 보기</label>
  </div>

  <div class="stats" id="stats"></div>
  <div class="loading" id="loading">검색 중...</div>
  <div class="empty" id="empty">검색 결과가 없습니다. 다른 검색어를 시도해보세요.</div>
  <div class="grid" id="results"></div>

  <div class="footer-note">파이썬(Flask) + 네이버 블로그 검색 API로 동작합니다</div>

</div>

<script>
  // 엔터 키로 검색
  document.getElementById('query').addEventListener('keydown', function(e) {
    if (e.key === 'Enter') doSearch();
  });

  document.getElementById('showAds').addEventListener('change', function() {
    if (window.lastData) renderResults(window.lastData);
  });

  async function doSearch() {
    const query = document.getElementById('query').value.trim();
    if (!query) { alert('검색어를 입력해주세요.'); return; }

    document.getElementById('stats').style.display = 'none';
    document.getElementById('empty').style.display = 'none';
    document.getElementById('results').innerHTML = '';
    document.getElementById('loading').style.display = 'block';

    try {
      const resp = await fetch('/api/search?q=' + encodeURIComponent(query));
      const data = await resp.json();
      document.getElementById('loading').style.display = 'none';
      if (data.error) { alert(data.error); return; }
      window.lastData = data;
      renderResults(data);
    } catch (err) {
      document.getElementById('loading').style.display = 'none';
      alert('오류가 발생했습니다: ' + err.message);
    }
  }

  function renderResults(data) {
    const showAds = document.getElementById('showAds').checked;
    const resultsEl = document.getElementById('results');
    resultsEl.innerHTML = '';

    const statsEl = document.getElementById('stats');
    statsEl.innerHTML = '"' + data.query + '" 검색 결과 · 총 <span class="num">' + data.total +
      '</span>개 중 <span class="ad-num">' + data.ad_count + '</span>개 광고 의심 필터링됨';
    statsEl.style.display = 'block';

    if (data.normal.length === 0 && !showAds) {
      document.getElementById('empty').textContent =
        '걸러지지 않은 후기 글이 없습니다. 위 체크박스로 광고 의심 글도 볼 수 있어요.';
      document.getElementById('empty').style.display = 'block';
      return;
    }

    data.normal.forEach(function(item) { resultsEl.appendChild(makeCard(item, false)); });
    if (showAds) {
      data.ads.forEach(function(item) { resultsEl.appendChild(makeCard(item, true)); });
    }
  }

  function makeCard(item, isAd) {
    const card = document.createElement('div');
    card.className = 'card' + (isAd ? ' ad' : '');
    const badge = isAd
      ? '<span class="badge ad">광고 의심 · ' + escapeHtml(item.keyword) + '</span>'
      : '<span class="badge normal">후기</span>';
    card.innerHTML = badge +
      '<div class="title"><a href="' + item.link + '" target="_blank">' + escapeHtml(item.title) + '</a></div>' +
      '<div class="blogger">' + escapeHtml(item.blogger) + '</div>' +
      '<div class="desc">' + escapeHtml(item.description) + '</div>';
    return card;
  }

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }
</script>
</body>
</html>
"""


@app.route("/")
def index():
    """메인 페이지를 보여줍니다."""
    return render_template_string(PAGE_HTML)


# ──────────────────────────────────────────────
#  프로그램 진입점
# ──────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("=" * 55)
    print("  광고 없는 검색기 서버 시작")
    print(f"  브라우저에서 http://localhost:{port} 으로 접속하세요")
    print("=" * 55)
    app.run(host="0.0.0.0", port=port, debug=True)
