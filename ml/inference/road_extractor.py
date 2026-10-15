import os
import sys
import numpy as np
from PIL import Image
import torch
from scipy import ndimage

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(ROOT_DIR)

from ml.models.road_extraction.unet_road_extractor import UNetRoadExtractor

WEIGHTS_DIR = os.path.join(ROOT_DIR, "ml", "models", "road_extraction")
RESNET_WEIGHTS = os.path.join(WEIGHTS_DIR, "best_road_resnet34.pt")
UNET_WEIGHTS = os.path.join(WEIGHTS_DIR, "best_road_unet.pt")
FALLBACK_WEIGHTS = os.path.join(WEIGHTS_DIR, "unet_road_extractor.pt")


class RoadExtractor:
    def __init__(self, weights_path: str = None, device: str = "cpu"):
        self.device = torch.device(device)
        self.net = UNetRoadExtractor(in_channels=3, out_channels=1).to(self.device)
        self._load_weights(weights_path)
        self.net.eval()

    def _load_weights(self, path: str = None):
        if path:
            target = path
        elif os.path.exists(RESNET_WEIGHTS):
            target = RESNET_WEIGHTS
        elif os.path.exists(UNET_WEIGHTS):
            target = UNET_WEIGHTS
        else:
            target = FALLBACK_WEIGHTS

        if os.path.exists(target):
            try:
                ckpt = torch.load(target, map_location=self.device)
                mtype = ckpt.get("model_type") if isinstance(ckpt, dict) else None
                state = ckpt.get("state_dict", ckpt.get("model_state_dict", ckpt)) if isinstance(ckpt, dict) else ckpt

                if mtype == "smp_resnet34_scse":
                    try:
                        import segmentation_models_pytorch as smp
                        self.net = smp.Unet(
                            encoder_name="resnet34",
                            encoder_weights=None,
                            in_channels=3,
                            classes=1,
                            decoder_attention_type="scse"
                        ).to(self.device)
                    except ImportError:
                        pass

                self.net.load_state_dict(state, strict=False)
            except Exception:
                pass

    def extract_roads(
        self,
        image: Image.Image | np.ndarray,
        threshold: float = 0.50,
        min_pixels: int = 15,
    ) -> dict:
        if isinstance(image, Image.Image):
            arr = np.array(image.convert("RGB"), dtype=np.float32) / 255.0
        else:
            arr = image.astype(np.float32)
            if arr.max() > 1.0:
                arr /= 255.0

        h, w, _ = arr.shape
        pad_y = (32 - h % 32) % 32
        pad_x = (32 - w % 32) % 32
        if pad_y > 0 or pad_x > 0:
            padded = np.pad(arr, ((0, pad_y), (0, pad_x), (0, 0)), mode="reflect")
        else:
            padded = arr

        inp = torch.from_numpy(padded.transpose(2, 0, 1)).unsqueeze(0).to(self.device)

        with torch.no_grad():
            out = self.net(inp)
            prob_full = torch.sigmoid(out).squeeze().cpu().numpy()

        probs = prob_full[:h, :w]
        bin_mask = probs >= threshold

        labeled, count = ndimage.label(bin_mask)
        if count > 0:
            sizes = ndimage.sum(bin_mask, labeled, range(1, count + 1))
            drop = sizes < min_pixels
            remove = drop[labeled - 1]
            remove[labeled == 0] = False
            bin_mask[remove] = False

        skel = self._thin(bin_mask)
        road_count = int(np.sum(bin_mask))
        coverage = round((road_count / (h * w)) * 100.0, 2)

        return {
            "probability_map": probs,
            "binary_mask": bin_mask,
            "skeleton": skel,
            "road_coverage_pct": coverage,
            "road_pixel_count": road_count,
        }

    def _thin(self, mask: np.ndarray) -> np.ndarray:
        skel = np.zeros(mask.shape, dtype=bool)
        elem = ndimage.generate_binary_structure(2, 1)
        cur = mask.copy()

        for _ in range(50):
            eroded = ndimage.binary_erosion(cur, structure=elem)
            opened = ndimage.binary_opening(cur, structure=elem)
            skel |= (cur & ~opened)
            cur = eroded
            if not np.any(cur):
                break
        return skel
