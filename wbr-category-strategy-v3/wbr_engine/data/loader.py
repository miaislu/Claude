#!/usr/bin/env python3
"""WBR 数据加载与解析公共模块"""
from __future__ import annotations

import re
from typing import Optional, List, Dict, Any

import numpy as np
import pandas as pd

_df_cache: Dict[str, pd.DataFrame] = {}


def load_wbr_excel(file_path: str, force_reload: bool = False) -> pd.DataFrame:
    """
    加载 WBR Excel 文件并标准化。

    自动检测表头行（找到含"指标"列的行），解析周列名，
    推断指标层次关系。
    """
    if file_path in _df_cache and not force_reload:
        return _df_cache[file_path]

    raw = pd.read_excel(file_path, header=None)

    header_row = None
    for i in range(min(5, len(raw))):
        row_vals = [str(v).strip() for v in raw.iloc[i] if pd.notna(v)]
        if '指标' in row_vals:
            header_row = i
            break

    if header_row is None:
        raise ValueError(f"无法在 {file_path} 中找到表头行（需包含'指标'列）")

    headers = raw.iloc[header_row].tolist()

    data_rows = []
    for i in range(header_row + 1, len(raw)):
        row = raw.iloc[i].tolist()
        if all(pd.isna(v) or str(v).strip() == '' for v in row):
            continue
        data_rows.append(row)

    if not data_rows:
        raise ValueError(f"{file_path} 中无有效数据行")

    df = pd.DataFrame(data_rows, columns=headers)

    col_mapping = {}
    week_cols = []

    for col in df.columns:
        col_str = str(col).strip()

        if col_str in ('第一分组标题',):
            col_mapping[col] = 'group'
        elif col_str == '指标':
            col_mapping[col] = 'metric'
        elif col_str == '单位':
            col_mapping[col] = 'unit'
        elif col_str in ('趋势图', '环比趋势图：-比率'):
            col_mapping[col] = '_trend_chart'
        elif re.match(r'^WoW##', col_str) or col_str.startswith('WoW'):
            col_mapping[col] = '_wow_raw'
        elif re.match(r'^W\d+##', col_str):
            week_num = re.match(r'^(W\d+)##', col_str).group(1)
            col_mapping[col] = week_num
            week_cols.append(week_num)
        elif re.match(r'^W\d+$', col_str):
            col_mapping[col] = col_str
            week_cols.append(col_str)

    df = df.rename(columns=col_mapping)

    actual_drop = [c for c in df.columns if c.startswith('_trend')]
    df = df.drop(columns=actual_drop, errors='ignore')

    df = _infer_hierarchy(df)

    for wc in week_cols:
        if wc in df.columns:
            df[wc] = df[wc].apply(parse_val)

    _df_cache[file_path] = df
    return df


def _infer_hierarchy(df: pd.DataFrame) -> pd.DataFrame:
    """推断指标的父子层次关系。"""
    PARENT_INDICATORS = {
        '消费GTV', '消费订单量', '曝光UV', '搜索UV', '购买用户数',
        '品类新客数', '交易用户数', '日均搜索UV', '消费实付单均价',
        '单均消费实付配送费', '消费美补率', '消费实付美补率（不含歪马三方）',
        '消费实付品牌补贴率（不含歪马三方）', '新客占比', '新客实付单均价',
        '800元以上单品消费GTV占比', '消费GTV占比', '消费订单量',
        '订单渗透率', '用户渗透率', '搜索UV_CXR',
        '曝光UV-CXR', '搜索UV-CXR',
        '搜索结果页闪购商家_强闪购意图商品意图全渠道_搜索设备CXR',
        '全国啤酒核心品做功门店在售率', '省份啤酒核心品做功门店在售率',
    }

    df['_is_child'] = False
    df['_parent_metric'] = None
    df['_is_yoy'] = False

    current_parent = None
    current_group = None

    for idx in df.index:
        metric = str(df.at[idx, 'metric']).strip() if pd.notna(df.at[idx, 'metric']) else ''
        group = str(df.at[idx, 'group']).strip() if pd.notna(df.at[idx, 'group']) else ''

        if metric.lower() == 'yoy':
            df.at[idx, '_is_yoy'] = True
            df.at[idx, '_parent_metric'] = current_parent
            continue

        if group and group != current_group:
            current_group = group
            current_parent = None

        if metric in PARENT_INDICATORS:
            current_parent = metric
            df.at[idx, '_is_child'] = False
        elif current_parent and metric:
            df.at[idx, '_is_child'] = True
            df.at[idx, '_parent_metric'] = current_parent

    return df


def parse_val(val: Any) -> Optional[float]:
    """解析数值，支持百分比、千分位逗号、空值"""
    if pd.isna(val) or val == '' or val == '-' or val == '--':
        return None
    if isinstance(val, (int, float)):
        return float(val) if not np.isnan(val) else None
    if isinstance(val, str):
        val = val.replace('%', '').replace('pp', '').replace(',', '').strip()
        try:
            return float(val)
        except (ValueError, TypeError):
            return None
    return None


def get_week_columns(df: pd.DataFrame) -> List[str]:
    """获取 DataFrame 中所有周列名（有序）"""
    week_cols = [c for c in df.columns if re.match(r'^W\d+$', str(c))]
    week_cols.sort(key=lambda x: int(x[1:]))
    return week_cols


def get_latest_week(df: pd.DataFrame) -> Optional[str]:
    """获取最新周标识"""
    week_cols = get_week_columns(df)
    return week_cols[-1] if week_cols else None


def get_metric_value(df: pd.DataFrame, metric_name: str, week: str) -> Optional[float]:
    """安全获取某指标某周的数值"""
    rows = df[df['metric'] == metric_name]
    if len(rows) == 0 or week not in df.columns:
        return None
    val = rows.iloc[0][week]
    return parse_val(val) if not isinstance(val, float) else val


def get_metric_series(df: pd.DataFrame, metric_name: str) -> Optional[np.ndarray]:
    """获取某指标的周序列（有序，从早到晚）。"""
    rows = df[df['metric'] == metric_name]
    if len(rows) == 0:
        return None

    week_cols = get_week_columns(df)
    if not week_cols:
        return None

    row = rows.iloc[0]
    values = []
    for wc in week_cols:
        v = row.get(wc)
        fv = parse_val(v) if not isinstance(v, float) else v
        if fv is not None:
            values.append(fv)

    return np.array(values) if values else None


def get_children_metrics(df: pd.DataFrame, parent_metric: str) -> List[str]:
    """获取某父指标的所有子指标名"""
    children = df[(df['_parent_metric'] == parent_metric) & (df['_is_child'] == True) & (df['_is_yoy'] == False)]
    return children['metric'].tolist()


def get_all_parent_metrics(df: pd.DataFrame) -> List[str]:
    """获取所有父级指标名"""
    parents = df[(df['_is_child'] == False) & (df['_is_yoy'] == False)]
    return parents['metric'].tolist()


def compute_wow(series: np.ndarray) -> Optional[float]:
    """计算最新一周的 WoW%（环比变化率）"""
    if series is None or len(series) < 2:
        return None
    prev = series[-2]
    curr = series[-1]
    if prev == 0 or prev is None:
        return None
    return (curr - prev) / abs(prev) * 100


def compute_wow_series(series: np.ndarray) -> Optional[np.ndarray]:
    """计算整个序列的逐周 WoW%"""
    if series is None or len(series) < 2:
        return None
    wow_arr = []
    for i in range(1, len(series)):
        if series[i - 1] == 0:
            wow_arr.append(None)
        else:
            wow_arr.append((series[i] - series[i - 1]) / abs(series[i - 1]) * 100)
    return np.array([v if v is not None else np.nan for v in wow_arr])


def get_yoy_value(df: pd.DataFrame, metric_name: str, week: Optional[str] = None) -> Optional[float]:
    """获取 YoY 值（如果数据中有 yoy 行）。"""
    yoy_rows = df[(df['_is_yoy'] == True) & (df['_parent_metric'] == metric_name)]
    if len(yoy_rows) == 0:
        return None

    if week is None:
        week = get_latest_week(df)
    if week is None:
        return None

    val = yoy_rows.iloc[0].get(week)
    return parse_val(val) if not isinstance(val, float) else val


def summarize_excel(file_path: str) -> Dict[str, Any]:
    """快速总结 Excel 文件的结构信息，用于诊断和报告。"""
    df = load_wbr_excel(file_path)
    week_cols = get_week_columns(df)
    parents = get_all_parent_metrics(df)

    summary = {
        'file': file_path,
        'total_rows': len(df),
        'week_columns': week_cols,
        'num_weeks': len(week_cols),
        'latest_week': week_cols[-1] if week_cols else None,
        'groups': df['group'].dropna().unique().tolist(),
        'parent_metrics': parents,
        'has_yoy_rows': df['_is_yoy'].any(),
        'has_wow_column': '_wow_raw' in df.columns,
    }
    return summary
