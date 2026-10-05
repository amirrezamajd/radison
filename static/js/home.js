(() => {
  const properties = window.RADISON_PROPERTIES || [];
  const backdrop = document.getElementById("propertyModal");
  if (!backdrop) return;

  const titleEl = document.getElementById("modalTitle");
  const priceEl = document.getElementById("modalPrice");
  const priceMeterEl = document.getElementById("modalPriceMeter");
  const chipsEl = document.getElementById("modalChips");
  const specsEl = document.getElementById("modalSpecs");
  const tourWrap = document.getElementById("modalTourWrap");
  const tourLink = document.getElementById("modalTourLink");
  const galleryEl = document.getElementById("modalGallery");
  const stageEl = document.getElementById("zoomStage");
  const imageEl = document.getElementById("modalImage");
  const countEl = document.getElementById("modalCount");
  const thumbsEl = document.getElementById("modalThumbs");
  const prevBtn = document.getElementById("modalPrev");
  const nextBtn = document.getElementById("modalNext");
  const closeBtn = document.getElementById("modalClose");
  const zoomInBtn = document.getElementById("zoomInBtn");
  const zoomOutBtn = document.getElementById("zoomOutBtn");
  const zoomResetBtn = document.getElementById("zoomResetBtn");

  const MIN_ZOOM = 1;
  const MAX_ZOOM = 4;
  const ZOOM_STEP = 0.35;

  let current = null;
  let index = 0;
  let scale = 1;
  let offsetX = 0;
  let offsetY = 0;
  let dragging = false;
  let dragStartX = 0;
  let dragStartY = 0;
  let originX = 0;
  let originY = 0;
  let pinchStartDistance = 0;
  let pinchStartScale = 1;

  function clamp(value, min, max) {
    return Math.min(max, Math.max(min, value));
  }

  function applyTransform(animate = true) {
    imageEl.style.transition = animate ? "transform 0.12s ease-out" : "none";
    imageEl.style.transform = `translate(${offsetX}px, ${offsetY}px) scale(${scale})`;

    const zoomed = scale > 1.01;
    galleryEl.classList.toggle("is-zoomed", zoomed);
    stageEl.classList.toggle("is-zoomed", zoomed);
    zoomResetBtn.textContent = `${Math.round(scale * 100)}٪`;
  }

  function resetZoom(animate = true) {
    scale = 1;
    offsetX = 0;
    offsetY = 0;
    applyTransform(animate);
  }

  function setZoom(nextScale, clientX, clientY) {
    const rect = stageEl.getBoundingClientRect();
    const centerX = clientX == null ? rect.left + rect.width / 2 : clientX;
    const centerY = clientY == null ? rect.top + rect.height / 2 : clientY;
    const relX = centerX - rect.left - rect.width / 2;
    const relY = centerY - rect.top - rect.height / 2;
    const prev = scale;
    scale = clamp(nextScale, MIN_ZOOM, MAX_ZOOM);

    if (scale === MIN_ZOOM) {
      offsetX = 0;
      offsetY = 0;
    } else if (prev > 0) {
      const ratio = scale / prev;
      offsetX = relX - (relX - offsetX) * ratio;
      offsetY = relY - (relY - offsetY) * ratio;
    }

    applyTransform();
  }

  function zoomBy(delta, clientX, clientY) {
    setZoom(scale + delta, clientX, clientY);
  }

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
    resetZoom(false);

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

    if (current.virtual_tour_url) {
      tourWrap.hidden = false;
      tourLink.href = current.virtual_tour_url;
      tourLink.textContent = current.virtual_tour_name
        ? `بازدید مجازی · ${current.virtual_tour_name}`
        : "مشاهده بازدید مجازی";
    } else {
      tourWrap.hidden = true;
      tourLink.removeAttribute("href");
    }

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
    resetZoom(false);
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

  zoomInBtn.addEventListener("click", () => zoomBy(ZOOM_STEP));
  zoomOutBtn.addEventListener("click", () => zoomBy(-ZOOM_STEP));
  zoomResetBtn.addEventListener("click", () => resetZoom());

  stageEl.addEventListener(
    "wheel",
    (event) => {
      if (!backdrop.classList.contains("open")) return;
      event.preventDefault();
      const direction = event.deltaY > 0 ? -ZOOM_STEP : ZOOM_STEP;
      zoomBy(direction, event.clientX, event.clientY);
    },
    { passive: false }
  );

  stageEl.addEventListener("dblclick", (event) => {
    if (scale > 1.01) {
      resetZoom();
    } else {
      setZoom(2.2, event.clientX, event.clientY);
    }
  });

  stageEl.addEventListener("pointerdown", (event) => {
    if (event.pointerType === "mouse" && event.button !== 0) return;
    if (scale <= 1.01) return;

    dragging = true;
    dragStartX = event.clientX;
    dragStartY = event.clientY;
    originX = offsetX;
    originY = offsetY;
    stageEl.classList.add("is-dragging");
    stageEl.setPointerCapture(event.pointerId);
  });

  stageEl.addEventListener("pointermove", (event) => {
    if (!dragging) return;
    offsetX = originX + (event.clientX - dragStartX);
    offsetY = originY + (event.clientY - dragStartY);
    applyTransform(false);
  });

  function endDrag(event) {
    if (!dragging) return;
    dragging = false;
    stageEl.classList.remove("is-dragging");
    if (event?.pointerId != null) {
      try {
        stageEl.releasePointerCapture(event.pointerId);
      } catch (_) {
        /* ignore */
      }
    }
  }

  stageEl.addEventListener("pointerup", endDrag);
  stageEl.addEventListener("pointercancel", endDrag);

  stageEl.addEventListener(
    "touchstart",
    (event) => {
      if (event.touches.length === 2) {
        dragging = false;
        const [a, b] = event.touches;
        pinchStartDistance = Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY);
        pinchStartScale = scale;
      }
    },
    { passive: true }
  );

  stageEl.addEventListener(
    "touchmove",
    (event) => {
      if (event.touches.length !== 2 || !pinchStartDistance) return;
      event.preventDefault();
      const [a, b] = event.touches;
      const distance = Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY);
      const midX = (a.clientX + b.clientX) / 2;
      const midY = (a.clientY + b.clientY) / 2;
      setZoom(pinchStartScale * (distance / pinchStartDistance), midX, midY);
    },
    { passive: false }
  );

  stageEl.addEventListener(
    "touchend",
    () => {
      pinchStartDistance = 0;
    },
    { passive: true }
  );

  window.addEventListener("keydown", (event) => {
    if (!backdrop.classList.contains("open")) return;

    if (event.key === "Escape") {
      if (scale > 1.01) {
        resetZoom();
        return;
      }
      closeModal();
      return;
    }

    if (event.key === "+" || event.key === "=") zoomBy(ZOOM_STEP);
    if (event.key === "-" || event.key === "_") zoomBy(-ZOOM_STEP);
    if (event.key === "0") resetZoom();

    if (scale > 1.01) return;
    if (event.key === "ArrowLeft") prevBtn.click();
    if (event.key === "ArrowRight") nextBtn.click();
  });
})();
