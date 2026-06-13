"""Trực giao hóa không gian nhân tố bằng Phân tích thành phần chính (PCA)."""

import polars as pl
import numpy as np
from sklearn.decomposition import PCA

def orthogonalize_momentum(df: pl.DataFrame, feature_cols: list[str]) -> pl.DataFrame:
    """
    Trích xuất PC_1 làm đại diện duy nhất cho nhóm Động lượng.
    Sử dụng NumPy để lọc triệt để các giá trị NaN trước khi đưa vào PCA.
    """
    if df.height == 0:
        return df.with_columns(pl.lit(np.nan).alias("Z_momentum_ortho"))
        
    # 1. Chuyển đổi trực tiếp các cột tính toán sang mảng NumPy phẳng (Matrix)
    X_full = df.select(feature_cols).to_numpy()
    
    # 2. SỬA LỖI TẠI ĐÂY: Quét trực tiếp trên NumPy để tìm các hàng KHÔNG chứa bất kỳ giá trị NaN nào
    # np.isnan(X_full).any(axis=1) trả về True nếu hàng đó có ít nhất 1 ô NaN
    # Dấu ~ dùng để đảo ngược (Phép phủ định) -> Chỉ lấy các hàng sạch 100%
    valid_mask_np = ~np.isnan(X_full).any(axis=1)
    
    # 3. Trích xuất tập dữ liệu sạch hoàn toàn khuyết thiếu
    X_clean = X_full[valid_mask_np]
    
    # Nếu số lượng dòng sạch quá ít (không đủ để tính ma trận hiệp biến), trả về cột NaN
    if len(X_clean) < 2:
        return df.with_columns(pl.lit(np.nan).alias("Z_momentum_ortho"))
        
    try:
        # 4. Thực thi fit toán học PCA trên tập dữ liệu đã sạch 100%
        pca = PCA(n_components=1)
        pc1 = pca.fit_transform(X_clean).flatten()
        
        # 5. Khôi phục kích thước mảng gốc để map ngược lại vào Polars DataFrame
        ortho_series = np.full(df.height, np.nan)
        ortho_series[valid_mask_np] = pc1
        
        return df.with_columns(pl.Series("Z_momentum_ortho", ortho_series))
        
    except Exception as e:
        # Bọc an toàn nếu có lỗi tính toán phát sinh từ thư viện tuyến tính
        print(f"⚠️ Cảnh báo lỗi toán học PCA: {e}")
        return df.with_columns(pl.lit(np.nan).alias("Z_momentum_ortho"))