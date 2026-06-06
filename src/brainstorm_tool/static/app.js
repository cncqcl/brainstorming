const app = document.querySelector("#app");
const overviewTemplate = document.querySelector("#overviewTemplate");
const detailTemplate = document.querySelector("#detailTemplate");
const refreshButton = document.querySelector("#refreshButton");
const historyDialog = document.querySelector("#historyDialog");
const dialogClose = document.querySelector("#dialogClose");
const dialogMeta = document.querySelector("#dialogMeta");
const dialogTitle = document.querySelector("#dialogTitle");
const dialogContent = document.querySelector("#dialogContent");

const statuses = [
  "seed",
  "exploring",
  "active",
  "paused",
  "researched",
  "shipped",
  "archived",
];

let editing = false;
let autosaveTimer = null;
let currentIdea = null;

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (response.status === 204) {
    return {};
  }
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.message || "Request failed");
  }
  return data;
}

function statusLabel(value) {
  return value.replace("-", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function routeIdeaId() {
  const match = window.location.pathname.match(/^\/ideas\/([a-f0-9]+)/);
  return match ? match[1] : null;
}

function setDraftState(message) {
  const node = document.querySelector("#draftState");
  if (node) {
    node.textContent = message;
  }
}

function renderEmpty(node, text) {
  node.innerHTML = `<div class="empty">${text}</div>`;
}

async function renderOverview() {
  stopEditing();
  app.replaceChildren(overviewTemplate.content.cloneNode(true));
  const [ideasData, graph] = await Promise.all([
    api("/api/ideas"),
    api("/api/graph"),
  ]);
  const ideaList = document.querySelector("#ideaList");
  document.querySelector("#ideaCount").textContent = ideasData.ideas.length;

  if (ideasData.ideas.length === 0) {
    renderEmpty(ideaList, "No ideas recorded.");
  } else {
    ideaList.replaceChildren(
      ...ideasData.ideas.map((idea) => {
        const row = document.createElement("a");
        row.className = "idea-row";
        row.href = `/ideas/${idea.idea_id}`;
        row.innerHTML = `
          <div>
            <div class="idea-title">${escapeHtml(idea.title)}</div>
            <div class="idea-brief">${escapeHtml(idea.brief)}</div>
            <div class="meta-line">
              <span class="status-pill">${statusLabel(idea.status)}</span>
              <span class="meta">Version ${idea.version_number}</span>
            </div>
          </div>
          <span class="version-pill">v${idea.version_number}</span>
        `;
        return row;
      }),
    );
  }

  drawGraph(graph);
  document.querySelector("#newIdeaForm").addEventListener("submit", createIdea);
}

async function createIdea(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const data = Object.fromEntries(new FormData(form));
  const idea = await api("/api/ideas", {
    method: "POST",
    body: JSON.stringify(data),
  });
  history.pushState({}, "", `/ideas/${idea.idea_id}`);
  await renderDetail(idea.idea_id);
}

function drawGraph(graph) {
  const svg = document.querySelector("#graphSvg");
  svg.replaceChildren();
  const width = svg.clientWidth || 420;
  const height = Math.max(svg.clientHeight || 360, 320);
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  if (graph.nodes.length === 0) {
    const text = svgNode("text", {
      x: width / 2,
      y: height / 2,
      "text-anchor": "middle",
      fill: "#6f6a60",
    });
    text.textContent = "No graph data";
    svg.append(text);
    return;
  }

  const centerX = width / 2;
  const centerY = height / 2;
  const radius = Math.min(width, height) * 0.34;
  const positions = new Map();

  graph.nodes.forEach((node, index) => {
    const angle = (Math.PI * 2 * index) / graph.nodes.length - Math.PI / 2;
    positions.set(node.idea_id, {
      x: centerX + Math.cos(angle) * radius,
      y: centerY + Math.sin(angle) * radius,
    });
  });

  graph.edges.forEach((edge) => {
    const source = positions.get(edge.source_id);
    const target = positions.get(edge.target_id);
    if (!source || !target) {
      return;
    }
    const line = svgNode("line", {
      x1: source.x,
      y1: source.y,
      x2: target.x,
      y2: target.y,
      stroke: "#315f78",
      "stroke-width": "2",
    });
    svg.append(line);
  });

  graph.nodes.forEach((node) => {
    const point = positions.get(node.idea_id);
    const group = svgNode("g", {});
    const circle = svgNode("circle", {
      cx: point.x,
      cy: point.y,
      r: 24,
      fill: statusColor(node.status),
      stroke: "#20201d",
      "stroke-width": "1",
    });
    const text = svgNode("text", {
      x: point.x,
      y: point.y + 44,
      "text-anchor": "middle",
      fill: "#20201d",
      "font-size": "12",
      "font-weight": "700",
    });
    text.textContent = node.title.slice(0, 18);
    group.append(circle, text);
    svg.append(group);
  });
}

function statusColor(status) {
  return {
    seed: "#ede4d5",
    exploring: "#d7c57f",
    active: "#9ab08f",
    paused: "#c9c1b4",
    researched: "#9ab7c8",
    shipped: "#456b50",
    archived: "#bba5a0",
  }[status] || "#ede4d5";
}

async function renderDetail(ideaId) {
  app.replaceChildren(detailTemplate.content.cloneNode(true));
  currentIdea = await api(`/api/ideas/${ideaId}`);
  editing = false;

  document.querySelector("#detailStatus").textContent = statusLabel(currentIdea.status);
  document.querySelector("#detailTitle").textContent = currentIdea.title;
  document.querySelector("#detailBrief").textContent = currentIdea.brief;
  document.querySelector(
    "#detailVersion",
  ).textContent = `v${currentIdea.current_version.version_number}`;
  document.querySelector("#ideaContent").value = currentIdea.current_version.content;

  const statusSelect = document.querySelector("#statusSelect");
  statusSelect.replaceChildren(
    ...statuses.map((status) => {
      const option = document.createElement("option");
      option.value = status;
      option.textContent = statusLabel(status);
      option.selected = status === currentIdea.status;
      return option;
    }),
  );
  statusSelect.addEventListener("change", updateStatus);

  document.querySelector("#editButton").addEventListener("click", startEditing);
  document.querySelector("#saveButton").addEventListener("click", saveVersion);
  document.querySelector("#closeEditButton").addEventListener("click", closeEditing);
  document.querySelector("#commentForm").addEventListener("submit", addComment);
  document
    .querySelector("#attachmentForm")
    .addEventListener("submit", addAttachment);
  document.querySelector("#annotationForm").addEventListener("submit", addAnnotation);
  document.querySelector("#agentForm").addEventListener("submit", addAgentNote);

  renderLists(currentIdea);
}

function renderLists(idea) {
  renderStack("#commentsList", idea.comments, (item) => item.body);
  renderStack("#attachmentsList", idea.attachments, (item) => {
    const topic = item.topic ? `[${item.topic}] ` : "";
    return `${topic}${item.label}: ${item.uri}`;
  });
  renderStack("#annotationsList", idea.annotations, (item) => item.body);
  renderStack("#agentNotesList", idea.agent_notes, (item) => {
    return `${item.topic}: ${item.recommendation}`;
  });
  renderHistory(idea.history);
  renderDrafts(idea.drafts);
}

function renderStack(selector, items, labeler) {
  const node = document.querySelector(selector);
  if (items.length === 0) {
    renderEmpty(node, "Empty");
    return;
  }
  node.replaceChildren(
    ...items.map((item) => {
      const row = document.createElement("div");
      row.className = "note-row";
      const topic = item.topic ? `[${item.topic}] ` : "";
      row.textContent = selector === "#commentsList" ? `${topic}${labeler(item)}` : labeler(item);
      return row;
    }),
  );
}

function renderHistory(history) {
  const node = document.querySelector("#historyList");
  node.replaceChildren(
    ...history.map((version) => {
      const row = document.createElement("button");
      row.type = "button";
      row.className = "history-row";
      row.innerHTML = `
        <strong>v${version.version_number}</strong>
        <span>${escapeHtml(version.one_line_summary)}</span>
      `;
      row.addEventListener("click", () => openVersion(version));
      return row;
    }),
  );
}

function renderDrafts(drafts) {
  const node = document.querySelector("#draftList");
  if (drafts.length === 0) {
    renderEmpty(node, "No cached drafts.");
    return;
  }
  node.replaceChildren(
    ...drafts.map((draft) => {
      const row = document.createElement("button");
      row.type = "button";
      row.className = "history-row";
      row.textContent = new Date(draft.created_at).toLocaleString();
      row.addEventListener("click", () => {
        document.querySelector("#ideaContent").value = draft.content;
        startEditing();
      });
      return row;
    }),
  );
}

function startEditing() {
  editing = true;
  document.querySelector("#ideaContent").readOnly = false;
  document.querySelector("#saveButton").disabled = false;
  document.querySelector("#closeEditButton").disabled = false;
  setDraftState("Editing");
  if (!autosaveTimer) {
    autosaveTimer = window.setInterval(cacheDraft, 10 * 60 * 1000);
  }
}

async function cacheDraft() {
  if (!editing || !currentIdea) {
    return;
  }
  const content = document.querySelector("#ideaContent").value;
  await api(`/api/ideas/${currentIdea.idea_id}/drafts`, {
    method: "POST",
    body: JSON.stringify({ content }),
  });
  setDraftState(`Draft cached at ${new Date().toLocaleTimeString()}`);
}

function stopEditing() {
  editing = false;
  if (autosaveTimer) {
    window.clearInterval(autosaveTimer);
    autosaveTimer = null;
  }
}

async function closeEditing() {
  await api(`/api/ideas/${currentIdea.idea_id}/close-editing`, { method: "POST" });
  stopEditing();
  await renderDetail(currentIdea.idea_id);
}

async function saveVersion() {
  await api(`/api/ideas/${currentIdea.idea_id}/versions`, {
    method: "POST",
    body: JSON.stringify({
      content: document.querySelector("#ideaContent").value,
    }),
  });
  stopEditing();
  await renderDetail(currentIdea.idea_id);
}

async function updateStatus(event) {
  await api(`/api/ideas/${currentIdea.idea_id}/status`, {
    method: "POST",
    body: JSON.stringify({ status: event.currentTarget.value }),
  });
  await renderDetail(currentIdea.idea_id);
}

async function addComment(event) {
  event.preventDefault();
  const form = event.currentTarget;
  await api(`/api/ideas/${currentIdea.idea_id}/comments`, {
    method: "POST",
    body: JSON.stringify(Object.fromEntries(new FormData(form))),
  });
  await renderDetail(currentIdea.idea_id);
}

async function addAttachment(event) {
  event.preventDefault();
  const form = event.currentTarget;
  await api(`/api/ideas/${currentIdea.idea_id}/attachments`, {
    method: "POST",
    body: JSON.stringify(Object.fromEntries(new FormData(form))),
  });
  await renderDetail(currentIdea.idea_id);
}

async function addAnnotation(event) {
  event.preventDefault();
  const form = event.currentTarget;
  await api(`/api/ideas/${currentIdea.idea_id}/annotations`, {
    method: "POST",
    body: JSON.stringify(Object.fromEntries(new FormData(form))),
  });
  await renderDetail(currentIdea.idea_id);
}

async function addAgentNote(event) {
  event.preventDefault();
  const form = event.currentTarget;
  await api(`/api/ideas/${currentIdea.idea_id}/agent-notes`, {
    method: "POST",
    body: JSON.stringify(Object.fromEntries(new FormData(form))),
  });
  await renderDetail(currentIdea.idea_id);
}

function openVersion(version) {
  dialogMeta.textContent = `Version ${version.version_number}`;
  dialogTitle.textContent = version.one_line_summary;
  dialogContent.textContent = version.content;
  historyDialog.showModal();
}

function svgNode(name, attrs) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", name);
  Object.entries(attrs).forEach(([key, value]) => {
    node.setAttribute(key, String(value));
  });
  return node;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

async function renderRoute() {
  const ideaId = routeIdeaId();
  if (ideaId) {
    await renderDetail(ideaId);
  } else {
    await renderOverview();
  }
}

window.addEventListener("popstate", renderRoute);
refreshButton.addEventListener("click", renderRoute);
dialogClose.addEventListener("click", () => historyDialog.close());
document.addEventListener("click", (event) => {
  const link = event.target.closest("a");
  if (!link || link.origin !== window.location.origin) {
    return;
  }
  event.preventDefault();
  history.pushState({}, "", link.href);
  renderRoute();
});

renderRoute().catch((error) => {
  app.innerHTML = `<div class="empty">${escapeHtml(error.message)}</div>`;
});
