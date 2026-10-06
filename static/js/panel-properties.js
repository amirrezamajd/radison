(() => {
  const backdrop = document.getElementById("panelEditModal");
  if (!backdrop) return;

  const items = window.PANEL_PROPERTIES || [];
  const titleEl = document.getElementById("editModalTitle");
  const subEl = document.getElementById("editModalSub");
  const coverEl = document.getElementById("editModalCover");
  const closeBtn = document.getElementById("editModalClose");
  const tourForm = document.getElementById("editTourForm");
  const tourSelect = document.getElementById("editTourSelect");
  const reextractForm = document.getElementById("editReextractForm");
  const crmUrl = document.getElementById("editCrmUrl");
  const djangoLink = document.getElementById("editDjangoLink");
  const deleteForm = document.getElementById("editDeleteForm");
  const pinForm = document.getElementById("editPinForm");
  const pinStatus = document.getElementById("editPinStatus");
  const pinBtn = document.getElementById("editPinBtn");
  const unpinBtn = document.getElementById("editUnpinBtn");
  const pageLink = document.getElementById("editPageLink");
  let current = null;

  function openEdit(id) {
    current = items.find((item) => String(item.id) === String(id));
    if (!current) return;

    titleEl.textContent = current.title || "ویرایش ملک";
    subEl.textContent = `${current.price_text || "—"} · ${current.images_count} تصویر · ${current.view_count} بازدید`;

    if (current.cover) {
      coverEl.innerHTML = `<img src="${current.cover}" alt="">`;
    } else {
      coverEl.innerHTML = `<div class="panel-property-empty">بدون تصویر</div>`;
    }

    tourForm.action = current.assign_url;
    tourSelect.value = current.virtual_tour_id ? String(current.virtual_tour_id) : "";
    reextractForm.action = current.reextract_url;
    crmUrl.value = current.source_url || "";
    djangoLink.href = current.django_url;
    deleteForm.action = current.delete_url;
    pageLink.href = current.page_url;

    pinForm.action = current.pin_url;
    pinBtn.hidden = current.pinned;
    unpinBtn.hidden = !current.pinned;
    pinStatus.textContent = current.pinned
      ? "این ملک الان جزو ملک‌های ابتدای صفحه اصلی است."
      : "این ملک به ترتیب عادی (جدید به قدیم) نمایش داده می‌شود.";

    backdrop.hidden = false;
    document.body.style.overflow = "hidden";
  }

  function closeEdit() {
    backdrop.hidden = true;
    document.body.style.overflow = "";
    current = null;
  }

  document.querySelectorAll("[data-open-edit]").forEach((button) => {
    button.addEventListener("click", () => openEdit(button.dataset.openEdit));
  });

  closeBtn.addEventListener("click", closeEdit);
  backdrop.addEventListener("click", (event) => {
    if (event.target === backdrop) closeEdit();
  });

  window.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !backdrop.hidden) closeEdit();
  });
})();
