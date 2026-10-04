(() => {
  const properties = window.RADISON_PROPERTIES || [];
  const backdrop = document.getElementById("propertyModal");
  if (!backdrop) return;

  const titleEl = document.getElementById("modalTitle");
  const priceEl = document.getElementById("modalPrice");
  const priceMeterEl = document.getElementById("modalPriceMeter");
  const chipsEl = document.getElementById("modalChips");
  const specsEl = document.getElementById("modalSpecs");
  const imageEl = document.getElementById("modalImage");
  const countEl = document.getElementById("modalCount");
  const thumbsEl = document.getElementById("modalThumbs");
  const prevBtn = document.getElementById("modalPrev");
  const nextBtn = document.getElementById("modalNext");
  const closeBtn = document.getElementById("modalClose");

  let current = null;
  let index = 0;

  function render() {
    if (!current) return;
    const images = current.images || [];
    imageEl.src = images[index] || "";
    imageEl.alt = `${current.title} - تصویر ${index + 1}`;
    countEl.textContent = `${index + 1} / ${images.length || 0}`;
    titleEl.textContent = current.title;
    priceEl.textContent = current.price_text || "";
    priceMeterEl.textContent = current.price_per_meter_text || "";
    priceMeterEl.hidden = !current.price_per_meter_text;

    chipsEl.innerHTML = "";
    [current.property_type, current.deal_type].filter(Boolean).forEach((text) => {
      const chip = document.createElement("span");
      chip.className = "chip";
      chip.textContent = text;
      chipsEl.appendChild(chip);
    });

    specsEl.innerHTML = "";
    (current.specs || []).forEach((spec) => {
      const item = document.createElement("span");
      item.className = "spec";
      item.textContent = spec;
      specsEl.appendChild(item);
    });

    thumbsEl.innerHTML = "";
    images.forEach((src, i) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = i === index ? "active" : "";
      button.innerHTML = `<img src="${src}" alt="تصویر کوچک ${i + 1}">`;
      button.addEventListener("click", () => {
        index = i;
        render();
      });
      thumbsEl.appendChild(button);
    });

    const multi = images.length > 1;
    prevBtn.hidden = !multi;
    nextBtn.hidden = !multi;
  }

  function openProperty(id) {
    current = properties.find((item) => String(item.id) === String(id));
    if (!current) return;
    index = 0;
    render();
    backdrop.classList.add("open");
    document.body.style.overflow = "hidden";
  }

  function closeModal() {
    backdrop.classList.remove("open");
    document.body.style.overflow = "";
    current = null;
  }

  document.querySelectorAll("[data-property-id]").forEach((button) => {
    button.addEventListener("click", () => openProperty(button.dataset.propertyId));
  });

  closeBtn.addEventListener("click", closeModal);
  backdrop.addEventListener("click", (event) => {
    if (event.target === backdrop) closeModal();
  });

  prevBtn.addEventListener("click", () => {
    if (!current?.images?.length) return;
    index = (index - 1 + current.images.length) % current.images.length;
    render();
  });

  nextBtn.addEventListener("click", () => {
    if (!current?.images?.length) return;
    index = (index + 1) % current.images.length;
    render();
  });

  window.addEventListener("keydown", (event) => {
    if (!backdrop.classList.contains("open")) return;
    if (event.key === "Escape") closeModal();
    if (event.key === "ArrowLeft") nextBtn.click();
    if (event.key === "ArrowRight") prevBtn.click();
  });
})();
