const tbody = document.getElementById("complaints-body");
const searchInput = document.getElementById("search");
const severityFilter = document.getElementById("severity-filter");
const modal = document.getElementById("modal");
const modalContent = document.getElementById("modal-content");

async function loadStats() {
  const response = await fetch("/api/stats");
  const stats = await response.json();
  document.getElementById("stat-total").textContent = stats.total;
  document.getElementById("stat-pending").textContent = stats.pending;
  document.getElementById("stat-critical").textContent = stats.critical;
  document.getElementById("stat-resolved").textContent = stats.resolved;
}

async function loadComplaints() {
  const params = new URLSearchParams();
  if (searchInput.value) params.set("search", searchInput.value);
  if (severityFilter.value) params.set("severity", severityFilter.value);
  const response = await fetch(`/api/complaints?${params}`);
  const complaints = await response.json();
  tbody.innerHTML = complaints.map((item) => `
    <tr>
      <td>#${item.id}</td>
      <td>${escapeHtml(item.citizen_name)}</td>
      <td>${escapeHtml(item.location)}</td>
      <td><span class="severity severity-${item.severity}">${item.severity}</span></td>
      <td><strong>${item.priority_score}</strong>/100</td>
      <td><span class="status">${escapeHtml(item.status)}</span></td>
      <td><button class="view-button" data-id="${item.id}">View</button></td>
    </tr>
  `).join("") || '<tr><td colspan="7">No complaints found.</td></tr>';
}

function escapeHtml(value) {
  const element = document.createElement("span");
  element.textContent = value ?? "";
  return element.innerHTML;
}

tbody.addEventListener("click", async (event) => {
  const button = event.target.closest(".view-button");
  if (!button) return;
  const response = await fetch(`/api/complaints/${button.dataset.id}`);
  const item = await response.json();
  modalContent.innerHTML = `
    <h2>Complaint #${item.id}</h2>
    <div class="detail-grid">
      ${item.image_url ? `<img src="${item.image_url}" alt="Damage">` : '<div>No image</div>'}
      <div>
        <p><strong>Citizen:</strong> ${escapeHtml(item.citizen_name)}</p>
        <p><strong>Location:</strong> ${escapeHtml(item.location)}</p>
        <p><strong>Damage:</strong> ${escapeHtml(item.damage_type)}</p>
        <p><strong>Severity:</strong> ${item.severity}</p>
        <p><strong>Priority:</strong> ${item.priority_score}/100</p>
        <p><strong>AI confidence:</strong> ${Math.round(item.ai_confidence * 100)}%</p>
      </div>
    </div>
    <p><strong>Description:</strong> ${escapeHtml(item.description || "None")}</p>
    <p><strong>Hazard:</strong> ${escapeHtml(item.hazard_type || "Not specified")}</p>
    <p><strong>Road:</strong> ${escapeHtml(item.road_type || "Not specified")}</p>
    <p><strong>Traffic impact:</strong> ${escapeHtml(item.traffic_impact || "Not specified")}</p>
    <p><strong>Safety risk:</strong> ${escapeHtml(item.safety_risk || "Not specified")}</p>
    <p><strong>Observed at:</strong> ${escapeHtml(item.observed_at || "Not specified")}</p>
    <p><strong>Affected area:</strong> ${escapeHtml(item.affected_area || "Not specified")}</p>
    <p><strong>Analysis:</strong> ${escapeHtml(item.analysis_notes || "Not available")}</p>
    ${item.duplicate_of ? `<p><strong>Possible duplicate of:</strong> #${item.duplicate_of}</p>` : ""}
    <label>Status
      <select class="status-select" id="status-select">
        ${["Submitted", "Assigned", "In Progress", "Resolved", "Rejected"].map(status =>
          `<option ${status === item.status ? "selected" : ""}>${status}</option>`
        ).join("")}
      </select>
    </label>
  `;
  modal.classList.add("open");
  modal.setAttribute("aria-hidden", "false");
  document.getElementById("status-select").addEventListener("change", async (statusEvent) => {
    await fetch(`/api/complaints/${item.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: statusEvent.target.value }),
    });
    loadStats();
    loadComplaints();
  });
});

document.getElementById("close-modal").addEventListener("click", closeModal);
modal.addEventListener("click", (event) => {
  if (event.target === modal) closeModal();
});
function closeModal() {
  modal.classList.remove("open");
  modal.setAttribute("aria-hidden", "true");
}

let searchTimer;
searchInput.addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(loadComplaints, 250);
});
severityFilter.addEventListener("change", loadComplaints);
loadStats();
loadComplaints();
