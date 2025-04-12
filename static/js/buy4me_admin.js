// Function to handle quick admin actions for Buy4Me requests
function confirmAction(action, requestId) {
  let confirmMsg = "";
  let endpoint = `/admin/buy4me/buy4merequest/${requestId}/`;
  let newStatus = "";

  switch (action) {
    case "submit":
      confirmMsg = "Are you sure you want to mark this request as SUBMITTED?";
      newStatus = "SUBMITTED";
      break;
    case "order_placed":
      confirmMsg =
        "Are you sure you want to mark this request as ORDER PLACED?";
      newStatus = "ORDER_PLACED";
      break;
    case "in_transit":
      confirmMsg = "Are you sure you want to mark this request as IN TRANSIT?";
      newStatus = "IN_TRANSIT";
      break;
    case "complete":
      confirmMsg = "Are you sure you want to mark this request as COMPLETED?";
      newStatus = "COMPLETED";
      break;
    default:
      alert("Invalid action");
      return;
  }

  if (confirm(confirmMsg)) {
    // Get CSRF token
    const csrfToken = document.querySelector(
      "[name=csrfmiddlewaretoken]"
    ).value;

    // Create form data
    const formData = new FormData();
    formData.append("status", newStatus);
    formData.append("csrfmiddlewaretoken", csrfToken);

    // Send POST request to update status
    fetch(endpoint, {
      method: "POST",
      body: formData,
      headers: {
        "X-CSRFToken": csrfToken,
      },
    })
      .then((response) => {
        if (response.ok) {
          // Reload the page to see changes
          window.location.reload();
        } else {
          alert("Failed to update status. Please try again.");
        }
      })
      .catch((error) => {
        console.error("Error:", error);
        alert("An error occurred. Please try again.");
      });
  }
}

// Initialize on page load
document.addEventListener("DOMContentLoaded", function () {
  // Add custom styles for the quick status actions
  const style = document.createElement("style");
  style.textContent = `
        .field-status_badge span, .field-payment_status_badge span {
            display: inline-block;
            min-width: 80px;
            text-align: center;
        }
        
        .field-total_cost_display b {
            color: #28a745;
        }
        
        .field-actions_column a {
            margin-bottom: 3px;
        }
    `;
  document.head.appendChild(style);
});
