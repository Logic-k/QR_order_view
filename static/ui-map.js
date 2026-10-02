/* Text and map position remain driven by the QR seat and real menu values. */
function useDrinkFallback(image) {
  if (image.dataset.drinkFallback && !image.dataset.fallbackUsed) {
    image.dataset.fallbackUsed = "true";
    image.src = image.dataset.drinkFallback;
  }
}
document.addEventListener(
  "error",
  (event) => {
    if (event.target instanceof HTMLImageElement)
      useDrinkFallback(event.target);
  },
  true,
);
document.querySelectorAll("img[data-drink-fallback]").forEach((image) => {
  if (image.complete && image.naturalWidth === 0) useDrinkFallback(image);
});
const selectionLabel = document.querySelector("#selected-drink-name");
if (selectionLabel) {
  document.querySelectorAll('input[name="drink"]').forEach((input) => {
    input.addEventListener("change", () => {
      selectionLabel.textContent = input.value;
    });
  });
}
const seatViewport = document.querySelector(".main-seat-viewport");
if (seatViewport) {
  const jumps = document.querySelectorAll("[data-jump-seat]");
  function markVisibleSeats() {
    const viewport = seatViewport.getBoundingClientRect();
    jumps.forEach((button) => {
      const card = document.querySelector(
        '[data-seat-card="' + button.dataset.jumpSeat + '"]',
      );
      const rect = card.getBoundingClientRect();
      const visible =
        rect.left >= viewport.left - 2 && rect.right <= viewport.right + 2;
      button.classList.toggle("is-visible", visible);
      button.setAttribute(
        "aria-label",
        button.dataset.jumpSeat + "번 자리로 이동",
      );
    });
  }
  jumps.forEach((button) => {
    button.addEventListener("click", () => {
      const card = document.querySelector(
        '[data-seat-card="' + button.dataset.jumpSeat + '"]',
      );
      seatViewport.scrollTo({
        left:
          card.offsetLeft -
          seatViewport.querySelector(".main-seats").offsetLeft,
        behavior: matchMedia("(prefers-reduced-motion: reduce)").matches
          ? "instant"
          : "smooth",
      });
    });
  });
  seatViewport.addEventListener("scroll", markVisibleSeats, { passive: true });
  window.addEventListener("resize", markVisibleSeats);
  markVisibleSeats();
}
