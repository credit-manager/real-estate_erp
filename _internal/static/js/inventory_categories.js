let categoriesData = [];

async function loadCategories() {
  try {
    const res = await api.get("/api/inventory/categories");
    categoriesData = res.categories || [];
    renderCategories();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

function openCategoryModal(cat) {
  document.getElementById("cat-id").value = cat ? cat.id : "";
  document.getElementById("cat-name").value = cat ? cat.name : "";
  document.getElementById("cat-description").value = cat ? (cat.description || "") : "";
  document.getElementById("cat-active").checked = cat ? cat.is_active : true;
  document.getElementById("category-modal-title").textContent = cat ? invT("inventory.editCategory") : invT("inventory.addCategory");
  document.getElementById("category-modal").classList.add("active");
}
window.openCategoryModal = openCategoryModal;

function closeCategoryModal() {
  document.getElementById("category-modal").classList.remove("active");
}
window.closeCategoryModal = closeCategoryModal;

function editCategory(cat) { openCategoryModal(cat); }
window.editCategory = editCategory;

function renderCategories() {
  const tbody = document.getElementById("categories-table");
  document.getElementById("categories-count").textContent = `(${categoriesData.length})`;
  document.getElementById("categories-empty").style.display = categoriesData.length ? "none" : "";
  tbody.innerHTML = categoriesData.map((c) => `
    <tr>
      <td><b>${escapeHtml(c.name)}</b></td>
      <td>${escapeHtml(c.description || "—")}</td>
      <td>${c.items_count || 0}</td>
      <td>${invStatusBadge(c.is_active)}</td>
      <td>
        ${invCan("edit") ? `<button class="icon-btn" title="${invT("common.edit")}" onclick='editCategory(${JSON.stringify(c)})'>✏️</button>` : ""}
        ${invCan("delete") ? `<button class="icon-btn" title="${invT("common.delete")}" onclick="deleteCategory(${c.id})">🗑️</button>` : ""}
      </td>
    </tr>
  `).join("");
}
window.renderCategories = renderCategories;

async function saveCategory() {
  const id = document.getElementById("cat-id").value;
  const payload = {
    name: document.getElementById("cat-name").value.trim(),
    description: document.getElementById("cat-description").value.trim(),
    is_active: document.getElementById("cat-active").checked,
  };
  if (!payload.name) {
    showToast(invT("inventory.noCategories"), "error");
    return;
  }
  try {
    if (id) {
      await api.request(`/api/inventory/categories/${id}`, "PUT", payload);
    } else {
      await api.request("/api/inventory/categories", "POST", payload);
    }
    showToast(t("common.saved"));
    closeCategoryModal();
    loadCategories();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}
window.saveCategory = saveCategory;

async function deleteCategory(id) {
  if (!confirm(t("inventory.confirmDelete"))) return;
  try {
    await api.request(`/api/inventory/categories/${id}`, "DELETE");
    showToast(t("common.deleted"));
    loadCategories();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}
window.deleteCategory = deleteCategory;

loadCategories();
