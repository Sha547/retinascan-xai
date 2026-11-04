"""Fine-tune an ImageNet-pretrained CNN to grade DR (0 to 4) on the train split.

Model selection uses the validation split (best val quadratic weighted kappa).
The test split is not touched here.

Writes to --out: best.pt (contract format, see docs/CONTRACT.md), last.pt,
history.json (per-epoch train loss, val loss/acc/QWK), train_config.json.
"""
from __future__ import annotations

import argparse
import math
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.metrics import cohen_kappa_score
from torch.utils.data import DataLoader

from common import NUM_CLASSES, PREPROCESS_VERSION, build_model, make_dataset, save_json, seed_everything


def class_weights(labels, power: float = 0.5) -> torch.Tensor:
    """Inverse-frequency^power weights, normalised to mean 1 (power 0.5 = sqrt)."""
    counts = np.bincount(labels, minlength=NUM_CLASSES).astype(np.float64)
    w = (counts.sum() / np.maximum(counts, 1)) ** power
    return torch.tensor(w / w.mean(), dtype=torch.float32)


@torch.no_grad()
def run_eval(model, loader, device, criterion):
    model.eval()
    logits, ys, loss_sum, n = [], [], 0.0, 0
    for x, y in loader:
        x, y = x.to(device, non_blocking=True), y.to(device, non_blocking=True)
        with torch.autocast(device_type=device.type, dtype=torch.float16, enabled=device.type == "cuda"):
            out = model(x)
        loss_sum += criterion(out.float(), y).item() * len(y)
        n += len(y)
        logits.append(out.float().cpu())
        ys.append(y.cpu())
    logits, ys = torch.cat(logits).numpy(), torch.cat(ys).numpy()
    pred = logits.argmax(1)
    return {
        "loss": loss_sum / n,
        "acc": float((pred == ys).mean()),
        "qwk": float(cohen_kappa_score(ys, pred, weights="quadratic")),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--splits", required=True)
    ap.add_argument("--cache_dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--arch", default="efficientnet_b0")
    ap.add_argument("--size", type=int, default=512, help="must match the cache size")
    ap.add_argument("--clahe", type=int, default=1, help="whether the cache was built with CLAHE (recorded in model.pt)")
    ap.add_argument("--epochs", type=int, default=15)
    ap.add_argument("--bs", type=int, default=16)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--wd", type=float, default=1e-4)
    ap.add_argument("--warmup_epochs", type=float, default=1.0)
    ap.add_argument("--cw_power", type=float, default=0.5, help="class-weight power; 0 disables")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--patience", type=int, default=6, help="early stop after N epochs without val QWK gain")
    ap.add_argument("--limit", type=int, default=0, help="use N train and N//4 val images (smoke test)")
    ap.add_argument("--no_pretrained", action="store_true", help="offline smoke tests only")
    ap.add_argument("--version", default="", help="model version string; default <arch>-<out dir name>")
    args = ap.parse_args()

    seed_everything(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    version = args.version or f"{args.arch}-{out.name}"

    df = pd.read_csv(args.splits)
    tr, va = df[df.split == "train"], df[df.split == "val"]
    if args.limit:
        tr, va = tr.head(args.limit), va.head(max(args.limit // 4, 8))
    print(f"device={device} train={len(tr)} val={len(va)} arch={args.arch} size={args.size} bs={args.bs}", flush=True)
    if device.type == "cuda":
        print(f"gpu={torch.cuda.get_device_name(0)} "
              f"vram={torch.cuda.get_device_properties(0).total_memory / 2**30:.1f}GB", flush=True)

    dl_tr = DataLoader(make_dataset(tr.id_code, tr.diagnosis, args.cache_dir, train=True), batch_size=args.bs,
                       shuffle=True, num_workers=args.workers, pin_memory=True, drop_last=True,
                       persistent_workers=args.workers > 0)
    dl_va = DataLoader(make_dataset(va.id_code, va.diagnosis, args.cache_dir, train=False), batch_size=args.bs * 2,
                       shuffle=False, num_workers=args.workers, pin_memory=True)

    model = build_model(args.arch, pretrained=not args.no_pretrained).to(device)
    w = class_weights(tr.diagnosis.values, args.cw_power) if args.cw_power > 0 else torch.ones(NUM_CLASSES)
    print(f"class weights: {[round(float(x), 3) for x in w]}", flush=True)
    criterion = nn.CrossEntropyLoss(weight=w.to(device))
    eval_criterion = nn.CrossEntropyLoss()  # unweighted, comparable across runs
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.wd)
    steps_per_epoch = len(dl_tr)
    total, warm = args.epochs * steps_per_epoch, int(args.warmup_epochs * steps_per_epoch)

    def lr_at(step):
        if step < warm:
            return (step + 1) / max(warm, 1)
        p = (step - warm) / max(total - warm, 1)
        return 0.5 * (1 + math.cos(math.pi * p))

    sched = torch.optim.lr_scheduler.LambdaLR(opt, lr_at)
    scaler = torch.amp.GradScaler(enabled=device.type == "cuda")

    meta = {"arch": args.arch, "img_size": args.size, "num_classes": NUM_CLASSES,
            "preprocess": PREPROCESS_VERSION, "clahe": bool(args.clahe), "version": version}
    save_json({**vars(args), **meta, "device": str(device)}, out / "train_config.json")

    history, best_qwk, best_epoch, bad = [], -1.0, -1, 0
    for epoch in range(1, args.epochs + 1):
        model.train()
        t0, loss_sum, n = time.time(), 0.0, 0
        for x, y in dl_tr:
            x, y = x.to(device, non_blocking=True), y.to(device, non_blocking=True)
            with torch.autocast(device_type=device.type, dtype=torch.float16, enabled=device.type == "cuda"):
                loss = criterion(model(x).float(), y)
            opt.zero_grad(set_to_none=True)
            scaler.scale(loss).backward()
            scaler.step(opt)
            scaler.update()
            sched.step()
            loss_sum += loss.item() * len(y)
            n += len(y)
        val = run_eval(model, dl_va, device, eval_criterion)
        rec = {"epoch": epoch, "train_loss": loss_sum / max(n, 1), "val_loss": val["loss"],
               "val_acc": val["acc"], "val_qwk": val["qwk"], "lr": opt.param_groups[0]["lr"],
               "sec": round(time.time() - t0, 1)}
        if device.type == "cuda":
            rec["max_mem_gb"] = round(torch.cuda.max_memory_allocated() / 2**30, 2)
        history.append(rec)
        save_json(history, out / "history.json")
        improved = val["qwk"] > best_qwk
        print(f"epoch {epoch:2d} train_loss {rec['train_loss']:.4f} val_loss {val['loss']:.4f} "
              f"val_acc {val['acc']:.4f} val_qwk {val['qwk']:.4f} {rec['sec']}s{' *best' if improved else ''}",
              flush=True)
        ckpt = {**meta, "state_dict": model.state_dict(), "epoch": epoch, "val_qwk": val["qwk"]}
        torch.save(ckpt, out / "last.pt")
        if improved:
            best_qwk, best_epoch, bad = val["qwk"], epoch, 0
            torch.save(ckpt, out / "best.pt")
        else:
            bad += 1
            if bad >= args.patience:
                print(f"early stop: no val QWK gain for {args.patience} epochs", flush=True)
                break

    save_json({"best_epoch": best_epoch, "best_val_qwk": best_qwk, "epochs_run": len(history)},
              out / "train_summary.json")
    print(f"done. best val QWK {best_qwk:.4f} at epoch {best_epoch}", flush=True)


if __name__ == "__main__":
    main()
