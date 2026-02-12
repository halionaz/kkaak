# 🐦‍⬛🪙 kkaak

까악, 돈을 벌어다 주는 까마귀

GPT-4o mini를 활용한 **미국 주식 뉴스 기반 트레이딩 시그널 봇**입니다.
장전 및 실시간 뉴스를 LLM으로 분석하여 매수/매도/hold 시그널을 Discord로 전송합니다.

⚠️ **면책사항**: 이 봇은 투자 조언이 아닙니다. 모든 투자 결정과 손실은 사용자 책임입니다.

---

## ✨ 주요 기능

- 🔔 **장전 리포트**: 매일 아침 overnight 뉴스 종합 분석 + 20개 종목 시그널 (08:30 ET)
- 🚨 **실시간 시그널 업데이트**: 30분 간격으로 뉴스 & 가격 변동 모니터링, 보수적 시그널 업데이트
- 📊 **보수적 필터링**:
  - 신뢰도 70% 미만 자동 HOLD
  - 매수 ↔ 매도 전환 시 80% 이상 신뢰도 요구
  - 이전 시그널과 비교하여 중복 알림 방지
- 💡 **포지션 추적**: 현재 매수/매도/유지 포지션 자동 추적 및 변경사항 감지
- 📈 **Discord 알림**: Webhook을 통한 실시간 리포트 및 시그널 전송

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

### 1. 테스트 실행 (권장)
```bash
# 전체 파이프라인 테스트
python test_pipeline.py

# 또는 개별 컴포넌트 테스트
python test_llm_analysis.py  # LLM 분석 테스트
python src/data/news_collector.py  # 뉴스 수집 테스트
python src/data/price_collector.py  # 가격 수집 테스트
```

### 2. 실제 실행

#### 테스트 모드 (즉시 한 번 실행)
```bash
python main.py --test
```

#### 프로덕션 모드 (스케줄에 따라 자동 실행)
```bash
python main.py
```

실행 시 자동으로:
- **08:30 ET**: 장전 리포트 Discord 전송 (overnight 뉴스 분석)
- **09:30-16:00 ET**: 30분마다 실시간 뉴스 모니터링 및 시그널 업데이트 (보수적)
- Discord로 변경사항만 알림

### 3. Docker 실행 (선택사항)
```bash
docker build -t kkaak .
docker run -d --env-file .env kkaak
```

## 📋 시스템 구조

```
┌─────────────────────────────────────────────────────────────────┐
│                    Trading Pipeline (main.py)                   │
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐     │
│  │   Scheduler  │───>│   Pre-Market │───>│   Realtime   │     │
│  │   (08:30 ET) │    │   Analysis   │    │   Analysis   │     │
│  │  (30min int) │    │              │    │  (30min int) │     │
│  └──────────────┘    └──────────────┘    └──────────────┘     │
│                             │                     │             │
└─────────────────────────────┼─────────────────────┼─────────────┘
                              │                     │
                              v                     v
                    ┌──────────────────────────────────┐
                    │     Data Collection Layer       │
                    ├──────────────────────────────────┤
                    │  • News (Massive API)           │
                    │  • Prices (Finnhub API)         │
                    └──────────────────────────────────┘
                              │
                              v
                    ┌──────────────────────────────────┐
                    │     LLM Analysis Layer          │
                    ├──────────────────────────────────┤
                    │  • GPT-4o mini Analysis         │
                    │  • Sentiment + Signals          │
                    │  • Confidence Scoring           │
                    └──────────────────────────────────┘
                              │
                              v
                    ┌──────────────────────────────────┐
                    │   Signal Management Layer       │
                    ├──────────────────────────────────┤
                    │  • Signal Generation            │
                    │  • Conservative Filtering       │
                    │  • Position Tracking            │
                    └──────────────────────────────────┘
                              │
                              v
                    ┌──────────────────────────────────┐
                    │   Notification Layer            │
                    ├──────────────────────────────────┤
                    │  • Discord Webhooks             │
                    │  • Pre-market Reports           │
                    │  • Realtime Alerts              │
                    └──────────────────────────────────┘
```

## 📊 Discord 알림 예시

### 장전 리포트 (08:30 ET)
```
🔔 [PREMARKET REPORT] 2026-02-12 08:30 ET

📈 BUY 시그널 (High Confidence):
• AAPL (85%) - 신제품 발표로 긍정적 전망, 기술 지표 상승세
• NVDA (82%) - AI 칩 수요 급증, 파트너십 확대

⚠️ SELL 시그널:
• META (75%) - 규제 리스크 증가, 광고 수익 전망 하락

✅ HOLD: 나머지 17개 종목

---
💡 오늘의 주요 뉴스:
기술주 강세 지속, Fed 금리 동결 전망, AI 칩 시장 경쟁 심화
```

### 실시간 시그널 업데이트 (30분 간격, 변경사항만)
```
🚨 [BREAKING] NVDA - BUY (90%)

"Nvidia announces major AI chip breakthrough"

📍 현재 상태:
• Price: $850.00 (📈+2.5%)

💡 분석:
AI 칩 기술 혁신으로 시장 점유율 확대 예상. 단기 상승 모멘텀 강력.

🔗 [뉴스 원문](https://...)
```

## 🔄 파이프라인 워크플로우

### Pre-Market Analysis (08:30 ET)
1. **뉴스 수집**: 지난 24시간 주요 뉴스 수집 (Massive API)
2. **가격 수집**: 현재 pre-market 가격 수집 (Finnhub API)
3. **LLM 분석**: GPT-4o mini로 overnight 뉴스 종합 분석
4. **시그널 생성**: 20개 종목에 대한 매수/매도/유지 시그널 생성
5. **포지션 초기화**: 오늘의 초기 포지션 설정
6. **Discord 알림**: 장전 리포트 전송

### Realtime Analysis (30분 간격, 09:30-16:00 ET)
1. **뉴스 수집**: 최근 30분간 브레이킹 뉴스 수집
2. **가격 수집**: 현재 가격 + 이전 가격과 비교
3. **LLM 분석**: 실시간 뉴스 및 가격 변동 분석
4. **보수적 필터링**:
   - 신뢰도 70% 미만 → HOLD
   - 매수 ↔ 매도 전환 시 80% 이상 요구
   - 이전 시그널과 비교하여 유의미한 변화만 선택
5. **포지션 업데이트**: 변경사항 감지 및 업데이트
6. **Discord 알림**: 변경된 시그널만 전송 (중복 방지)

### 보수적 필터링 규칙
```python
# Signal Manager 설정
MIN_CONFIDENCE = 0.7   # 최소 신뢰도
HIGH_CONFIDENCE = 0.8  # 강한 시그널 (방향 전환 시 필요)

# 필터링 로직
if confidence < 0.7:
    → HOLD

if 이전 시그널 == BUY and 새 시그널 == SELL:
    if confidence < 0.8:
        → 이전 시그널 유지 (BUY)

if confidence < 이전 confidence - 0.1:
    → HOLD (신뢰도 하락)
```

## ⚙️ 설정 커스터마이징

### 종목 설정 (`config/stocks.yaml`)
```yaml
stocks:
  - ticker: "AAPL"
    name: "Apple Inc."
    sector: "Technology"
    priority: 1  # 1=high, 2=medium
```

### 스케줄 설정 (`src/pipeline/scheduler.py`)
```python
PRE_MARKET_ANALYSIS_TIME = dt_time(8, 30)  # 장전 분석 시간
REALTIME_INTERVAL_MINUTES = 30              # 실시간 분석 간격
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

## 📁 프로젝트 구조

```
kkaak/
├── main.py                      # 메인 실행 파일
├── test_pipeline.py             # 파이프라인 테스트
├── test_llm_analysis.py         # LLM 분석 테스트
│
├── config/
│   └── stocks.yaml              # 모니터링 종목 설정 (20개)
│
├── src/
│   ├── data/                    # 데이터 수집
│   │   ├── news_collector.py   # Massive API 뉴스 수집
│   │   ├── price_collector.py  # Finnhub API 가격 수집
│   │   └── models.py            # 데이터 모델
│   │
│   ├── analysis/                # LLM 분석
│   │   ├── llm_agent.py        # GPT-4o mini 연동
│   │   ├── models.py            # 분석 결과 모델
│   │   └── prompt_templates.py  # 프롬프트 템플릿
│   │
│   ├── pipeline/                # 트레이딩 파이프라인
│   │   ├── signal_manager.py   # 시그널 생성 및 관리
│   │   ├── position_tracker.py # 포지션 추적
│   │   └── scheduler.py         # 스케줄링
│   │
│   ├── notification/            # 알림
│   │   └── discord_notifier.py # Discord 웹훅
│   │
│   └── utils/                   # 유틸리티
│       └── config_loader.py    # 설정 로더
│
└── data/                        # 데이터 저장소
    ├── news/                    # 뉴스 아카이브
    ├── prices/                  # 가격 데이터
    ├── signals/                 # 시그널 히스토리
    │   └── positions.json      # 현재 포지션
    ├── logs/                    # 로그
    └── cache/                   # 캐시
```

## 📈 개발 로드맵

- [x] Massive API 연동
- [x] Finnhub API 연동
- [x] GPT-4o mini 뉴스 분석
- [x] 트레이딩 시그널 파이프라인
- [x] 포지션 추적 시스템
- [x] Discord 알림 시스템
- [x] 보수적 시그널 필터링
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
