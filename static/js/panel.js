(() => {
  function reloadSoon(delay = 700) {
    window.setTimeout(() => {
      const url = new URL(window.location.href);
      url.searchParams.set("t", String(Date.now()));
      window.location.replace(url.toString());
    }, delay);
  }

  async function submitExtract(form, statusEl, submitBtn, loadingText) {
    statusEl.hidden = false;
    statusEl.className = "status";
    statusEl.textContent = loadingText;
    if (submitBtn) submitBtn.disabled = true;

    const formData = new FormData(form);
    try {
      const response = await fetch(form.action, {
        method: "POST",
        body: formData,
        headers: { "X-Requested-With": "XMLHttpRequest" },
      });
      const data = await response.json();
      if (!response.ok || !data.ok) {
        throw new Error(data.error || "استخراج ناموفق بود");
      }
      statusEl.className = "status ok";
      const count = data.property.images_count || 0;
      const actionText = data.replaced ? "به‌روزرسانی" : "بارگذاری";
      statusEl.textContent =
        count > 0
          ? `ملک «${data.property.title}» با ${count} تصویر ${actionText} شد.`
          : `ملک «${data.property.title}» بدون تصویر ${actionText} شد.`;
      reloadSoon();
    } catch (error) {
      statusEl.className = "status error";
      statusEl.textContent = error.message || "خطا در استخراج";
      if (submitBtn) submitBtn.disabled = false;
    }
  }

  const form = document.getElementById("extractForm");
  const statusEl = document.getElementById("extractStatus");
  const submitBtn = document.getElementById("extractBtn");
  if (form && statusEl && submitBtn) {
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      submitExtract(form, statusEl, submitBtn, "در حال استخراج اطلاعات و تصاویر...");
    });
  }

  document.querySelectorAll("form[data-reextract]").forEach((reextractForm) => {
    const status =
      reextractForm.querySelector(".reextract-status") ||
      reextractForm.parentElement.querySelector(".reextract-status");
    const button = reextractForm.querySelector('button[type="submit"]');
    reextractForm.addEventListener("submit", (event) => {
      event.preventDefault();
      if (!status) return;
      submitExtract(
        reextractForm,
        status,
        button,
        "در حال استخراج مجدد و جایگزینی این ملک..."
      );
    });
  });
})();
