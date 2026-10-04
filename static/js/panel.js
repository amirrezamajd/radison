(() => {
  const form = document.getElementById("extractForm");
  const statusEl = document.getElementById("extractStatus");
  const submitBtn = document.getElementById("extractBtn");
  if (!form) return;

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    statusEl.className = "status";
    statusEl.textContent = "در حال استخراج اطلاعات و تصاویر...";
    submitBtn.disabled = true;

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
      statusEl.textContent = `ملک «${data.property.title}» با ${data.property.images_count} تصویر بارگذاری شد.`;
      window.setTimeout(() => window.location.reload(), 900);
    } catch (error) {
      statusEl.className = "status error";
      statusEl.textContent = error.message || "خطا در استخراج";
      submitBtn.disabled = false;
    }
  });
})();
