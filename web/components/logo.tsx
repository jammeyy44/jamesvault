/** The stakesweep badge. The artwork already contains the name, so no extra wordmark is drawn next to it. */
export function Logo({ className = "", size = 44 }: { className?: string; size?: number }) {
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src="/images/logo.webp"
      alt="stakesweep.net"
      width={size}
      height={size}
      decoding="async"
      className={`block shrink-0 rounded-full shadow-[0_0_18px_rgba(124,58,237,0.55)] ${className}`}
      style={{ width: size, height: size }}
    />
  );
}
