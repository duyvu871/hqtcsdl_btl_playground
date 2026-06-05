"""Train and evaluate FastText spam classifier."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import fasttext
from sklearn.metrics import classification_report, confusion_matrix


def train_model(
    train_path: Path,
    model_dir: Path,
    *,
    model_name: str = "spam_model",
    dim: int = 100,
    epoch: int = 25,
    lr: float = 0.5,
    word_ngrams: int = 2,
    min_count: int = 1,
    loss: str = "softmax",
) -> fasttext.FastText._FastText:
    model_dir.mkdir(parents=True, exist_ok=True)
    out_prefix = model_dir / model_name
    model = fasttext.train_supervised(
        input=str(train_path),
        dim=dim,
        epoch=epoch,
        lr=lr,
        wordNgrams=word_ngrams,
        minCount=min_count,
        loss=loss,
        verbose=2,
    )
    model.save_model(str(out_prefix) + ".bin")
    return model


def _predict_raw(
    model: fasttext.FastText._FastText,
    text: str,
    *,
    k: int = 1,
    threshold: float = 0.0,
) -> tuple[list[str], list[float]]:
    """Call fastText C API directly — avoids NumPy 2.x bug in model.predict()."""
    clean = text.replace("\n", " ").strip()
    if not clean:
        return [], []
    predictions = model.f.predict(clean + "\n", k, threshold, "strict")
    if not predictions:
        return [], []
    probs, labels = zip(*predictions)
    return list(labels), [float(p) for p in probs]


def predict_text(
    model: fasttext.FastText._FastText, text: str, *, k: int = 1
) -> tuple[str, float]:
    labels, probs = _predict_raw(model, text, k=k)
    if not labels:
        return "human", 0.0
    return labels[0].replace("__label__", ""), probs[0]


def predict_batch(
    model: fasttext.FastText._FastText, texts: list[str], *, k: int = 1
) -> list[tuple[str, float]]:
    """Batch predict via multilinePredict (also avoids NumPy 2.x single-line bug)."""
    cleaned = [t.replace("\n", " ").strip() for t in texts]
    if not cleaned:
        return []
    # model.predict(list) uses multilinePredict internally — safe on NumPy 2.x
    all_labels, all_probs = model.predict(cleaned, k=k)
    results: list[tuple[str, float]] = []
    for labels, probs in zip(all_labels, all_probs):
        if labels:
            results.append((labels[0].replace("__label__", ""), float(probs[0])))
        else:
            results.append(("human", 0.0))
    return results


def _load_labeled_lines(test_path: Path) -> tuple[list[str], list[str]]:
    y_true: list[str] = []
    texts: list[str] = []
    with test_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line.startswith("__label__"):
                continue
            parts = line.split(" ", 1)
            y_true.append(parts[0].replace("__label__", ""))
            texts.append(parts[1] if len(parts) > 1 else "")
    return y_true, texts


def classification_report_from_file(
    model: fasttext.FastText._FastText, test_path: Path, *, batch_size: int = 256
) -> str:
    y_true, texts = _load_labeled_lines(test_path)
    y_pred: list[str] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        y_pred.extend(label for label, _ in predict_batch(model, batch))
    return classification_report(y_true, y_pred, digits=4)


def evaluate_on_file(model: fasttext.FastText._FastText, test_path: Path) -> tuple[dict[str, Any], str]:
    n, precision, recall = model.test(str(test_path))
    report = classification_report_from_file(model, test_path)
    summary = (
        f"samples={n}  precision={precision:.4f}  recall={recall:.4f}\n\n{report}"
    )
    metrics = {"samples": n, "precision": precision, "recall": recall}
    return metrics, summary


def confusion_matrix_from_file(
    model: fasttext.FastText._FastText, test_path: Path, *, batch_size: int = 256
) -> tuple[list[str], list[list[int]]]:
    y_true, texts = _load_labeled_lines(test_path)
    y_pred: list[str] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        y_pred.extend(label for label, _ in predict_batch(model, batch))
    labels = sorted(set(y_true) | set(y_pred))
    matrix = confusion_matrix(y_true, y_pred, labels=labels)
    return labels, matrix.tolist()
