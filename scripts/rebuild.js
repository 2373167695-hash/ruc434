/**
 * CI/CD 重新构建脚本
 * 将更新后的 data/*.json 内嵌到 index.html 中
 * 用于 GitHub Actions 自动部署流程
 * 
 * 关键保护：数据质量校验，防止错误数据覆盖正常数据
 */
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const HTML_PATH = path.join(ROOT, "index.html");
const DATA_DIR = path.join(ROOT, "data");

const MIN_INDICATORS = 3;           // 至少要有3个指标
const MIN_DATA_POINTS = 1;          // 每个指标至少1个数据点
const EXPECTED_YEAR = 2026;
const TOLERATED_YEARS = 2;

function validateMacroData(data) {
    const indicators = data?.dashboard?.indicators;
    if (!indicators || indicators.length < MIN_INDICATORS) {
        console.log(`[校验失败] 指标数量不足: ${indicators?.length || 0} < ${MIN_INDICATORS}`);
        return false;
    }

    for (const ind of indicators) {
        const dataPoints = ind.data || [];
        
        // 检查数据点数量
        if (dataPoints.length < MIN_DATA_POINTS) {
            console.log(`[校验失败] "${ind.name}" 数据点不足: ${dataPoints.length} < ${MIN_DATA_POINTS}`);
            return false;
        }

        // 检查日期是否合理（应该在2024-2028年范围内）
        for (const pt of dataPoints) {
            const dt = pt.date || "";
            const yearMatch = dt.match(/^(\d{4})/);
            if (yearMatch) {
                const year = parseInt(yearMatch[1]);
                if (Math.abs(year - EXPECTED_YEAR) > TOLERATED_YEARS) {
                    console.log(`[校验失败] "${ind.name}" 数据年份异常: ${dt} (期望 ${EXPECTED_YEAR}±${TOLERATED_YEARS})`);
                    return false;
                }
            }
        }

        // 检查值是否合理（CFETS指数应该在80-110之间，汇率在5-8之间，百分比在-5到20之间）
        for (const pt of dataPoints) {
            const val = pt.value;
            if (typeof val !== "number" || isNaN(val)) continue;
            
            // 指数类指标（仅限CFETS等汇率指数，不包括CPI/PPI等价格指数）
            if (ind.name.includes("CFETS") || (ind.name.includes("汇率") && ind.name.includes("指数"))) {
                if (val < 70 || val > 120) {
                    console.log(`[校验失败] "${ind.name}" 数值异常: ${val} (CFETS正常范围70-120)`);
                    return false;
                }
            }
            // 汇率类
            else if (ind.name.includes("汇率") || ind.name.includes("USD")) {
                if (val < 5 || val > 9) {
                    console.log(`[校验失败] "${ind.name}" 数值异常: ${val} (汇率正常范围5-9)`);
                    return false;
                }
            }
            // 百分比类
            else if (ind.unit === "%") {
                if (val < -10 || val > 30) {
                    console.log(`[校验失败] "${ind.name}" 数值异常: ${val}% (百分比正常范围-10~30)`);
                    return false;
                }
            }
        }

        // 检查数据是否全部相同（可能是采集失败）
        if (dataPoints.length >= 4) {
            const values = dataPoints.map(p => p.value);
            const uniqueValues = new Set(values.filter(v => typeof v === "number"));
            if (uniqueValues.size === 1) {
                console.log(`[校验失败] "${ind.name}" 所有数据点完全相同: ${values[0]} (可能是采集失败)`);
                return false;
            }
        }

        console.log(`[校验通过] "${ind.name}": ${dataPoints.length}个数据点, 范围 ${dataPoints[0].date}~${dataPoints[dataPoints.length-1].date}`);
    }

    console.log(`[总体验收] 通过! ${indicators.length}个指标数据质量合格`);
    return true;
}


function validateHotTopics(data) {
    const sections = data?.sections;
    if (!sections || sections.length === 0) {
        console.log("[校验失败] 热点数据没有有效内容");
        return false;
    }
    console.log(`[校验通过] 热点数据: ${sections.length}个章节`);
    return true;
}


function main() {
    console.log("=" .repeat(50));
    console.log("重新构建 HTML（内嵌最新数据）");
    console.log("=" .repeat(50));

    let html = fs.readFileSync(HTML_PATH, "utf8");
    let updatedCount = 0;

    // 处理 macro_data.json
    const macroPath = path.join(DATA_DIR, "macro_data.json");
    if (fs.existsSync(macroPath)) {
        const macroData = JSON.parse(fs.readFileSync(macroPath, "utf8"));
        
        if (validateMacroData(macroData)) {
            const newValue = `var MACRO_DATA = ${JSON.stringify(macroData)};`;
            const regex = /var MACRO_DATA\s*=\s*\{[\s\S]*?\};/m;
            const match = html.match(regex);
            
            if (match) {
                html = html.replace(regex, newValue);
                console.log(`[更新] MACRO_DATA: ${(match[0].length/1024).toFixed(1)}KB → ${(newValue.length/1024).toFixed(1)}KB`);
                updatedCount++;
            }
        } else {
            console.log("[跳过] MACRO_DATA 数据校验未通过，保留原有数据");
        }
    } else {
        console.log("[跳过] macro_data.json 不存在");
    }

    // 处理 hot_topics.json  
    const hotspotsPath = path.join(DATA_DIR, "hot_topics.json");
    if (fs.existsSync(hotspotsPath)) {
        const hotspotsData = JSON.parse(fs.readFileSync(hotspotsPath, "utf8"));
        
        if (validateHotTopics(hotspotsData)) {
            const newValue = `var HOT_TOPICS = ${JSON.stringify(hotspotsData)};`;
            const regex = /var HOT_TOPICS\s*=\s*\{[\s\S]*?\};/m;
            const match = html.match(regex);
            
            if (match) {
                html = html.replace(regex, newValue);
                console.log(`[更新] HOT_TOPICS: ${(match[0].length/1024).toFixed(1)}KB → ${(newValue.length/1024).toFixed(1)}KB`);
                updatedCount++;
            }
        } else {
            console.log("[跳过] HOT_TOPICS 数据校验未通过，保留原有数据");
        }
    } else {
        console.log("[跳过] hot_topics.json 不存在");
    }

    if (updatedCount === 0) {
        console.log("\n没有数据需要更新，HTML 保持不变");
        return;
    }

    fs.writeFileSync(HTML_PATH, html, "utf8");
    
    const finalSize = (fs.statSync(HTML_PATH).size / 1024).toFixed(1);
    console.log(`\n构建完成: ${finalSize}KB`);
    console.log("HTML 已更新，准备部署");
}

main();
