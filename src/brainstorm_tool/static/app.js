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
  const [ideasData, graph, draftsData] = await Promise.all([
    api("/api/ideas"),
    api("/api/graph"),
    api("/api/drafts"),
  ]);
  const ideaList = document.querySelector("#ideaList");
  document.querySelector("#ideaCount").textContent = ideasData.ideas.length;
  document.querySelector("#draftCount").textContent = draftsData.drafts.length;

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
  renderDraftInbox(draftsData.drafts);
  document.querySelector("#quickCaptureForm").addEventListener("submit", captureDraft);
}

async function captureDraft(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const data = {
    ...Object.fromEntries(new FormData(form)),
    source: "dashboard",
  };
  await api("/api/drafts", {
    method: "POST",
    body: JSON.stringify(data),
  });
  form.reset();
  await renderOverview();
}

function renderDraftInbox(drafts) {
  const node = document.querySelector("#draftInbox");
  if (drafts.length === 0) {
    renderEmpty(node, "No captured drafts.");
    return;
  }
  node.replaceChildren(
    ...drafts.map((draft) => {
      const row = document.createElement("article");
      row.className = "draft-row";
      row.innerHTML = `
        <div>
          <div class="draft-title">Draft ${draft.draft_id}</div>
          <div class="draft-message">${escapeHtml(draft.raw_message)}</div>
          <div class="meta-line">
            <span class="status-pill">${statusLabel(draft.status)}</span>
            <span class="meta">${escapeHtml(draft.source)}</span>
          </div>
        </div>
        <button class="ghost-button" type="button">Refine</button>
      `;
      row.querySelector("button").addEventListener("click", () => {
        showRefinementPrompt(draft.draft_id);
      });
      return row;
    }),
  );
}

function bindPromptCopy() {
  const copyButton = document.querySelector("#copyPromptButton");
  const prompt = document.querySelector("#refinePrompt");
  if (!copyButton || !prompt) {
    return;
  }
  copyButton.addEventListener("click", async () => {
    await copyText(prompt);
    copyButton.textContent = "Copied";
    window.setTimeout(() => {
      copyButton.textContent = "Copy";
    }, 1400);
  });
}

async function copyText(prompt) {
  if (navigator.clipboard) {
    await navigator.clipboard.writeText(prompt.value);
    return;
  }
  prompt.focus();
  prompt.select();
  document.execCommand("copy");
}

async function showRefinementPrompt(draftId) {
  const result = await api(`/api/drafts/${draftId}/refine-prompt`, {
    method: "POST",
  });
  const panel = document.querySelector("#refinePromptPanel");
  const prompt = document.querySelector("#refinePrompt");
  panel.hidden = false;
  prompt.value = result.prompt;
  bindPromptCopy();
  prompt.focus();
  prompt.select();
  await renderOverview();
  document.querySelector("#refinePromptPanel").hidden = false;
  document.querySelector("#refinePrompt").value = result.prompt;
  bindPromptCopy();
}

function drawGraph(graph) {
  const svg = document.querySelector("#graphSvg");
  svg.replaceChildren();
  const width = svg.clientWidth || 420;
  const height = Math.max(svg.clientHeight || 560, 480);
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  const defs = svgNode("defs", {});
  const glow = svgNode("filter", {
    id: "nodeGlow",
    x: "-30%",
    y: "-30%",
    width: "160%",
    height: "160%",
  });
  glow.append(
    svgNode("feDropShadow", {
      dx: "0",
      dy: "8",
      stdDeviation: "6",
      "flood-color": "#000000",
      "flood-opacity": "0.28",
    }),
  );
  const marker = svgNode("marker", {
    id: "arrow",
    viewBox: "0 0 10 10",
    refX: "8",
    refY: "5",
    markerWidth: "6",
    markerHeight: "6",
    orient: "auto-start-reverse",
  });
  marker.append(svgNode("path", { d: "M 0 0 L 10 5 L 0 10 z", fill: "#62b6cb" }));
  defs.append(glow, marker);
  svg.append(defs);

  if (graph.nodes.length === 0) {
    const text = svgNode("text", {
      x: width / 2,
      y: height / 2,
      "text-anchor": "middle",
      fill: "#a7c5cd",
      "font-size": "14",
      "font-weight": "700",
    });
    text.textContent = "No graph data";
    svg.append(text);
    return;
  }

  const centerX = width / 2;
  const centerY = height / 2 - 8;
  const radiusX = Math.max(96, Math.min(width * 0.36, 260));
  const radiusY = Math.max(92, Math.min(height * 0.31, 210));
  const positions = new Map();

  graph.nodes.forEach((node, index) => {
    const angle = (Math.PI * 2 * index) / graph.nodes.length - Math.PI / 2;
    positions.set(node.idea_id, {
      x: centerX + Math.cos(angle) * radiusX,
      y: centerY + Math.sin(angle) * radiusY,
    });
  });

  graph.edges.forEach((edge) => {
    const source = positions.get(edge.source_id);
    const target = positions.get(edge.target_id);
    if (!source || !target) {
      return;
    }
    const curveX = (source.x + target.x) / 2 + (target.y - source.y) * 0.08;
    const curveY = (source.y + target.y) / 2 - (target.x - source.x) * 0.08;
    const path = svgNode("path", {
      d: `M ${source.x} ${source.y} Q ${curveX} ${curveY} ${target.x} ${target.y}`,
      fill: "none",
      stroke: "#62b6cb",
      "stroke-width": "2",
      "stroke-opacity": "0.72",
      "marker-end": "url(#arrow)",
    });
    svg.append(path);
    if (edge.label) {
      const label = svgNode("text", {
        x: curveX,
        y: curveY - 6,
        "text-anchor": "middle",
        fill: "#b8dbe3",
        "font-size": "11",
        "font-weight": "700",
      });
      label.textContent = edge.label.slice(0, 18);
      svg.append(label);
    }
  });

  graph.nodes.forEach((node) => {
    const point = positions.get(node.idea_id);
    const group = svgNode("g", {});
    const halo = svgNode("circle", {
      cx: point.x,
      cy: point.y,
      r: 35,
      fill: statusColor(node.status),
      opacity: "0.18",
    });
    const circle = svgNode("circle", {
      cx: point.x,
      cy: point.y,
      r: 25,
      fill: statusColor(node.status),
      stroke: "rgb(255 255 255 / 72%)",
      "stroke-width": "2",
      filter: "url(#nodeGlow)",
    });
    const version = svgNode("text", {
      x: point.x,
      y: point.y + 5,
      "text-anchor": "middle",
      fill: "#ffffff",
      "font-size": "13",
      "font-weight": "800",
    });
    version.textContent = `v${node.version_number}`;
    const text = svgNode("text", {
      x: point.x,
      y: point.y + 50,
      "text-anchor": "middle",
      fill: "#f3fbfc",
      "font-size": "12",
      "font-weight": "700",
    });
    text.textContent = trimGraphLabel(node.title);
    const status = svgNode("text", {
      x: point.x,
      y: point.y + 66,
      "text-anchor": "middle",
      fill: "#99b9c2",
      "font-size": "10",
      "font-weight": "700",
    });
    status.textContent = statusLabel(node.status);
    group.append(halo, circle, version, text, status);
    svg.append(group);
  });
}

function trimGraphLabel(value) {
  return value.length > 20 ? `${value.slice(0, 19)}...` : value;
}

function statusColor(status) {
  return {
    seed: "#9aa4ac",
    exploring: "#b7791f",
    active: "#2f6f5f",
    paused: "#747d83",
    researched: "#246a8f",
    shipped: "#1f8a70",
    archived: "#8c5f5b",
  }[status] || "#9aa4ac";
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
