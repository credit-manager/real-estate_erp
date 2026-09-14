/* HR Performance Reviews */
let reviewsData = [];
let reviewEmployees = [];

async function loadReviews() {
  try {
    const [reviews, emps] = await Promise.all([
      api.get("/api/hr/reviews"),
      api.get("/api/hr/employees"),
    ]);
    reviewsData = reviews;
    reviewEmployees = emps;
    document.getElementById("review-employee").innerHTML =
      `<option value="">${t("common.select")}</option>` +
      emps.map((e) => `<option value="${e.id}">${escapeHtml(e.full_name)}</option>`).join("");
    renderReviews();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

function ratingStars(rating) {
  const n = Math.round(rating || 0);
  return "★".repeat(Math.max(0, Math.min(5, n))) + `<small class="muted"> ${(rating || 0).toFixed(1)}</small>`;
}

function renderReviews() {
  const tbody = document.getElementById("reviews-table");
  document.getElementById("reviews-count").textContent = `(${reviewsData.length})`;
  document.getElementById("reviews-empty").style.display = reviewsData.length ? "none" : "";
  tbody.innerHTML = reviewsData.map((r) => `
    <tr>
      <td><b>${escapeHtml(r.employee_name || "—")}</b></td>
      <td>${formatDate(r.review_date)}</td>
      <td>${escapeHtml(r.period || "—")}</td>
      <td style="color:var(--amber);">${ratingStars(r.rating)}</td>
      <td>${escapeHtml(r.reviewer || "—")}</td>
      <td>${hrStatusBadge(r.status)}</td>
      <td>${hrActionButtons("Review", r, "openReviewModal", "deleteReview")}</td>
    </tr>`).join("");
}

function openReviewModal(review) {
  document.getElementById("review-modal-title").textContent = review ? t("hr.editReview") : t("hr.addReview");
  document.getElementById("review-id").value = review ? review.id : "";
  document.getElementById("review-employee").value = review ? (review.employee_id || "") : "";
  document.getElementById("review-date").value = review ? (review.review_date || "") : "";
  document.getElementById("review-period").value = review ? (review.period || "") : "";
  document.getElementById("review-rating").value = review ? (review.rating || "") : "";
  document.getElementById("review-reviewer").value = review ? (review.reviewer || "") : "";
  document.getElementById("review-strengths").value = review ? (review.strengths || "") : "";
  document.getElementById("review-weaknesses").value = review ? (review.weaknesses || "") : "";
  document.getElementById("review-goals").value = review ? (review.goals || "") : "";
  document.getElementById("review-status").value = review ? (review.status || "completed") : "completed";
  document.getElementById("review-modal").classList.add("active");
}

function closeReviewModal() {
  document.getElementById("review-modal").classList.remove("active");
}

async function saveReview() {
  const id = document.getElementById("review-id").value;
  const body = {
    employee_id: document.getElementById("review-employee").value || null,
    review_date: document.getElementById("review-date").value || null,
    period: document.getElementById("review-period").value.trim(),
    rating: parseFloat(document.getElementById("review-rating").value) || 0,
    reviewer: document.getElementById("review-reviewer").value.trim(),
    strengths: document.getElementById("review-strengths").value.trim(),
    weaknesses: document.getElementById("review-weaknesses").value.trim(),
    goals: document.getElementById("review-goals").value.trim(),
    status: document.getElementById("review-status").value,
  };
  if (!body.employee_id) { showToast(t("hr.employeeRequired"), "warning"); return; }
  try {
    if (id) await api.put(`/api/hr/reviews/${id}`, body);
    else await api.post("/api/hr/reviews", body);
    showToast(t("hr.saved"));
    closeReviewModal();
    loadReviews();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

async function deleteReview(id) {
  if (!confirm(t("hr.confirmDelete"))) return;
  try {
    await api.delete(`/api/hr/reviews/${id}`);
    showToast(t("hr.deleted"));
    loadReviews();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

window.openReviewModal = openReviewModal;
window.closeReviewModal = closeReviewModal;
window.saveReview = saveReview;
window.deleteReview = deleteReview;

loadReviews();
