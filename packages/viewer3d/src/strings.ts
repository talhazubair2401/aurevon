/** Everything the viewer says. The storefront passes its own (English or Urdu) from @aurevon/i18n. */
export interface ViewerLabels {
  loading: string;
  stillLoading: string;
  slow: string;
  failed: string;
  lost: string;
  unavailable: string;
  noColour: string;
  tryAgain: string;
  showImage: string;
  showThreeD: string;
  rotateOn: string;
  zoomIn: string;
  zoomOut: string;
  reset: string;
  badge: string;
  viewerLabel: string;
  hintPointer: string;
  hintTouch: string;
  hintKeyboard: string;
  wheelHint: string;
  shownIn: string;
}

export const ENGLISH: ViewerLabels = {
  loading: "Loading the 3D view…",
  stillLoading: "Still loading the 3D view. You can keep shopping meanwhile.",
  slow: "Slow connection. The 3D view will appear here when it's ready.",
  failed: "The 3D view couldn't load. Check your connection and try again.",
  lost: "The 3D view stopped responding.",
  unavailable: "3D isn't available on this device. Everything else on the page works as normal.",
  noColour: "3D isn't available in this colour yet.",
  tryAgain: "Try again",
  showImage: "Show image",
  showThreeD: "Show 3D",
  rotateOn: "Auto-rotate",
  zoomIn: "Zoom in",
  zoomOut: "Zoom out",
  reset: "Reset view",
  badge: "Interactive 3D",
  viewerLabel:
    "3D view of the garment. Arrow keys rotate and tilt, plus and minus zoom, Home resets the view.",
  hintPointer: "Drag to rotate · {key} + scroll to zoom",
  hintTouch: "Swipe sideways to rotate · pinch to zoom",
  hintKeyboard: "Arrow keys rotate · + and − zoom · Home resets",
  wheelHint: "Use {key} + scroll to zoom",
  shownIn: "3D view shown in {colour}",
};
