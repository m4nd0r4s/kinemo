<script lang="ts">
  // An example's code, its render and its timeline, kept in sync. The bars are the scene's
  // real timeline; the playhead follows the video, a bar seeks to its start and the lines
  // that scheduled the running bars light up.
  import { base } from "$app/paths";
  import type { Bar, Token } from "$lib/site-data";

  interface Props {
    name: string;
    duration: number;
    bars: Bar[];
    lines: Token[][];
  }

  let { name, duration, bars, lines }: Props = $props();

  let video = $state<HTMLVideoElement>();
  let studio = $state<HTMLElement>();
  let track = $state<HTMLElement>();
  let t = $state(0);
  let playing = $state(false);

  const percent = (x: number) => `${(100 * x) / duration}%`;
  const ticks = $derived(Array.from({ length: Math.floor(duration) + 1 }, (_, i) => i));
  const running = $derived(new Set(bars.filter((b) => t >= b.start && t < b.end).map((b) => b.line)));
  const indent = (line: Token[]) => {
    const text = line.map((token) => token.content).join("");
    return text.length - text.trimStart().length;
  };

  /** Greedy lane packing: each bar goes into the first lane where it does not overlap. */
  const lanes = $derived.by(() => {
    const ends: number[] = [];
    const out: Bar[][] = [];
    for (const bar of bars) {
      let lane = ends.findIndex((end) => end <= bar.start + 1e-6);
      if (lane < 0) {
        lane = ends.length;
        ends.push(0);
        out.push([]);
      }
      ends[lane] = bar.end;
      out[lane].push(bar);
    }
    return out;
  });

  function seek(time: number) {
    if (!video) return;
    video.currentTime = Math.max(0, Math.min(duration - 0.01, time));
    t = video.currentTime;
  }

  function frame() {
    if (!video) return;
    t = Math.min(video.currentTime, duration);
    if (!video.paused) requestAnimationFrame(frame);
  }

  function toggle() {
    if (!video) return;
    if (video.paused) video.play().catch(() => {});
    else video.pause();
  }

  // Drag on the track to scrub, as in the preview.
  let scrubbing = false;
  function timeAt(e: PointerEvent) {
    const box = track!.getBoundingClientRect();
    return ((e.clientX - box.left) / box.width) * duration;
  }
  function onTrackDown(e: PointerEvent) {
    if ((e.target as Element).closest(".bar")) return;
    scrubbing = true;
    track!.setPointerCapture(e.pointerId);
    video?.pause();
    seek(timeAt(e));
  }

  // Play while the studio is on screen, unless the reader prefers less motion.
  $effect(() => {
    if (!studio || !video || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && entry.intersectionRatio > 0.5) video!.play().catch(() => {});
        else video!.pause();
      },
      { threshold: [0, 0.5] }
    );
    observer.observe(studio);
    return () => observer.disconnect();
  });
</script>

<section class="studio" aria-label="An example and its timeline" bind:this={studio}>
  <div class="studio-code">
    <div class="pane-title"><span>examples/{name}.py</span></div>
    <pre class="code numbered"><code
        >{#each lines as line, i (i)}<span class="ln" class:now={running.has(i + 1)}
            ><span class="num">{i + 1}</span><span class="src" style="--indent: {indent(line)}"
              >{#each line as token, j (j)}<span style:color={token.color}>{token.content}</span>{:else}{" "}{/each}</span
            ></span
          >{/each}</code
      ></pre>
  </div>
  <div class="studio-stage">
    <!-- svelte-ignore a11y_media_has_caption -->
    <video
      class="studio-video"
      bind:this={video}
      src="{base}/media/{name}.mp4"
      poster="{base}/media/{name}.png"
      muted
      playsinline
      loop
      preload="auto"
      onclick={toggle}
      onplay={() => {
        playing = true;
        requestAnimationFrame(frame);
      }}
      onpause={() => (playing = false)}
      onseeked={() => video && (t = video.currentTime)}
    ></video>
  </div>
  <div class="studio-timeline">
    <div class="transport">
      <button type="button" class="play" onclick={toggle} aria-label={playing ? "Pause" : "Play"}>{playing ? "Pause" : "Play"}</button>
      <span class="clock">{t.toFixed(2)} s</span>
      <span class="total">/ {duration.toFixed(2)} s</span>
    </div>
    <div
      class="track"
      bind:this={track}
      role="slider"
      tabindex="0"
      aria-label="Scene time"
      aria-valuemin={0}
      aria-valuemax={duration}
      aria-valuenow={Number(t.toFixed(2))}
      onpointerdown={onTrackDown}
      onpointermove={(e) => scrubbing && seek(timeAt(e))}
      onpointerup={() => (scrubbing = false)}
      onkeydown={(e) => {
        if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
          e.preventDefault();
          video?.pause();
          seek(t + (e.key === "ArrowRight" ? 0.1 : -0.1));
        }
      }}
    >
      <div class="ruler">
        {#each ticks as tick (tick)}<span style:left={percent(tick)}>{tick}s</span>{/each}
      </div>
      <div class="lanes">
        {#each lanes as lane, i (i)}
          <div class="lane">
            {#each lane as bar (bar.start + bar.label)}
              <button
                type="button"
                class="bar"
                class:now={t >= bar.start && t < bar.end}
                style:left={percent(bar.start)}
                style:width="calc({percent(bar.end - bar.start)} - 2px)"
                title="{bar.label}, {bar.start.toFixed(2)}–{bar.end.toFixed(2)} s, line {bar.line}"
                onclick={(e) => {
                  e.stopPropagation();
                  seek(bar.start + 0.02);
                }}>{bar.label}<span class="line">:{bar.line}</span></button
              >
            {/each}
          </div>
        {/each}
      </div>
      <div class="playhead" style:left={percent(t)}></div>
    </div>
  </div>
  <p class="studio-caption">
    The bars are this scene's timeline, as <code>kinemo check</code> reports it. Click one to jump
    there: the line that scheduled it lights up. Drag the track to scrub.
  </p>
</section>
