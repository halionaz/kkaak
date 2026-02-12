#!/bin/bash
# KKAAK 트레이딩 파이프라인 실행 스크립트

set -e  # 에러 발생 시 즉시 중단

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR="venv"
LOG_FILE="kkaak.log"
PID_FILE="kkaak.pid"

# 색상 코드
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 가상환경 설정
setup_venv() {
    if [ ! -d "$VENV_DIR" ]; then
        echo -e "${YELLOW}가상환경이 없습니다. 생성 중...${NC}"
        python3 -m venv "$VENV_DIR"

        echo -e "${YELLOW}의존성 패키지 설치 중...${NC}"
        source "$VENV_DIR/bin/activate"
        pip install --upgrade pip
        pip install -r requirements.txt
        echo -e "${GREEN}✓ 가상환경 설정 완료${NC}"
    else
        source "$VENV_DIR/bin/activate"
    fi
}

# 실행 중인 프로세스 확인
is_running() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            return 0
        else
            rm -f "$PID_FILE"
            return 1
        fi
    fi
    return 1
}

# foreground 실행
run_foreground() {
    setup_venv
    echo -e "${GREEN}🐦‍⬛ 까악 파이프라인 시작...${NC}"
    python main.py "$@"
}

# background 실행 (daemon)
run_background() {
    if is_running; then
        echo -e "${YELLOW}⚠️  이미 실행 중입니다. (PID: $(cat $PID_FILE))${NC}"
        exit 1
    fi

    setup_venv
    echo -e "${GREEN}🐦‍⬛ 까악 파이프라인 백그라운드 시작...${NC}"

    nohup python main.py "$@" > "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"

    echo -e "${GREEN}✓ 백그라운드 실행 시작됨 (PID: $!)${NC}"
    echo -e "  로그 확인: ${YELLOW}tail -f $LOG_FILE${NC}"
    echo -e "  프로세스 종료: ${YELLOW}./run.sh stop${NC}"
}

# 프로세스 종료
stop_process() {
    if is_running; then
        PID=$(cat "$PID_FILE")
        echo -e "${YELLOW}프로세스 종료 중... (PID: $PID)${NC}"
        kill "$PID"

        # 프로세스가 종료될 때까지 대기 (최대 10초)
        for i in {1..10}; do
            if ! ps -p "$PID" > /dev/null 2>&1; then
                rm -f "$PID_FILE"
                echo -e "${GREEN}✓ 프로세스 종료됨${NC}"
                return 0
            fi
            sleep 1
        done

        # 여전히 살아있으면 강제 종료
        echo -e "${RED}강제 종료 중...${NC}"
        kill -9 "$PID" 2>/dev/null || true
        rm -f "$PID_FILE"
        echo -e "${GREEN}✓ 프로세스 강제 종료됨${NC}"
    else
        echo -e "${YELLOW}실행 중인 프로세스가 없습니다.${NC}"
    fi
}

# 상태 확인
status() {
    if is_running; then
        PID=$(cat "$PID_FILE")
        echo -e "${GREEN}✓ 실행 중 (PID: $PID)${NC}"
        echo ""
        ps -p "$PID" -o pid,etime,cmd
    else
        echo -e "${YELLOW}실행 중이지 않습니다.${NC}"
    fi
}

# 로그 확인
show_logs() {
    if [ -f "$LOG_FILE" ]; then
        tail -f "$LOG_FILE"
    else
        echo -e "${RED}로그 파일이 없습니다: $LOG_FILE${NC}"
        exit 1
    fi
}

# 사용법
usage() {
    cat << EOF
사용법: $0 [명령] [옵션]

명령:
  (없음)          foreground로 실행 (기본)
  start           백그라운드로 실행
  stop            실행 중인 프로세스 종료
  restart         재시작 (stop + start)
  status          실행 상태 확인
  logs            로그 확인 (실시간)
  test            테스트 모드로 실행

옵션:
  --test          테스트 모드 (main.py에 전달)

예시:
  $0                    # foreground 실행
  $0 start              # 백그라운드 실행
  $0 stop               # 종료
  $0 logs               # 로그 확인
  $0 test               # 테스트 모드
  $0 start --test       # 백그라운드 테스트 모드
EOF
}

# 메인 로직
case "${1:-}" in
    start)
        shift
        run_background "$@"
        ;;
    stop)
        stop_process
        ;;
    restart)
        stop_process
        sleep 2
        shift
        run_background "$@"
        ;;
    status)
        status
        ;;
    logs)
        show_logs
        ;;
    test)
        shift
        run_foreground --test "$@"
        ;;
    -h|--help|help)
        usage
        ;;
    "")
        run_foreground
        ;;
    *)
        echo -e "${RED}알 수 없는 명령: $1${NC}"
        echo ""
        usage
        exit 1
        ;;
esac
