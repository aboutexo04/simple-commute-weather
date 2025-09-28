"""FastAPI web application for commute weather predictions."""

import os
from datetime import datetime
from typing import Dict, Any
import pytz

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
import uvicorn

# Import our commute weather modules
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from commute_weather.config import KMAAPIConfig
from commute_weather.pipelines.commute_predictor import CommutePredictor
from commute_weather.data_sources.kma_api import fetch_recent_weather_kma

app = FastAPI(
    title="출퇴근길 날씨 친구",
    description="기상청 데이터를 활용한 실시간 출퇴근 날씨 쾌적도 예측 서비스",
    version="1.0.0"
)

# Create KMA config from environment variables
def get_kma_config() -> KMAAPIConfig:
    auth_key = os.getenv("KMA_AUTH_KEY")
    if not auth_key:
        raise HTTPException(status_code=500, detail="KMA_AUTH_KEY not configured")

    return KMAAPIConfig(
        base_url="https://apihub.kma.go.kr/api/typ01/url/kma_sfctm2.php",
        auth_key=auth_key,
        station_id=os.getenv("KMA_STATION_ID", "108"),
    )

@app.get("/", response_class=HTMLResponse)
async def home():
    """Main page with weather prediction interface."""
    html_content = """
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>출퇴근길 날씨 친구</title>

        <!-- PWA 메타데이터 -->
        <meta name="description" content="기상청 데이터 기반 실시간 출퇴근 쾌적지수 예측 서비스">
        <meta name="theme-color" content="#4A90E2">
        <meta name="apple-mobile-web-app-capable" content="yes">
        <meta name="apple-mobile-web-app-status-bar-style" content="default">
        <meta name="apple-mobile-web-app-title" content="날씨친구">

        <!-- 아이콘 -->
        <link rel="apple-touch-icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><rect width='100' height='100' fill='%234A90E2' rx='20'/><text x='50' y='65' font-size='40' text-anchor='middle' fill='white'>☀️</text></svg>">
        <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><rect width='100' height='100' fill='%234A90E2' rx='20'/><text x='50' y='65' font-size='40' text-anchor='middle' fill='white'>☀️</text></svg>">

        <!-- 매니페스트 -->
        <link rel="manifest" href="/manifest.json">

        <!-- Service Worker 등록 -->
        <script>
            if ('serviceWorker' in navigator) {
                navigator.serviceWorker.register('/sw.js')
                    .then(function(registration) {
                        console.log('SW registered');
                    })
                    .catch(function(registrationError) {
                        console.log('SW registration failed');
                    });
            }
        </script>
        <style>
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
                background: linear-gradient(135deg, #4A90E2 0%, #2E86AB 100%);
                min-height: 100vh;
                color: white;
            }
            .container {
                background: rgba(255, 255, 255, 0.1);
                backdrop-filter: blur(10px);
                border-radius: 20px;
                padding: 30px;
                box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37);
            }
            h1 {
                text-align: center;
                margin-bottom: 30px;
                font-size: 2.5em;
                text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
            }
            .buttons {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px;
                margin-bottom: 30px;
            }
            button {
                padding: 15px 25px;
                font-size: 16px;
                border: none;
                border-radius: 10px;
                background: rgba(255, 255, 255, 0.2);
                color: white;
                cursor: pointer;
                transition: all 0.3s ease;
                backdrop-filter: blur(5px);
            }
            button:hover {
                background: rgba(255, 255, 255, 0.3);
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(0,0,0,0.3);
            }
            #result {
                background: rgba(255, 255, 255, 0.15);
                border-radius: 15px;
                padding: 20px;
                margin-top: 20px;
                min-height: 100px;
                white-space: pre-line;
            }
            .loading {
                text-align: center;
                color: #ccc;
            }
            .score {
                font-size: 2em;
                font-weight: bold;
                text-align: center;
                margin: 20px 0;
            }
            .excellent { color: #FFD700; text-shadow: 1px 1px 2px rgba(0,0,0,0.5); }
            .good { color: #90EE90; text-shadow: 1px 1px 2px rgba(0,0,0,0.5); }
            .uncomfortable { color: #FFA500; text-shadow: 1px 1px 2px rgba(0,0,0,0.5); }
            .harsh { color: #FF6B6B; text-shadow: 1px 1px 2px rgba(0,0,0,0.5); }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🌤️ 출퇴근길 날씨 친구</h1>

            <div class="buttons">
                <button onclick="getPrediction('now')">📱 지금 날씨</button>
                <button onclick="getPrediction('morning')">🌅 출근길 예측</button>
                <button onclick="getPrediction('evening')">🌆 퇴근길 예측</button>
            </div>

            <div id="result">
                <div class="loading" id="welcomeMessage">메시지 로딩 중...</div>
            </div>
        </div>

        <script>
            // 시간대별 메시지 설정
            function setWelcomeMessage() {
                const now = new Date();
                const kstTime = new Date(now.toLocaleString("en-US", {timeZone: "Asia/Seoul"}));
                const hour = kstTime.getHours();
                let message = "";

                if (hour >= 5 && hour < 9) {
                    // 새벽~아침 (5-8시)
                    message = "좋은 아침이에요! 😊<br>오늘 하루도 화이팅입니다! ☀️";
                } else if (hour >= 9 && hour < 12) {
                    // 오전 (9-11시)
                    message = "활기찬 오전이네요! 💪<br>오늘도 좋은 하루 되세요! ✨";
                } else if (hour >= 12 && hour < 14) {
                    // 점심시간 (12-13시)
                    message = "점심시간이에요! 🍽️<br>맛있는 식사 하시고 힘내세요! 😋";
                } else if (hour >= 14 && hour < 18) {
                    // 오후 (14-17시)
                    message = "근무하시느라 힘드시죠? 💼<br>조금만 더 힘내세요! 응원합니다! 📈";
                } else if (hour >= 18 && hour < 22) {
                    // 저녁 (18-21시)
                    message = "오늘도 고생 많으셨어요! 😊<br>푹 쉬시고 좋은 저녁 되세요! 🌆";
                } else {
                    // 밤/새벽 (22-4시)
                    message = "늦은 시간이네요! 🌙<br>푹 쉬시고 내일도 좋은 하루 되세요! 💤";
                }

                document.getElementById('welcomeMessage').innerHTML = message;
            }

            // 페이지 로드 시 메시지 설정
            window.onload = function() {
                setWelcomeMessage();
            };

            async function getPrediction(type) {
                const resultDiv = document.getElementById('result');
                if (type === 'now') {
                    resultDiv.innerHTML = '<div class="loading">⏳ 관측 중...</div>';
                } else {
                    resultDiv.innerHTML = '<div class="loading">⏳ 예측 중...</div>';
                }

                try {
                    const response = await fetch(`/predict/${type}`);
                    const data = await response.json();

                    console.log('Response data:', data); // 디버깅용

                    if (response.ok) {
                        displayResult(data);
                    } else {
                        resultDiv.innerHTML = `❌ 오류: ${data.detail}`;
                    }
                } catch (error) {
                    resultDiv.innerHTML = `❌ 네트워크 오류: ${error.message}`;
                }
            }


            function displayResult(data) {
                // 시간대 안내 메시지 처리
                if (data.message) {
                    document.getElementById('result').innerHTML = `
                        <h3>${data.title}</h3>
                        <p>⏰ <strong>현재 시간:</strong> ${data.current_time}</p>
                        <p>💡 ${data.message}</p>
                        <p>${data.recommendation}</p>
                    `;
                    return;
                }

                const scoreClass = data.score >= 80 ? 'excellent' :
                                 data.score >= 60 ? 'good' :
                                 data.score >= 50 ? 'uncomfortable' : 'harsh';

                const emoji = data.score >= 80 ? '☀️' :
                             data.score >= 60 ? '😊' :
                             data.score >= 50 ? '😣' : '🥶';

                const scoreIcon = data.score >= 60 ? '🌟' : '⚠️';

                // 지금 날씨는 온도/습도/강수량 표시 (쾌적지수 없음)
                if (data.title.includes('현재 시점')) {
                    const precipitationValue = Number(data.current_precipitation ?? 0);
                    let precipitationInfo = '<p>☀️ 강수: 없음</p>';
                    if (precipitationValue > 0) {
                        const precipIcon = data.current_precipitation_type === 'snow' ? '❄️' : '🌧️';
                        const precipType = data.current_precipitation_type === 'snow' ? '눈' : '비';
                        precipitationInfo = `<p>${precipIcon} ${precipType}: ${precipitationValue}mm</p>`;
                    }

                    document.getElementById('result').innerHTML = `
                        <p><strong>📅 현재 시간:</strong> ${data.prediction_time}</p>
                        <p>🌡️ 온도: ${data.current_temp ?? 'N/A'}°C</p>
                        <p>💧 습도: ${data.current_humidity ?? 'N/A'}%</p>
                        ${precipitationInfo}
                    `;
                } else {
                    // 출퇴근 예측은 쾌적지수와 평가만 표시
                    document.getElementById('result').innerHTML = `
                        <div class="score ${scoreClass}">${scoreIcon} ${data.score}/100 (${data.label})</div>
                        <p>${data.evaluation} ${emoji}</p>
                    `;
                }
            }
        </script>
    </body>
    </html>
    """
    return html_content

@app.get("/predict/{prediction_type}")
async def predict(prediction_type: str) -> Dict[str, Any]:
    """Get weather prediction for specified type."""
    try:
        config = get_kma_config()
        predictor = CommutePredictor(config)

        if prediction_type == "now":
            title = "📱 현재 시점 예측"

            prediction = None
            prediction_error = None
            try:
                prediction = predictor.get_current_prediction()
            except Exception as exc:
                prediction_error = str(exc)

            latest = (
                prediction.latest_observation
                if prediction and prediction.latest_observation
                else None
            )

            fetch_error = None
            if latest is None:
                try:
                    latest_observations = fetch_recent_weather_kma(
                        config, lookback_hours=1
                    )
                    latest = latest_observations[-1] if latest_observations else None
                except Exception as exc:  # pragma: no cover - network failure
                    fetch_error = str(exc)

            if latest is None:
                detail = "현재 관측 데이터를 불러오지 못했습니다."
                reason = fetch_error or prediction_error
                if reason:
                    detail = f"{detail} (원인: {reason})"
                raise HTTPException(status_code=502, detail=detail)

            current_temp = latest.temperature_c
            current_humidity = latest.relative_humidity
            current_precipitation = latest.precipitation_mm
            current_precipitation_type = latest.precipitation_type
        elif prediction_type == "morning":
            # 현재 시간이 오전 6-9시가 아니면 안내 메시지 (한국 시간 기준)
            kst = pytz.timezone('Asia/Seoul')
            current_hour = datetime.now(kst).hour
            if not (6 <= current_hour < 9):
                return {
                    "title": "🌅 출근길 예측",
                    "message": "출근길 예측은 오전 6-8시에 가장 정확합니다.",
                    "current_time": datetime.now(kst).strftime("%Y-%m-%d %H:%M"),
                    "recommendation": "아침 시간대에 다시 확인해주세요! 😊"
                }
            prediction = predictor.predict_morning_commute()
            title = "🌅 출근길 예측"
        elif prediction_type == "evening":
            # 현재 시간이 오후 2-6시가 아니면 안내 메시지 (한국 시간 기준)
            kst = pytz.timezone('Asia/Seoul')
            current_hour = datetime.now(kst).hour
            if not (14 <= current_hour <= 18):
                return {
                    "title": "🌆 퇴근길 예측",
                    "message": "퇴근길 예측은 오후 2-6시에 가장 정확합니다.",
                    "current_time": datetime.now(kst).strftime("%Y-%m-%d %H:%M"),
                    "recommendation": "오후 시간대에 다시 확인해주세요! 😊"
                }
            prediction = predictor.predict_evening_commute()
            title = "🌆 퇴근길 예측"
        else:
            raise HTTPException(status_code=400, detail="Invalid prediction type")

        # Generate evaluation message
        score = prediction.comfort_score.score if prediction else 0.0

        # 출근길/퇴근길에 따라 다른 메시지
        if prediction_type == "morning":
            if score >= 80:
                evaluation = "완벽한 출근 날씨입니다!"
            elif score >= 60:
                evaluation = "쾌적한 출근길이 예상됩니다."
            elif score >= 50:
                evaluation = "불편한 출근 날씨입니다. 대비하세요!"
            else:
                evaluation = "매우 불편한 출근 날씨입니다. 각별히 주의하세요!"
        elif prediction_type == "evening":
            if score >= 80:
                evaluation = "완벽한 퇴근 날씨입니다!"
            elif score >= 60:
                evaluation = "쾌적한 퇴근길이 예상됩니다."
            elif score >= 50:
                evaluation = "불편한 퇴근 날씨입니다. 대비하세요!"
            else:
                evaluation = "매우 불편한 퇴근 날씨입니다. 각별히 주의하세요!"
        else:
            # 기본 메시지 (now의 경우)
            if score >= 80:
                evaluation = "완벽한 날씨입니다!"
            elif score >= 60:
                evaluation = "쾌적한 날씨입니다."
            elif score >= 50:
                evaluation = "불편한 날씨입니다. 대비하세요!"
            else:
                evaluation = "매우 불편한 날씨입니다. 각별히 주의하세요!"

        if prediction:
            prediction_time_str = prediction.prediction_time.strftime("%Y-%m-%d %H:%M")
            data_period = prediction.data_period
            observations_count = prediction.observations_count
            penalties = prediction.comfort_score.penalties
            label = prediction.comfort_score.label
        else:
            kst = pytz.timezone('Asia/Seoul')
            prediction_time_str = datetime.now(kst).strftime("%Y-%m-%d %H:%M")
            data_period = ""
            observations_count = 0
            penalties = {}
            label = "unknown"

        response_data = {
            "title": title,
            "score": round(score, 1),
            "label": label,
            "prediction_time": prediction_time_str,
            "data_period": data_period,
            "observations_count": observations_count,
            "penalties": penalties,
            "evaluation": evaluation
        }

        # 현재 날씨 요청의 경우 온도, 습도, 강수량 추가
        if prediction_type == "now":
            response_data["current_temp"] = current_temp
            response_data["current_humidity"] = current_humidity
            response_data["current_precipitation"] = current_precipitation
            response_data["current_precipitation_type"] = current_precipitation_type

        return response_data

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/test")
async def test_api() -> Dict[str, str]:
    """Test KMA API connection."""
    try:
        config = get_kma_config()
        observations = fetch_recent_weather_kma(config, lookback_hours=1)

        if observations:
            latest = observations[-1]
            return {
                "message": "API 연결 성공!",
                "details": f"{len(observations)}개 관측 데이터 수신 - 최신: {latest.timestamp} ({latest.temperature_c}°C)"
            }
        else:
            return {
                "message": "API 연결됨",
                "details": "데이터가 없습니다."
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"API 연결 실패: {str(e)}")

@app.get("/manifest.json")
async def get_manifest():
    """PWA manifest file."""
    return {
        "name": "출퇴근길 날씨 친구",
        "short_name": "날씨친구",
        "description": "기상청 데이터 기반 실시간 출퇴근 쾌적지수 예측 서비스",
        "start_url": "/",
        "display": "standalone",
        "categories": ["weather", "productivity"],
        "background_color": "#4A90E2",
        "theme_color": "#4A90E2",
        "orientation": "portrait",
        "scope": "/",
        "icons": [
            {
                "src": "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 192 192'><rect width='192' height='192' fill='%234A90E2' rx='40'/><text x='96' y='130' font-size='80' text-anchor='middle' fill='white'>☀️</text></svg>",
                "sizes": "192x192",
                "type": "image/svg+xml",
                "purpose": "any maskable"
            },
            {
                "src": "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 512 512'><rect width='512' height='512' fill='%234A90E2' rx='100'/><text x='256' y='350' font-size='200' text-anchor='middle' fill='white'>☀️</text></svg>",
                "sizes": "512x512",
                "type": "image/svg+xml",
                "purpose": "any maskable"
            }
        ]
    }

@app.get("/sw.js")
async def get_service_worker():
    """Service Worker for PWA."""
    sw_content = """
const CACHE_NAME = 'weather-friend-v1';
const urlsToCache = [
  '/',
  '/manifest.json'
];

self.addEventListener('install', function(event) {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(function(cache) {
        return cache.addAll(urlsToCache);
      })
  );
});

self.addEventListener('fetch', function(event) {
  event.respondWith(
    caches.match(event.request)
      .then(function(response) {
        if (response) {
          return response;
        }
        return fetch(event.request);
      }
    )
  );
});
"""
    return Response(content=sw_content, media_type="application/javascript")

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
