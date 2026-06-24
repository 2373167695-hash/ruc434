/**
 * CloudBase 云函数 — AI 请求代理（HTTP 触发器）
 * 部署后在函数配置中开启 HTTP 访问，设置环境变量 MIMO_API_KEY
 * 
 * 前端调用：POST {云函数HTTP地址}
 * 请求体：{ messages: [...] }
 * 返回：{ choices: [{ message: { content: "..." } }] }
 */

exports.main = async (event, context) => {
  // HTTP trigger: event 是 Express 风格的 { httpMethod, body, ... }
  const { httpMethod, body } = event;
  
  // CORS preflight
  if (httpMethod === 'OPTIONS') {
    return {
      statusCode: 204,
      headers: {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type'
      }
    };
  }

  if (httpMethod !== 'POST') {
    return { statusCode: 405, body: JSON.stringify({ error: '只支持 POST' }) };
  }

  let params;
  try {
    params = typeof body === 'string' ? JSON.parse(body) : body;
  } catch (e) {
    return { 
      statusCode: 400, 
      headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
      body: JSON.stringify({ error: 'JSON 解析失败' })
    };
  }

  const { messages } = params;
  if (!messages || !Array.isArray(messages)) {
    return {
      statusCode: 400,
      headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
      body: JSON.stringify({ error: '缺少 messages 参数' })
    };
  }

  const API_KEY = process.env.MIMO_API_KEY;
  if (!API_KEY) {
    return {
      statusCode: 500,
      headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
      body: JSON.stringify({ error: 'API Key 未配置' })
    };
  }

  const resp = await fetch('https://api.xiaomimimo.com/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${API_KEY}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      model: 'mimo-v2.5',
      messages: messages,
      stream: false,
      temperature: 0.3,
      max_tokens: 4096
    })
  });

  const data = await resp.json();

  return {
    statusCode: 200,
    headers: {
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': '*'
    },
    body: JSON.stringify(data)
  };
};
