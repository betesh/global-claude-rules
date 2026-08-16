# Give a file path for renders and debug images, not an inline display

_Inline image display in the conversation does not work for this user — always lead with an
absolute file path they can open themselves._

Rendering a PNG or other image inline (e.g. via the Read tool showing it in the transcript) does
not reach this user — confirmed directly ("Rendering images in the conversation has never
worked"). When producing a render, diagram, or screenshot for review, lead with an absolute file
path, not an inline display followed by the path as an afterthought.

For an ad-hoc debug/review render — a one-off HTML page comparing a handful of candidate outputs,
a diagnostic visualization, anything meant for the user's own inspection rather than something to
hand off or share onward — write it to a file and give the path; don't also publish it as an
Artifact unless asked. Artifact is still the right tool for a polished, shareable deliverable; a
throwaway review page is not that.

## Scope

Applies whenever producing a visual output — image, render, diagram, HTML review page — for this
user to look at.
