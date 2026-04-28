(() => {
  const COPY_LABEL = "Copy";
  const COPIED_LABEL = "Copied";

  function getCodeText(container) {
    const codeEl = container.querySelector("pre code");
    const preEl = container.querySelector("pre");
    const source = codeEl || preEl;
    return source ? source.innerText.replace(/\n$/, "") : "";
  }

  async function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return;
    }

    const ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed";
    ta.style.left = "-9999px";
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    document.body.removeChild(ta);
  }

  function addCopyButtons() {
    const blocks = document.querySelectorAll("div.highlighter-rouge, .highlight");

    blocks.forEach((block) => {
      if (block.querySelector(".code-copy-btn")) return;
      if (!block.querySelector("pre")) return;

      const button = document.createElement("button");
      button.type = "button";
      button.className = "code-copy-btn";
      button.textContent = COPY_LABEL;
      button.setAttribute("aria-label", "Copy code block");

      button.addEventListener("click", async () => {
        const text = getCodeText(block);
        if (!text) return;

        try {
          await copyText(text);
          button.textContent = COPIED_LABEL;
          button.classList.add("is-copied");
          window.setTimeout(() => {
            button.textContent = COPY_LABEL;
            button.classList.remove("is-copied");
          }, 1400);
        } catch (err) {
          button.textContent = "Error";
          window.setTimeout(() => {
            button.textContent = COPY_LABEL;
          }, 1400);
        }
      });

      block.appendChild(button);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", addCopyButtons);
  } else {
    addCopyButtons();
  }
})();
