"""매 3시간마다 자동 실행 스케줄러 (06:00, 09:00, 12:00, 15:00, 18:00, 21:00 KST).

KST 기준 실행을 보장하기 위해 schedule.at(..., "Asia/Seoul")를 명시한다.
systemd 환경에서도 TZ=Asia/Seoul을 함께 설정하는 것을 권장한다.
"""
import asyncio
import os
import schedule
import time

from datetime import datetime
from loguru import logger

from main import run_daily_report

KST_TZ = "Asia/Seoul"
RUN_HOURS = (6, 9, 12, 15, 18, 21)


def _run():
    """동기 래퍼 - schedule 라이브러리 호환."""
    logger.info(f"스케줄 실행 시작: {datetime.now():%Y-%m-%d %H:%M:%S}")
    try:
        asyncio.run(run_daily_report())
        logger.info("스케줄 실행 완료")
    except Exception:
        # 예외로 프로세스가 종료되면 다음 슬롯(예: 21:00)을 통째로 놓칠 수 있으므로
        # 로그를 남기고 루프는 계속 유지한다.
        logger.exception("스케줄 실행 실패")


def _log_schedule_plan() -> None:
    for job in schedule.jobs:
        logger.info(f"등록된 스케줄: next_run={job.next_run:%Y-%m-%d %H:%M:%S} interval={job.interval} {job.unit}")


if __name__ == "__main__":
    tz = os.getenv("TZ", "")
    if tz not in (KST_TZ, "KST-9", "KST"):
        logger.warning(
            f"⚠️ TZ 환경변수가 {KST_TZ}이 아닙니다 (현재: {tz or '미설정'}). "
            f"코드상 스케줄은 {KST_TZ}로 등록되지만, 로그/운영 혼선을 막으려면 "
            f"'export TZ={KST_TZ}' 또는 systemd/docker에 TZ={KST_TZ}을 설정하세요."
        )

    # 3시간 간격: 06:00, 09:00, 12:00, 15:00, 18:00, 21:00 KST
    for hour in RUN_HOURS:
        schedule.every().day.at(f"{hour:02d}:00", KST_TZ).do(_run)

    logger.info(
        "스케줄러 시작 (06:00 / 09:00 / 12:00 / 15:00 / 18:00 / 21:00 KST, 3시간 간격)"
    )
    _log_schedule_plan()
    while True:
        schedule.run_pending()
        time.sleep(30)
