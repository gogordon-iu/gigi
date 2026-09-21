"""
Rockchip RK3588 NPU (Neural Processing Unit) runtime helper for Orange Pi 5 Pro.
Provides a unified wrapper for loading RKNN models with graceful CPU fallback.
"""

import logging
from pathlib import Path
from typing import Optional, Any, List
import numpy as np

from gigi.core.config import IS_ROBOT

logger = logging.getLogger(__name__)


class RKNNModelRunner:
    """
    Wrapper for RKNNLite runtime on Rockchip RK3588.
    Gracefully handles missing hardware/drivers when executing in simulation.
    """

    def __init__(self, model_path: Path):
        self.model_path = Path(model_path)
        self.rknn = None
        self.is_available = False

        if not self.model_path.exists():
            logger.warning(f"RKNN model file not found: {self.model_path}")
            return

        if IS_ROBOT:
            try:
                from rknnlite.api import RKNNLite

                self.rknn = RKNNLite()
                ret = self.rknn.load_rknn(str(self.model_path))
                if ret != 0:
                    logger.error(f"Failed to load RKNN model {self.model_path} (code {ret})")
                    return

                ret = self.rknn.init_runtime()
                if ret != 0:
                    logger.error(f"Failed to init RKNN runtime for {self.model_path} (code {ret})")
                    return

                self.is_available = True
                logger.info(f"Successfully loaded RKNN model on NPU: {self.model_path.name}")
            except Exception as e:
                logger.warning(f"Could not initialize RKNNLite on this platform: {e}")
        else:
            logger.debug(f"NPU runtime not active in host simulation for {self.model_path.name}")

    def inference(self, inputs: List[np.ndarray]) -> Optional[List[np.ndarray]]:
        """Runs inference on the NPU."""
        if not self.is_available or self.rknn is None:
            return None
        try:
            return self.rknn.inference(inputs=inputs)
        except Exception as e:
            logger.error(f"Error during RKNN inference: {e}")
            return None

    def release(self) -> None:
        """Frees the NPU runtime resources."""
        if self.rknn is not None:
            try:
                self.rknn.release()
            except Exception:
                pass
            self.rknn = None
            self.is_available = False

    def __del__(self):
        self.release()
