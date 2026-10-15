"""Automated Evidence Processing Background Worker.

Claims pending evidence tasks, executes YOLO road-damage computer vision inference,
submits validated detection results idempotently, and triggers segment risk updates.
"""

import asyncio
import logging
import signal
import uuid
from datetime import datetime, timezone
from typing import Any
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.database import AsyncSessionLocal
from backend.models.incidents import IncidentEvidence
from backend.services.evidence_service import EvidenceService
from backend.services.risk_service import RiskService
from backend.services.storage import get_storage_service
from ml.inference.yolo_worker import YOLORoadDamageWorker

logger = logging.getLogger(__name__)
settings = get_settings()


class EvidenceWorker:
    """Automated ML worker for evidence processing and road damage detection."""

    def __init__(
        self,
        worker_id: str | None = None,
        yolo_worker: YOLORoadDamageWorker | None = None,
    ):
        self.worker_id = worker_id or settings.ML_WORKER_ID
        self.yolo_worker = yolo_worker or YOLORoadDamageWorker(worker_id=self.worker_id)
        self.storage = get_storage_service()

    async def process_task(
        self,
        evidence_id: uuid.UUID,
        session: AsyncSession,
    ) -> IncidentEvidence | None:
        """
        Processes a single evidence task end-to-end:
        1. Atomically claims task with lease timeout.
        2. Retrieves authorized image binary.
        3. Executes YOLO road damage inference.
        4. Submits validated detection result idempotently.
        5. Triggers road risk update if segment ID is present.
        """
        evidence_service = EvidenceService(session)

        # 1. Claim task atomically
        try:
            evidence = await evidence_service.claim_task(evidence_id=evidence_id, worker_id=self.worker_id)
        except HTTPException as e:
            if e.status_code == 409:
                logger.info(f"Task '{evidence_id}' already claimed by another active worker. Skipping.")
                return None
            elif e.status_code == 400:
                logger.info(f"Task '{evidence_id}' cannot be claimed: {e.detail}")
                return None
            raise

        # 2. Retrieve image binary from storage
        stored_name = evidence.stored_filename
        if not stored_name:
            err_msg = f"Evidence '{evidence_id}' has no stored filename reference."
            logger.error(err_msg)
            return await evidence_service.submit_task_result(
                evidence_id=evidence_id,
                worker_id=self.worker_id,
                status_val="FAILED",
                error_message=err_msg,
            )

        try:
            raw_bytes, _ = await self.storage.get_evidence_file(stored_name)
        except Exception as read_err:
            err_msg = f"Failed to retrieve storage file '{stored_name}': {read_err}"
            logger.error(err_msg)
            return await evidence_service.submit_task_result(
                evidence_id=evidence_id,
                worker_id=self.worker_id,
                status_val="FAILED",
                error_message=err_msg,
            )

        # 3. Execute YOLO inference
        inference_res = self.yolo_worker.detect_damage(raw_bytes)
        status_val = inference_res.get("status", "FAILED")
        det_class = inference_res.get("detection_class")
        confidence = inference_res.get("confidence")
        metadata = inference_res.get("metadata", {})
        err_msg = inference_res.get("error")

        # 4. Submit task result
        updated_evidence = await evidence_service.submit_task_result(
            evidence_id=evidence_id,
            worker_id=self.worker_id,
            status_val=status_val,
            model_detection_class=det_class,
            model_confidence=confidence,
            model_metadata=metadata,
            error_message=err_msg,
        )

        logger.info(
            f"Evidence '{evidence_id}' processed by '{self.worker_id}': status={status_val}, class={det_class}, conf={confidence}"
        )

        # 5. If successful detection and road segment is associated, trigger segment risk re-evaluation
        if status_val == "COMPLETED" and updated_evidence.road_segment_id:
            try:
                risk_service = RiskService(session)
                await risk_service.evaluate_segment_risk(
                    road_segment_id=updated_evidence.road_segment_id,
                    actor_id=None,
                )
                risk_service.close()
            except Exception as r_err:
                logger.warning(
                    f"Post-inference risk evaluation failed for segment '{updated_evidence.road_segment_id}': {r_err}"
                )

        return updated_evidence

    async def run_once(self, limit: int = 10) -> int:
        """
        Polls and processes up to `limit` pending evidence tasks.
        Returns the count of successfully processed tasks.
        """
        processed_count = 0
        async with AsyncSessionLocal() as session:
            evidence_service = EvidenceService(session)
            tasks = await evidence_service.get_pending_tasks(limit=limit)

            for task in tasks:
                try:
                    res = await self.process_task(evidence_id=task.id, session=session)
                    if res:
                        processed_count += 1
                except Exception as exc:
                    logger.error(f"Error processing evidence task '{task.id}': {exc}", exc_info=True)

        return processed_count

    async def run_loop(self, poll_interval: float = 2.0, stop_event: asyncio.Event | None = None):
        """Continuous background execution loop."""
        logger.info(f"Starting ML Evidence Worker loop (worker_id={self.worker_id}, interval={poll_interval}s)...")
        while stop_event is None or not stop_event.is_set():
            try:
                count = await self.run_once(limit=10)
                if count == 0 and (stop_event is None or not stop_event.is_set()):
                    await asyncio.sleep(poll_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Unexpected error in evidence worker loop: {e}", exc_info=True)
                await asyncio.sleep(poll_interval)
        logger.info(f"Evidence Worker '{self.worker_id}' loop stopped.")


async def main():
    """Standalone CLI entry point for running the evidence worker service."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    worker = EvidenceWorker()
    stop_event = asyncio.Event()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            pass

    await worker.run_loop(poll_interval=2.0, stop_event=stop_event)


if __name__ == "__main__":
    asyncio.run(main())
