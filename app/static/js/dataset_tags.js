document.addEventListener("DOMContentLoaded", () => {
  const btn = document.querySelector(".show-more-btn");
  const extra = document.querySelector(".extra-tags");

  if (!btn) return;

  btn.addEventListener("click", () => {
    extra.classList.toggle("display-none");

    btn.textContent = extra.classList.contains("display-none")
      ? `+ ${extra.children.length} more`
      : "Show less";
  });
});
