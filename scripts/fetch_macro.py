"""
宏观数据自动采集脚本
使用 AKShare 获取最新宏观经济指标
每月1号由 GitHub Actions 自动运行
"""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

def safe_float(val):
    """安全转换为浮点数"""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None

def fetch_cfets_index():
    """CFETS 人民币汇率指数"""
    try:
        import akshare as ak
        df = ak.currency_boc_safe()
        if df is None or df.empty:
            return []
        
        result = []
        for _, row in df.tail(24).iterrows():
            date_str = str(row.get("日期", ""))
            if len(date_str) >= 7:
                d = date_str[:7]
                val = safe_float(row.get("美元", row.get("美元/人民币", 0)))
                if val and val > 1:
                    val = 100 / val
                    val = round(val * 100) / 100
                if val:
                    result.append({"date": d, "value": val, "note": "AKShare自动获取"})
        return result[-12:] if result else []
    except Exception as e:
        print(f"[CFETS指数] 获取失败: {e}")
        return []

def fetch_usdcny():
    """人民币对美元汇率中间价（月均）"""
    try:
        import akshare as ak
        df = ak.currency_boc_sina()
        if df is None or df.empty:
            return []
        
        result = []
        for _, row in df.tail(24).iterrows():
            date_val = str(row.get("日期", ""))
            val = safe_float(row.get("美元", 0))
            if val and len(date_val) >= 7:
                result.append({
                    "date": date_val[:7],
                    "value": round(val / 100, 4),
                    "note": "AKShare自动获取"
                })
        return result[-12:] if result else []
    except Exception as e:
        print(f"[USD/CNY] 获取失败: {e}")
        return []

def fetch_cpi_ppi():
    """CPI 和 PPI 数据"""
    try:
        import akshare as ak
        cpi_df = ak.macro_china_cpi_monthly()
        ppi_df = ak.macro_china_ppi_yearly()
        
        result = {"cpi": [], "ppi": []}
        
        if cpi_df is not None and not cpi_df.empty:
            for _, row in cpi_df.tail(12).iterrows():
                d = str(row.get("日期", ""))
                val = safe_float(row.get("全国-当月", row.get("当月", 0)))
                if val and len(d) >= 7:
                    result["cpi"].append({"date": d[:7], "value": val})
        
        if ppi_df is not None and not ppi_df.empty:
            for _, row in ppi_df.tail(12).iterrows():
                d = str(row.get("日期", ""))
                val = safe_float(row.get("当月", 0))
                if val and len(d) >= 7:
                    result["ppi"].append({"date": d[:7], "value": val})
        
        return result
    except Exception as e:
        print(f"[CPI/PPI] 获取失败: {e}")
        return {"cpi": [], "ppi": []}

def fetch_pmi_m2():
    """制造业PMI 和 M2增速"""
    try:
        import akshare as ak
        result = {"pmi": [], "m2": []}
        
        # PMI
        try:
            pmi_df = ak.macro_china_pmi()
            if pmi_df is not None and not pmi_df.empty:
                for _, row in pmi_df.tail(12).iterrows():
                    d = str(row.get("日期", ""))
                    val = safe_float(row.get("制造业", row.get("制造业-PMI", 0)))
                    if val and len(d) >= 7:
                        result["pmi"].append({"date": d[:7], "value": val})
        except:
            pass
        
        # M2
        try:
            m2_df = ak.macro_china_money_supply()
            if m2_df is not None and not m2_df.empty:
                for _, row in m2_df.tail(12).iterrows():
                    d = str(row.get("月份", ""))
                    val = safe_float(row.get("货币和准货币(M2)-同比增长", row.get("M2同比增长", 0)))
                    if val and len(d) >= 7:
                        result["m2"].append({"date": d[:7], "value": val})
        except:
            pass
        
        return result
    except Exception as e:
        print(f"[PMI/M2] 获取失败: {e}")
        return {"pmi": [], "m2": []}

def fetch_trade_balance():
    """贸易差额"""
    try:
        import akshare as ak
        df = ak.macro_china_trade_balance()
        if df is None or df.empty:
            return []
        
        result = []
        for _, row in df.tail(12).iterrows():
            d = str(row.get("日期", ""))
            val = safe_float(row.get("贸易差额", 0))
            if val and len(d) >= 7:
                result.append({"date": d[:7], "value": round(val, 2)})
        return result
    except Exception as e:
        print(f"[贸易差额] 获取失败: {e}")
        return []


def build_macro_data():
    """构建完整的宏观数据结构"""
    today = datetime.now().strftime("%Y-%m-%d")
    
    cfets = fetch_cfets_index()
    usdcny = fetch_usdcny()
    cpi_ppi = fetch_cpi_ppi()
    pmi_m2 = fetch_pmi_m2()
    trade = fetch_trade_balance()
    
    indicators = []
    
    if cfets:
        indicators.append({
            "name": "CFETS人民币汇率指数",
            "unit": "",
            "description": "人民币对一篮子货币的综合汇率指数，反映人民币整体对外价值",
            "source": "中国外汇交易中心(CFETS)",
            "data": cfets
        })
    
    if usdcny:
        indicators.append({
            "name": "人民币对美元汇率(中间价月均)",
            "unit": "USD/CNY",
            "description": "中国人民银行授权公布的银行间外汇市场人民币汇率中间价月均值",
            "source": "中国人民银行/中国外汇交易中心",
            "data": usdcny
        })
    
    if cpi_ppi.get("cpi"):
        indicators.append({
            "name": "居民消费价格指数 CPI",
            "unit": "%",
            "description": "反映居民家庭一般所购买的消费品和服务项目价格水平变动情况",
            "source": "国家统计局",
            "data": cpi_ppi["cpi"]
        })
    
    if cpi_ppi.get("ppi"):
        indicators.append({
            "name": "工业生产者出厂价格指数 PPI",
            "unit": "%",
            "description": "反映工业企业产品第一次出售时的出厂价格变化趋势和变动幅度",
            "source": "国家统计局",
            "data": cpi_ppi["ppi"]
        })
    
    if pmi_m2.get("pmi"):
        indicators.append({
            "name": "制造业采购经理指数 PMI",
            "unit": "",
            "description": "PMI>50表示制造业扩张，<50表示收缩",
            "source": "国家统计局",
            "data": pmi_m2["pmi"]
        })
    
    if pmi_m2.get("m2"):
        indicators.append({
            "name": "M2货币供应量同比增速",
            "unit": "%",
            "description": "广义货币供应量同比增速，反映货币政策松紧程度",
            "source": "中国人民银行",
            "data": pmi_m2["m2"]
        })
    
    if trade:
        indicators.append({
            "name": "贸易差额",
            "unit": "亿美元",
            "description": "月度出口额减进口额",
            "source": "海关总署",
            "data": trade
        })
    
    macro_data = {
        "update_date": today,
        "data_source": "中国人民银行、国家统计局、海关总署、中国外汇交易中心（数据由AKShare自动获取）",
        "dashboard": {
            "indicators": indicators
        }
    }
    
    return macro_data


def main():
    print("=" * 60)
    print("宏观数据自动采集")
    print(f"运行时间: {datetime.now().isoformat()}")
    print("=" * 60)
    
    macro_data = build_macro_data()
    
    n_indicators = len(macro_data.get("dashboard", {}).get("indicators", []))
    total_points = sum(len(ind.get("data", [])) for ind in macro_data.get("dashboard", {}).get("indicators", []))
    
    print(f"\n采集完成: {n_indicators} 项指标, 共 {total_points} 个数据点")
    
    # 保存到 data 目录
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    output_path = DATA_DIR / "macro_data.json"
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(macro_data, f, ensure_ascii=False, indent=2)
    
    print(f"已保存到: {output_path}")
    print(f"文件大小: {output_path.stat().st_size} bytes")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
