# Kaggle acceptance

Chạy contract-only:

```bash
./scripts/kaggle-acceptance.sh
```

Chạy thêm live API check (cần credential đã cấu hình trong môi trường):

```bash
RUN_KAGGLE_ACCEPTANCE=1 ./scripts/kaggle-acceptance.sh
```

Live check chỉ kiểm tra CLI/version và quyền đọc dataset của account; không
upload hoặc xoá dataset/notebook.
