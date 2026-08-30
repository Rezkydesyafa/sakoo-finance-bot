import Image from "next/image";

type BrandMarkProps = {
  alt?: string;
  className?: string;
  priority?: boolean;
  sizes?: string;
};

export function BrandMark({ alt = "", className = "", priority = false, sizes = "64px" }: BrandMarkProps) {
  return (
    <Image
      src="/brand/sakoo-mark.png"
      alt={alt}
      width={540}
      height={545}
      priority={priority}
      sizes={sizes}
      className={`object-contain ${className}`}
    />
  );
}
