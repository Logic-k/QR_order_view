/* Order requests remain tied to the existing Flask endpoints. */
const customerForm = document.querySelector("#order-form");
if (customerForm) {
  let submitting = false;
  customerForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (submitting) return;
    submitting = true;
    const button = document.querySelector("#order-submit");
    const error = document.querySelector("#order-error");
    const pending = document.querySelector("#order-pending");
    button.disabled = true;
    customerForm.setAttribute("aria-busy", "true");
    pending.hidden = false;
    error.hidden = true;
    try {
      const response = await fetch(window.location.href, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          drink: new FormData(customerForm).get("drink"),
        }),
      });
      if (!response.ok) throw new Error("Order request failed");
      window.location.assign(
        "/order-complete?seat=" + encodeURIComponent(customerForm.dataset.seat),
      );
    } catch {
      error.textContent =
        "주문 접수를 확인할 수 없습니다. 다시 주문하기 전에 직원에게 확인해 주세요. / We could not confirm your order. Please check with staff before retrying. / 无法确认订单，请先向工作人员确认再重试。";
      error.hidden = false;
      button.disabled = false;
      submitting = false;
      pending.hidden = true;
      customerForm.removeAttribute("aria-busy");
    }
  });
}
const masterToggle = document.querySelector("#master-toggle");
if (masterToggle) {
  const panel = document.querySelector("#master-order-form");
  let adminBusy = false;
  masterToggle.addEventListener("click", () => {
    panel.hidden = !panel.hidden;
    masterToggle.setAttribute("aria-expanded", String(!panel.hidden));
    if (!panel.hidden) document.querySelector("#master-seat").focus();
  });
  async function adminRequest(endpoint, payload, button) {
    if (adminBusy) return;
    adminBusy = true;
    button.disabled = true;
    const error = document.querySelector("#admin-error");
    error.hidden = true;
    try {
      const response = await fetch(endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": document.querySelector('meta[name="csrf-token"]').content,
        },
        ...(payload ? { body: JSON.stringify(payload) } : {}),
      });
      if (!response.ok) throw new Error("Admin request failed");
      location.reload();
    } catch {
      error.textContent =
        "처리를 확인할 수 없습니다. 주문 목록을 새로고침하여 확인한 후 다시 시도해 주세요.";
      error.hidden = false;
      button.disabled = false;
      adminBusy = false;
    }
  }
  document.querySelectorAll(".delete-one").forEach((button) => {
    button.addEventListener("click", () => {
      if (confirm("이 주문을 삭제하시겠습니까?"))
        adminRequest("/delete-order", { id: button.dataset.orderId }, button);
    });
  });
  document.querySelector("#delete-all").addEventListener("click", (event) => {
    if (confirm("접수된 모든 주문을 삭제하시겠습니까?"))
      adminRequest("/delete-all-orders", null, event.currentTarget);
  });
  document.querySelector("#master-form").addEventListener("submit", (event) => {
    event.preventDefault();
    adminRequest(
      "/master-order",
      {
        seat: document.querySelector("#master-seat").value,
        drink: document.querySelector("#master-drink").value,
      },
      event.currentTarget.querySelector("button"),
    );
  });
  setInterval(() => {
    if (
      !adminBusy &&
      panel.hidden &&
      document.querySelector("#admin-error").hidden
    )
      location.reload();
  }, 30000);
}
