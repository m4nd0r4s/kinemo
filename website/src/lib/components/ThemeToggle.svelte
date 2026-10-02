<script lang="ts">
  /** Switches between the light and the dark theme; the choice is kept for the next visit. */
  function toggle() {
    const prefersDark = matchMedia("(prefers-color-scheme: dark)").matches;
    const current = document.documentElement.dataset.theme || (prefersDark ? "dark" : "light");
    const next = current === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem("theme", next);
    } catch {
      // Private mode: the choice lasts for this page.
    }
  }
</script>

<button class="theme-button" type="button" onclick={toggle} aria-label="Switch light and dark theme">
  <svg viewBox="0 0 20 20" aria-hidden="true">
    <circle cx="10" cy="10" r="4.2" />
    <path d="M10 1.5v2.3M10 16.2v2.3M1.5 10h2.3M16.2 10h2.3M4 4l1.6 1.6M14.4 14.4 16 16M4 16l1.6-1.6M14.4 5.6 16 4" />
  </svg>
</button>
