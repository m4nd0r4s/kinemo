<script lang="ts">
  import { base } from "$app/paths";
  import Logo from "./Logo.svelte";

  let { version }: { version: string } = $props();
</script>

<footer class="site-footer">
  <p><a class="brand small" href="{base}/"><Logo /><span>kinemo</span></a> {version}, dual-licensed MIT or Apache-2.0.</p>
  <p>
    Built from the repository: every video on this site is rendered by kinemo, every terminal
    block is a real run.
  </p>
  <p>
    <a href="https://github.com/m4nd0r4s/kinemo" rel="noopener">Source on GitHub</a>
    <a href="{base}/docs/latest/">Documentation</a>
    <a href="{base}/llms.txt">llms.txt</a>
    <a href="{base}/docs/latest/caveats/">Caveats</a>
    <a href="{base}/docs/latest/status/">Status</a>
  </p>
</footer>
