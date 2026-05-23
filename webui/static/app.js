const state = {
  settings: null,
  refreshTimer: null,
  hits: [],
};

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }
  return response.json();
}

function linesToArray(text) {
  return text
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);
}

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatTime(value) {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("zh-CN", {
    hour12: false,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function deriveErrorHint(rawError) {
  if (!rawError) {
    return "-";
  }
  const text = String(rawError);
  if (text.includes("HTTP request failed")) {
    return "接口请求失败，优先检查 Cookie 是否失效。";
  }
  if (text.includes("empty list")) {
    return "接口返回空列表，可能是 Cookie 失效或当前没有数据。";
  }
  return text.slice(0, 80);
}

function showToast(message, type = "success") {
  const el = document.getElementById("toast");
  el.textContent = message;
  el.className = `toast ${type === "error" ? "error" : ""}`.trim();
  el.hidden = false;
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => {
    el.hidden = true;
  }, 2600);
}

function renderRiskBanner(rawError) {
  const banner = document.getElementById("riskBanner");
  const text = String(rawError || "");
  if (text.includes("HTTP request failed") || text.includes("empty list")) {
    banner.hidden = false;
    banner.textContent = "Cookie 可能已失效。建议尽快重新抓包并更新 Session Cookie 值。";
    return;
  }
  banner.hidden = true;
  banner.textContent = "";
}

function renderStatus(statusPayload) {
  const container = document.getElementById("statusGrid");
  const service = statusPayload.service;
  const latestRun = statusPayload.latest_run || {};
  const items = [
    ["后台运行", service.running ? "执行中" : "空闲"],
    ["监控开关", service.enabled ? "已启用" : "已暂停"],
    ["最近启动", formatTime(service.last_started_at)],
    ["最近完成", formatTime(service.last_finished_at)],
    ["最近命中", String(service.last_report?.matched_count ?? latestRun.matched_count ?? 0)],
    ["最近错误", deriveErrorHint(service.last_error)],
  ];
  container.innerHTML = items
    .map(
      ([label, value]) => `
        <div class="status-pill">
          <span class="label">${escapeHtml(label)}</span>
          <span class="value">${escapeHtml(value)}</span>
        </div>
      `,
    )
    .join("");
  renderRiskBanner(service.last_error || latestRun.error_text || "");
}

function renderHits(items) {
  const container = document.getElementById("hitsList");
  if (!items.length) {
    container.innerHTML = `<div class="list-item"><p>暂时没有命中记录。</p></div>`;
    return;
  }
  container.innerHTML = items
    .map(
      (item) => `
        <article class="list-item">
          <h3>${escapeHtml(item.title || item.summary || "未命名帖子")}</h3>
          <p>分类：${escapeHtml(item.category || "-")}</p>
          <p>帖子ID：${escapeHtml(item.source_id || "-")}</p>
          <p>联系方式：${escapeHtml(item.contact || "-")}</p>
          <p>摘要：${escapeHtml(item.summary || "-")}</p>
          <p>抓取时间：${escapeHtml(formatTime(item.captured_at))}</p>
          <div class="tag-row">
            ${(item.matched_keywords || []).map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`).join("")}
          </div>
          <details>
            <summary>查看原文</summary>
            <div class="content-box">${escapeHtml(item.content || "")}</div>
          </details>
        </article>
      `,
    )
    .join("");
}

function renderRuns(items) {
  const container = document.getElementById("runsList");
  if (!items.length) {
    container.innerHTML = `<div class="list-item"><p>暂时没有运行历史。</p></div>`;
    return;
  }
  container.innerHTML = items
    .map(
      (item) => `
        <article class="list-item">
          <h3>${escapeHtml(item.status)} · ${escapeHtml(formatTime(item.created_at))}</h3>
          <p>拉取：${item.total_posts} / 命中：${item.matched_count}</p>
          <p>分类过滤：${item.category_skipped} / 补详情：${item.detail_checked}</p>
          <p>关键词未命中：${item.keyword_skipped} / 已通知：${item.seen_skipped}</p>
          <p>帖子ID：${escapeHtml((item.matched_post_ids || []).join(", ") || "none")}</p>
          <p>错误：${escapeHtml(deriveErrorHint(item.error_text || "-"))}</p>
        </article>
      `,
    )
    .join("");
}

function filterHits() {
  const q = document.getElementById("hitSearch").value.trim().toLowerCase();
  if (!q) {
    renderHits(state.hits);
    return;
  }
  const filtered = state.hits.filter((item) => {
    const haystack = [
      item.title,
      item.summary,
      item.contact,
      item.content,
      ...(item.matched_keywords || []),
    ]
      .join("\n")
      .toLowerCase();
    return haystack.includes(q);
  });
  renderHits(filtered);
}

function fillSettings(settings) {
  state.settings = settings;
  document.getElementById("enabled").checked = Boolean(settings._meta?.enabled);
  document.getElementById("pollInterval").value = settings.poll_interval_seconds ?? 60;
  document.getElementById("keywords").value = (settings.keywords || []).join("\n");
  document.getElementById("categories").value = (settings.categories || []).join("\n");
  document.getElementById("pushplusToken").value = settings.notifiers?.pushplus?.token || "";
  document.getElementById("pushplusTopic").value = settings.notifiers?.pushplus?.topic || "";
  document.getElementById("pageSize").value = settings.source?.body?.pageSize ?? 50;

  const cookieHeader = settings.source?.headers?.Cookie || "";
  const cookieValue = cookieHeader.includes("=") ? cookieHeader.split("=").slice(1).join("=") : cookieHeader;
  document.getElementById("sessionCookie").value = cookieValue;
}

function buildSettingsPayload() {
  const source = structuredClone(state.settings.source);
  const notifiers = structuredClone(state.settings.notifiers);
  const cookieValue = document.getElementById("sessionCookie").value.trim();
  source.headers.Cookie = cookieValue ? `ys7_ysxy_session=${cookieValue}` : "";
  source.body.pageSize = Number(document.getElementById("pageSize").value || 50);

  if (!notifiers.pushplus) {
    notifiers.pushplus = {};
  }
  notifiers.pushplus.token = document.getElementById("pushplusToken").value.trim();
  notifiers.pushplus.topic = document.getElementById("pushplusTopic").value.trim();
  notifiers.pushplus.enabled = Boolean(notifiers.pushplus.token);

  return {
    enabled: document.getElementById("enabled").checked,
    poll_interval_seconds: Number(document.getElementById("pollInterval").value || 60),
    keywords: linesToArray(document.getElementById("keywords").value),
    categories: linesToArray(document.getElementById("categories").value),
    source,
    notifiers,
  };
}

async function refreshAll() {
  const [settings, status, hits, runs] = await Promise.all([
    request("/api/settings"),
    request("/api/status"),
    request("/api/hits?limit=20"),
    request("/api/runs?limit=20"),
  ]);
  fillSettings(settings);
  renderStatus(status);
  state.hits = hits.items || [];
  filterHits();
  renderRuns(runs.items);
}

function startAutoRefresh() {
  if (state.refreshTimer) {
    clearInterval(state.refreshTimer);
  }
  state.refreshTimer = setInterval(() => {
    refreshAll().catch(() => {});
  }, 5000);
}

document.getElementById("refreshBtn").addEventListener("click", async () => {
  await refreshAll();
  showToast("状态已刷新。");
});

document.getElementById("runBtn").addEventListener("click", async () => {
  await request("/api/run-now", { method: "POST" });
  await refreshAll();
  showToast("已触发一轮检查。");
});

document.getElementById("testNotifyBtn").addEventListener("click", async () => {
  await request("/api/test-notify", {
    method: "POST",
    body: JSON.stringify({}),
  });
  showToast("测试通知已发送。");
});

document.getElementById("settingsForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = buildSettingsPayload();
  const saved = await request("/api/settings", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
  fillSettings(saved);
  await refreshAll();
  showToast("设置已保存。");
});

document.getElementById("hitSearch").addEventListener("input", () => {
  filterHits();
});

refreshAll()
  .then(() => startAutoRefresh())
  .catch((error) => {
    showToast(`初始化失败：${error.message}`, "error");
  });
