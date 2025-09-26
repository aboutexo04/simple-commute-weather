# Commute Weather Comfort Baseline

Practice project for estimating a commute "comfort score" from recent weather conditions.
The initial version prioritizes a simple heuristic baseline built on the last 3 hours of
observations so you can iterate quickly before investing in full machine learning models.

## Project Goals

- fetch recent weather observations via HTTP API (or from stored samples)
- normalize raw payloads into a consistent schema
- compute commute comfort score using interpretable heuristics
- establish testing + packaging scaffold that is ready for ML upgrades

## Project Layout

```text
commute-weather-self/
├── data/
│   ├── raw/                 # staged downloads or sample payloads
│   ├── interim/             # intermediate feature sets or caches
│   └── processed/           # curated datasets ready for modeling
├── notebooks/               # exploratory analysis (placeholder)
├── scripts/
│   └── run_baseline.py      # CLI entry-point for baseline scoring
├── src/commute_weather/
│   ├── __init__.py
│   ├── config.py            # dataclasses for paths + API configuration
│   ├── data_sources/
│   │   └── weather_api.py   # HTTP fetch + normalization helpers
│   └── pipelines/
│       └── baseline.py      # heuristic comfort score pipeline
├── tests/
│   └── test_baseline.py     # pytest coverage for heuristics
├── .env.example             # expected environment variables
├── pyproject.toml           # package + dependency metadata
└── README.md
```

## Getting Started

1. **Python environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   pip install -e .[dev]
   ```

2. **Environment variables**
   ```bash
   cp .env.example .env
   # edit .env with your provider's values
   ```
   Export the variables or use a tool like `direnv`/`dotenv` when running scripts.

3. **Run heuristic baseline with sample payload**
   ```bash
   python scripts/run_baseline.py sample
   ```

4. **Hit a real API (when ready)**
   ```bash
   python scripts/run_baseline.py api \
     --base-url "https://api.your-provider.com/weather" \
     --location "Seoul,KR"
   ```

   The script expects an `/observations` endpoint that accepts `location` and `hours`
   query parameters and returns JSON matching the stub in
   `data/raw/example_recent_weather.json`. Adjust
   `src/commute_weather/data_sources/weather_api.py` to fit your provider.

5. **Pull directly from KMA typ01 API**
   ```bash
   python scripts/run_baseline.py kma \
     --kma-auth-key "<your auth key>" \
     --kma-station 108 \
     --lookback-hours 3
   ```
   The CLI rounds to the latest full hour in Asia/Seoul, so no database is required—observations stream straight from KMA.

6. **Run tests**
   ```bash
   pytest
   ```

## Extending Toward Machine Learning

- Log raw hourly pulls under `data/raw/` and promote cleaned datasets into
  `data/processed/` for model training.
- Use `notebooks/` to explore candidate features, evaluate correlations, and decide on
  targets (e.g., binning comfort into labels).
- Snapshot the heuristic score as your baseline metric so that future ML experiments can
  prove value.
- Add pipelines under `src/commute_weather/pipelines/` for feature engineering and model
  inference; save models to `models/` (create the directory once needed).

## KMA Weather API Integration

이 프로젝트는 한국 기상청(KMA) API를 사용하여 실시간 기상 데이터를 받아와 출퇴근길 쾌적지수를 예측합니다.

### 새로운 기능

- ✅ 기상청 API 연동 (`fetch_kma_weather`)
- ✅ 출퇴근 시간대별 예측 (`CommutePredictor`)
- ✅ 자동화된 스케줄러 (`CommuteScheduler`)
- ✅ CLI 인터페이스 (`run_commute_predictor.py`)

### 사용법

1. **환경 설정**
   ```bash
   cp .env.example .env
   # .env 파일에서 KMA_AUTH_KEY를 설정하세요
   export KMA_AUTH_KEY="your-api-key"
   export KMA_STATION_ID="108"  # 108 = 서울
   ```

2. **즉시 예측**
   ```bash
   python scripts/run_commute_predictor.py now
   ```

3. **출근길 예측** (최근 3시간 데이터 기반)
   ```bash
   python scripts/run_commute_predictor.py morning
   ```

4. **퇴근길 예측** (오후 2-5시 데이터 기반)
   ```bash
   python scripts/run_commute_predictor.py evening
   ```

5. **자동 스케줄 실행**
   ```bash
   python scripts/run_commute_predictor.py schedule
   ```
   - 매일 오전 7시: 출근길 예측
   - 오후 2-6시: 매시간 퇴근길 예측

6. **API 연결 테스트**
   ```bash
   python scripts/run_commute_predictor.py test
   ```

### 쾌적지수 계산 방식

기본 점수 100점에서 다음 요소들에 대해 페널티를 적용:

- **온도**: 10-25°C 외 구간에서 페널티 (최대 40점)
- **강수량**: 강수 시 페널티 (최대 35점)
- **풍속**: 4m/s 초과 시 페널티 (최대 25점)
- **습도**: 30-70% 외 구간에서 페널티 (최대 15점)

결과:
- 80점 이상: 완벽 ☀️
- 60-79점: 쾌적 😊
- 40-59점: 보통 🌤️
- 40점 미만: 불편 🌧️

## 🌐 웹앱 배포

### FastAPI 웹 인터페이스

프로젝트에 웹 인터페이스가 추가되었습니다!

#### 로컬 실행
```bash
# 의존성 설치
pip install fastapi uvicorn

# 웹앱 실행
export KMA_AUTH_KEY="your-api-key"
uvicorn app:app --host 0.0.0.0 --port 8001

# 브라우저에서 http://localhost:8001 접속
```

#### Vercel 배포 (추천)

1. **GitHub 저장소에 푸시**
   ```bash
   git add .
   git commit -m "Add FastAPI web interface"
   git push origin main
   ```

2. **Vercel에서 배포**
   - [Vercel](https://vercel.com)에 접속
   - GitHub 저장소 연결
   - 자동 배포 시작

3. **환경변수 설정**
   - Vercel Dashboard → Settings → Environment Variables
   - `KMA_AUTH_KEY`: 기상청 API 키 입력
   - `KMA_STATION_ID`: 108 (서울, 기본값)

#### 대안 배포 옵션

- **Railway**: GitHub 연동 자동 배포
- **Render**: 무료 플랜 제공
- **Heroku**: 클래식한 배포 플랫폼

### 웹앱 기능

🖥️ **사용자 친화적 인터페이스**
- 반응형 디자인
- 실시간 날씨 예측
- 직관적인 버튼 인터페이스

📱 **주요 기능**
- 📱 지금 날씨: 현재 시점 예측
- 🌅 출근길 예측: 최근 3시간 데이터
- 🌆 퇴근길 예측: 오후 2-5시 데이터
- 🔍 API 테스트: 연결 상태 확인

🎨 **UI/UX 특징**
- 그라데이션 배경
- 글래스모피즘 디자인
- 점수별 색상 구분 (완벽/쾌적/보통/불편)
- 실시간 로딩 상태 표시

## Next Steps Checklist

- [x] hook up a real weather API client (KMA API implemented)
- [x] schedule periodic data pulls (scheduler implemented)
- [x] create web interface (FastAPI implemented)
- [x] setup deployment configuration (Vercel ready)
- [ ] design evaluation metrics and create an experiment notebook
- [ ] prototype an ML model and compare against the heuristic baseline
