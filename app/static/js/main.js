// Theme Handling
document.addEventListener("DOMContentLoaded", () => {
  const html = document.querySelector("html");
  const toggleBtn = document.getElementById("theme-toggle");

  if (window.hljs) {
    hljs.highlightAll();
  }

  renderLocalTimes();

  if (
    localStorage.theme === "dark" ||
    (!("theme" in localStorage) &&
      window.matchMedia("(prefers-color-scheme: dark)").matches)
  ) {
    html.classList.add("dark");
  }

  if (toggleBtn) {
    toggleBtn.addEventListener("click", () => {
      html.classList.toggle("dark");
      localStorage.theme = html.classList.contains("dark") ? "dark" : "light";
    });
  }
});

// Dynamic Link Input Generator
function addLinkInput(containerId, prefix) {
  const container = document.getElementById(containerId);
  const div = document.createElement("div");
  div.className = "flex gap-2 mb-2 items-center";
  div.innerHTML = `
        <input type="text" name="${prefix}_names" placeholder="Name (e.g. Jira)" 
               class="flex-1 bg-bgPrimary border border-borderColor rounded px-3 py-2 text-sm focus:border-accent outline-none">
        <input type="url" name="${prefix}_urls" placeholder="https://..." 
               class="flex-[2] bg-bgPrimary border border-borderColor rounded px-3 py-2 text-sm focus:border-accent outline-none">
        <button type="button" onclick="this.parentElement.remove()" class="text-red-500 hover:text-red-600 p-2">
            &times;
        </button>
    `;
  container.appendChild(div);
}

// Timezone Converter
function renderLocalTimes() {
  const elements = document.querySelectorAll(".datetime-local");

  elements.forEach((el) => {
    // Prevent double-processing
    if (el.getAttribute("data-processed") === "true") return;

    const utcStr = el.getAttribute("data-utc");
    if (!utcStr || utcStr === "None") return;

    const date = new Date(utcStr);

    // Format: "24 Nov, 18:53"
    const localString = date.toLocaleString(undefined, {
      day: "numeric",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      hour12: true, // Change to true if you prefer AM/PM
    });

    el.textContent = localString;
    el.setAttribute("data-processed", "true");
    el.classList.remove("opacity-0"); // Fade in effect
  });
}
