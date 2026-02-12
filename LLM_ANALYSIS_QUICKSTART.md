# 🤖 GPT-4o mini 뉴스 분석 가이드

## 빠른 시작

### 1단계: OpenAI API 키 설정

1. [OpenAI Platform](https://platform.openai.com/api-keys)에서 API 키 발급
2. `.env` 파일에 추가:
   ```env
   OPENAI_API_KEY=your_openai_api_key_here
   OPENAI_MODEL=gpt-4o-mini
   ```

### 2단계: 연결 테스트

```bash
python test_llm_analysis.py
```

성공 출력:
```
✓ ALL TESTS PASSED - LLM Analysis System Ready!
```

## 📊 주요 기능

### 1. 뉴스 분석 및 트레이딩 시그널 생성

- **Pre-Market 분석**: 장 시작 전 overnight 뉴스 분석
- **Realtime 분석**: 실시간 브레이킹 뉴스 분석
- **배치 처리**: 대량 뉴스를 배치로 나눠 처리 (토큰 제한 대응)

### 2. 분석 결과 구조

```json
{
  "market_sentiment": "bullish|bearish|neutral",
  "market_summary": "간단한 시장 요약",
  "ticker_analyses": [
    {
      "ticker": "AAPL",
      "signal": "strong_buy|buy|hold|sell|strong_sell",
      "sentiment": "positive|negative|neutral",
      "confidence": 0.85,
      "expected_impact": "bullish|bearish|neutral",
      "impact_magnitude": "low|medium|high",
      "key_points": ["포인트 1", "포인트 2"],
      "risk_factors": ["리스크 1", "리스크 2"],
      "reasoning": "시그널에 대한 상세 설명"
    }
  ],
  "top_opportunities": ["기회 1", "기회 2"],
  "top_risks": ["리스크 1", "리스크 2"],
  "priority_tickers": ["TICKER1", "TICKER2"],
  "avoid_tickers": ["TICKER1", "TICKER2"],
  "overall_risk_level": "low|medium|high|extreme"
}
```

## 💡 사용 예시

### Python 코드로 분석 실행

```python
from src.analysis.llm_agent import LLMAgent
from dotenv import load_dotenv
import os
import json

# 환경 변수 로드
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

# Agent 초기화
agent = LLMAgent(api_key=api_key)

# 뉴스 데이터 로드
with open("data/news/news_20260212_222419.json") as f:
    news_articles = json.load(f)

# 가격 데이터
current_prices = {
    "AAPL": 275.50,
    "NVDA": 190.05,
    "TSLA": 428.27,
}

# Pre-Market 분석
result = agent.analyze_news(
    news_articles=news_articles[:10],
    current_prices=current_prices,
    mode="pre_market",
    time_to_open="30 minutes"
)

# 결과 확인
print(f"Market Sentiment: {result.market_sentiment}")
print(f"Signals: {len(result.ticker_analyses)}")

for analysis in result.ticker_analyses:
    print(f"\n{analysis.ticker}: {analysis.signal.value}")
    print(f"  Confidence: {analysis.confidence}")
    print(f"  Reasoning: {analysis.reasoning}")

print(f"\nCost: ${result.cost_usd:.4f}")
print(f"Tokens: {result.tokens_used:,}")
```

### 배치 분석 (대량 뉴스)

```python
# 뉴스를 배치로 나누기 (20개씩)
batches = LLMAgent.create_news_batches(news_articles, batch_size=20)

# 배치 분석 실행
results = agent.batch_analyze(
    news_batches=batches,
    current_prices=current_prices,
    mode="pre_market"
)

# 전체 비용 계산
total_cost = sum(r.cost_usd for r in results)
print(f"Total Cost: ${total_cost:.4f}")
```

## 📈 분석 모드

### Pre-Market Mode

**용도:** 장 시작 전 overnight 뉴스 종합 분석

**특징:**
- 시장 개장 전 주요 이벤트 파악
- Earnings, 제품 발표, M&A 등 중점 분석
- 장 시작 시 큰 움직임 예상 종목 식별

**예시:**
```python
result = agent.analyze_news(
    news_articles=overnight_news,
    current_prices=pre_market_prices,
    mode="pre_market",
    time_to_open="30 minutes"
)
```

### Realtime Mode

**용도:** 실시간 브레이킹 뉴스 분석

**특징:**
- 즉각적인 트레이딩 기회 포착
- 가격 변동과 뉴스 sentiment 비교
- 빠른 포지션 조정 시그널

**예시:**
```python
result = agent.analyze_news(
    news_articles=breaking_news,
    current_prices=current_prices,
    previous_prices=prices_1h_ago,
    mode="realtime",
    market_status="OPEN",
    time_window="30 minutes"
)
```

## 💰 비용 최적화

### GPT-4o mini 가격 (2025 기준)

| 항목 | 가격 |
|------|------|
| Input Tokens | $0.15 / 1M tokens |
| Output Tokens | $0.60 / 1M tokens |

### 실제 비용 예시

**테스트 결과:**
- 10개 뉴스 분석: ~$0.0005 (~2,000 tokens)
- 배치 분석 (15개 뉴스, 3 batches): ~$0.0016 (~5,500 tokens)

**예상 비용:**
- 일 1회 Pre-market 분석 (50개 뉴스): ~$0.003
- 실시간 분석 10회/일 (각 10개 뉴스): ~$0.005
- **월간 예상 비용: ~$0.25**

### 비용 절감 팁

1. **배치 처리 활용**
   ```python
   # 20개씩 배치로 나눠서 처리
   batches = LLMAgent.create_news_batches(news, batch_size=20)
   ```

2. **뉴스 필터링**
   - 관련성 낮은 뉴스 사전 제거
   - 중복 뉴스 제거
   - 주요 종목 관련 뉴스만 선택

3. **Description 축약**
   - 200자로 자동 축약 (prompt_templates.py)
   - 불필요한 메타데이터 제외

4. **Temperature 낮추기**
   - 더 결정적인 응답 (토큰 절약)
   - 기본값: 0.1

## 🎯 시그널 활용

### Buy Signals 필터링

```python
# Strong Buy 시그널만 추출
strong_buys = [
    a for a in result.ticker_analyses
    if a.signal == TradingSignal.STRONG_BUY
]

# 고신뢰도 시그널 (confidence > 0.8)
high_confidence = [
    a for a in result.ticker_analyses
    if a.confidence > 0.8
]

# 또는 헬퍼 메서드 사용
buy_signals = result.get_buy_signals()
high_conf_signals = result.high_confidence_signals
```

### 리스크 관리

```python
# 전체 리스크 레벨 확인
if result.overall_risk_level == RiskLevel.EXTREME:
    print("⚠️ Extreme risk - reduce position sizes")

# 종목별 리스크 확인
for analysis in result.ticker_analyses:
    if analysis.risk_factors:
        print(f"{analysis.ticker} risks:")
        for risk in analysis.risk_factors:
            print(f"  - {risk}")
```

## 📁 파일 구조

```
src/analysis/
├── __init__.py           # 모듈 초기화
├── models.py             # Pydantic 모델 (AnalysisResult, TradingSignal)
├── prompt_templates.py   # 프롬프트 템플릿
└── llm_agent.py          # OpenAI API 연동

test_llm_analysis.py      # 테스트 스크립트
```

## 🔧 고급 사용

### 커스텀 프롬프트

```python
from src.analysis.prompt_templates import PromptTemplates

# 커스텀 프롬프트 빌드
custom_prompt = PromptTemplates.build_pre_market_prompt(
    news_articles=news,
    current_prices=prices,
    time_to_open="1 hour"
)

# 직접 OpenAI API 호출
response = agent.client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": PromptTemplates.SYSTEM_PROMPT},
        {"role": "user", "content": custom_prompt}
    ],
    response_format={"type": "json_object"}
)
```

### 모델 변경

```python
# 더 강력한 모델 사용 (비용 증가)
agent = LLMAgent(
    api_key=api_key,
    model="gpt-4o",  # 더 비싸지만 정확
    max_tokens=8192,
    temperature=0.0
)
```

## ⚠️ 주의사항

1. **API 키 보안**
   - `.env` 파일을 git에 커밋하지 마세요
   - API 키를 코드에 하드코딩하지 마세요

2. **Rate Limits**
   - OpenAI Tier 1: 500 RPM, 200K TPM
   - Tier 2: 5,000 RPM, 2M TPM
   - 배치 분석 시 rate limit 주의

3. **JSON 파싱 에러**
   - 드물게 LLM이 잘못된 JSON 반환 가능
   - 자동으로 재시도 로직 구현 권장

4. **시그널 검증**
   - LLM 시그널을 맹신하지 마세요
   - 실제 가격 데이터와 교차 검증
   - 백테스팅 필수

## 🚀 다음 단계

1. **뉴스 수집과 통합**
   ```bash
   python collect_news.py  # 뉴스 수집
   python test_llm_analysis.py  # 분석 실행
   ```

2. **실시간 가격과 연동**
   ```python
   # Finnhub 가격 + GPT-4o mini 분석
   from src.data.price_collector import FinnhubPriceCollector

   price_collector = FinnhubPriceCollector(api_key=finnhub_key)
   current_prices = price_collector.get_quotes(tickers)

   analysis = agent.analyze_news(news, current_prices, mode="realtime")
   ```

3. **Discord 알림 통합**
   - 고신뢰도 시그널 자동 알림
   - 리스크 경고 알림

4. **백테스팅**
   - 과거 뉴스로 시그널 생성
   - 실제 가격 변동과 비교
   - 시그널 정확도 측정

## 📚 참고 자료

- [OpenAI API Documentation](https://platform.openai.com/docs/api-reference)
- [GPT-4o mini Pricing](https://openai.com/api/pricing/)
- [JSON Mode Guide](https://platform.openai.com/docs/guides/structured-outputs)

---

**팁:** 실제 트레이딩에 사용하기 전에 충분한 백테스팅과 검증을 거치세요!
