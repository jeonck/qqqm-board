# QQQM 말뚝박기 보드

조던 원칙으로 QQQM 포지션을 매일 장 마감 후 기록하는 게시판.

**사이트:** https://jeonck.github.io/qqqm-board/

## 규칙 (확정)

- 종목: QQQM (Invesco NASDAQ 100 ETF)
- 기준 전고점: 약 $300 (최근 고점 $299.74 반올림)
- 총 현금: $10,000
- 매수: 전고점 대비 -5% 하락할 때마다 $1,000씩 분할 매수
- V자 반등: 종가 기준 저점(running low) 대비 +10% 상승 시 잔여 현금 전량 매수
- 매수·매도 실행은 본인이 직접 — 이 보드는 기록과 트리거 알림만 한다.

## 현재 상태

| 항목 | 값 |
|---|---|
| 투자금 / 현금 | $2,000 / $8,000 |
| 저점 (running low) | $266.85 (2026-11-05) |
| 다음 매수 트리거 | 종가 $255.00 이하 시 3차 말뚝 $1,000 |
| V자 반등 트리거 | $293.54 |

## 어떻게 돌아가나

1. 평일 22:15 UTC (16:15 CST)에 GitHub Actions가 돈다.
2. `pipeline/update.py`가 Yahoo Finance에서 QQQM 종가를 가져온다 (무료, 키 불필요).
3. 새 거래일이면 `data/history.json`에 한 줄을 추가하고 `index.html` 게시판을 다시 만든 뒤 커밋·푸시하고 GitHub Pages에 배포한다.
4. 종가를 가져오지 못하면 아무것도 기록하지 않고 실패로 끝난다 — 숫자를 지어내지 않는다.

수동 실행: Actions 탭 → "QQQM daily close board" → Run workflow.

## 파일

- `index.html` — 게시판 (자동 생성, 직접 고치지 말 것)
- `data/history.json` — 모든 일일 기록 + 상태 (유일한 원본)
- `pipeline/update.py` — 종가 조회·트리거 판정·게시판 생성
