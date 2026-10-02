<script lang="ts">
  // A real command and its output, as a terminal shows it.
  import type { Run } from "$lib/site-data";

  let { run, title = "" }: { run: Run; title?: string } = $props();
</script>

<figure class="terminal">
  {#if title}<div class="term-title">{title}</div>{/if}
  <pre><code><span class="prompt">$</span> {run.command}
{run.output}</code></pre>
</figure>
