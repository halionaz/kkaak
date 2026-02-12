# 🐦‍⬛🪙 kkaak

까악, 돈을 벌어다 주는 까마귀

GPT-4o mini를 활용한 **미국 주식 뉴스 기반 트레이딩 시그널 봇**입니다.
장전 및 실시간 뉴스를 LLM으로 분석하여 매수/매도/hold 시그널을 Discord로 전송합니다.

⚠️ **면책사항**: 이 봇은 투자 조언이 아닙니다. 모든 투자 결정과 손실은 사용자 책임입니다.

---

## ✨ 주요 기능

- 🔔 **장전 리포트**: 매일 아침 전일 뉴스 분석 + 20개 종목 시그널 (08:00-09:30 ET)
- 🚨 **실시간 긴급 시그널**: 중요 뉴스 발생 시 즉시 분석 및 알림 (5분 간격 모니터링)
- 📊 **기술 지표 결합**: RSI, MACD, EMA, SMA 등 기술 분석 교차 검증
- 💡 **신뢰도 기반 판단**: LLM 분석 신뢰도 70% 미만은 자동 HOLD 처리
- 📈 **Discord 알림**: Webhook을 통한 실시간 시그널 전송

## 🛠️ 기술 스택

- **데이터 소스**: [Massive.com API](https://massive.com) (미국 주식 뉴스 + 시세 + 기술 지표)
- **LLM**: OpenAI GPT-4o mini
- **알림**: Discord Webhook
- **언어**: Python 3.10+
- **주요 라이브러리**: `requests`, `openai`, `pydantic`, `loguru`, `schedule`

## 📦 설치 방법

### 1. 저장소 클론
```bash
git clone https://github.com/yourusername/kkaak.git
cd kkaak
```

### 2. 의존성 설치
```bash
pip install -r requirements.txt
```

### 3. 환경 변수 설정
`.env.example`을 복사하여 `.env` 파일 생성 후 API 키 입력:
```bash
cp .env.example .env
```

`.env` 파일 내용:
```env
MASSIVE_API_KEY=your_massive_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
DISCORD_WEBHOOK_URL=your_discord_webhook_url_here
```

### 4. 종목 설정
`config/stocks.yaml`에 모니터링할 20개 미국 주식 종목 추가:
```yaml
stocks:
  - ticker: "AAPL"
    name: "Apple Inc."
    sector: "Technology"
  - ticker: "TSLA"
    name: "Tesla Inc."
    sector: "Automotive"
  # ... 18개 추가
```

## 🚀 사용 방법

### 로컬 실행
```bash
python src/main.py
```

실행 시 자동으로:
- **08:00 ET**: 장전 리포트 Discord 전송
- **09:30-16:00 ET**: 5분마다 실시간 뉴스 모니터링
- **16:00 ET**: 장후 일일 요약 전송

### Docker 실행 (선택사항)
```bash
docker build -t kkaak .
docker run -d --env-file .env kkaak
```

## 📋 시스템 구조

```
[Massive API] ──┬──> [뉴스 수집] ────┐
                │                    │
                └──> [시세 수집] ─────┼──> [LLM 분석] ──> [의사결정] ──> [Discord 알림]
                                     │    (GPT-4o mini)    (리스크 관리)
[기술 지표] ─────────────────────────┘
```

## 📊 Discord 알림 예시

### 장전 리포트
```
🔔 [PREMARKET REPORT] 2026-02-12 08:30 ET

📈 BUY 시그널 (High Confidence):
• AAPL (85%) - 신제품 발표로 긍정적 전망
  📍 RSI: 45, MACD: +1.2

⚠️ SELL 시그널:
• META (72%) - 규제 리스크 증가

✅ HOLD: 나머지 17개 종목
```

### 실시간 긴급 시그널
```
🚨 [BREAKING] NVDA - BUY (90%)

"Nvidia announces new AI chip partnership"

📍 Price: $850 (+2.5%)
💡 AI 칩 시장 선점 강화로 단기 급등 전망
```

## ⚙️ 설정 커스터마이징

### 리스크 관리 (`config/trading_rules.yaml`)
```yaml
risk_management:
  confidence_threshold: 0.7      # 최소 신뢰도 70%
  max_trades_per_day: 3          # 종목당 일일 최대 시그널

decision_weights:
  llm_analysis: 0.6              # LLM 분석 가중치 60%
  technical_analysis: 0.4        # 기술 지표 가중치 40%
```

## 🐛 문제 해결

### API 연결 오류
```
⚠️ Massive API 연결 실패
```
→ `.env` 파일의 `MASSIVE_API_KEY` 확인

### Discord 알림 미수신
```
🚨 Discord webhook 전송 실패
```
→ `DISCORD_WEBHOOK_URL`이 올바른지 확인

## 📈 개발 로드맵

- [x] Massive API 연동
- [x] GPT-4o mini 뉴스 분석
- [x] Discord 알림 시스템
- [ ] 백테스팅 기능
- [ ] 웹 대시보드
- [ ] 다중 Discord 채널 지원

## 📄 라이선스

MIT License

## ⚠️ 법적 고지

- 본 소프트웨어는 **교육 및 연구 목적**으로 제공됩니다
- 실제 투자에 사용 시 발생하는 **모든 손실은 사용자 책임**입니다
- 제공되는 시그널은 **투자 조언이 아니며**, 참고용 정보입니다
- 주식 투자는 원금 손실 위험이 있습니다

---

🐦‍⬛ 까악이 좋은 소식을 물어다 드릴게요! 💰
