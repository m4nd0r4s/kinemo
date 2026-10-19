// `<kinemo-lesson src="lessons/slope/">`: a lesson embedded in a page, as an element.
//
// The lesson runs in an iframe and reports what happens as DOM events on the element
// (`loaded`, `question`, `answer`, `result`, `branch`, `finished`, `error`; the details are
// the protocol messages below). Methods send commands: `play()`, `pause()`, `restart()`,
// `goto(questionId)`, `grading("host" | "player")` and `result(questionId, correct)`.
//
// Protocol (version 1), for hosts that use an iframe directly:
// - the player posts `{source: "kinemo", version: 1, type, ...}` to its parent;
// - the parent posts `{target: "kinemo", type, ...}` to the iframe.
// With `grading="host"` (attribute, command or `?grading=host`), the player sends `answer`
// and waits for the host's `result` before going on.
const PROTOCOL = 1;

class KinemoLesson extends HTMLElement {
  static get observedAttributes() {
    return ["src"];
  }

  connectedCallback() {
    if (this.frame) return;
    this.frame = document.createElement("iframe");
    this.frame.title = this.getAttribute("title") || "Lesson";
    this.frame.allow = "autoplay; fullscreen";
    this.frame.style.cssText = "border:0;width:100%;display:block;aspect-ratio:16/13;";
    this.frame.src = this.url();
    this.listener = (event) => {
      const message = event.data;
      if (event.source !== this.frame.contentWindow || !message || message.source !== "kinemo") return;
      if (message.version !== PROTOCOL) console.warn(`kinemo-lesson: protocol ${message.version}, expected ${PROTOCOL}`);
      this.dispatchEvent(new CustomEvent(message.type, { detail: message }));
    };
    window.addEventListener("message", this.listener);
    this.append(this.frame);
  }

  disconnectedCallback() {
    window.removeEventListener("message", this.listener);
    this.frame?.remove();
    this.frame = null;
  }

  attributeChangedCallback() {
    if (this.frame) this.frame.src = this.url();
  }

  url() {
    const src = this.getAttribute("src") || "";
    const url = new URL(src.endsWith("/") || src.endsWith(".html") ? src : `${src}/`, document.baseURI);
    if (this.getAttribute("grading") === "host") url.searchParams.set("grading", "host");
    if (this.hasAttribute("autoplay")) url.searchParams.set("autoplay", "1");
    return url.href;
  }

  send(type, detail = {}) {
    this.frame?.contentWindow?.postMessage({ target: "kinemo", type, ...detail }, "*");
  }

  play() { this.send("play"); }
  pause() { this.send("pause"); }
  restart() { this.send("restart"); }
  goto(id) { this.send("goto", { id }); }
  grading(by) { this.send("grading", { by }); }
  result(id, correct) { this.send("result", { id, correct }); }
}

if (!customElements.get("kinemo-lesson")) customElements.define("kinemo-lesson", KinemoLesson);
