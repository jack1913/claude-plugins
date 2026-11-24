// Shared by edges.test.mjs and edges-clip.test.mjs: the mark that crosses the edge, and its project.
import fs from "node:fs";
import path from "node:path";
import { motionProject, byId, writeProof, writePage, pageCase } from "./_motion.mjs";

// A 320 x 90 mark (a disc and a part, g#letter-a) at the top left of its page, and the same drawing as the still. The part is a 50 x 40 box at x 250..300,
// y 10..50, so it ends 60 px inside the 360 px screen; the keyframes (`move`) push it out and bring it back. `svg` holds extra attributes of the mark's root.
export const DRAWING = (extra = "") => `<svg xmlns="http://www.w3.org/2000/svg" ${extra} viewBox="0 0 320 90" width="320" height="90" role="img" aria-label="Edge mark">`
  + `<circle cx="40" cy="45" r="30" fill="#0d1b2d"/><g id="letter-a"><rect x="250" y="10" width="50" height="40" fill="#007d71"/></g></svg>`;
// The same mark made of HTML boxes (the disc is an svg, the part a div): what it pushes out of the page counts in the page's width, which an svg's
// own drawing does not (the content of an <svg> never makes the page scroll, whatever its overflow).
export const HTML_MARK = `<div id="mark" style="position:relative;width:320px;height:90px"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 90" width="320" height="90" style="display:block">`
  + `<circle cx="40" cy="45" r="30" fill="#0d1b2d"/></svg><div id="letter-a" style="position:absolute;left:250px;top:10px;width:50px;height:40px;background:#007d71"></div></div>`;
export function projectWith({ move, css = "", body = "", svg = 'style="overflow:visible"', html = false, extra = {} }) {
  const p = motionProject();
  fs.writeFileSync(path.join(p, "assets/logo/edge.svg"), DRAWING());
  writePage(p, "edge", {
    css: `#mark{display:block}#letter-a{animation:go 400ms linear 1 both}@keyframes go{from{transform:none}50%{transform:${move}}to{transform:none}}`
      + `@media (prefers-reduced-motion: reduce){#letter-a,.moving{animation:none!important}}${css}`,
    body: (html ? HTML_MARK : DRAWING(`id="mark" ${svg}`)) + body,
  });
  const proof = writeProof(p, [pageCase({ page: "motion/edge.html", static: "assets/logo/edge.svg", ...extra })]);
  return { p, proof };
}
export const row = (p, proof, w) => byId(p, proof)[`motion:case:edges:${w}`];
