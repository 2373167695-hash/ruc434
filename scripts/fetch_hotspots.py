"""
热点追踪采集脚本（优化版）
来源：人大经济学院官网 + 知网检索
缩短超时、限制单源数量、快速失败
"""
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

PROFESSORS = ["杨瑞龙","刘守英","王孝松","孙浦阳","聂辉华","李三希","刘伟","易靖韬"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

TIMEOUT = 10  # 缩短到10秒
MAX_PER_SOURCE = 10

def fetch_page(url, timeout=TIMEOUT):
    """安全获取页面"""
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        return r
    except Exception as e:
        print(f"    HTTP失败: {e}")
        return None


def fetch_econ_ruc():
    """人大经济学院 - 学术动态 + 科研成果"""
    results = []
    urls = [
        "http://econ.ruc.edu.cn/kxyj/xsdt/index.htm",
        "http://econ.ruc.edu.cn/kxyj/kycg/index.htm",
    ]
    
    for url in urls:
        print(f"  爬取: {url}")
        r = fetch_page(url)
        if not r:
            continue
        
        r.encoding = "utf-8"
        soup = BeautifulSoup(r.text, "html.parser")
        
        items = soup.select("li a[href*='.htm']") or soup.select(".news-list a") or soup.select("a[title]")
        count = 0
        for item in items[:MAX_PER_SOURCE]:
            title = item.get_text(strip=True)
            href = item.get("href", "")
            
            if len(title) < 6:
                continue
            
            if href and not href.startswith("http"):
                href = "http://econ.ruc.edu.cn" + href.lstrip(".")
            
            for prof in PROFESSORS:
                if prof in title:
                    results.append({
                        "source": "经济学院",
                        "professor": prof,
                        "title": title,
                        "url": href,
                    })
                    count += 1
                    break
        
        print(f"    找到 {count} 条")
    
    return results


def fetch_cnki():
    """知网检索（简化版，只查标题）"""
    results = []
    
    for prof in PROFESSORS[:4]:  # 只查前4位导师，节省时间
        print(f"  检索: {prof}")
        try:
            url = f"https://kns.cnki.net/kns8/defaultresult/index"
            r = requests.get(url, headers=HEADERS, params={"kwd": prof}, timeout=12)
            r.encoding = "utf-8"
            soup = BeautifulSoup(r.text, "html.parser")
            
            # 从 script 标签中提取数据
            for script in soup.select("script"):
                if not script.string:
                    continue
                text = script.string
                if '"Title"' not in text:
                    continue
                
                titles = re.findall(r'"Title":"([^"]+)"', text)[:3]
                years = re.findall(r'"Year":"(\d{4})"', text)[:3]
                sources = re.findall(r'"Source":"([^"]+)"', text)[:3]
                
                for i, t in enumerate(titles):
                    y = years[i] if i < len(years) else ""
                    s = sources[i] if i < len(sources) else ""
                    if y in ("2025", "2026") or prof in t:
                        results.append({
                            "source": "知网",
                            "professor": prof,
                            "title": t,
                            "year": y,
                            "journal": s,
                        })
                break
            
            time.sleep(0.5)
        except Exception as e:
            print(f"    失败: {e}")
    
    return results


def deduplicate(items):
    seen = set()
    result = []
    for item in items:
        key = item.get("title", "")[:30]
        if key and key not in seen:
            seen.add(key)
            result.append(item)
    return result


def main():
    print("=" * 60)
    print(f"热点采集 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)
    
    all_results = []
    
    print("\n[1/2] 经济学院官网...")
    econ = fetch_econ_ruc()
    all_results.extend(econ)
    print(f"  小计: {len(econ)} 条")
    
    print("\n[2/2] 知网检索...")
    cnki = fetch_cnki()
    all_results.extend(cnki)
    print(f"  小计: {len(cnki)} 条")
    
    all_results = deduplicate(all_results)
    
    output = {
        "fetch_date": datetime.now().strftime("%Y-%m-%d"),
        "total": len(all_results),
        "raw_items": all_results[:30],
    }
    
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    output_path = DATA_DIR / "hotspots_raw.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"\n总计: {len(all_results)} 条（去重后）")
    if len(all_results) == 0:
        print("提示: 未发现新内容，可能是网络限制或近期无更新")
    else:
        for item in all_results[:5]:
            print(f"  [{item.get('professor','')}] {item.get('title','')[:50]}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
