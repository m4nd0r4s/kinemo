// A Svelte action: a Copy button on every code block inside the node.

export function copyButtons(node: HTMLElement) {
  for (const pre of node.querySelectorAll<HTMLPreElement>("pre.code")) {
    if (pre.querySelector(".copy")) continue;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "copy";
    button.textContent = "Copy";
    button.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText((pre.querySelector("code") ?? pre).innerText);
        button.textContent = "Copied";
      } catch {
        button.textContent = "Select and copy";
      }
      setTimeout(() => (button.textContent = "Copy"), 1600);
    });
    pre.append(button);
  }
}
