/* The Deccan mark: the company's logo, traced from the official artwork
   rather than drawn by eye. It is a filled outline — the inner counter is a
   second subpath under fill-rule evenodd — which keeps the hand-drawn
   variation in stroke weight that a uniform stroke cannot reproduce.
   The viewBox has padding built in, so nothing clips at any size. */
export const MARK_PATH =
  "M250.9 16.0L275.4 17.0L304.1 23.2L328.7 32.4L348.1 42.6L362.4 51.8L381.9 67.2L400.3 85.6L416.7 105.0L431.0 126.5L436.1 138.8L438.2 149.0L437.2 179.8L433.1 192.0L418.7 219.7L406.4 239.1L391.1 259.6L325.6 335.3L312.3 354.8L291.8 394.7L271.4 447.9L264.2 462.2L256.0 474.5L245.8 484.7L231.4 492.9L219.2 496.0L199.7 496.0L184.4 491.9L167.0 483.7L148.5 469.4L134.2 453.0L119.9 431.5L108.6 409.0L93.3 368.1L93.3 364.0L91.2 359.9L86.1 334.3L84.1 329.2L81.0 304.6L78.9 297.4L75.9 260.6L74.8 259.6L74.8 236.0L73.8 235.0L74.8 199.2L75.9 198.2L77.9 179.8L84.1 160.3L93.3 146.0L105.6 132.7L140.3 104.0L159.8 84.6L186.4 50.8L202.8 34.4L213.0 27.3L225.3 21.1L241.7 17.0L249.9 17.0ZM157.7 127.6L178.2 108.1L208.9 69.2L221.2 56.9L227.3 52.8L241.7 46.7L270.3 45.7L290.8 49.8L311.3 56.9L338.9 71.3L350.2 79.5L362.4 89.7L390.1 119.4L402.4 135.7L408.5 150.1L409.5 162.4L407.5 171.6L404.4 180.8L393.1 203.3L369.6 239.1L353.2 259.6L351.2 260.6L308.2 310.8L287.7 339.4L271.4 369.1L271.4 371.1L260.1 394.7L244.7 435.6L237.6 451.0L231.4 460.2L226.3 465.3L219.2 469.4L214.0 470.4L198.7 469.4L180.3 460.2L167.0 447.9L152.6 429.5L139.3 405.9L132.2 386.5L130.1 384.4L130.1 381.4L124.0 366.0L113.7 328.2L113.7 322.0L108.6 297.4L108.6 290.3L107.6 289.3L107.6 282.1L105.6 272.9L105.6 261.6L104.5 260.6L103.5 211.5L104.5 210.5L105.6 190.0L108.6 178.7L116.8 164.4L127.0 153.1L156.7 128.6Z";

export function Mark({ size = 15, className }: { size?: number; className?: string }) {
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 512 512"
      aria-hidden="true"
    >
      <path d={MARK_PATH} fill="currentColor" fillRule="evenodd" />
    </svg>
  );
}

/* The watermark IS the loading indicator. One mark on the page rather than a
   second, smaller copy appearing next to it while the first sits there inert.
   The fill layer is invisible until work is in flight.

   Two stacked copies: the upper one is revealed from the bottom with a CSS
   inset clip — animating an SVG <clipPath> rect is not reliably supported,
   and silently did nothing. */
export function Backdrop() {
  return (
    <div className="backdrop" aria-hidden="true">
      <svg width="465" height="465" viewBox="0 0 512 512" aria-hidden="true">
        <path className="bdbase" d={MARK_PATH} fill="currentColor" fillRule="evenodd" />
        <path className="bdfill" d={MARK_PATH} fill="currentColor" fillRule="evenodd" />
      </svg>
    </div>
  );
}
