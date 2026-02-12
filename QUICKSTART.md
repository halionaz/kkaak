# 🚀 Quick Start Guide

## 빠른 시작

### 1단계: 의존성 설치

```bash
pip install -r requirements.txt
```

### 2단계: API 키 설정

`.env` 파일을 생성하고 Massive API 키를 입력하세요:

```bash
cp .env.example .env
```

`.env` 파일을 편집:
```env
MASSIVE_API_KEY=your_actual_api_key_here
OPENAI_API_KEY=your_openai_key_here  # 선택사항
DISCORD_WEBHOOK_URL=your_webhook_url # 선택사항
```

**Massive API 키 발급 방법:**
1. [Massive.com](https://massive.com) 방문
2. 회원가입 및 로그인
3. [Dashboard > API Keys](https://massive.com/dashboard/api-keys)에서 키 생성

### 3단계: 연결 테스트

```bash
python test_massive_api.py
```

성공하면 다음과 같이 표시됩니다:
```
✓ ALL TESTS PASSED - System is ready to use!
```

### 4단계: 뉴스 수집 시작

#### 옵션 A: 과거 뉴스 한 번만 수집
```bash
python collect_news.py --mode historical --hours 24
```

#### 옵션 B: 실시간 뉴스 모니터링 (권장)
```bash
python collect_news.py --mode realtime --interval 60
```

#### 옵션 C: 통합 모드 (과거 + 실시간)
```bash
python collect_news.py --mode both --hours 24 --interval 60
```

## 📊 수집된 데이터 확인

수집된 뉴스는 `data/news/` 디렉토리에 JSON 형식으로 저장됩니다:

```bash
ls -lh data/news/
```

JSON 파일 예시:
```json
[
  {
    "id": "abc123",
    "title": "Apple announces new product",
    "tickers": ["AAPL"],
    "sentiment": "positive",
    "published_utc": "2026-02-12T14:30:00Z",
    "article_url": "https://...",
    "description": "Apple has announced..."
  }
]
```

## 🎯 특정 종목만 모니터링

설정 파일의 모든 종목 대신 특정 종목만 모니터링하려면:

```bash
python collect_news.py --tickers AAPL NVDA TSLA --mode realtime
```

## ⚙️ 고급 옵션

### 폴링 간격 조정
```bash
python collect_news.py --mode realtime --interval 30  # 30초마다 체크
```

### 제한 시간 실행
```bash
python collect_news.py --mode realtime --duration 120  # 2시간 동안만 실행
```

### 과거 데이터 기간 설정
```bash
python collect_news.py --mode historical --hours 48  # 최근 48시간
```

## 🔔 Discord 알림 설정 (선택사항)

1. Discord에서 서버 선택
2. 채널 설정 > 통합 > 웹후크 생성
3. 웹후크 URL 복사
4. `.env` 파일에 추가:
   ```env
   DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
   ```

5. 테스트:
   ```bash
   python -c "from src.notification.discord_notifier import test_discord_webhook; import os; from dotenv import load_dotenv; load_dotenv(); test_discord_webhook(os.getenv('DISCORD_WEBHOOK_URL'))"
   ```

## 📁 프로젝트 구조

```
kkaak/
├── collect_news.py          # 뉴스 수집 실행 스크립트
├── test_massive_api.py      # API 연결 테스트
├── .env                     # API 키 설정 (생성 필요)
├── config/
│   └── stocks.yaml          # 모니터링 종목 설정
├── data/
│   ├── logs/               # 로그 파일
│   └── news/               # 수집된 뉴스 JSON
└── src/
    ├── data/               # 데이터 수집
    ├── notification/       # Discord 알림
    └── utils/              # 유틸리티
```

## ❓ 문제 해결

### Q: "massive library not installed" 오류
```bash
pip install massive
```

### Q: "MASSIVE_API_KEY not found" 오류
`.env` 파일을 생성하고 API 키를 입력하세요.

### Q: 뉴스가 수집되지 않음
- API 키가 유효한지 확인
- 최근 뉴스가 있는 종목인지 확인
- `--hours` 값을 늘려보세요 (예: `--hours 48`)

### Q: Discord 알림이 안 옴
- `DISCORD_WEBHOOK_URL`이 정확한지 확인
- 웹후크가 비활성화되지 않았는지 확인
- Discord 테스트 스크립트 실행:
  ```bash
  python src/notification/discord_notifier.py
  ```

## 🎓 다음 단계

1. `config/stocks.yaml`에서 원하는 종목으로 변경
2. 실시간 모니터링을 백그라운드에서 실행:
   ```bash
   nohup python collect_news.py --mode realtime --interval 60 > output.log 2>&1 &
   ```
3. 로그 확인:
   ```bash
   tail -f data/logs/news_collection_*.log
   ```

## 💡 팁

- **최적 폴링 간격**: 60초 (Massive API rate limit 고려)
- **권장 시간대**: 미국 장중 09:30-16:00 ET
- **종목 수**: 20개 이하 권장 (API 호출 최적화)
- **데이터 저장**: 정기적으로 `data/news/` 백업

---

문제가 해결되지 않으면 GitHub Issues에 문의하세요.
