const form = document.getElementById("complaint-form");
const steps = [...form.querySelectorAll(".form-step")];
const stepLabels = [...form.querySelectorAll("[data-step-label]")];
const progressFill = document.getElementById("step-progress-fill");
const imageInput = document.getElementById("image");
const preview = document.getElementById("preview");
const uploadBox = document.getElementById("upload-box");
const uploadTitle = document.getElementById("upload-title");
const message = document.getElementById("form-message");
const locationInput = document.getElementById("location");
const locationMessage = document.getElementById("location-message");
let currentStep = 0;
let previewUrl;

function showStep(index) {
  currentStep = index;
  steps.forEach((step, stepIndex) => {
    step.hidden = stepIndex !== index;
  });
  stepLabels.forEach((label, stepIndex) => {
    label.classList.toggle("active", stepIndex === index);
    label.classList.toggle("complete", stepIndex < index);
    label.setAttribute("aria-current", stepIndex === index ? "step" : "false");
  });
  progressFill.style.width = `${(index / (steps.length - 1)) * 100}%`;
  message.textContent = "";
  if (index === 3) updateReview();
  steps[index].querySelector("input:not([type=hidden]), textarea")?.focus({ preventScroll: true });
}

function validateStep(index, showError = true) {
  const fields = [...steps[index].querySelectorAll("input, textarea, select")];
  const invalidField = fields.find((field) => !field.checkValidity());
  if (invalidField) {
    if (showError) invalidField.reportValidity();
    return false;
  }
  return true;
}

function updateReview() {
  document.getElementById("review-location").textContent = locationInput.value.trim() || "Not provided";
  document.getElementById("review-name").textContent =
    form.elements.citizen_name.value.trim() || "Not provided";
  const phone = form.elements.phone.value.trim();
  const email = form.elements.email.value.trim();
  document.getElementById("review-contact").textContent =
    [phone, email].filter(Boolean).join(" · ") || "Not provided";
  document.getElementById("review-hazard").textContent =
    form.elements.hazard_type.value || "Not specified";
  document.getElementById("review-traffic").textContent =
    form.elements.traffic_impact.value || "Not specified";
  document.getElementById("review-risk").textContent =
    form.elements.safety_risk.value || "Not specified";
}

form.querySelectorAll("[data-next]").forEach((button) => {
  button.addEventListener("click", () => {
    if (validateStep(currentStep)) showStep(Math.min(currentStep + 1, steps.length - 1));
  });
});

form.querySelectorAll("[data-back]").forEach((button) => {
  button.addEventListener("click", () => showStep(Math.max(currentStep - 1, 0)));
});

form.addEventListener("input", updateReview);

imageInput.addEventListener("change", () => {
  const file = imageInput.files[0];
  if (!file) return;
  const allowedTypes = ["image/jpeg", "image/png", "image/webp"];
  if (!allowedTypes.includes(file.type) || file.size > 10 * 1024 * 1024) {
    imageInput.value = "";
    message.className = "form-message error";
    message.textContent = file.size > 10 * 1024 * 1024
      ? "The selected photo is larger than 10 MB."
      : "Choose a JPG, PNG, or WEBP image.";
    return;
  }
  if (previewUrl) URL.revokeObjectURL(previewUrl);
  previewUrl = URL.createObjectURL(file);
  preview.src = previewUrl;
  preview.style.display = "block";
  uploadBox.classList.add("has-image");
  uploadTitle.textContent = file.name;
  message.textContent = "";
});

document.getElementById("locate-button").addEventListener("click", () => {
  if (!navigator.geolocation) {
    locationMessage.textContent = "Location access is not available in this browser.";
    return;
  }
  locationMessage.textContent = "Finding your location…";
  navigator.geolocation.getCurrentPosition(
    ({ coords }) => {
      document.getElementById("latitude").value = coords.latitude.toFixed(7);
      document.getElementById("longitude").value = coords.longitude.toFixed(7);
      locationMessage.textContent = "Coordinates added. Please enter a nearby road or landmark above.";
      locationInput.focus();
    },
    () => {
      locationMessage.textContent = "Could not get your location. Enter the road or landmark instead.";
    },
    { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 },
  );
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (currentStep !== steps.length - 1) return;
  for (let index = 0; index < 3; index += 1) {
    if (!validateStep(index, false)) {
      showStep(index);
      validateStep(index);
      return;
    }
  }
  if (!validateStep(currentStep)) {
    return;
  }

  const button = form.querySelector('button[type="submit"]');
  button.disabled = true;
  button.textContent = "Analyzing and submitting…";
  message.className = "form-message";
  message.textContent = "";

  try {
    const response = await fetch("/api/complaints", {
      method: "POST",
      body: new FormData(form),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Submission failed. Please try again.");

    const successMessage =
      `Report #${data.complaint.id} submitted. Estimated severity: ${data.complaint.severity}.` +
      (data.is_duplicate ? " A possible duplicate was linked." : "") +
      " You can track it in the dashboard.";
    form.reset();
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = null;
    preview.removeAttribute("src");
    preview.style.display = "none";
    uploadBox.classList.remove("has-image");
    uploadTitle.textContent = "Choose a road damage photo";
    locationMessage.textContent = "";
    showStep(0);
    message.className = "form-message success";
    message.textContent = successMessage;
  } catch (error) {
    message.className = "form-message error";
    message.textContent = error.message || "Submission failed. Please try again.";
  } finally {
    button.disabled = false;
    button.textContent = "Analyze & submit report";
  }
});

showStep(0);
