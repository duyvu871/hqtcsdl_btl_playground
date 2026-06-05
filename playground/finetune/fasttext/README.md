# FastText Spam Classifier (CPU playground)

Train và test model **FastText supervised** lọc spam/bot trên tweet crypto, dùng dataset
[sandiumenge/bitcoin-tweets-spam-emotion-sentiment](https://huggingface.co/datasets/sandiumenge/bitcoin-tweets-spam-emotion-sentiment).

## Setup (pyproject.toml)

Chạy từ **repo root** hoặc dùng đường dẫn tuyệt đối:

```bash
cd /home/adc300/src/ptit/hqtcsdl_btl_new/playground/finetune/fasttext

# uv (khuyến nghị)
uv sync --group dev
uv run python -m ipykernel install --user --name fasttext-spam --display-name "Python (fasttext-spam)"

# Gỡ kernel cũ (nếu cần cài lại)
# jupyter kernelspec uninstall fasttext-spam

# hoặc pip
python -m venv .venv
source .venv/bin/activate
pip install -e ".[notebook]"
python -m ipykernel install --user --name fasttext-spam --display-name "Python (fasttext-spam)"
```

> Trong Jupyter/VS Code: chọn kernel **Python (fasttext-spam)**. Sau khi sửa `lib/train.py`, **Restart Kernel** rồi chạy lại từ cell import.

## Chạy notebook

```bash
uv run jupyter notebook notebooks/train_and_test.ipynb
```

## Output

| Path | Mô tả |
| --- | --- |
| `data/train.txt`, `data/test.txt` | File FastText format |
| `models/spam_model.bin` | Model đã train |
| Notebook cells | Metrics + demo inference |

## Nhãn

| Dataset gốc | FastText label |
| --- | --- |
| `human` | `__label__human` |
| `spam`, `bot` | `__label__spam` |
