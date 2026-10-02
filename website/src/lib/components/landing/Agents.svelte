<script lang="ts">
  // What agents get: stable JSON, frames on demand, an MCP server and llms.txt.
  import { base } from "$app/paths";
  import type { Run } from "$lib/site-data";
  import Terminal from "./Terminal.svelte";

  let { report }: { report: Run } = $props();
</script>

<section class="band" id="agents">
  <div class="band-head">
    <h2>Readable by people and by agents</h2>
    <p>
      The API has one form per concept and full typing, so code written by a model checks the same
      way yours does. Agents close the write, verify, fix loop without needing vision:
    </p>
  </div>
  <div class="split">
    <div class="prose">
      <ul class="facts">
        <li><code>kinemo check --json</code> and <code>kinemo inspect --json</code> report the timeline, diagnostics and scene graph as stable JSON.</li>
        <li><code>kinemo snap scene.py --at 2.5</code> writes the frames worth looking at.</li>
        <li><code>kinemo mcp</code> serves check, inspect, snap, docs and explain over the Model Context Protocol.</li>
        <li><a href="{base}/llms.txt">llms.txt</a> is the whole API in one file, generated from the code.</li>
      </ul>
    </div>
    <Terminal run={report} />
  </div>
</section>
