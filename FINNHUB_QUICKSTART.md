# 🚀 Finnhub 실시간 가격 수집 가이드

## 빠른 시작

### 1단계: API 키 발급

1. [Finnhub 회원가입](https://finnhub.io/register) (무료)
2. 대시보드에서 API 키 복사
3. `.env` 파일에 추가:
   ```env
   FINNHUB_API_KEY=your_finnhub_api_key_here
   ```

### 2단계: 의존성 설치

```bash
pip install finnhub-python websocket-client
```

### 3단계: 연결 테스트

```bash
python test_finnhub_api.py
```

성공 출력:
```
✓ ALL TESTS PASSED - System is ready to use!
```

## 📊 사용 방법

### 옵션 A: 현재 가격 스냅샷 (권장 시작)

```bash
python collect_prices.py --mode snapshot
```

**용도:**
- 현재 시점의 모든 종목 가격 조회
- 빠른 시장 체크
- 데이터 수집 시작 전 확인

**출력 예시:**
```
AAPL  : $  275.50 ( +0.67%) [O:274.69 H:280.18 L:274.45]
NVDA  : $  190.05 ( +0.80%) [O:192.45 H:193.26 L:188.77]
TSLA  : $  428.27 ( +0.72%) [O:427.95 H:436.35 L:420.03]
...
```

### 옵션 B: WebSocket 실시간 스트리밍 (권장)

```bash
python collect_prices.py --mode websocket --duration 60
```

**특징:**
- 실시간 가격 업데이트 (지연 ~100ms)
- Push 방식 (폴링 불필요)
- 거래량 포함
- 60분 동안 실행

**옵션:**
```bash
# 무한 실행 (Ctrl+C로 중지)
python collect_prices.py --mode websocket

# 특정 종목만
python collect_prices.py --mode websocket --tickers AAPL NVDA TSLA

# 30분 실행
python collect_prices.py --mode websocket --duration 30
```

### 옵션 C: REST API 폴링

```bash
python collect_prices.py --mode polling --interval 5 --duration 60
```

**특징:**
- 주기적 가격 조회 (Pull 방식)
- 5초마다 업데이트
- WebSocket 대안

## 📈 실시간 업데이트 예시

WebSocket 모드 실행 시 (시장 개장 중):
```
[14:30:15] AAPL  : $  275.52 (Vol: 1,234)
[14:30:16] NVDA  : $  190.08 (Vol: 892)
[14:30:16] AAPL  : $  275.51 (Vol: 567)
[14:30:17] TSLA  : $  428.30 (Vol: 2,301)
```

## 🔔 Discord 알림 (선택사항)

가격이 1% 이상 변동하면 자동으로 Discord 알림:

```env
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

알림 예시:
```
📈 AAPL 가격 상승
현재가: $275.50 (+1.2%)
```

## 📁 수집된 데이터

### 저장 위치
```
data/prices/prices_20260212_224745.json
```

### JSON 구조
```json
{
  "AAPL": {
    "ticker": "AAPL",
    "current_price": 275.50,
    "change": 1.82,
    "percent_change": 0.67,
    "high": 280.18,
    "low": 274.45,
    "open": 274.69,
    "previous_close": 273.68,
    "timestamp": "2026-02-12T13:47:41"
  }
}
```

## 🎯 추천 사용 시나리오

### 개발/테스트 단계
```bash
# 1. 현재 가격 확인
python collect_prices.py --mode snapshot

# 2. 30초 WebSocket 테스트
python collect_prices.py --mode websocket --duration 0.5 --tickers AAPL NVDA
```

### 실전 트레이딩 (장중)
```bash
# WebSocket으로 실시간 모니터링 (무한)
python collect_prices.py --mode websocket
```

### 장 마감 후
```bash
# 스냅샷으로 최종 가격 기록
python collect_prices.py --mode snapshot
```

## 📊 Finnhub API 무료 Tier 제약

| 항목 | 제한 |
|------|------|
| REST API | 60 calls/분 |
| WebSocket | 1 connection |
| 동시 구독 | 무제한 ticker |
| 지연 | ~100ms |
| Historical | 1년 |

**20개 종목 모니터링 가능:**
- WebSocket: 1 connection에 20개 ticker 구독 ✅
- REST: 60/min ÷ 20 tickers = 3번/분 폴링 가능 ✅

## ⚠️ 주의사항

1. **시장 개장 시간**
   - WebSocket은 시장 개장 중에만 실시간 업데이트
   - 장 마감 후: 스냅샷 모드 사용

2. **Rate Limit**
   - REST: 60/분 초과 시 429 에러
   - WebSocket: 1 API key = 1 connection만

3. **데이터 지연**
   - 무료 Tier: ~100ms 지연
   - 실시간 트레이딩에는 충분

## 🔧 문제 해결

### Q: WebSocket에서 업데이트가 없음
**A:** 시장이 닫혀 있을 수 있습니다.
- 미국 장중 시간: 09:30-16:00 ET (23:30-06:00 KST)
- 스냅샷 모드로 확인: `python collect_prices.py --mode snapshot`

### Q: "Invalid API key" 오류
**A:** `.env` 파일에 올바른 API 키 입력 확인
```bash
FINNHUB_API_KEY=your_actual_key_here
```

### Q: 429 Too Many Requests
**A:** Rate limit 초과
- WebSocket 모드 사용 (권장)
- REST 폴링 간격 증가: `--interval 10`

## 💡 성능 최적화 팁

1. **WebSocket 우선 사용**: 폴링보다 효율적
2. **장중 사용**: 실시간 데이터는 시장 개장 중에만
3. **필요한 종목만**: `--tickers` 옵션으로 선택
4. **백그라운드 실행**:
   ```bash
   nohup python collect_prices.py --mode websocket > prices.log 2>&1 &
   ```

## 📚 추가 리소스

- [Finnhub API 문서](https://finnhub.io/docs/api)
- [WebSocket API 가이드](https://finnhub.io/docs/api/websocket-trades)
- [Python SDK](https://github.com/Finnhub-Stock-API/finnhub-python)

## 🚀 다음 단계

1. 뉴스 + 가격 통합 수집
2. GPT-4o mini 분석 연동
3. 실시간 트레이딩 시그널 생성

---

**팁:** 시장 개장 시간에 WebSocket 모드를 실행하면 실시간으로 거래가 활발한 종목의 가격 변동을 볼 수 있습니다!
