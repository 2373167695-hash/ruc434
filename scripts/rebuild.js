/**
 * CI/CD 重新构建脚本
 * 将更新后的 data/*.json 内嵌到 index.html 中
 * 用于 GitHub Actions 自动部署流程
 */
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const HTML_PATH = path.join(ROOT, "index.html");
const DATA_DIR = path.join(ROOT, "data");

// 需要更新的数据文件与对应的 JS 变量名
const DATA_FILES = {
  "macro_data.json": "MACRO_DATA",
  "hot_topics.json": "HOT_TOPICS",
};

function main() {
  console.log("=" .repeat(50));
  console.log("重新构建 HTML（内嵌最新数据）");
  console.log("=" .repeat(50));

  let html = fs.readFileSync(HTML_PATH, "utf8");
  let updatedCount = 0;

  for (const [filename, varName] of Object.entries(DATA_FILES)) {
    const jsonPath = path.join(DATA_DIR, filename);
    
    if (!fs.existsSync(jsonPath)) {
      console.log(`[跳过] ${filename} 不存在`);
      continue;
    }

    const jsonData = JSON.parse(fs.readFileSync(jsonPath, "utf8"));
    const newValue = `var ${varName} = ${JSON.stringify(jsonData)};`;

    // 在 HTML 中查找并替换对应的变量声明
    const regex = new RegExp(`var ${varName}\\s*=\\s*\\{[\\s\\S]*?\\};`, "m");
    const match = html.match(regex);

    if (match) {
      html = html.replace(regex, newValue);
      const oldSize = match[0].length;
      const newSize = newValue.length;
      console.log(`[更新] ${varName}: ${(oldSize/1024).toFixed(1)}KB → ${(newSize/1024).toFixed(1)}KB`);
      updatedCount++;
    } else {
      console.log(`[跳过] ${varName}: 未在 HTML 中找到变量声明`);
    }
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
