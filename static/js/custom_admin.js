// Custom Admin JavaScript

document.addEventListener("DOMContentLoaded", function () {
  // Initialize Select2 for all select elements
  if (typeof $ !== "undefined" && $.fn.select2) {
    $(".select2").select2({
      theme: "bootstrap4",
      width: "100%",
    });
  }

  // Add loading state to forms on submit
  const forms = document.querySelectorAll("form");
  forms.forEach((form) => {
    form.addEventListener("submit", function () {
      this.classList.add("loading");
    });
  });

  // Initialize Dashboard Charts if on dashboard page
  if (document.querySelector(".dashboard-chart")) {
    initializeDashboardCharts();
  }

  // Enhance many-to-many widgets
  enhanceManyToManyWidgets();

  // Add responsive behavior to related modals
  enhanceRelatedModals();
});

// Dashboard Charts Initialization
function initializeDashboardCharts() {
  // Only proceed if Chart.js is available
  if (typeof Chart === "undefined") return;

  // Shipments by Status Chart
  const shipmentCtx = document.getElementById("shipmentsByStatusChart");
  if (shipmentCtx) {
    new Chart(shipmentCtx, {
      type: "doughnut",
      data: {
        labels: ["Pending", "In Progress", "Delivered", "Cancelled"],
        datasets: [
          {
            data: [12, 19, 3, 5],
            backgroundColor: ["#ffc107", "#17a2b8", "#28a745", "#dc3545"],
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
      },
    });
  }

  // Revenue Trend Chart
  const revenueCtx = document.getElementById("revenueTrendChart");
  if (revenueCtx) {
    new Chart(revenueCtx, {
      type: "line",
      data: {
        labels: ["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
        datasets: [
          {
            label: "Revenue",
            data: [65, 59, 80, 81, 56, 55],
            borderColor: "#28a745",
            tension: 0.1,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
      },
    });
  }
}

// Enhance Many to Many Widgets
function enhanceManyToManyWidgets() {
  const widgets = document.querySelectorAll(".related-widget-wrapper");
  widgets.forEach((widget) => {
    // Add search functionality
    const select = widget.querySelector("select");
    if (select && typeof $ !== "undefined" && $.fn.select2) {
      $(select).select2({
        theme: "bootstrap4",
        width: "100%",
        dropdownParent: widget,
      });
    }

    // Add bulk selection buttons
    const buttonGroup = document.createElement("div");
    buttonGroup.className = "btn-group mt-2";
    buttonGroup.innerHTML = `
            <button type="button" class="btn btn-sm btn-outline-secondary select-all">Select All</button>
            <button type="button" class="btn btn-sm btn-outline-secondary deselect-all">Deselect All</button>
        `;

    widget.appendChild(buttonGroup);

    // Add button functionality
    buttonGroup.querySelector(".select-all").addEventListener("click", () => {
      Array.from(select.options).forEach((option) => (option.selected = true));
      $(select).trigger("change");
    });

    buttonGroup.querySelector(".deselect-all").addEventListener("click", () => {
      Array.from(select.options).forEach((option) => (option.selected = false));
      $(select).trigger("change");
    });
  });
}

// Enhance Related Modals
function enhanceRelatedModals() {
  // Make modals draggable if jQuery UI is available
  if (typeof $ !== "undefined" && typeof $.fn.draggable !== "undefined") {
    $(".related-modal .modal-dialog").draggable({
      handle: ".modal-header",
    });
  }

  // Add responsive behavior
  const modals = document.querySelectorAll(".related-modal");
  modals.forEach((modal) => {
    const dialog = modal.querySelector(".modal-dialog");
    if (!dialog) return;

    // Add resize observer
    const observer = new ResizeObserver(() => {
      const modalHeight = window.innerHeight * 0.8;
      dialog.style.maxHeight = `${modalHeight}px`;
    });

    observer.observe(document.body);
  });
}

// Add status badge styling
function addStatusBadges() {
  const statusCells = document.querySelectorAll("td.field-status");
  statusCells.forEach((cell) => {
    const status = cell.textContent.trim().toLowerCase();
    cell.innerHTML = `<span class="status-badge status-${status}">${cell.textContent}</span>`;
  });
}

// Initialize status badges when DOM is ready
document.addEventListener("DOMContentLoaded", addStatusBadges);
