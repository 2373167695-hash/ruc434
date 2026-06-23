"""
宏观数据直爬脚本 v2
数据源：东方财富API（CPI、PMI）+ 中国银行API（汇率）
关键：每个数据源独立容错，rebuild.js质检把关
"""
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import requests

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
TIMEOUT = 15


def fetch_usdcny_boc():
    """中国银行外汇牌价 → USD/CNY 中间价"""
    print("  [汇率] BOC牌价...")
    try:
        r = requests.get(
            "https://www.boc.cn/sourcedb/whpj/",
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        r.encoding = "utf-8"
        
        # BOC页面返回HTML表格，找美元行
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(r.text, "html.parser")
        rows = soup.select("table tr")
        
        usd_row = None
        for row in rows:
            cols = row.select("td")
            if cols and "美元" in cols[0].get_text():
                usd_row = [c.get_text(strip=True) for c in cols]
                break
        
        if usd_row and len(usd_row) >= 6:
            # 中行牌价表: [货币, 现汇买入, 现钞买入, 现汇卖出, 现钞卖出, 中行折算价, 日期, 时间]
            mid_price = usd_row[5]  # 中行折算价
            try:
                # BOC牌价: 100美元=X人民币，如 681.71 → 1美元=6.8171
                val = float(mid_price) / 100
                today = datetime.now().strftime("%Y-%m")
                result = [{"date": today, "value": round(val, 4), "note": "中国银行牌价"}]
                print(f"    获取: {today}={round(val,4)}")
                return result
            except ValueError:
                print(f"    解析失败: {mid_price}")
        else:
            print(f"    未找到美元行")
    except Exception as e:
        print(f"    失败: {e}")
    return []


def fetch_eastmoney(report_name, columns, label, unit=""):
    """通用东方财富数据中心API"""
    try:
        params = {
            "sortColumns": "REPORT_DATE",
            "sortTypes": "-1",
            "pageSize": "12",
            "pageNumber": "1",
            "reportName": report_name,
            "columns": columns,
            "source": "WEB",
            "client": "WEB",
        }
        r = requests.get(
            "https://datacenter-web.eastmoney.com/api/data/v1/get",
            headers={**HEADERS, "Referer": "https://data.eastmoney.com/"},
            params=params,
            timeout=TIMEOUT,
        )
        data = r.json()
        if not data.get("success"):
            print(f"    API失败: {data.get('message','')[:80]}")
            return []
        
        items = data.get("result", {}).get("data", [])
        if not items:
            return []
        
        # 获取除REPORT_DATE和TIME外的第一个数值字段
        result = []
        for item in reversed(items):
            date_str = item.get("REPORT_DATE", "")[:7]
            if not date_str:
                continue
            
            # 找数值字段
            val = None
            for k, v in item.items():
                if k in ("REPORT_DATE", "TIME"):
                    continue
                if isinstance(v, (int, float)):
                    val = v
                    break
            
            if val is not None:
                result.append({"date": date_str, "value": round(float(val), 2 if unit == "亿美元" else 1)})
        
        if result:
            print(f"    获取 {len(result)} 个数据点: {result[-1]['date']}={result[-1]['value']}{unit}")
        return result
    except Exception as e:
        print(f"    失败: {e}")
        return []


def fetch_cpi():
    """CPI 同比"""
    print("  [CPI] 东方财富...")
    return fetch_eastmoney(
        "RPT_ECONOMY_CPI",
        "REPORT_DATE,TIME,NATIONAL_SAME,NATIONAL_BASE,CITY_SAME,RURAL_SAME",
        "CPI", "%"
    )


def fetch_ppi():
    """PPI 同比 — 尝试多种列名"""
    print("  [PPI] 东方财富...")
    for cols in [
        "REPORT_DATE,TIME,NATIONAL_SAME,NATIONAL_BASE",
    ]:
        result = fetch_eastmoney("RPT_ECONOMY_PPI", cols, "PPI", "%")
        if result:
            return result
    return []


def fetch_pmi():
    """制造业PMI"""
    print("  [PMI] 东方财富...")
    return fetch_eastmoney(
        "RPT_ECONOMY_PMI",
        "REPORT_DATE,TIME,MAKE_INDEX,NMAKE_INDEX",
        "PMI"
    )


def fetch_m2():
    """M2 货币供应量"""
    print("  [M2] 东方财富...")
    # 货币供应量报表不容易找到正确列名，跳过
    print("    (暂不可用，列名需进一步确认)")
    return []


def fetch_trade():
    """贸易差额"""
    print("  [贸易] 东方财富...")
    print("    (暂不可用，列名需进一步确认)")
    return []


def build_macro_data():
    today = datetime.now().strftime("%Y-%m-%d")
    indicators = []
    
    usdcny = fetch_usdcny_boc()
    if usdcny:
        indicators.append({
            "name": "人民币对美元汇率(中间价)",
            "unit": "USD/CNY",
            "description": "中国银行公布的美元对人民币折算价",
            "source": "中国银行",
            "data": usdcny
        })
    
    cpi = fetch_cpi()
    if cpi:
        indicators.append({
            "name": "居民消费价格指数 CPI",
            "unit": "%",
            "description": "CPI同比涨幅",
            "source": "国家统计局",
            "data": cpi
        })
    
    ppi = fetch_ppi()
    if ppi:
        indicators.append({
            "name": "工业生产者出厂价格 PPI",
            "unit": "%",
            "description": "PPI同比涨幅",
            "source": "国家统计局",
            "data": ppi
        })
    
    pmi = fetch_pmi()
    if pmi:
        indicators.append({
            "name": "制造业PMI",
            "unit": "",
            "description": "PMI>50扩张，<50收缩",
            "source": "国家统计局",
            "data": pmi
        })
    
    m2 = fetch_m2()
    if m2:
        indicators.append({
            "name": "M2货币供应量同比增速",
            "unit": "%",
            "description": "广义货币增速",
            "source": "中国人民银行",
            "data": m2
        })
    
    trade = fetch_trade()
    if trade:
        indicators.append({
            "name": "货物贸易差额",
            "unit": "亿美元",
            "description": "月度进出口差额",
            "source": "海关总署",
            "data": trade
        })
    
    return {
        "update_date": today,
        "data_source": "中国银行/东方财富/国家统计局（直爬）",
        "dashboard": {"indicators": indicators}
    }


def main():
    print("=" * 60)
    print(f"宏观数据直爬 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)
    
    macro = build_macro_data()
    
    n = len(macro["dashboard"]["indicators"])
    pts = sum(len(ind["data"]) for ind in macro["dashboard"]["indicators"])
    print(f"\n采集完成: {n}/6 项指标, {pts} 个数据点")
    
    for ind in macro["dashboard"]["indicators"]:
        print(f"  ✓ {ind['name']}: {len(ind['data'])}点")
    
    if n < 3:
        print(f"\n⚠ 仅 {n} 项指标（目标≥3），rebuild.js 将拒绝部署")
    
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    output = DATA_DIR / "macro_data.json"
    with open(output, "w", encoding="utf-8") as f:
        json.dump(macro, f, ensure_ascii=False, indent=2)
    
    print(f"已保存: {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
