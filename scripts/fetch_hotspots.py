"""
热点追踪自动采集脚本
爬取人大经济学院官网学术动态 + 知网公开摘要
每周一由 GitHub Actions 自动运行
"""
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# 人大434重点导师列表
PROFESSORS = [
    "杨瑞龙", "刘守英", "王孝松", "孙浦阳",
    "聂辉华", "李三希", "刘伟", "易靖韬"
]

# 导师所属学院关键词（用于搜索结果过滤）
PROF_KEYWORDS = {
    "杨瑞龙": ["制度经济学", "企业理论", "国企改革", "经济学范式"],
    "刘守英": ["数字经济", "土地制度", "资源配置", "智能复合配置"],
    "王孝松": ["国际贸易", "贸易政策", "贸易摩擦", "反倾销"],
    "孙浦阳": ["技术标准", "国际贸易", "世界经济", "贸易新优势"],
    "聂辉华": ["政企关系", "企业理论", "数据收集", "消费者福利"],
    "李三希": ["信息经济学", "平台经济", "数字经济", "数据网络"],
    "刘伟": ["高质量发展", "新质生产力", "宏观经济", "政治经济学"],
    "易靖韬": ["跨国公司", "平台生态", "共生战略", "数字经济"],
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def fetch_econ_ruc():
    """爬取人大经济学院官网学术动态"""
    results = []
    urls = [
        "http://econ.ruc.edu.cn/kxyj/xsdt/index.htm",
        "http://econ.ruc.edu.cn/kxyj/kycg/index.htm",
    ]
    
    for url in urls:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "html.parser")
            
            # 查找新闻列表项
            items = soup.select(".news-list li, .list-item, .news-item, .xwzx li")
            if not items:
                items = soup.select("a[href*='.htm']")
            
            for item in items[:20]:
                link = item.select_one("a")
                if not link:
                    continue
                
                title = link.get_text(strip=True)
                href = link.get("href", "")
                
                # 补全URL
                if href and not href.startswith("http"):
                    base = url.rsplit("/", 2)[0]
                    href = base + "/" + href.lstrip("/")
                
                date_el = item.select_one(".date, .time, span.fr")
                date_str = date_el.get_text(strip=True) if date_el else ""
                
                # 检查标题是否包含导师姓名
                for prof in PROFESSORS:
                    if prof in title:
                        results.append({
                            "source": "人大经济学院",
                            "source_url": href,
                            "professor": prof,
                            "title": title,
                            "date": date_str,
                        })
                        break
            
            print(f"[经济学院] {url} 采集完成，找到 {len([r for r in results if r['source']=='人大经济学院'])} 条")
        
        except Exception as e:
            print(f"[经济学院] {url} 采集失败: {e}")
    
    return results


def fetch_cnki():
    """爬取知网公开摘要（按导师姓名检索）"""
    results = []
    
    for prof in PROFESSORS:
        try:
            # 知网公开检索接口
            search_url = f"https://kns.cnki.net/kns8/defaultresult/index"
            params = {
                "kwd": prof,
                "dbcode": "CJFD",
            }
            
            resp = requests.get(search_url, headers=HEADERS, params=params, timeout=20)
            resp.encoding = "utf-8"
            
            # 尝试从页面提取论文信息
            # 知网页面是客户端渲染的，直接解析HTML可能拿不到数据
            # 使用备用方案：从页面meta或script标签提取
            soup = BeautifulSoup(resp.text, "html.parser")
            
            # 尝试从 script 标签中提取初始数据
            scripts = soup.select("script")
            for script in scripts:
                if not script.string:
                    continue
                text = script.string
                if "resultlist" in text.lower() or "论文" in text:
                    # 尝试匹配论文标题模式
                    titles = re.findall(r'"Title":"([^"]+)"', text)
                    authors = re.findall(r'"Author":"([^"]+)"', text)
                    sources = re.findall(r'"Source":"([^"]+)"', text)
                    years = re.findall(r'"Year":"(\d{4})"', text)
                    
                    for i, title in enumerate(titles[:5]):
                        author = authors[i] if i < len(authors) else ""
                        source = sources[i] if i < len(sources) else ""
                        year = years[i] if i < len(years) else ""
                        
                        # 只收录2025-2026年的论文
                        if year in ("2025", "2026") or prof in title:
                            results.append({
                                "source": "知网",
                                "source_url": f"https://kns.cnki.net/kns8/defaultresult/index?kwd={prof}",
                                "professor": prof,
                                "title": title,
                                "author": author,
                                "journal": source,
                                "year": year,
                            })
                    break
            
            print(f"[知网] {prof}: 找到 {len([r for r in results if r.get('professor')==prof and r.get('source')=='知网'])} 篇")
            import time
            time.sleep(2)  # 避免请求过快
        
        except Exception as e:
            print(f"[知网] {prof} 检索失败: {e}")
    
    return results


def fetch_ssrn():
    """从 SSRN / Google Scholar 获取导师最新英文论文（备用方案）"""
    results = []
    
    # 英文名映射
    english_names = {
        "杨瑞龙": "Yang Ruilong",
        "刘守英": "Liu Shouying",
        "王孝松": "Wang Xiaosong",
        "易靖韬": "Yi Jingtao",
        "聂辉华": "Nie Huihua",
        "李三希": "Li Sanxi",
        "刘伟": "Liu Wei",
        "孙浦阳": "Sun Puyang",
    }
    
    for prof, en_name in english_names.items():
        try:
            # SSRN 搜索
            url = f"https://papers.ssrn.com/sol3/results.cfm"
            resp = requests.get(url, headers=HEADERS, params={"q": en_name}, timeout=15)
            resp.encoding = "utf-8"
            
            soup = BeautifulSoup(resp.text, "html.parser")
            items = soup.select(".search-result, .title-option")
            
            for item in items[:3]:
                title_el = item.select_one("h3 a, .title a")
                if title_el:
                    title = title_el.get_text(strip=True)
                    results.append({
                        "source": "SSRN",
                        "source_url": f"https://papers.ssrn.com/sol3/results.cfm?q={en_name.replace(' ', '+')}",
                        "professor": prof,
                        "title": title,
                    })
            
            import time
            time.sleep(1)
        
        except Exception as e:
            print(f"[SSRN] {prof} 搜索失败: {e}")
    
    return results


def deduplicate(items):
    """按标题去重"""
    seen = set()
    result = []
    for item in items:
        key = item.get("title", "")
        if key and key not in seen:
            seen.add(key)
            result.append(item)
    return result


def main():
    print("=" * 60)
    print("热点追踪自动采集")
    print(f"运行时间: {datetime.now().isoformat()}")
    print("=" * 60)
    
    all_results = []
    
    # 1. 人大经济学院官网
    print("\n[1/3] 采集人大经济学院官网...")
    econ_results = fetch_econ_ruc()
    all_results.extend(econ_results)
    print(f"    结果: {len(econ_results)} 条")
    
    # 2. 知网摘要
    print("\n[2/3] 检索知网论文...")
    cnki_results = fetch_cnki()
    all_results.extend(cnki_results)
    print(f"    结果: {len(cnki_results)} 条")
    
    # 3. SSRN（备用）
    print("\n[3/3] 检索 SSRN...")
    ssrn_results = fetch_ssrn()
    all_results.extend(ssrn_results)
    print(f"    结果: {len(ssrn_results)} 条")
    
    # 去重
    all_results = deduplicate(all_results)
    
    # 构建结构化输出
    output = {
        "fetch_date": datetime.now().strftime("%Y-%m-%d"),
        "total": len(all_results),
        "professor_coverage": {
            prof: len([r for r in all_results if r.get("professor") == prof])
            for prof in PROFESSORS
        },
        "raw_items": all_results[:50],  # 最多保留50条
    }
    
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    output_path = DATA_DIR / "hotspots_raw.json"
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"\n最终结果: {len(all_results)} 条（去重后）")
    print(f"已保存到: {output_path}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
