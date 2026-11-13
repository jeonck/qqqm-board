#!/usr/bin/env python3
"""QQQM 말뚝박기 일일 보드 갱신 스크립트 (조던 원칙).

매일 장 마감 후 GitHub Actions에서 실행:
  1. Yahoo Finance chart API(무료, 키 불필요)로 QQQM 최근 종가를 가져온다.
  2. data/history.json에 아직 없는 거래일이면 한 줄을 추가한다.
     - 전고점($300) 대비 -5%마다 $1,000씩 분할 매수 (말뚝)
     - 종가 기준 저점(running low) 대비 +10% 반등 시 잔여 현금 전량 매수
  3. index.html 게시판을 다시 만든다.

숫자를 지어내지 않는다: 종가를 가져오지 못하면 실패로 종료하고 아무것도
기록하지 않는다. 매수·매도 실행은 CK 본인이 한다 — 이 스크립트는 기록만 한다.
"""
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
HISTORY = ROOT / "data" / "history.json"
INDEX = ROOT / "index.html"
NY = ZoneInfo("America/New_York")
UA = {"User-Agent": "Mozilla/5.0 (compatible; qqqm-board/1.0)"}


def load():
    return json.loads(HISTORY.read_text(encoding="utf-8"))


def save(data):
    HISTORY.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fetch_last_close():
    """Yahoo chart API에서 마지막 완성된 일봉(날짜, 종가)을 가져온다.

    장중(미국 동부 16:05 이전)에 실행되면 당일 봉은 아직 마감 전
    장중가이므로 건너뛰고, 전날까지의 마지막 완성 봉을 쓴다.
    장 마감 뒤(16:05 이후)에는 당일 봉이 최종 종가다.
    """
    url = "https://query1.finance.yahoo.com/v8/finance/chart/QQQM?range=5d&interval=1d"
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    result = payload["chart"]["result"][0]
    stamps = result["timestamp"]
    closes = result["indicators"]["quote"][0]["close"]
    now_et = datetime.now(tz=NY)
    today = now_et.date().isoformat()
    market_closed = (now_et.hour, now_et.minute) >= (16, 5)
    for ts, close in reversed(list(zip(stamps, closes))):
        if close is None:
            continue
        date = datetime.fromtimestamp(ts, tz=NY).date().isoformat()
        if date == today and not market_closed:
            continue  # 장중 봉은 종가가 아님 — 기록하지 않는다
        return date, round(float(close), 2)
    raise RuntimeError("Yahoo 응답에 완성된 종가가 없음")


def next_stake_price(data):
    """다음 말뚝 트리거가: 투자된 말뚝 수로 계산한다."""
    stakes_done = data["invested"] // data["stake"]
    step = data["high"] * data["stake_step_pct"] / 100
    return round(data["high"] - step * (stakes_done + 1), 2)


def rebound_trigger(data):
    return round(data["running_low"] * (1 + data["rebound_pct"] / 100), 2)


def fmt_money(n):
    return f"${n:,.0f}"


def fmt_signed(n, suffix=""):
    sign = "+" if n > 0 else ""
    return f"{sign}{n:,.2f}{suffix}"


PAGER_JS = """<script>
(function(){
var rows = Array.prototype.slice.call(document.querySelectorAll('#boardTable tr')).slice(1);
var per = 10, page = 0, pages = Math.max(1, Math.ceil(rows.length / per));
var info = document.getElementById('pageInfo');
var prev = document.getElementById('prevBtn'), next = document.getElementById('nextBtn');
function show(){
  rows.forEach(function(r, i){ r.style.display = (i >= page*per && i < (page+1)*per) ? '' : 'none'; });
  info.textContent = (page+1) + ' / ' + pages + ' 페이지';
  prev.disabled = page === 0; next.disabled = page >= pages-1;
}
prev.onclick = function(){ if(page > 0){ page--; show(); } };
next.onclick = function(){ if(page < pages-1){ page++; show(); } };
show();
})();
</script>"""


def render(data):
    entries = sorted(data["entries"], key=lambda e: e["date"], reverse=True)
    latest = entries[0]
    nxt = next_stake_price(data)
    reb = rebound_trigger(data)
    updated = datetime.now(tz=NY).strftime("%Y-%m-%d %H:%M ET")
    stakes_done = data["invested"] // data["stake"]

    ladder_rows = ""
    step = data["high"] * data["stake_step_pct"] / 100
    for i in range(1, 6):
        price = round(data["high"] - step * i, 2)
        pct = -data["stake_step_pct"] * i
        status = "✅ 완료" if i <= stakes_done else ("⏳ 다음" if i == stakes_done + 1 else "대기")
        ladder_rows += (
            f"<tr><td>{i}차</td><td>{pct}%</td><td>${price:,.2f}</td>"
            f"<td>{status}</td></tr>\n"
        )

    board_rows = ""
    for e in entries:
        day = (
            f"{fmt_signed(e['day_change'])} ({fmt_signed(e['day_pct'], '%')})"
            if e["day_change"] is not None
            else "—"
        )
        day_cls = "up" if (e["day_change"] or 0) > 0 else ("down" if (e["day_change"] or 0) < 0 else "")
        trig = e["trigger"] or "없음"
        trig_cls = "trig" if e["trigger"] else ""
        board_rows += (
            f"<tr><td>{e['date']}</td><td class='num'>${e['close']:,.2f}</td>"
            f"<td class='num {day_cls}'>{day}</td>"
            f"<td class='num'>{fmt_signed(e['vs_high_pct'], '%')}</td>"
            f"<td class='{trig_cls}'>{trig}</td>"
            f"<td class='num'>{fmt_money(e['invested_after'])} / {fmt_money(e['cash_after'])}</td></tr>\n"
        )

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>QQQM 말뚝박기 보드 — 조던 원칙</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;max-width:880px;margin:0 auto;padding:24px 16px;color:#1a1a1a;line-height:1.5}}
h1{{font-size:1.5rem;margin-bottom:4px}} .sub{{color:#666;margin-top:0}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:20px 0}}
.card{{border:1px solid #ddd;border-radius:10px;padding:14px}}
.card .label{{font-size:.8rem;color:#666}} .card .value{{font-size:1.35rem;font-weight:700}}
.card .note{{font-size:.8rem;color:#666}}
table{{width:100%;border-collapse:collapse;margin:16px 0;font-size:.95rem}}
th,td{{border-bottom:1px solid #e5e5e5;padding:8px 6px;text-align:left}}
th{{background:#f6f6f6}} .num{{text-align:right;font-variant-numeric:tabular-nums}}
.up{{color:#0a7d2c}} .down{{color:#c0272d}} .trig{{font-weight:700;color:#8a5a00}}
.pager{{margin:8px 0 20px;text-align:center}} .pager button{{padding:6px 14px;margin:0 8px;cursor:pointer}} .pager button:disabled{{opacity:.4;cursor:default}}
footer{{color:#666;font-size:.85rem;margin-top:28px;border-top:1px solid #eee;padding-top:12px}}
@media(max-width:640px){{table{{font-size:.85rem}}}}
</style>
</head>
<body>
<h1>📋 QQQM 말뚝박기 보드</h1>
<p class="sub">조던 원칙 · 전고점 $300 기준 -5%마다 $1,000씩 분할 매수 · 저점 대비 +10% 반등 시 잔여 현금 전량 매수 · 매수·매도는 본인이 직접</p>
<p class="sub">마지막 업데이트: {updated} · 최신 종가 {latest['date']}</p>

<div class="cards">
<div class="card"><div class="label">최신 종가 ({latest['date']})</div><div class="value">${latest['close']:,.2f}</div><div class="note">전고점 대비 {fmt_signed(latest['vs_high_pct'], '%')}</div></div>
<div class="card"><div class="label">포지션</div><div class="value">{fmt_money(data['invested'])} / {fmt_money(data['cash'])}</div><div class="note">투자금 / 현금 (총 {fmt_money(data['total_cash'])})</div></div>
<div class="card"><div class="label">다음 매수 트리거</div><div class="value">${nxt:,.2f}</div><div class="note">{stakes_done + 1}차 말뚝 · 종가 ${nxt:,.2f} 이하 시 $1,000 매수</div></div>
<div class="card"><div class="label">V자 반등 트리거</div><div class="value">${reb:,.2f}</div><div class="note">저점 ${data['running_low']:,.2f} ({data['running_low_date']}) 대비 +10%</div></div>
</div>

<h2>말뚝 ladder</h2>
<table><tr><th>말뚝</th><th>하락률</th><th>트리거가</th><th>상태</th></tr>
{ladder_rows}</table>

<h2>일일 종가 게시판</h2>
<table id="boardTable"><tr><th>날짜</th><th>종가</th><th>전일 대비</th><th>전고점 대비</th><th>트리거</th><th>투자 / 현금</th></tr>
{board_rows}</table>
<div class="pager" id="pager"><button id="prevBtn">← 이전</button><span id="pageInfo"></span><button id="nextBtn">다음 →</button></div>
{PAGER_JS}

<footer>
규칙: 전고점 약 $300(최근 고점 $299.74 반올림), 총 현금 $10,000, -5%마다 $1,000 분할 매수, 저점 대비 +10% 반등 시 잔여 현금 전량 매수.
종가는 미국 동부 16:00 마감 기준, 출처 Yahoo Finance. 원본 데이터: <a href="data/history.json">history.json</a> ·
<a href="https://github.com/jeonck/qqqm-board">GitHub 저장소</a>
</footer>
</body>
</html>
"""


def main():
    data = load()
    known = {e["date"] for e in data["entries"]}
    try:
        date, close = fetch_last_close()
    except Exception as exc:
        print(f"종가 조회 실패: {exc}", file=sys.stderr)
        return 1

    if date in known:
        print(f"{date} 종가 ${close:.2f} — 이미 기록됨, 게시판만 다시 만듦")
    else:
        prev = data["entries"][-1]
        day_change = round(close - prev["close"], 2)
        day_pct = round(day_change / prev["close"] * 100, 2)
        vs_high = round((close - data["high"]) / data["high"] * 100, 2)
        invested, cash = data["invested"], data["cash"]
        trigger = None
        new_low = min(data["running_low"], close)
        # V자 반등을 먼저 본다 (둘은 동시에 일어날 수 없는 가격대).
        if cash > 0 and close >= rebound_trigger(data):
            trigger = f"V자 반등 전량 매수 (${rebound_trigger(data):,.2f} 도달)"
            invested += cash
            cash = 0
        elif cash >= data["stake"] and close <= next_stake_price(data):
            n = data["invested"] // data["stake"] + 1
            trigger = f"{n}차 말뚝 $1,000 매수 (${next_stake_price(data):,.2f} 도달)"
            invested += data["stake"]
            cash -= data["stake"]
        entry = {
            "date": date, "close": close, "prev_close": prev["close"],
            "day_change": day_change, "day_pct": day_pct, "vs_high_pct": vs_high,
            "trigger": trigger, "invested_after": invested, "cash_after": cash,
            "running_low_after": new_low,
            "note": "Yahoo Finance 종가 (미국 동부 16:00 기준)",
        }
        data["entries"].append(entry)
        data["invested"], data["cash"] = invested, cash
        if new_low < data["running_low"]:
            data["running_low_date"] = date
        data["running_low"] = new_low
        save(data)
        print(f"{date} 종가 ${close:.2f} 기록됨 — 트리거: {trigger or '없음'}")

    INDEX.write_text(render(data), encoding="utf-8")
    print("index.html 생성 완료")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
