import torch
import torch.nn as nn
import torch.nn.functional as F


class DoubleConv(nn.Module):
    def __init__(self, in_ch: int, out_ch: int):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(in_ch, out_ch, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_ch),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_ch, out_ch, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_ch),
            nn.ReLU(inplace=True),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.conv(x)


class UNetRoadExtractor(nn.Module):
    def __init__(self, in_channels: int = 3, out_channels: int = 1, features: list[int] = None):
        super().__init__()
        if features is None:
            features = [32, 64, 128, 256]

        self.downs = nn.ModuleList()
        self.ups = nn.ModuleList()
        self.pool = nn.MaxPool2d(kernel_size=2, stride=2)

        cur_in = in_channels
        for f in features:
            self.downs.append(DoubleConv(cur_in, f))
            cur_in = f

        self.bottleneck = nn.Sequential(
            DoubleConv(features[-1], features[-1] * 2),
            nn.Dropout2d(p=0.2),
        )

        for f in reversed(features):
            self.ups.append(
                nn.ConvTranspose2d(f * 2, f, kernel_size=2, stride=2)
            )
            self.ups.append(DoubleConv(f * 2, f))

        self.head = nn.Conv2d(features[0], out_channels, kernel_size=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        skips = []
        for down in self.downs:
            x = down(x)
            skips.append(x)
            x = self.pool(x)

        x = self.bottleneck(x)
        skips = skips[::-1]

        for i in range(0, len(self.ups), 2):
            x = self.ups[i](x)
            skip = skips[i // 2]
            if x.shape != skip.shape:
                x = F.interpolate(x, size=skip.shape[2:], mode="bilinear", align_corners=True)
            x = self.ups[i + 1](torch.cat((skip, x), dim=1))

        return self.head(x)

    def predict_mask(self, x: torch.Tensor, threshold: float = 0.5) -> torch.Tensor:
        self.eval()
        with torch.no_grad():
            probs = torch.sigmoid(self.forward(x))
            return (probs >= threshold).float()


class DiceLoss(nn.Module):
    def __init__(self, eps: float = 1e-6):
        super().__init__()
        self.eps = eps

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        probs = torch.sigmoid(logits).view(-1)
        targets_f = targets.view(-1)
        inter = (probs * targets_f).sum()
        dice = (2.0 * inter + self.eps) / (probs.sum() + targets_f.sum() + self.eps)
        return 1.0 - dice


class CombinedRoadLoss(nn.Module):
    def __init__(self, w_bce: float = 0.5, w_dice: float = 0.5, pos_weight: float = 4.0):
        super().__init__()
        self.w_bce = w_bce
        self.w_dice = w_dice
        self.pos_weight = torch.tensor([pos_weight])
        self.dice_fn = DiceLoss()

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        pw = self.pos_weight.to(logits.device)
        bce = F.binary_cross_entropy_with_logits(logits, targets, pos_weight=pw)
        dice = self.dice_fn(logits, targets)
        return self.w_bce * bce + self.w_dice * dice
