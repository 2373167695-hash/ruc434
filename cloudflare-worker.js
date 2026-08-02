/**
 * 人大434备考系统 - Cloudflare Worker AI代理
 * 
 * 接受与 server.py 相同的请求格式，构建上下文后转发到 DeepSeek API
 * 
 * 部署步骤:
 * 1. npm install -g wrangler
 * 2. wrangler login
 * 3. wrangler secret put DEEPSEEK_KEY
 *    (输入你的 DeepSeek API Key)
 * 4. wrangler deploy
 * 部署后得到 URL: https://r434-ai-proxy.你的用户名.workers.dev
 */

// 知识库数据（精简版，只有关键字段用于匹配，完整数据在前端）
const KNOWLEDGE_KEYS = {};

export default {
  async fetch(request, env, ctx) {
    const corsHeaders = {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
    };

    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: corsHeaders });
    }

    const url = new URL(request.url);
    const path = url.pathname;

    if (path !== '/api/chat' && path !== '/api/generate_question' && path !== '/api/diagnose') {
      return new Response(JSON.stringify({ error: 'Not Found' }), { status: 404, headers: corsHeaders });
    }

    try {
      const body = await request.json();
      let messages = [];

      if (path === '/api/chat') {
        messages = buildChatMessages(body);
      } else if (path === '/api/generate_question') {
        messages = buildGenerateMessages(body);
      } else if (path === '/api/diagnose') {
        messages = buildDiagnoseMessages(body);
      }

      // Call DeepSeek API
      const resp = await fetch('https://api.deepseek.com/v1/chat/completions', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${env.DEEPSEEK_KEY}`,
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream',
        },
        body: JSON.stringify({
          model: 'deepseek-v4-flash',
          messages: messages,
          stream: true,
          temperature: 0.3,
          max_tokens: 2048,
        }),
      });

      if (!resp.ok) {
        const err = await resp.text();
        return new Response(
          `data: [ERROR] API ${resp.status}: ${err.substring(0, 200)}\n\n`,
          { headers: { ...corsHeaders, 'Content-Type': 'text/event-stream' } }
        );
      }

      return new Response(resp.body, {
        headers: { ...corsHeaders, 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache' }
      });

    } catch (err) {
      return new Response(
        `data: [ERROR] ${err.message}\n\n`,
        { headers: { ...corsHeaders, 'Content-Type': 'text/event-stream' } }
      );
    }
  },
};

function buildChatMessages(body) {
  const query = body.query || '';
  const history = body.history || [];
  const page = body.page || {};
  const knowledge = body.knowledge || '';

  const system = '你是人大434国际商务考研AI助手。回答要结构化：先概述，再分要点(1)(2)(3)。语言专业化，使用学术术语。涉及理论对比用相同点/不同点框架。如果问题与备考无关，简短友好回答。';

  const messages = [{ role: 'system', content: system }];
  for (const h of history.slice(-10)) {
    messages.push({ role: h.role, content: h.content });
  }
  messages.push({ role: 'user', content: query });

  return messages;
}

function buildGenerateMessages(body) {
  const knowledge = body.knowledge || '';
  const system = '你是资深考研出题老师，专门为人大434国际商务专业基础设计题目。题目风格：学术化、理论与实践结合、有区分度。';

  const prompt = `目标知识点：${knowledge}\n\n请模仿人大434真题风格，生成3道模拟题：\n1.简答题（考察基础理论）\n2.论述题（理论+实际）\n3.计算/案例题\n\n每题附上：题目原文、简要参考答案要点（3-5个）。用「第1题」「第2题」「第3题」编号。`;

  return [
    { role: 'system', content: system },
    { role: 'user', content: prompt },
  ];
}

function buildDiagnoseMessages(body) {
  const views = body.views || {};
  const marks = body.marks || {};

  let summary = '学习数据：\n';
  summary += '浏览知识点：' + Object.keys(views).length + '个\n';
  const doneCount = Object.values(marks).filter(v => v.done).length;
  summary += '已做真题：' + doneCount + '/124道\n';

  const system = '你是考研备考规划专家，擅长根据学习数据分析薄弱环节并给出建议。回复结构化，500字内。';
  const prompt = summary + '\n\n请分析：1.进度评价 2.薄弱模块 3.优先复习建议 4.冲刺建议。';

  return [
    { role: 'system', content: system },
    { role: 'user', content: prompt },
  ];
}
