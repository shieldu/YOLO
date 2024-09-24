import threading
from flask import Flask, render_template_string, jsonify
from ultralytics import YOLO
import cv2
import datetime
import time
import platform

# 침입 감지 시 소리 재생 (Windows 전용)
if platform.system() == "Windows":
    import winsound

# YOLOv8s 모델 로드
model = YOLO("yolov8s.pt")

# 침입 로그 리스트 및 상태
intrusion_log = []
intrusion_detected = False  # 침입 상태를 추적하기 위한 bool 플래그

# 웹캠 피드 열기
cap = cv2.VideoCapture(0)

# Flask 애플리케이션 설정
app = Flask(__name__)

# 동적 배경 색상을 가진 HTML 템플릿 문자열
html_template = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Intrusion Detection Log</title>
    <style>
        body {
            {% if intrusion %}
                background-color: red;
            {% else %}
                background-color: white;
            {% endif %}
            transition: background-color 0.5s;
        }
    </style>
</head>
<body>
    <h1>Real-time Intrusion Detection Log</h1>
    <ul id="log-list">
        {% for log in logs %}
            <li>{{ log }}</li>
        {% endfor %}
    </ul>
    <script>
    function updateLogs() {
        fetch('/get_logs')
            .then(response => response.json())
            .then(data => {
                const logList = document.getElementById('log-list');
                logList.innerHTML = '';  // Clear the current log list
                data.logs.forEach(log => {
                    const li = document.createElement('li');
                    li.textContent = log;
                    logList.appendChild(li);
                });
            });
    }

    function checkIntrusionStatus() {
        fetch('/intrusion_status')
            .then(response => response.json())
            .then(data => {
                if (data.intrusion) {
                    document.body.style.backgroundColor = "red";
                } else {
                    document.body.style.backgroundColor = "white";
                }
            });
    }

    // Poll the server every second to check intrusion status and update logs
    setInterval(() => {
        checkIntrusionStatus();
        updateLogs();
    }, 1000);
    </script>
</body>
</html>
'''


@app.route('/')
def index():
    # 웹페이지에 로그 및 침입 상태 전달
    return render_template_string(html_template, logs=intrusion_log, intrusion=intrusion_detected)


@app.route('/intrusion_status')
def intrusion_status():
    # 현재 침입 상태를 JSON으로 반환
    return jsonify({"intrusion": intrusion_detected})


@app.route('/get_logs')
def get_logs():
    # 칩입 로그를 JSON으로 반환
    return jsonify({"logs": intrusion_log})


def detect_people():
    global intrusion_log, intrusion_detected
    while True:
        try:
            ret, frame = cap.read()
            if not ret:
                print("웹캠에서 프레임을 가져오지 못했습니다.")
                break

            # 사람 탐지를 위해 YOLO 모델 실행
            results = model.predict(source=frame, show=True)

            # 각 프레임마다 침입 상태 초기화
            intrusion_detected = False

            # 사람이 감지되었는지 확인 (COCO 클래스 ID 0)
            for result in results:
                for r in result.boxes.data:
                    class_id = int(r[-1])
                    if class_id == 0:  # 사람이 감지된 경우
                        intrusion_detected = True
                        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        log_entry = f"침입 감지: {timestamp}"
                        intrusion_log.append(log_entry)

                        # # 마지막 10개의 로그만 유지
                        # if len(intrusion_log) > 10:
                        #     intrusion_log.pop(0)

                        # 침입 감지 시 경고음 재생
                        if platform.system() == "Windows":
                            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)

            time.sleep(1)  # CPU 사용량을 줄이기 위해 약간의 지연 추가
        except Exception as e:
            print(f"YOLO 감지 중 오류: {e}")

# Flask 서버를 백그라운드 스레드에서 실행
def run_flask():
    print("Flask 서버 시작 중...")
    app.run(debug=False, use_reloader=False)

# YOLO 감지 스레드 실행
yolo_thread = threading.Thread(target=detect_people)
yolo_thread.daemon = True
yolo_thread.start()
print("YOLO 감지 스레드가 시작되었습니다.")

# Flask 서버 스레드 실행
flask_thread = threading.Thread(target=run_flask)
flask_thread.daemon = True
flask_thread.start()
print("Flask 서버 스레드가 시작되었습니다.")

# 메인 스레드 유지
while True:
    time.sleep(1)
